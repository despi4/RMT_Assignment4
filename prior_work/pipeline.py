"""Audit source-reported QA results; never trains or evaluates a language model."""
import argparse
import csv
import hashlib
import json
import math
import platform
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

CATEGORIES = {'newly_introduced', 'existing_seen', 'common_popular', 'rare_long_tail', 'not_specified'}
METHODS = {'BASE', 'RAG', 'UFT', 'SFT'}
MATCH = ['study_id', 'model', 'model_version', 'dataset', 'split', 'fact_category',
         'metric', 'unit', 'higher_is_better', 'evaluation_task', 'baseline_id']
FIELDS = ['record_id', 'study_id', 'source_url', 'source_location', 'model', 'model_version',
          'dataset', 'split', 'fact_category', 'source_fact_category', 'category_definition',
          'method', 'variant', 'metric', 'value', 'unit', 'higher_is_better', 'group_id',
          'evaluation_task', 'scoring', 'baseline_id', 'training_data', 'retrieval_data',
          'conditions', 'verification_status']

def validate(rows, headers=None):
    if headers is not None and not set(FIELDS).issubset(headers):
        raise ValueError('Missing schema columns: ' + ', '.join(sorted(set(FIELDS)-set(headers))))
    if not rows:
        raise ValueError('Dataset is empty')
    ids, configurations = set(), set()
    for n, r in enumerate(rows, 2):
        missing = [k for k in FIELDS if not str(r.get(k, '')).strip()]
        if missing:
            raise ValueError(f'Row {n}: missing values {missing}')
        if r['record_id'] in ids:
            raise ValueError('Duplicate record_id: ' + r['record_id'])
        ids.add(r['record_id'])
        key = tuple(r[k] for k in MATCH + ['method', 'variant', 'scoring'])
        if key in configurations:
            raise ValueError(f'Row {n}: duplicate experimental configuration')
        configurations.add(key)
        if r['fact_category'] not in CATEGORIES or r['method'] not in METHODS:
            raise ValueError(f'Row {n}: invalid category or method')
        u = urlparse(r['source_url'])
        if u.scheme not in ('http', 'https') or not u.hostname:
            raise ValueError(f'Row {n}: invalid HTTP(S) URL syntax')
        if r['higher_is_better'] not in ('TRUE', 'FALSE'):
            raise ValueError(f'Row {n}: invalid metric direction')
        if r['metric'] != 'accuracy' or r['unit'] not in ('fraction', 'percent'):
            raise ValueError(f'Row {n}: unsupported metric or unit')
        try:
            v = float(r['value'])
        except ValueError as e:
            raise ValueError(f'Row {n}: nonnumeric metric') from e
        if not math.isfinite(v) or not 0 <= v <= (1 if r['unit']=='fraction' else 100):
            raise ValueError(f'Row {n}: metric outside declared range')
    return rows

def difference_pp(rag, ft):
    def percent(r):
        return Decimal(r['value']) * (100 if r['unit']=='fraction' else 1)
    return float(percent(rag)-percent(ft))

def compare(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r['group_id']].append(r)
    accepted, rejected = [], []
    for group, items in sorted(groups.items()):
        fts = [r for r in items if r['method'] in ('UFT', 'SFT')]
        rags = [r for r in items if r['method']=='RAG']
        for ft in fts:
            if len(rags) != 1:
                rejected.append({'ft_id':ft['record_id'], 'group_id':group,
                                 'reason':'Requires exactly one RAG arm'})
                continue
            rag = rags[0]
            mismatches = [k for k in MATCH if ft[k] != rag[k]]
            # SFT and RAG may use different scoring heads. Retain this source-reported
            # contrast explicitly as qualified, rather than calling it controlled.
            if ft['scoring'] != rag['scoring'] and ft['method'] != 'SFT':
                mismatches.append('scoring')
            if mismatches:
                rejected.append({'ft_id':ft['record_id'], 'group_id':group,
                                 'reason':'Mismatch: '+', '.join(mismatches)})
                continue
            delta = difference_pp(rag, ft)
            note = ('Qualified source-reported contrast: SFT uses labelled QA and a classification head; '
                    'RAG uses retrieved text and label likelihood; not an isolated knowledge-injection effect.'
                    if ft['method']=='SFT' else
                    'Within-paper contrast; prompts, corpus exposure and tuning budgets still require manual assessment.')
            base = next((r for r in items if r['record_id']==ft['baseline_id'] and r['method']=='BASE'), None)
            accepted.append({'study_id':ft['study_id'], 'group_id':group, 'model':ft['model'],
                'dataset':ft['dataset'], 'fact_category':ft['fact_category'],
                'ft_id':ft['record_id'], 'rag_id':rag['record_id'], 'ft_type':ft['method'],
                'ft_variant':ft['variant'], 'ft_source_value':ft['value'],
                'rag_source_value':rag['value'], 'source_unit':ft['unit'],
                'rag_minus_ft_pp':delta, 'baseline_source_value':base['value'] if base else 'NR',
                'ft_minus_base_pp':difference_pp(ft,base) if base else 'NR',
                'rag_minus_base_pp':difference_pp(rag,base) if base else 'NR',
                'comparability':'qualified' if ft['method']=='SFT' else 'within_paper',
                'interpretation_note':note, 'source_location':ft['source_location']})
    return accepted, rejected

def write_csv(path, rows, fields):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

def run(input_path, output_dir):
    input_path, output_dir = Path(input_path), Path(output_dir)
    with input_path.open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f); rows=list(reader); headers=reader.fieldnames
    validate(rows,headers)
    accepted,rejected=compare(rows)
    output_dir.mkdir(parents=True,exist_ok=True)
    write_csv(output_dir/'comparisons.csv',accepted,list(accepted[0]) if accepted else ['ft_id','rag_id','rag_minus_ft_pp'])
    write_csv(output_dir/'rejected_pairs.csv',rejected,['ft_id','group_id','reason'])
    summary={'records':len(rows),'studies_with_numeric_results':len({r['study_id'] for r in rows}),
        'configurations':len({r['group_id'] for r in rows}), 'ft_rag_contrasts':len(accepted),
        'qualified_sft_contrasts':sum(r['comparability']=='qualified' for r in accepted),
        'rejected_pairs':len(rejected), 'methods':dict(Counter(r['method'] for r in rows)),
        'category_record_counts':dict(Counter(r['fact_category'] for r in rows)),
        'categories_without_numeric_records':sorted(CATEGORIES-{r['fact_category'] for r in rows}),
        'input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest()}
    (output_dir/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    (output_dir/'runtime.json').write_text(json.dumps({'python':platform.python_version(),
        'platform':platform.platform(),'dependencies':'Python standard library only',
        'run_utc':datetime.now(timezone.utc).isoformat()},indent=2)+'\n')
    log=f"Validated {len(rows)} records; {summary['studies_with_numeric_results']} studies; {summary['configurations']} configurations\nComputed {len(accepted)} contrasts ({summary['qualified_sft_contrasts']} qualified SFT); rejected {len(rejected)}\n"
    (output_dir/'run.log').write_text(log,encoding='utf-8')
    print(log,end='')
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',default='data/results.csv')
    parser.add_argument('--output',default='outputs')
    args=parser.parse_args()
    try:
        run(args.input,args.output)
    except (ValueError,OSError) as e:
        parser.exit(1,'Validation failed: '+str(e)+'\n')
