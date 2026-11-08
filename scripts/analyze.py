"""Validate complete real logs, compute paired statistics and create SVG figures."""
import argparse
from collections import defaultdict
import csv
import html
import json
import random
import statistics
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, assert_frozen, normalize, answered, quantile_diagnostics, read_json, read_jsonl, score, sha256, write_csv, write_json
from error_schema import review_selection, DEFINITIONS

def percentile(values, q):
    vals = sorted(values)
    t = (len(vals) - 1) * q
    lo = int(t)
    return vals[lo] + (vals[min(lo+1, len(vals)-1)] - vals[lo]) * (t-lo)

def paired_statistics(differences, n_boot, n_perm, seed):
    if not differences:
        raise ValueError('No paired facts')
    rng = random.Random(seed)
    n = len(differences)
    observed = statistics.mean(differences)
    boots = [sum(rng.choice(differences) for _ in range(n))/n for _ in range(n_boot)]
    extreme = 0
    for _ in range(n_perm):
        simulated = sum(d * rng.choice([-1, 1]) for d in differences) / n
        extreme += abs(simulated) >= abs(observed) - 1e-12
    return {'n_independent_facts': n, 'difference_pp': 100*observed,
            'paired_ci_low_pp': 100*percentile(boots, .025),
            'paired_ci_high_pp': 100*percentile(boots, .975),
            'test': 'two-sided paired sign-flip permutation on per-fact mean differences',
            'p_raw': (extreme+1)/(n_perm+1), 'permutations': n_perm}

def holm(pvalues):
    result = [0.] * len(pvalues)
    previous = 0.
    for rank, i in enumerate(sorted(range(len(pvalues)), key=lambda i: pvalues[i])):
        previous = max(previous, min(1., pvalues[i]*(len(pvalues)-rank)))
        result[i] = previous
    return result

def validate_logs(rows, expected, metadata, frozen, phase='final'):
    if metadata['backend'] != 'transformers_real_model' or metadata['phase'] != phase:
        raise ValueError('Analysis requires real final inference, not fixtures or pilot')
    if metadata['freeze_sha256'] != sha256(ROOT / 'freeze/freeze.json'):
        raise ValueError('Freeze does not match run')
    expected_by_id = {x['record_id']: x for x in expected}
    if len({r['record_id'] for r in rows}) != len(rows) or {r['record_id'] for r in rows} != set(expected_by_id):
        raise ValueError('Missing, extra or duplicate calls: do not publish partial results')
    for row in rows:
        if row.get('error') or row.get('backend') != 'transformers_real_model' or row.get('phase') != phase:
            raise ValueError('Failed or non-final call found')
        original = expected_by_id[row['record_id']]
        if any(row[k] != v for k, v in original.items()):
            raise ValueError('Stimulus or ground truth differs from frozen data')
        if row['model_revision'] != frozen['model_lock']['revision']:
            raise ValueError('Mixed model checkpoints')
        if score(row['answer'], row['expected']) != row['correct']:
            raise ValueError('Stored correctness differs from frozen scoring rule')

def bar_svg(path, title, values, ylabel, ymin=0, ymax=100):
    # Standalone vector figures require no plotting dependencies.
    width, height = 1120, 600
    left, right, top, bottom = 90, 45, 75, 150
    w, h = width-left-right, height-top-bottom
    def y(v): return top+h-(v-ymin)/(ymax-ymin)*h
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<style>text{font-family:Arial,sans-serif;fill:#1e293b;font-size:14px}</style>',
             f'<text x="{left}" y="35" font-size="22">{html.escape(title)}</text>',
             f'<text x="20" y="60">{html.escape(ylabel)}</text>']
    for tick in range(0, 101, 20):
        parts += [f'<line x1="{left}" y1="{y(tick)}" x2="{width-right}" y2="{y(tick)}" stroke="#d9e1e8"/>',
                  f'<text x="{left-35}" y="{y(tick)+5}">{tick}</text>']
    slot = w / max(len(values), 1)
    for i, (label, value, lo, hi) in enumerate(values):
        x = left + slot*i + slot*.2
        bw = slot*.6
        parts.append(f'<rect x="{x}" y="{y(value)}" width="{bw}" height="{y(0)-y(value)}" fill="#2563a5"/>')
        mid = x + bw/2
        if lo is not None:
            parts += [f'<line x1="{mid}" y1="{y(lo)}" x2="{mid}" y2="{y(hi)}" stroke="#111827" stroke-width="2"/>',
                      f'<line x1="{mid-7}" y1="{y(lo)}" x2="{mid+7}" y2="{y(lo)}" stroke="#111827"/>',
                      f'<line x1="{mid-7}" y1="{y(hi)}" x2="{mid+7}" y2="{y(hi)}" stroke="#111827"/>']
        parts += [f'<text x="{mid}" y="{max(top+12,y(hi if hi is not None else value)-10)}" text-anchor="middle">{value:.1f}</text>',
                  f'<text transform="translate({mid},{top+h+24}) rotate(30)" text-anchor="start">{html.escape(label)}</text>']
    parts.append('</svg>')
    Path(path).write_text('\n'.join(parts), encoding='utf-8')

