"""Trace a reported condition accuracy to individual raw model responses."""
import argparse
import statistics
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT, read_jsonl, score

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--condition',required=True)
    p.add_argument('--record-id')
    a=p.parse_args()
    rows=read_jsonl(ROOT/'results/final/raw.jsonl')
    selected=[r for r in rows if r['condition']==a.condition]
    if not selected:raise ValueError('Unknown condition or no final data')
    print('Numerator:',sum(score(r['answer'],r['city']) for r in selected),'Denominator:',len(selected))
    print('Gold-city accuracy %:',statistics.mean(score(r['answer'],r['city']) for r in selected)*100)
    if a.record_id:
        candidates=[r for r in selected if r['record_id']==a.record_id]
        if not candidates:raise ValueError('Record does not belong to selected condition')
    else:candidates=selected[:3]
    for r in candidates:
        print('\nRecord:',r['record_id'],'Model revision:',r['model_revision'])
        print('Question:',r['question'],'\nContext:',r['context'])
        print('Gold city:',r['city'],'Expected response:',r['expected'],'Actual answer:',repr(r['answer']))
        print('Strict gold-city correctness:',score(r['answer'],r['city']))
        print('Prompt SHA256:',r['prompt_sha256'])

if __name__=='__main__':main()
