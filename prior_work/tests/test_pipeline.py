"""Mutated fixtures below are tests, never additional research observations."""
import copy
import csv
import tempfile
import unittest
from pathlib import Path
import pipeline as p

class PipelineTests(unittest.TestCase):
    def setUp(self):
        with (Path(__file__).resolve().parents[1]/'data/results.csv').open() as f:
            self.rows=list(csv.DictReader(f))
    def test_valid_data_and_output_files(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(__file__).resolve().parents[1]/'data/results.csv'
            result=p.run(source,d)
            self.assertEqual((result['records'],result['ft_rag_contrasts']),(30,14))
            self.assertTrue((Path(d)/'comparisons.csv').exists())
    def test_missing_value(self):
        self.rows[0]['source_location']=''
        with self.assertRaises(ValueError): p.validate(self.rows)
    def test_missing_column(self):
        with self.assertRaises(ValueError): p.validate(self.rows,['record_id'])
    def test_duplicate_id(self):
        self.rows[1]['record_id']=self.rows[0]['record_id']
        with self.assertRaises(ValueError): p.validate(self.rows)
    def test_duplicate_configuration(self):
        r=copy.deepcopy(self.rows[0]);r['record_id']='FIXTURE_COPY';self.rows.append(r)
        with self.assertRaises(ValueError): p.validate(self.rows)
    def test_invalid_category(self):
        self.rows[0]['fact_category']='seen_equals_popular'
        with self.assertRaises(ValueError): p.validate(self.rows)
    def test_invalid_metric_and_unit(self):
        for field,value in [('value','1.01'),('value','NaN'),('value','NR'),('unit','unknown')]:
            rows=copy.deepcopy(self.rows);rows[0][field]=value
            with self.assertRaises(ValueError): p.validate(rows)
    def test_invalid_url(self):
        self.rows[0]['source_url']='not_a_url'
        with self.assertRaises(ValueError): p.validate(self.rows)
    def test_incompatible_pairs(self):
        for r in self.rows:
            if r['method']=='RAG': r['split']='different_test_split'
        accepted,rejected=p.compare(self.rows)
        self.assertEqual(len(accepted),0);self.assertEqual(len(rejected),14)
    def test_sft_is_qualified_and_negative(self):
        accepted,_=p.compare(self.rows)
        sft=[r for r in accepted if r['ft_type']=='SFT']
        self.assertEqual(len(sft),3)
        self.assertTrue(all(r['comparability']=='qualified' and r['rag_minus_ft_pp']<0 for r in sft))
    def test_arithmetic_and_percent_units(self):
        self.assertEqual(p.difference_pp({'value':'0.654','unit':'fraction'},
                                        {'value':'0.813','unit':'fraction'}),-15.9)
        self.assertEqual(p.difference_pp({'value':'65.4','unit':'percent'},
                                        {'value':'32.0','unit':'percent'}),33.4)
    def test_missing_rag_is_rejected(self):
        accepted,rejected=p.compare([r for r in self.rows if r['method']!='RAG'])
        self.assertEqual(len(accepted),0);self.assertEqual(len(rejected),14)

if __name__=='__main__': unittest.main()
