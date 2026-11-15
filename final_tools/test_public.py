import unittest
import json
from pathlib import Path
from analyze_public import extractor, exact, sha, ROOT, RAW_HASH

class DiagnosticTests(unittest.TestCase):
    def test_exact_entity_not_prefix(self):
        context='The capital city of Veloria-T12 is Wrong. The capital city of Veloria-T1 is Right.'
        self.assertEqual(extractor('What is the capital of Veloria-T1?',context),'Right')
    def test_missing_target_cannot_copy_distractor(self):
        self.assertEqual(extractor('What is the capital of Veloria-T1?','The capital city of Veloria-T2 is Distractor.'),'UNKNOWN')
    def test_lake_relation_not_capital(self):
        self.assertEqual(extractor('What is the capital of Veloria-T1?','The largest lake of Veloria-T1 is Distractor.'),'UNKNOWN')
    def test_conflicting_unique_associations_abstain(self):
        self.assertEqual(extractor('What is the capital of Veloria-T1?','The capital city of Veloria-T1 is Aaa. The capital city of Veloria-T1 is Bbb.'),'UNKNOWN')
    def test_scoring_preserves_name_errors(self):
        self.assertEqual(exact('Vmode','Vemode'),0)
        self.assertEqual(exact('  Vemode. ','vemode'),1)
    def test_original_evidence_hash_unchanged(self):
        self.assertEqual(sha(ROOT/'results/final/raw.jsonl'),RAW_HASH)
    def test_result_table_matches_original_archived_table(self):
        import csv
        with (ROOT/'results/final_paper/table_1_results.csv').open(encoding='utf-8') as f:
            new={r['condition']:r for r in csv.DictReader(f)}
        with (ROOT/'results/analysis/main_results.csv').open(encoding='utf-8') as f:
            old=list(csv.DictReader(f))
        for r in old:
            for a,b in [('accuracy_pct','accuracy_pct'),('ci_low','ci95_low_pct'),('ci_high','ci95_high_pct')]:
                self.assertAlmostEqual(float(new[r['condition']][a]),float(r[b]),places=9)

if __name__=='__main__':unittest.main()
