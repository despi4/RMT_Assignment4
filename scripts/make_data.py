"""Generate synthetic stimuli; this creates data, not model results."""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_json, sha256, write_json

QUESTIONS = [
    'What is the capital city of {country}?',
    'Which city serves as the capital of {country}?',
    'Name the capital associated with the country {country}.',
]

def make_facts(n, seed, split):
    rng = random.Random(seed)
    starts = ['Ve', 'Sa', 'Lo', 'Mi', 'Na', 'Te', 'Ko', 'Ru', 'Fa', 'Di', 'Ba', 'Zu']
    middles = ['ra', 'li', 'mo', 'ne', 'ta', 'vi', 'su', 'pa', 'ko', 'di', 'ze', 'fu']
    ends = ['na', 'ra', 'lo', 'mi', 'sa', 'te', 'vi', 'po', 'ku', 'de', 'za', 'fo']
    cities = [a+b+c for a in starts for b in middles for c in ends]
    rng.shuffle(cities)
    # Prefixes also separate dev and test names, so no gold test associations occur in dev prompts.
    prefix = 'D' if split == 'dev' else 'T'
    codes = rng.sample(range(1000, 9999), n)
    return [{'fact_id': f'{split}-{i:03d}', 'country': f'Veloria-{prefix}{code}',
             'city': cities[i], 'split': split, 'question_type': i % 3}
            for i, code in enumerate(codes)]

def build_records(facts, config):
    records = []
    for i, fact in enumerate(facts):
        pool = [f for f in facts if f['fact_id'] != fact['fact_id']]
        for seed_index, seed in enumerate(config['context_seeds']):
            rng = random.Random(f'{config["dataset_seed"]}:{fact["fact_id"]}:{seed}')
            others = rng.sample(pool, 16)
            position = ['first', 'middle', 'last'][(i + seed_index) % 3]
            target = f'The capital city of {fact["country"]} is {fact["city"]}.'
            for condition in config['conditions']:
                k = 16 if condition.endswith('_16') else (4 if condition.endswith('_4') else 0)
                similar = condition.startswith('similar') or condition == 'target_absent_16'
                predicate = 'capital city' if similar else 'central lake'
                selected = others[:k]
                distractors = [f'The {predicate} of {f["country"]} is {f["city"]}.' for f in selected]
                target_present = condition not in ['closed_book', 'target_absent_16']
                lines = list(distractors)
                idx = 0 if position == 'first' else (k // 2 if position == 'middle' else k)
                if target_present:
                    lines.insert(idx, target)
                context = '\n'.join(lines) if lines else '(No context supplied.)'
                question = QUESTIONS[fact['question_type']].format(country=fact['country'])
                prompt = f'Context:\n{context}\n\nQuestion: {question}\nAnswer:'
                records.append({
                    'record_id': f'{fact["fact_id"]}-s{seed}-{condition}',
                    'fact_id': fact['fact_id'], 'split': fact['split'], 'seed': seed,
                    'condition': condition, 'question_type': fact['question_type'],
                    'country': fact['country'], 'city': fact['city'],
                    'target_present': target_present,
                    'expected': fact['city'] if target_present else 'UNKNOWN',
                    'position': position if k and target_present else 'NA',
                    'distractor_count': k, 'distractor_answers': [f['city'] for f in selected],
                    'question': question, 'context': context, 'prompt': prompt,
                    'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                })
    return records

def validate(dev, test, config):
    assert not ({x['fact_id'] for x in dev} & {x['fact_id'] for x in test})
    assert not ({x['country'] for x in dev} & {x['country'] for x in test})
    for rows, count in [(dev, config['dev_facts']), (test, config['test_facts'])]:
        assert len(rows) == count * len(config['conditions']) * len(config['context_seeds'])
        assert len({r['record_id'] for r in rows}) == len(rows)
        for row in rows:
            if row['target_present']:
                assert row['city'] in row['context']
            else:
                assert row['city'] not in row['context']
            assert row['city'] not in row['distractor_answers']

def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    if (ROOT / 'freeze/freeze.json').exists():
        raise SystemExit('Data are frozen. Do not regenerate without declaring a protocol deviation.')
    config = read_json(ROOT / 'config/experiment.json')
    dev_facts = make_facts(config['dev_facts'], config['dataset_seed'], 'dev')
    candidates = make_facts(config['test_facts'] + config['dev_facts'], config['dataset_seed'] + 1, 'test')
    # Disjoint associations without an artificial test-only city suffix/distribution shift.
    used_cities = {f['city'] for f in dev_facts}
    available_cities = [f['city'] for f in candidates if f['city'] not in used_cities]
    test_facts = [{**x, 'city': available_cities[i]} for i, x in enumerate(candidates[:config['test_facts']])]
    dev, test = build_records(dev_facts, config), build_records(test_facts, config)
    validate(dev, test, config)
    (ROOT / 'data').mkdir(exist_ok=True)
    for split, rows in [('dev', dev), ('test', test)]:
        path = ROOT / f'data/{split}.jsonl'
        path.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    write_json(ROOT / 'data/facts.json', dev_facts + test_facts)
    write_json(ROOT / 'data/manifest.json', {
        'version': '1.0', 'dataset_seed': config['dataset_seed'],
        'dev_facts': len(dev_facts), 'test_facts': len(test_facts),
        'dev_calls': len(dev), 'final_calls': len(test),
        'files': {f'{s}.jsonl': sha256(ROOT / f'data/{s}.jsonl') for s in ['dev', 'test']},
        'origin': 'Programmatically created fictional stimuli, not observed LLM outcomes',
    })
    print(f'Generated {len(dev_facts)} dev facts and {len(test_facts)} held-out test facts; {len(test)} final calls.')

if __name__ == '__main__':
    main()
