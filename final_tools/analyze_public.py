"""Recompute final-paper evidence with Python 3.10+ and no external packages.

This is an analysis-only extension dated 2026-11-16. It never authenticates
Moodle receipts and never relaxes the frozen inference entry points.
"""
import argparse
import csv
import hashlib
import html
import json
import random
import re
import statistics
import string
import unicodedata
from math import fsum
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_HASH = '446e3bf1e57eac89d75191e6c00f4b35ce394bb6c492968b0e03204c6b8929af'

def normalize(s):
    return ' '.join(unicodedata.normalize('NFKC', s).casefold().split()).strip(string.punctuation + ' ')

def exact(a, b):
    return int(normalize(a) == normalize(b))

def extractor(question, context):
    """Post-hoc template diagnostic. Receives no gold label or presence flag."""
    entities = re.findall(r'\b[A-Za-z]+-[A-Z]\d+\b', question)
    if len(set(entities)) != 1:
        return 'UNKNOWN'
    pairs = re.findall(r'The capital city of ([A-Za-z]+-[A-Z]\d+) is ([A-Za-z]+)\.', context)
    candidates = {city for entity, city in pairs if entity == entities[0]}
    return next(iter(candidates)) if len(candidates) == 1 else 'UNKNOWN'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def percentile(values, q):
    values = sorted(values)
    t = (len(values)-1)*q
    i = int(t)
    return values[i] + (values[min(i+1, len(values)-1)]-values[i])*(t-i)

def csv_write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def figure(path, title, labels, values, limits=None):
    # Horizontal bars, fixed 0-100 scale; standalone vector output.
    width, height = 920, 110+len(values)*65
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<style>text{font-family:Arial,sans-serif;font-size:18px;fill:#172b42}</style>',
             f'<text x="22" y="30" font-size="22">{html.escape(title)}</text>']
    for tick in [0,25,50,75,100]:
        x=230+tick*5.8
        lines += [f'<line x1="{x}" y1="55" x2="{x}" y2="{height-40}" stroke="#ddd"/>',f'<text x="{x}" y="{height-15}" text-anchor="middle">{tick}%</text>']
    for i,(label,value) in enumerate(zip(labels,values)):
        y=65+i*65
        label_position=limits[i][1] if limits else value
        lines += [f'<text x="220" y="{y+23}" text-anchor="end">{html.escape(label)}</text>',f'<rect x="230" y="{y}" width="{value*5.8}" height="32" fill="#306a91"/>',f'<text x="{240+label_position*5.8}" y="{y+24}">{value:.2f}</text>']
        if limits:
            lo,hi=limits[i];xx1=230+lo*5.8;xx2=230+hi*5.8
            lines += [f'<path d="M {xx1} {y+16} H {xx2} M {xx1} {y+9} V {y+23} M {xx2} {y+9} V {y+23}" stroke="#101010" stroke-width="2"/>']
    lines.append('</svg>');path.write_text('\n'.join(lines),encoding='utf-8')

