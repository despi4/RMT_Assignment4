"""Compare an independently executed reproduction without overwriting final results."""
import argparse
import csv
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT, read_json, sha256, utc_now, write_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id',required=True)
    p.add_argument('--person',required=True,help='Actual person who executed the reproduction')
    p.add_argument('--commit',required=True)
    p.add_argument('--notes',default='')
    a=p.parse_args()
    if not a.run_id.replace('_','').replace('-','').isalnum():p.error('Invalid run ID')
    original=ROOT/'results/analysis/main_results.csv'
    reproduced=ROOT/'results/reproduction'/a.run_id/'analysis/main_results.csv'
    def rows(path):
        with path.open(encoding='utf-8',newline='') as f:return {r['condition']:r for r in csv.DictReader(f)}
    before,after=rows(original),rows(reproduced)
    if set(before)!=set(after):raise ValueError('Reproduction condition set differs')
    differences={c:float(after[c]['accuracy_pct'])-float(before[c]['accuracy_pct']) for c in before}
    metadata=read_json(reproduced.parent.parent/'metadata.json')
    if metadata['phase']!='reproduction':raise ValueError('Requires real separately recorded reproduction')
    record={'person_declared_by_team':a.person,'date_utc':utc_now(),'commit_or_release':a.commit,
       'run_id':a.run_id,'machine_environment':metadata['environment'],'hardware':metadata['hardware'],
       'original_main_results_sha256':sha256(original),'reproduced_main_results_sha256':sha256(reproduced),
       'accuracy_differences_pp':differences,
       'main_accuracy_table_match':all(abs(v)<1e-10 for v in differences.values()),
       'commands':[f'python scripts/run.py --phase reproduction --run-id {a.run_id}',
                   f'python scripts/analyze.py --reproduction-id {a.run_id}'],
       'notes_and_readme_fixes':a.notes,
       'scope':'Checks numeric agreement; human identity and independence require genuine student declaration. Runtime is not expected identical.'}
    write_json(reproduced.parent.parent/'Appendix_C_Record.json',record)
    print('Recorded actual table comparison for Appendix C. Inspect discrepancies and complete the human account.')

if __name__=='__main__':main()