def sensitivity_svg(path,summaries):
    lookup={r['condition']:r for r in summaries}
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" viewBox="0 0 1000 560">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<style>text{font-family:Arial,sans-serif;fill:#1e293b;font-size:16px}</style>',
           '<text x="75" y="35" font-size="22">Sensitivity to distractor quantity and type</text>',
           '<text x="75" y="60">Accuracy % with 95% fact-cluster bootstrap intervals</text>']
    def x(k):return 100+k/16*760
    def y(v):return 450-v/100*280
    for tick in range(0,101,20):
        parts.extend([f'<line x1="100" y1="{y(tick)}" x2="860" y2="{y(tick)}" stroke="#d9e1e8"/>',
                      f'<text x="60" y="{y(tick)+5}">{tick}</text>'])
    for k in [0,4,16]:parts.append(f'<text x="{x(k)}" y="485" text-anchor="middle">{k}</text>')
    parts.append('<text x="380" y="530">Number of distractor facts</text>')
    for series,color,offset in [('irrelevant','#2563a5',-4),('similar','#b94b31',4)]:
        points=[]
        for k in [0,4,16]:
            r=lookup['clean' if k==0 else f'{series}_{k}'];xx=x(k)+offset;yy=y(r['accuracy_pct'])
            points.append(f'{xx},{yy}')
            parts.extend([f'<line x1="{xx}" y1="{y(r["ci95_low_pct"])}" x2="{xx}" y2="{y(r["ci95_high_pct"])}" stroke="{color}" stroke-width="2"/>',
                          f'<circle cx="{xx}" cy="{yy}" r="5" fill="{color}"/>'])
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3"/>')
        yy=85 if series=='irrelevant' else 110
        parts.append(f'<text x="680" y="{yy}" style="fill:{color}">{series} distractors</text>')
    parts.append('</svg>');Path(path).write_text('\n'.join(parts),encoding='utf-8')

def confusion_svg(path,counts):
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="740" height="510" viewBox="0 0 740 510">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<style>text{font-family:Arial,sans-serif;fill:#1e293b;font-size:17px}</style>',
           '<text x="35" y="35" font-size="22">Answerability confusion counts</text>',
           '<text x="35" y="65">Counts are repeated calls; an answer can still name the wrong city.</text>',
           '<text x="285" y="120">Model abstained or empty</text>',
           '<text x="520" y="120">Model answered</text>']
    for i,present in enumerate([False,True]):
        parts.append(f'<text x="20" y="{210+i*140}">Target {"present" if present else "absent"}</text>')
        for j,response in enumerate([False,True]):
            xx=250+j*220;yy=145+i*140
            parts.extend([f'<rect x="{xx}" y="{yy}" width="210" height="130" fill="{("#e5eff8" if present==response else "#f8eae6")}" stroke="#94a3b8"/>',
                          f'<text x="{xx+105}" y="{yy+75}" text-anchor="middle" font-size="30">{counts.get((present,response),0)}</text>'])
    parts.append('</svg>');Path(path).write_text('\n'.join(parts),encoding='utf-8')

