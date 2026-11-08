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
from common import ROOT, assert_frozen, environment, read_json, read_jsonl, score, sha256, utc_now, write_json

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['pilot', 'final', 'reproduction'], required=True)
    p.add_argument('--run-id', help='Required for independent reproduction; creates separate logs')
    p.add_argument('--limit-facts', type=int, default=3, help='Pilot only; ignored for final')
    a = p.parse_args()
    config = read_json(ROOT / 'config/experiment.json')
    if a.phase=='reproduction' and (not a.run_id or not a.run_id.replace('_','').replace('-','').isalnum()):
        p.error('Reproduction requires a simple --run-id; it never overwrites final logs.')
    frozen = assert_frozen(strict_environment=False) if a.phase=='reproduction' else (assert_frozen() if a.phase == 'final' else None)
    lock = frozen['model_lock'] if frozen else read_json(ROOT / 'config/model_lock.json')
    if lock['model_id'] != config['model_id']:
        raise ValueError('Checkpoint/config mismatch')
    split = 'dev' if a.phase=='pilot' else 'test'
    rows = read_jsonl(ROOT / f'data/{split}.jsonl')
    if a.phase == 'pilot':
        ids = sorted({r['fact_id'] for r in rows})[:a.limit_facts]
        rows = [r for r in rows if r['fact_id'] in ids]
    out = ROOT / 'results' / a.phase
    if a.phase=='reproduction': out=out/a.run_id
    out.mkdir(parents=True, exist_ok=True)
    metadata_path = out / 'metadata.json'
    if metadata_path.exists():
        metadata = read_json(metadata_path)
        if metadata['model_lock']['revision'] != lock['revision'] or metadata['input_sha256'] != sha256(ROOT / f'data/{split}.jsonl'):
            raise ValueError('Cannot resume different model/data in same run directory')
        if metadata['source_hashes'] != (frozen['source_hashes'] if frozen else {}):
            raise ValueError('Source changed since run began')
        if metadata.get('config') != config or metadata['planned_calls'] != len(rows):
            raise ValueError('Configuration or pilot subset changed; preserve the old log and use a separate project copy.')
    if not rows: raise ValueError('No planned calls')
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    dtype = torch.float16 if device == 'cuda' else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(lock['model_id'], revision=lock['revision'])
    model = AutoModelForCausalLM.from_pretrained(lock['model_id'], revision=lock['revision'],
                                              torch_dtype=dtype, attn_implementation='eager')
    model.to(device).eval()
    if metadata_path.exists():
        previous = read_json(metadata_path)
        current_hardware = torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'
        if previous['hardware'] != current_hardware or previous['dtype'] != str(dtype):
            raise ValueError('Cannot mix hardware/precision in a resumed run; preserve original logs and document a separate rerun')
    metadata = {
        'backend': 'transformers_real_model', 'phase': a.phase, 'split': split,
        'config':config,
        'started_at': utc_now(), 'model_lock': lock, 'environment': environment(),
        'device': device, 'dtype': str(dtype),
        'hardware': torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU',
        'input_sha256': sha256(ROOT / f'data/{split}.jsonl'),
        'planned_calls': len(rows), 'source_hashes': frozen['source_hashes'] if frozen else {},
        'freeze_sha256': sha256(ROOT / 'freeze/freeze.json') if frozen else None,
        'reproduction_environment_comparison':{'original':frozen['environment'],'current':environment()} if a.phase=='reproduction' else None,
        'latency_note': 'Single-item generation; first generation is a discarded warm-up; timings depend on hardware/load',
    }
    if not metadata_path.exists():
        write_json(metadata_path, metadata)
    raw_path = out / 'raw.jsonl'
    existing = read_jsonl(raw_path) if raw_path.exists() else []
    done = {r['record_id'] for r in existing}
    if len(done) != len(existing):
        raise ValueError('Duplicate records in existing log')
    if not done.issubset({r['record_id'] for r in rows}):
        raise ValueError('Unplanned records found in resumed log')
    if any(r.get('error') for r in existing):
        raise ValueError('Earlier failures are preserved. Record deviation and use a separate versioned run for rerun.')
    random.Random(952).shuffle(rows)  # interleave conditions; same schedule on reproduction
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
                if warmup: raise
            if not warmup:
                with raw_path.open('a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                    f.flush()
                if len(done) % 50 == 0:
                    print(f'{len(done)} previous/completed calls; recording {row["record_id"]}', flush=True)
                done.add(row['record_id'])
                if entry['error']:
                    raise RuntimeError('Call failed and was logged. Do not silently drop it.')
    complete = read_jsonl(raw_path)
    write_json(out / 'completion.json', {'finished_at': utc_now(), 'recorded_calls': len(complete),
        'planned_calls': len(rows), 'raw_sha256': sha256(raw_path),
        'run_status': 'complete' if len(complete) == len(rows) else 'incomplete'})
    print('Finished. Pilot outputs are not final evidence.' if a.phase == 'pilot' else ('Reproduction calls recorded; analyze using --reproduction-id.' if a.phase=='reproduction' else 'Final calls recorded; run analyze.py.'))

if __name__ == '__main__':
    main()
