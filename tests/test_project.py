import importlib.util
import json
import random
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import read_json, read_jsonl, normalize, score, answered, quantile_diagnostics
from error_schema import validate_review, review_selection
from make_data import make_facts, build_records, validate
from analyze import paired_statistics, holm, validate_logs, bar_svg

class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=read_json(ROOT/'config/experiment.json')
        cls.dev=read_jsonl(ROOT/'data/dev.jsonl')
        cls.test=read_jsonl(ROOT/'data/test.jsonl')

    def test_complete_balanced_data(self):
        validate(self.dev,self.test,self.config)
        self.assertEqual(len(self.test),2520)

    def test_gold_only_in_supported_context(self):
        for r in self.test:
            self.assertEqual(r['city'] in r['context'],r['target_present'])

    def test_dev_does_not_expose_any_test_entities_or_answers(self):
        dev_text='\n'.join(r['prompt'] for r in self.dev).casefold()
        for r in self.test:
            self.assertNotIn(r['country'].casefold(),dev_text)
            self.assertNotIn(r['city'].casefold(),dev_text)

    def test_position_counterbalanced_per_fact(self):
        facts={r['fact_id'] for r in self.test}
        for fid in facts:
            positions={r['position'] for r in self.test if r['fact_id']==fid and r['condition']=='similar_16'}
            self.assertEqual(positions,{'first','middle','last'})

    def test_scoring_no_substring_shortcut(self):
        self.assertEqual(score('  CITY. ', 'city'),1)
        self.assertEqual(score('The answer is city', 'city'),0)
        self.assertEqual(score('city or another', 'city'),0)

    def test_empty_output_is_not_a_substantive_answer(self):
        self.assertFalse(answered(''))
        self.assertFalse(answered(' \n '))
        self.assertFalse(answered('UNKNOWN.'))
        self.assertTrue(answered('a city'))

    def test_latency_iqr_and_nonfinite_rejection(self):
        self.assertEqual(quantile_diagnostics([1.,2.,3.,4.])['latency_iqr_s'],1.5)
        with self.assertRaises(ValueError):quantile_diagnostics([float('nan')])

    def test_manual_review_cannot_remove_cases_or_alter_evidence(self):
        original={**self.test[0],'correct':0,'answer':'WRONG'}
        row={k:original[k] for k in ['record_id','condition','question','context','expected','answer']}
        row.update(rater_1='other',rater_2='other',final_category='other',explanation='Actual case-specific cause')
        validate_review([row],[original])
        with self.assertRaises(ValueError):validate_review([],[original])
        with self.assertRaises(ValueError):validate_review([{**row,'answer':'changed'}],[original])
        with self.assertRaises(ValueError):validate_review([{**row,'rater_2':''}],[original])

    def test_review_selection_keeps_all_failures_when_fewer_than_thirty(self):
        sample=[{**r,'correct':0,'answer':'WRONG'} for r in self.test[:8]]
        self.assertEqual(len(review_selection(sample)),8)

    def test_paraphrases_and_difficulty_balanced(self):
        for q in [0,1,2]:
            self.assertEqual(len({r['fact_id'] for r in self.test if r['question_type']==q}),40)

    def test_reproducible_generation(self):
        a=make_facts(30,2417,'dev'); b=make_facts(30,2417,'dev')
        self.assertEqual(build_records(a,self.config),build_records(b,self.config))

    def test_null_statistics(self):
        s=paired_statistics([0.]*30,100,100,13)
        self.assertEqual(s['p_raw'],1)
        self.assertEqual(s['difference_pp'],0)
        self.assertEqual(s['paired_ci_low_pp'],0)

    def test_strong_paired_effect(self):
        s=paired_statistics([-1.]*40,100,200,13)
        self.assertEqual(s['difference_pp'],-100)
        self.assertLess(s['p_raw'],.05)
        self.assertEqual(s['paired_ci_high_pp'],-100)

    def test_holm_known_values_and_original_order(self):
        got=holm([.03,.001,.04])
        for a,b in zip(got,[.06,.003,.06]): self.assertAlmostEqual(a,b)

    def test_no_statistics_on_empty(self):
        with self.assertRaises(ValueError): paired_statistics([],10,10,1)

    def test_reject_pilot_or_fixture_as_final_evidence(self):
        for backend,phase in [('fixture','final'),('transformers_real_model','pilot')]:
            with self.assertRaises(ValueError):
                validate_logs([],[],{'backend':backend,'phase':phase},{})

    def test_incomplete_or_changed_raw_evidence_is_rejected(self):
        import analyze
        original=self.test[0]
        metadata={'backend':'transformers_real_model','phase':'final','freeze_sha256':'fixture_hash'}
        frozen={'model_lock':{'revision':'fixture_revision'}}
        with patch.object(analyze,'sha256',return_value='fixture_hash'):
            with self.assertRaises(ValueError): validate_logs([],[original],metadata,frozen)
            tampered={**original,'expected':'fabricated','backend':'transformers_real_model','phase':'final','answer':'fabricated','correct':1,'model_revision':'fixture_revision','error':''}
            with self.assertRaises(ValueError): validate_logs([tampered],[original],metadata,frozen)

    def test_context_k4_is_subset_of_k16(self):
        for r in [r for r in self.test if r['condition']=='similar_4']:
            match=next(s for s in self.test if s['fact_id']==r['fact_id'] and s['seed']==r['seed'] and s['condition']=='similar_16')
            self.assertEqual(r['distractor_answers'],match['distractor_answers'][:4])

    def test_complete_analysis_io_with_explicit_test_stub(self):
        # Artificial fixture ONLY: validation is mocked to exercise downstream I/O.
        # No fixture output is shipped as LLM evidence; TemporaryDirectory is discarded.
        import analyze
        from common import write_json, sha256
        scratch=ROOT/'.test_tmp'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            root=Path(tmp)
            (root/'config').mkdir(); (root/'data').mkdir()
            (root/'results/final').mkdir(parents=True); (root/'freeze').mkdir()
            cfg={**self.config,'bootstrap_samples':30,'permutation_samples':30}
            write_json(root/'config/experiment.json',cfg)
            write_json(root/'freeze/freeze.json',{'TEST_FIXTURE':True})
            sample=[r for r in self.test if r['fact_id'] in ['test-000','test-001','test-002']]
            rows=[]
            for r in sample:
                answer='WRONG_FIXTURE_ANSWER' if r['condition']=='similar_16' else r['expected']
                rows.append({**r,'answer':answer,'correct':score(answer,r['expected']),'input_tokens':90,
                    'latency_seconds':.1,'reached_token_limit':False,'model_revision':'TEST_FIXTURE'})
            raw=root/'results/final/raw.jsonl'
            raw.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
            (root/'data/test.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in sample),encoding='utf-8')
            write_json(root/'results/final/metadata.json',{'TEST_FIXTURE':True})
            write_json(root/'results/final/completion.json',{'raw_sha256':sha256(raw),'run_status':'complete'})
            with patch.object(analyze,'ROOT',root), patch.object(analyze,'assert_frozen',return_value={}), patch.object(analyze,'validate_logs'):
                analyze.run_analysis()
            import csv,xml.etree.ElementTree as ET
            with (root/'results/analysis/main_results.csv').open(encoding='utf-8') as f:
                results=list(csv.DictReader(f))
            baseline=next(r for r in results if r['condition']=='closed_book')
            self.assertEqual(float(baseline['accuracy_pct']),0.)
            self.assertEqual(float(baseline['expected_response_accuracy_pct']),100.)
            for svg in (root/'results/analysis').glob('*.svg'): ET.parse(svg)
            self.assertTrue((root/'results/analysis/audit_rows.csv').exists())
            self.assertTrue((root/'results/analysis/success_examples.csv').exists())
            self.assertTrue((root/'results/analysis/error_selection.json').exists())
            self.assertTrue((root/'results/analysis/figure_4_answerability.svg').exists())
            with (root/'results/analysis/error_review.csv').open(encoding='utf-8') as f:
                self.assertEqual(len(list(csv.DictReader(f))),9)

if __name__=='__main__': unittest.main()