def run_analysis(run_directory=None, reproduction=False):
    config = read_json(ROOT / 'config/experiment.json')
    frozen = assert_frozen(strict_environment=False) if reproduction else assert_frozen()
    run_directory = Path(run_directory) if run_directory else ROOT / 'results/final'
    raw_path = run_directory / 'raw.jsonl'
    rows = read_jsonl(raw_path)
    metadata = read_json(run_directory / 'metadata.json')
    validate_logs(rows, read_jsonl(ROOT / 'data/test.jsonl'), metadata, frozen, phase='reproduction' if reproduction else 'final')
    completion = read_json(run_directory / 'completion.json')
    if completion['raw_sha256'] != sha256(raw_path) or completion['run_status'] != 'complete':
        raise ValueError('Run incomplete or raw log changed after completion')
    out = run_directory / 'analysis' if reproduction else ROOT / 'results/analysis'
    out.mkdir(parents=True, exist_ok=True)
    by_condition = defaultdict(list)
    for r in rows: by_condition[r['condition']].append(r)
    summaries, per_seed, fact_scores = [], [], {}
    rng = random.Random(config['analysis_seed'])
    for condition in config['conditions']:
        group = by_condition[condition]
        fact_groups = defaultdict(list)
        for r in group: fact_groups[r['fact_id']].append(score(r['answer'], r['city']))
        facts = {fid: statistics.mean(v) for fid, v in fact_groups.items()}
        fact_scores[condition] = facts
        vals = list(facts.values())
        boots = [statistics.mean(rng.choices(vals, k=len(vals))) for _ in range(config['bootstrap_samples'])]
        seed_accs = []
        for seed in config['context_seeds']:
            subset = [r for r in group if r['seed'] == seed]
            accuracy = statistics.mean(score(r['answer'], r['city']) for r in subset)
            seed_accs.append(accuracy)
            per_seed.append({'condition': condition, 'context_seed': seed, 'n': len(subset), 'accuracy_pct': accuracy*100})
        latency = [r['latency_seconds'] for r in group]
        summaries.append({'condition': condition, 'calls': len(group), 'independent_facts': len(facts),
            'metric': 'gold-city recall strict EM',
            'accuracy_pct': statistics.mean(seed_accs)*100,
            'sd_across_context_seeds_pp': statistics.stdev(seed_accs)*100,
            'ci95_low_pct': percentile(boots,.025)*100, 'ci95_high_pct': percentile(boots,.975)*100,
            'median_latency_s': statistics.median(latency),
            'latency_p95_s': percentile(latency,.95),
            **quantile_diagnostics(latency),
            'mean_input_tokens': statistics.mean(r['input_tokens'] for r in group),
            'token_limit_hits': sum(r['reached_token_limit'] for r in group),
            'expected_response_accuracy_pct': statistics.mean(r['correct'] for r in group)*100,
            'unsupported_answer_rate_pct': statistics.mean(answered(r['answer']) for r in group)*100
                if condition in ['closed_book', 'target_absent_16'] else '',
            'correct_fact_recall_pct': statistics.mean(score(r['answer'], r['city']) for r in group)*100,
            'empty_response_count':sum(not normalize(r['answer']) for r in group),
        })
    write_csv(out / 'main_results.csv', summaries)
    write_csv(out / 'per_seed.csv', per_seed)
    contrasts = []
    for i, (a,b) in enumerate(config['planned_comparisons']):
        # H1 uses supported fact accuracy; H2 clean vs closed-book uses actual gold city recall,
        # NOT abstention accuracy, whose ground truth differs across these conditions.
        paired = defaultdict(dict)
        for r in rows:
            if r['condition'] in [a,b]:
                paired[r['fact_id']].setdefault(r['condition'], []).append(score(r['answer'],r['city']))
        differences = [statistics.mean(v[a])-statistics.mean(v[b]) for v in paired.values()]
        stats = paired_statistics(differences, config['bootstrap_samples'], config['permutation_samples'], config['analysis_seed']+i)
        contrasts.append({'condition_a': a, 'condition_b': b, 'metric': 'gold-city recall strict EM', **stats})
    for row, adjusted in zip(contrasts, holm([r['p_raw'] for r in contrasts])):
        row['p_holm'] = adjusted
    write_csv(out / 'paired_comparisons.csv', contrasts)
    subgroups = []
    for field in ['position', 'question_type']:
        groups = defaultdict(list)
        for r in rows:
            if r['target_present'] and (field != 'position' or r[field] != 'NA'):
                groups[(r['condition'],str(r[field]))].append(r)
        for (condition, level), group in sorted(groups.items()):
            subgroups.append({'factor': field,'level': level,'condition':condition,'calls':len(group),
                              'accuracy_pct':statistics.mean(r['correct'] for r in group)*100})
    write_csv(out / 'subgroups.csv', subgroups)
    # Confusion matrix for answer presence: abstain vs any substantive output.
    confusion = defaultdict(int)
    for r in rows:
        confusion[(bool(r['target_present']), answered(r['answer']))] += 1
    write_csv(out / 'answerability_confusion.csv', [{'target_present':a,'model_answered':b,'count':confusion.get((a,b),0)}
              for a in [False,True] for b in [False,True]])
    write_csv(out / 'audit_rows.csv', [{**{k:r[k] for k in ['record_id','fact_id','condition','seed','city','expected','answer','correct','prompt_sha256','model_revision']},'primary_gold_city_correct':score(r['answer'],r['city'])} for r in rows])
    failures = [r for r in rows if not r['correct']]
    random.Random(991).shuffle(failures)
    selected=review_selection(rows)
    selection_path=out/'error_selection.json'
    selection={'raw_sha256':sha256(raw_path),'cases':selected}
    if selection_path.exists() and read_json(selection_path)!=selection:
        raise ValueError('Raw results changed since manual review selection; preserve old review and create a versioned analysis.')
    write_json(selection_path,selection)
    review_path = out / 'error_review.csv'
    if not review_path.exists():
        write_csv(review_path,[{'record_id':r['record_id'],'condition':r['condition'],'question':r['question'],
            'context':r['context'],'expected':r['expected'],'answer':r['answer'],
            'rater_1':'','rater_2':'','final_category':'','explanation':''} for r in selected],
            ['record_id','condition','question','context','expected','answer','rater_1','rater_2','final_category','explanation'])
    successes=[]
    for condition in config['conditions']:
        candidates=[r for r in rows if r['condition']==condition and r['target_present'] and r['correct']]
        successes.extend(sorted(candidates,key=lambda r:r['record_id'])[:2])
    write_csv(out/'success_examples.csv',[
        {k:r[k] for k in ['record_id','condition','question','context','answer','expected']} for r in successes],
        ['record_id','condition','question','context','answer','expected'])
    # Plot abstention separately so it cannot be mistaken for unknown-fact knowledge.
    factual = [s for s in summaries if s['condition'] not in ['closed_book','target_absent_16']]
    bar_svg(out/'figure_1_accuracy.svg','Factual accuracy and closed-book baseline',
            [(s['condition'],s['accuracy_pct'],s['ci95_low_pct'],s['ci95_high_pct']) for s in summaries if s['condition']!='target_absent_16'],
            'Accuracy %; 95% bootstrap CI over facts')
    sensitivity_svg(out/'figure_2_noise.svg',summaries)
    pos = sorted([s for s in subgroups if s['factor']=='position' and s['condition']=='similar_16'],key=lambda s:['first','middle','last'].index(s['level']))
    bar_svg(out/'figure_3_position.svg','Target position in similar_16 context',
            [(s['level'],s['accuracy_pct'],None,None) for s in pos], 'Accuracy %; descriptive subgroup result')
    confusion_svg(out/'figure_4_answerability.svg',confusion)
    write_json(out/'analysis_diagnostics.json',{
        'all_planned_calls_and_pairs_complete':True,
        'cluster_unit':'fact_id','n_fact_clusters':len({r['fact_id'] for r in rows}),
        'repeated_calls_are_not_independent':True,
        'normality_test_required':False,
        'test_assumption':'Paired sign-flip exchangeability under the null; no normality assumption',
        'causal_limits':['Clean/noise confounds context length and content','Type templates may differ in token length'],
        'context_token_counts_reported':True,'observed_model_failures_excluded':False})
    decisions = []
    for i,r in enumerate(contrasts):
        desired = r['difference_pp'] < 0 if i in [0,2] else r['difference_pp'] > 0
        supported = desired and r['p_holm'] < .05
        decisions.append({'hypothesis':f'H{i+1}', 'status':'supported' if supported else 'not supported by preregistered test',
                          'evidence':'paired_comparisons.csv', 'condition_a':r['condition_a'],'condition_b':r['condition_b'],
                          'difference_pp':r['difference_pp'],'ci95_low_pp':r['paired_ci_low_pp'],'ci95_high_pp':r['paired_ci_high_pp'],'p_holm':r['p_holm']})
    write_csv(out/'hypothesis_decisions.csv',decisions)
    write_csv(out/'objective_evidence.csv',[
        {'objective':1,'evidence':'prior_work/data/mechanism_map.csv; final metadata','scope':'Literature mechanisms and fixed-weight context use; no new training'},
        {'objective':2,'evidence':'prior_work/recomputed/summary.json; data/manifest.json','scope':'Newly supplied synthetic facts; common/rare direct contrasts remain missing'},
        {'objective':3,'evidence':'prior_work/recomputed/comparisons.csv','scope':'14 recomputed published contrasts; 3 SFT contrasts qualified; not new Qwen FT results'},
        {'objective':4,'evidence':'main_results.csv; paired_comparisons.csv; subgroups.csv; human error review','scope':'New context-quality evidence, with literature-only evidence on training repetition'},
        {'objective':5,'evidence':'analysis_diagnostics.json; provenance.json; completed Discussion','scope':'Bounded interpretation; limitations and contradictions retained'}])
    (out/'figure_captions.txt').write_text(
        'Figure 1. Gold-city exact-match accuracy by condition; 95% fact-cluster bootstrap intervals. Source: main_results.csv.\n'
        'Figure 2. Sensitivity to distractor count and type; clean condition supplies the 0-distractor reference. Source: main_results.csv.\n'
        'Figure 3. Descriptive target-position results under similar_16; distractor samples also change across context seeds. Source: subgroups.csv.\n'
        'Figure 4. Answerability confusion counts; empty responses count as no substantive answer, not correct abstentions. Source: answerability_confusion.csv.\n',encoding='utf-8')
    write_json(out/'provenance.json', {'raw_sha256':sha256(raw_path),'freeze_sha256':sha256(ROOT/'freeze/freeze.json'),
         'all_expected_calls_present':True,'failures':len(failures),'manual_review_required':len(selected),
         'uncertainty_unit':'fact; all three context-seed outcomes resampled together',
         'limitations':['Single small instruction-tuned model; synthetic English country/city task',
                        'Context seeds vary distractor choice/position, not model-training randomness',
                        'Clean vs noisy changes length and distraction together; type contrasts approximately length-matched',
                        'No real retriever and no fine-tuning; no claims of permanent knowledge acquisition',
                        'Human error coding and independent reproduction still required']})
    lines=['# Automatically computed results\n', 'Real final inference only. Complete the manual Discussion and error review.\n']
    for s in summaries:
        lines.append(f"- {s['condition']}: {s['accuracy_pct']:.2f}% {s['metric']}; SD {s['sd_across_context_seeds_pp']:.2f} pp; CI [{s['ci95_low_pct']:.2f}, {s['ci95_high_pct']:.2f}].")
    lines += ['\nPrimary contrast: similar_16 minus clean; see paired_comparisons.csv.',
              'Error categories require manual coding; do not claim Appendix B is completed yet.']
    (out/'RESULTS_TO_VERIFY.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Computed complete results. Manually review error_review.csv and write Discussion.')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reproduction-id')
    args=parser.parse_args()
    if args.reproduction_id:
        if not args.reproduction_id.replace('_','').replace('-','').isalnum(): parser.error('Invalid reproduction ID')
        run_analysis(ROOT/'results/reproduction'/args.reproduction_id,reproduction=True)
    else: run_analysis()
