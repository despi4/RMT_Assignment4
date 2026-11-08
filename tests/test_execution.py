"""Regression checks for actual execution risks; no fixture is research evidence."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import common
import run
from common import read_json, read_jsonl, validate_saved_calls, exclusive_run, write_json, sha256
from prepare import chosen_revision


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.test_tmp').mkdir(exist_ok=True)
        # An actual development response already preserved in the repository.
        self.real=read_jsonl(ROOT/'validation/dev_smoke_63/raw.jsonl')[0]
        self.expected=next(r for r in read_jsonl(ROOT/'data/dev.jsonl') if r['record_id']==self.real['record_id'])
        self.revision=read_json(ROOT/'config/model_lock.json')['revision']

    def test_preparation_preserves_checkpoint_without_querying_latest(self):
        resolve=Mock(side_effect=AssertionError('Must not resolve latest'))
        lock={'model_id':'chosen','revision':'a'*40}
        self.assertEqual(chosen_revision('chosen',lock,resolve),'a'*40)
        resolve.assert_not_called()
        with self.assertRaises(ValueError): chosen_revision('different',lock,resolve)

    def test_saved_real_dev_call_validates(self):
        self.assertEqual(validate_saved_calls([self.real],[self.expected],self.revision,'pilot'),{self.real['record_id']})

    def test_resume_rejects_changed_stimulus_score_and_token_evidence(self):
        changes=[{'prompt':'edited'}, {'answer':'edited'}, {'correct':1-self.real['correct']},
                 {'generated_tokens':999}, {'generated_token_ids':None}, {'latency_seconds':float('nan')},
                 {'phase':'final'}, {'backend':'fixture'}, {'model_revision':'different'},
                 {'error':'Recorded real execution failure'}, {'input_tokens':0}]
        for changed in changes:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_saved_calls([{**self.real,**changed}],[self.expected],self.revision,'pilot')

    def test_resume_rejects_duplicate_calls(self):
        with self.assertRaises(ValueError):
            validate_saved_calls([self.real,self.real],[self.expected],self.revision,'pilot')

    def test_os_lock_prevents_two_writers_and_releases_after_interruption(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.test_tmp') as directory:
            with self.assertRaises(KeyboardInterrupt):
                with exclusive_run(directory):
                    with self.assertRaises(ValueError):
                        with exclusive_run(directory): pass
                    raise KeyboardInterrupt
            with exclusive_run(directory): pass

    def test_final_without_freeze_fails_before_inference(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.test_tmp') as directory:
            root=Path(directory)
            (root/'config').mkdir()
            write_json(root/'config/experiment.json',read_json(ROOT/'config/experiment.json'))
            args=SimpleNamespace(phase='final',device=None)
            with patch.object(run,'ROOT',root),patch.object(common,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'Moodle'):
                    run.execute(args,root/'results/final')
            self.assertFalse((root/'results/final/metadata.json').exists())

    def test_reproduction_can_use_public_freeze_but_final_requires_private_receipt(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.test_tmp') as directory:
            root=Path(directory); (root/'config').mkdir(); (root/'freeze').mkdir()
            lock=read_json(ROOT/'config/model_lock.json')
            write_json(root/'config/model_lock.json',lock)
            frozen={'source_hashes':{},'model_lock':lock,'environment':common.environment(),
                    'upload_evidence':'moodle_upload.png','upload_evidence_sha256':'private',
                    'protocol_document':'protocol_document.docx','protocol_sha256':'private'}
            write_json(root/'freeze/freeze.json',frozen)
            with patch.object(common,'ROOT',root),patch.object(common,'source_hashes',return_value={}):
                common.assert_frozen(strict_environment=False)
                with self.assertRaisesRegex(ValueError,'receipt'): common.assert_frozen()

    def test_completed_resume_skips_loading_model_and_keeps_completion_bytes(self):
        import torch
        import transformers
        with tempfile.TemporaryDirectory(dir=ROOT/'.test_tmp') as directory:
            root=Path(directory); out=root/'results/pilot/test_resume'
            (root/'config').mkdir(); (root/'data').mkdir(); out.mkdir(parents=True)
            cfg=read_json(ROOT/'config/experiment.json'); lock=read_json(ROOT/'config/model_lock.json')
            write_json(root/'config/experiment.json',cfg); write_json(root/'config/model_lock.json',lock)
            write_json(root/'config/runtime.json',read_json(ROOT/'config/runtime.json'))
            rows=read_jsonl(ROOT/'validation/dev_smoke_63/raw.jsonl')
            stimulus={r['record_id']:r for r in read_jsonl(ROOT/'data/dev.jsonl')}
            data=root/'data/dev.jsonl'
            data.write_text(''.join(json.dumps(stimulus[r['record_id']])+'\n' for r in rows),encoding='utf-8')
            raw=out/'raw.jsonl'; raw.write_bytes((ROOT/'validation/dev_smoke_63/raw.jsonl').read_bytes())
            with patch.object(common,'ROOT',root): profile=common.runtime_profile(torch)
            meta={'model_lock':lock,'input_sha256':sha256(data),'source_hashes':{},'config':cfg,
                  'planned_calls':63,'environment':common.environment(),'runtime_profile':profile}
            write_json(out/'metadata.json',meta)
            write_json(out/'completion.json',{'finished_at':'ACTUAL_OLD_VALUE_FOR_TEST_ONLY',
                'raw_sha256':sha256(raw),'run_status':'complete','recorded_calls':63,'planned_calls':63})
            before=(out/'completion.json').read_bytes()
            args=SimpleNamespace(phase='pilot',limit_facts=3,device=None)
            with patch.object(run,'ROOT',root),patch.object(common,'ROOT',root),patch.object(run,'source_hashes',return_value={}),patch.object(transformers.AutoModelForCausalLM,'from_pretrained') as load:
                run.execute(args,out)
                load.assert_not_called()
            self.assertEqual(before,(out/'completion.json').read_bytes())
            with (out/'metadata.json').open(encoding='utf-8') as f: altered=json.load(f)
            altered['environment']['python']='changed'
            write_json(out/'metadata.json',altered)
            with patch.object(run,'ROOT',root),patch.object(common,'ROOT',root),patch.object(run,'source_hashes',return_value={}):
                with self.assertRaisesRegex(ValueError,'mix hardware'): run.execute(args,out)


if __name__=='__main__':unittest.main()
