"""Real local inference only. Pilot uses dev; final requires protocol freeze."""
import argparse
import hashlib
import importlib.metadata
import json
import random
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ROOT, assert_frozen, environment, read_json, read_jsonl, score, sha256,
                    utc_now, write_json, source_hashes, validate_saved_calls, runtime_profile, exclusive_run)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['pilot', 'final', 'reproduction'], required=True)
    p.add_argument('--run-id', help='Pilot/reproduction run folder; mandatory for reproduction')
    p.add_argument('--limit-facts', type=int, help='Pilot only; default 3 dev facts')
    p.add_argument('--device', choices=['cpu','cuda'], help='Defaults to config/runtime.json; final must match that file')
    a = p.parse_args()
    if a.run_id and (not a.run_id.isascii() or not a.run_id.replace('_','').replace('-','').isalnum()):
        p.error('Run ID must contain only ASCII letters, digits, underscores or hyphens.')
    if a.phase == 'final' and a.run_id:
        p.error('Final runs use results/final; preserve the frozen run.')
    if a.phase == 'reproduction' and not a.run_id:
        p.error('Reproduction requires --run-id.')
    if a.limit_facts is not None and (a.phase != 'pilot' or a.limit_facts < 1):
        p.error('--limit-facts must be positive and is allowed only for pilot.')
    out = ROOT / 'results' / a.phase
    if a.run_id:
        out = out / a.run_id
    with exclusive_run(out):
        try:
            execute(a, out)
        except KeyboardInterrupt:
            write_json(out/'interruption.json', {'interrupted_at':utc_now(),
                'note':'Stopped by user; completed rows retained. Resume using the same command.'})
            print('\nInterrupted. Completed responses are saved; use the same command to resume.', flush=True)
            raise SystemExit(130)