def run(out):
    out.mkdir(parents=True, exist_ok=True)
    frozen=json.loads((ROOT/'freeze/freeze.json').read_text(encoding='utf-8'))
    for name,expected in frozen['source_hashes'].items():
        if sha(ROOT/name) != expected:
            raise ValueError('Frozen source mismatch: '+name)
    rawpath=ROOT/'results/final/raw.jsonl'
    if sha(rawpath) != RAW_HASH: raise ValueError('Archived raw log mismatch')
    rows=[json.loads(s) for s in rawpath.read_text(encoding='utf-8').splitlines()]
    expected=[json.loads(s) for s in (ROOT/'data/test.jsonl').read_text(encoding='utf-8').splitlines()]
    config=json.loads((ROOT/'config/experiment.json').read_text(encoding='utf-8'))
    completion=json.loads((ROOT/'results/final/completion.json').read_text(encoding='utf-8'))
    if completion['raw_sha256'] != RAW_HASH or completion['run_status'] != 'complete': raise ValueError('Completion mismatch')
    index={r['record_id']:r for r in expected}
    if len(rows)!=2520 or len({r['record_id'] for r in rows})!=2520 or set(index)!={r['record_id'] for r in rows}: raise ValueError('Incomplete/duplicate calls')
    for r in rows:
        if r['error'] or r['phase']!='final' or r['backend']!='transformers_real_model': raise ValueError('Invalid call')
        if r['model_revision'] != frozen['model_lock']['revision']: raise ValueError('Revision mismatch')
        if any(r[k]!=v for k,v in index[r['record_id']].items()): raise ValueError('Changed stimulus')
        if exact(r['answer'],r['expected'])!=r['correct']: raise ValueError('Wrong stored score')
    tables=[];seeds=[];rng=random.Random(7341);parser_rows=[]
    for condition in config['conditions']:
        group=[r for r in rows if r['condition']==condition];clusters=defaultdict(list)
        for r in group:clusters[r['fact_id']].append(exact(r['answer'],r['city']))
        vals=[statistics.mean(v) for v in clusters.values()]
        boots=[statistics.mean(rng.choices(vals,k=len(vals))) for _ in range(4000)]
        svals=[]
        for seed in config['context_seeds']:
            sub=[r for r in group if r['seed']==seed];v=100*statistics.mean(exact(r['answer'],r['city']) for r in sub);svals.append(v)
            seeds.append(dict(condition=condition,context_seed=seed,accuracy_pct=v))
        latency=[r['latency_seconds'] for r in group]
        pp=[]
        for r in group:
            pred=extractor(r['question'],r['context']);pp.append(exact(pred,r['expected']))
            parser_rows.append(dict(record_id=r['record_id'],prediction=pred,expected=r['expected'],correct=pp[-1],status='post-hoc deterministic diagnostic'))
        tables.append(dict(condition=condition,calls=len(group),facts=len(clusters),correct=sum(exact(r['answer'],r['city']) for r in group),accuracy_pct=statistics.mean(svals),sd_pp=statistics.stdev(svals),ci_low=100*percentile(boots,.025),ci_high=100*percentile(boots,.975),expected_correct=sum(r['correct'] for r in group),expected_pct=100*statistics.mean(r['correct'] for r in group),parser_expected_pct=100*statistics.mean(pp),latency_median=statistics.median(latency),latency_iqr=percentile(latency,.75)-percentile(latency,.25),latency_p95=percentile(latency,.95),input_tokens_mean=statistics.mean(r['input_tokens'] for r in group)))
    contrasts=[]
    for i,(a,b) in enumerate(config['planned_comparisons']):
        paired=defaultdict(dict)
        for r in rows:
            if r['condition'] in [a,b]:paired[r['fact_id']].setdefault(r['condition'],[]).append(exact(r['answer'],r['city']))
        dif=[statistics.mean(v[a])-statistics.mean(v[b]) for v in paired.values()];rr=random.Random(7341+i);n=len(dif);observed=statistics.mean(dif)
        # Python 3.12 changed floating-point sum(); use the same accurate sum on all versions.
        boots=[fsum(rr.choice(dif) for _ in range(n))/n for _ in range(4000)]
        extreme=sum(abs(fsum(d*rr.choice([-1,1]) for d in dif)/n)>=abs(observed)-1e-12 for _ in range(10000))
        contrasts.append(dict(hypothesis='H'+str(i+1),a=a,b=b,delta_pp=100*observed,ci_low_pp=100*percentile(boots,.025),ci_high_pp=100*percentile(boots,.975),p_raw=(extreme+1)/10001))
    previous=0
    for rank,i in enumerate(sorted(range(3),key=lambda i:contrasts[i]['p_raw'])):
        previous=max(previous,min(1,contrasts[i]['p_raw']*(3-rank)));contrasts[i]['p_holm']=previous
    positions=[]
    for pos in ['first','middle','last']:
        g=[r for r in rows if r['condition']=='similar_16' and r['position']==pos]
        positions.append(dict(position=pos,n=len(g),correct=sum(r['correct'] for r in g),accuracy_pct=100*statistics.mean(r['correct'] for r in g)))
    diag=Counter()
    for r in rows:
        if r['correct']:continue
        ans=normalize(r['answer'])
        cat='unsupported_answer' if not r['target_present'] and ans not in ['','unknown'] else 'unnecessary_abstention' if r['target_present'] and ans=='unknown' else 'distractor_copy' if ans in [normalize(x) for x in r['distractor_answers']] else 'other_wrong_output'
        diag[cat]+=1
    diagnostics=[dict(category=k,count=v,percent=100*v/sum(diag.values())) for k,v in sorted(diag.items())]
    lookup={(r['fact_id'],r['seed'],r['condition']):r for r in rows}
    token_pairs={str(k):sum(r['input_tokens']==lookup[(r['fact_id'],r['seed'],'irrelevant_'+str(k))]['input_tokens'] for r in rows if r['condition']=='similar_'+str(k)) for k in [4,16]}
    for name,records in [('table_1_results',tables),('table_2_contrasts',contrasts),('table_3_diagnostics',diagnostics),('table_4_positions',positions),('per_seed',seeds),('extractor_outputs',parser_rows)]:csv_write(out/(name+'.csv'),records)
    summary=dict(raw_sha256=RAW_HASH,n_calls=len(rows),n_facts=120,max_input_tokens=max(r['input_tokens'] for r in rows),token_matched_pairs=token_pairs,empty_outputs=sum(not normalize(r['answer']) for r in rows),limit_hits=sum(r['reached_token_limit'] for r in rows),frozen_source_files_checked=len(frozen['source_hashes']),extractor_expected_correct=sum(r['correct'] for r in parser_rows),tables=tables,contrasts=contrasts,diagnostics=diagnostics,positions=positions,scope='Archived-output recalculation plus post-hoc deterministic parser; no new LLM inference or independent human reproduction')
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    supported=[r for r in tables if r['condition'] not in ['closed_book','target_absent_16']]
    figure(out/'figure_1_accuracy.svg','Gold-city exact-match accuracy',[r['condition'] for r in supported],[r['accuracy_pct'] for r in supported],[(r['ci_low'],r['ci_high']) for r in supported])
    figure(out/'figure_2_position.svg','Similar 16 position subgroups are descriptive',[r['position'] for r in positions],[r['accuracy_pct'] for r in positions])
    figure(out/'figure_3_abstention.svg','Correct UNKNOWN when target evidence is absent',['closed_book','target_absent_16'],[tables[0]['expected_pct'],tables[-1]['expected_pct']])
    figure(out/'figure_4_extractor.svg','Post-hoc template extractor expected-response accuracy',[r['condition'] for r in tables],[r['parser_expected_pct'] for r in tables])
    print(json.dumps({k:summary[k] for k in ['n_calls','n_facts','frozen_source_files_checked','extractor_expected_correct','scope']},indent=2))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'results/final_paper');args=p.parse_args();run(args.out)
