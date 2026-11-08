"""Summarize only human-completed Appendix B coding."""
from collections import Counter
import argparse
import csv
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_json, read_jsonl, sha256, write_csv, write_json
from error_schema import DEFINITIONS, review_selection, validate_review

CATEGORIES = {'distractor_copy','wrong_entity_or_binding','unsupported_answer','unnecessary_abstention','format_error','other'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rater-1-name',required=True)
    parser.add_argument('--rater-2-name',required=True)
    args=parser.parse_args()
    if not args.rater_1_name.strip() or not args.rater_2_name.strip() or args.rater_1_name.strip().casefold()==args.rater_2_name.strip().casefold():
        raise ValueError('Identify two distinct human raters; no independence claim can be prefilled.')
    path=ROOT/'results/analysis/error_review.csv'
    selection=read_json(ROOT/'results/analysis/error_selection.json')
    raw=ROOT/'results/final/raw.jsonl'
    if selection['raw_sha256']!=sha256(raw) or selection['cases']!=review_selection(read_jsonl(raw)):
        raise ValueError('Selection does not match real raw results')
    with path.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
    validate_review(rows,selection['cases'])
    if not rows:
        write_json(ROOT/'results/analysis/error_review_status.json',{'reviewed':0,'note':'No observed failures'})
        return
    counts=Counter(r['final_category'] for r in rows)
    write_csv(ROOT/'results/analysis/error_summary.csv',[
        {'category':k,'definition':DEFINITIONS[k],'count':v,'pct_of_reviewed_errors':v/len(rows)*100,
         'example_record_id':next(r['record_id'] for r in rows if r['final_category']==k),
         'possible_cause':next(r['explanation'] for r in rows if r['final_category']==k)} for k,v in sorted(counts.items())])
    agreement=sum(r['rater_1']==r['rater_2'] for r in rows)/len(rows)
    a=Counter(r['rater_1'] for r in rows); b=Counter(r['rater_2'] for r in rows)
    chance=sum(a[k]*b[k] for k in CATEGORIES)/(len(rows)**2)
    kappa=(agreement-chance)/(1-chance) if chance<1 else None
    write_json(ROOT/'results/analysis/error_review_status.json',{'reviewed':len(rows),
        'rater_1_name':args.rater_1_name,'rater_2_name':args.rater_2_name,
        'review_file_sha256':sha256(path),'raw_sha256':sha256(raw),
        'agreement':agreement,'cohens_kappa':kappa,'kappa_note':'Undefined if both raters use only the same one category',
        'sampling':'Condition-stratified review of at most 30 errors; percentages apply to this sample, not all failures'})
    print('Appendix B counts computed from human labels.')

if __name__=='__main__': main()