def execute(a, out):
    config = read_json(ROOT / 'config/experiment.json')
    frozen = assert_frozen(strict_environment=False) if a.phase=='reproduction' else (assert_frozen() if a.phase == 'final' else None)
    lock = frozen['model_lock'] if frozen else read_json(ROOT / 'config/model_lock.json')
    if lock['model_id'] != config['model_id']:
        raise ValueError('Checkpoint/config mismatch')
    split = 'dev' if a.phase=='pilot' else 'test'
    rows = read_jsonl(ROOT / f'data/{split}.jsonl')
    if a.phase == 'pilot':
        ids = sorted({r['fact_id'] for r in rows})[:(a.limit_facts or 3)]
        rows = [r for r in rows if r['fact_id'] in ids]
    out.mkdir(parents=True, exist_ok=True)
    hashes = frozen['source_hashes'] if frozen else source_hashes()
    metadata_path = out / 'metadata.json'
    if metadata_path.exists():
        metadata = read_json(metadata_path)
        if metadata['model_lock']['revision'] != lock['revision'] or metadata['input_sha256'] != sha256(ROOT / f'data/{split}.jsonl'):
            raise ValueError('Cannot resume different model/data in same run directory')
        if metadata['source_hashes'] != hashes:
            raise ValueError('Source changed since run began')
        if metadata.get('config') != config or metadata['planned_calls'] != len(rows):
            raise ValueError('Configuration or pilot subset changed; preserve the old log and use a separate project copy.')
    if not rows: raise ValueError('No planned calls')
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    profile = runtime_profile(torch, a.device)
    if a.phase == 'final' and profile['device'] != read_json(ROOT/'config/runtime.json')['device']:
        raise ValueError('Final device must match the frozen runtime config.')
    device = profile['device']
    dtype = torch.float16 if device == 'cuda' else torch.float32
    if metadata_path.exists():
        previous = read_json(metadata_path)
        if previous.get('runtime_profile') != profile or previous['environment'] != environment():
            raise ValueError('Cannot mix hardware/precision in a resumed run; preserve original logs and document a separate rerun')
    metadata = {
        'backend': 'transformers_real_model', 'phase': a.phase, 'split': split,
        'config':config,
        'started_at': utc_now(), 'model_lock': lock, 'environment': environment(),
        'device': device, 'dtype': str(dtype),
        'hardware':profile['hardware'], 'runtime_profile':profile,
        'input_sha256': sha256(ROOT / f'data/{split}.jsonl'),
        'planned_calls': len(rows), 'source_hashes':hashes,
        'freeze_sha256': sha256(ROOT / 'freeze/freeze.json') if frozen else None,
        'reproduction_environment_comparison':{'original':frozen['environment'],'current':environment()} if a.phase=='reproduction' else None,
        'latency_note': 'Single-item generation; first generation is a discarded warm-up; timings depend on hardware/load',
    }
    raw_path = out / 'raw.jsonl'
    if raw_path.exists() and not metadata_path.exists():
        raise ValueError('Raw log has no metadata. Preserve it; do not attach new metadata to old answers.')
    existing = read_jsonl(raw_path) if raw_path.exists() else []
    done = validate_saved_calls(existing, rows, lock['revision'], a.phase)
    if len(done) == len(rows):
        completion_path = out/'completion.json'
        if completion_path.exists():
            completion = read_json(completion_path)
            if completion['raw_sha256'] != sha256(raw_path) or completion['run_status'] != 'complete':
                raise ValueError('Completed log changed; preserve and investigate instead of resealing it.')
        else:
            write_json(completion_path, {'finished_at':utc_now(), 'completion_recovered':True,
                'note':'All calls were present after interruption; this time records completion verification.',
                'recorded_calls':len(done),'planned_calls':len(rows),
                'raw_sha256':sha256(raw_path),'run_status':'complete'})
        print(f'All {len(done)} calls already recorded; no model calls made.')
        return
    print(f'Loading {lock["model_id"]} on {profile["hardware"]}; threads={profile["num_threads"]}',flush=True)
    tokenizer = AutoTokenizer.from_pretrained(lock['model_id'], revision=lock['revision'])
    model = AutoModelForCausalLM.from_pretrained(lock['model_id'], revision=lock['revision'],
                                              torch_dtype=dtype, attn_implementation=profile['attention'])
    model.to(device).eval()
    if not metadata_path.exists():
        write_json(metadata_path, metadata)
    random.Random(profile['schedule_seed']).shuffle(rows)
    started = time.perf_counter()
    initial_done = len(done)
    print(f'{a.phase}: {len(done)}/{len(rows)} already saved; {len(rows)-len(done)} remaining.',flush=True)
    with torch.inference_mode():
        for warmup, row in [(True, rows[0])] + [(False, r) for r in rows if r['record_id'] not in done]:
            torch.manual_seed(row['seed'])
            if device == 'cuda':
                torch.cuda.manual_seed_all(row['seed'])
            entry = {**row, 'backend': 'transformers_real_model', 'phase': a.phase,
                     'model_revision': lock['revision'], 'timestamp': utc_now(), 'error': ''}
            try:
                inputs = tokenizer.apply_chat_template([
                    {'role': 'system', 'content': config['system_prompt']},
                    {'role': 'user', 'content': row['prompt']},
                ], tokenize=True, add_generation_prompt=True, return_tensors='pt')
                length = inputs.shape[-1]
                if length > config['max_input_tokens']:
                    raise ValueError(f'Input {length} exceeds frozen limit; truncation prohibited')
                inputs = inputs.to(device)
                if device == 'cuda': torch.cuda.synchronize()
                start = time.perf_counter()
                outputs = model.generate(input_ids=inputs, attention_mask=torch.ones_like(inputs),
                    do_sample=False, max_new_tokens=config['max_new_tokens'],
                    pad_token_id=tokenizer.eos_token_id)
                if device == 'cuda': torch.cuda.synchronize()
                latency = time.perf_counter() - start
                tokens = outputs[0, length:].tolist()
                answer = tokenizer.decode(tokens, skip_special_tokens=True).strip()
                entry.update(answer=answer, generated_token_ids=tokens, input_tokens=length,
                             generated_tokens=len(tokens), latency_seconds=latency,
                             correct=score(answer, row['expected']),
                             contains_gold=int(row['city'].casefold() in answer.casefold()),
                             reached_token_limit=(len(tokens) == config['max_new_tokens']))
            except Exception as exc:
                entry['error'] = f'{type(exc).__name__}: {exc}'
                if warmup:
                    write_json(out/f'warmup_failure_{time.time_ns()}.json',entry)
                    raise
            if not warmup:
                with raw_path.open('a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                    f.flush()
                done.add(row['record_id'])
                if len(done) == initial_done + 1 or len(done) % 25 == 0 or len(done) == len(rows):
                    elapsed = time.perf_counter()-started
                    eta = elapsed/(len(done)-initial_done)*(len(rows)-len(done))
                    print(f'{len(done)}/{len(rows)} ({len(done)/len(rows):.1%}); remaining about {eta/60:.1f} min',flush=True)
                if entry['error']:
                    raise RuntimeError('Call failed and was logged. Do not silently drop it.')
    complete = read_jsonl(raw_path)
    validate_saved_calls(complete, rows, lock['revision'], a.phase)
    write_json(out / 'completion.json', {'finished_at': utc_now(), 'recorded_calls': len(complete),
        'planned_calls': len(rows), 'raw_sha256': sha256(raw_path),
        'run_status': 'complete' if len(complete) == len(rows) else 'incomplete'})
    print('Finished. Pilot outputs are not final evidence.' if a.phase == 'pilot' else ('Reproduction calls recorded; analyze using --reproduction-id.' if a.phase=='reproduction' else 'Final calls recorded; run analyze.py.'))

if __name__ == '__main__':
    main()
