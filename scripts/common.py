import csv
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def read_jsonl(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def normalize(text):
    # Frozen strict EM: only case, whitespace, Unicode and boundary punctuation.
    text = unicodedata.normalize('NFKC', text).strip().casefold()
    return re.sub(r'\s+', ' ', text).strip(' \t\r\n.!,;:\"\'`')

def score(answer, expected):
    return int(normalize(answer) == normalize(expected))

def answered(answer):
    text = normalize(answer)
    return bool(text) and text != 'unknown'

def quantile_diagnostics(values):
    import math
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('Latency must contain finite nonnegative measurements')
    def q(p):
        v = sorted(values); t = (len(v)-1)*p; i = int(t)
        return v[i] + (v[min(i+1,len(v)-1)]-v[i])*(t-i)
    return {'latency_q1_s':q(.25),'latency_q3_s':q(.75),'latency_iqr_s':q(.75)-q(.25)}

def source_hashes():
    paths = list((ROOT / 'scripts').glob('*.py'))
    paths += [ROOT / 'config/experiment.json', ROOT / 'requirements.txt', ROOT / 'docs/PROTOCOL.md']
    paths += [ROOT / 'data/dev.jsonl', ROOT / 'data/test.jsonl', ROOT / 'data/facts.json', ROOT / 'data/manifest.json']
    paths += [ROOT / 'config/runtime.json', ROOT / 'docs/IMPLEMENTATION_UPDATE.json',
              ROOT / 'requirements-cpu.txt', ROOT / 'experiment.ps1']
    if (ROOT/'environment.lock.txt').exists(): paths.append(ROOT/'environment.lock.txt')
    for relative in ['prior_work/pipeline.py','prior_work/data/results.csv','prior_work/CODEBOOK.md']:
        if (ROOT/relative).exists(): paths.append(ROOT/relative)
    return {p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted(paths)}

def environment():
    import importlib.metadata
    import platform
    import sys
    versions = {}
    for package in ['torch', 'transformers', 'huggingface-hub', 'safetensors', 'tokenizers', 'numpy']:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = 'NOT INSTALLED'
    return {'python': sys.version, 'platform': platform.platform(), 'packages': versions}

def assert_frozen(strict_environment=True):
    if not (ROOT / 'freeze/freeze.json').is_file():
        raise ValueError('Upload the completed protocol to Moodle and run freeze.py before final inference.')
    frozen = read_json(ROOT / 'freeze/freeze.json')
    if frozen['source_hashes'] != source_hashes():
        raise ValueError('Frozen code/config/data changed. Record deviation and freeze a new version BEFORE new final runs.')
    current = environment()
    if frozen['model_lock'] != read_json(ROOT / 'config/model_lock.json'):
        raise ValueError('Model lock changed since freeze. Restore the frozen file.')
    evidence = ROOT / 'freeze' / frozen['upload_evidence']
    if (strict_environment and not evidence.is_file()) or (evidence.is_file() and sha256(evidence) != frozen['upload_evidence_sha256']):
        raise ValueError('The private Moodle receipt is missing or changed. Restore it locally.')
    protocol = ROOT/'freeze'/frozen['protocol_document']
    if (strict_environment and not protocol.is_file()) or (protocol.is_file() and sha256(protocol) != frozen['protocol_sha256']):
        raise ValueError('The private copy of the uploaded protocol is missing or changed.')
    if strict_environment and (frozen['environment']['packages'] != current['packages'] or frozen['environment']['python'] != current['python']):
        raise ValueError('Environment differs from the frozen environment. Use original environment or declare deviation.')
    return frozen


def validate_saved_calls(rows, expected, revision, phase):
    """Check partial or complete saved evidence before resuming or analysing."""
    import math
    originals = {r['record_id']: r for r in expected}
    seen = set()
    for row in rows:
        rid = row.get('record_id')
        if rid in seen or rid not in originals:
            raise ValueError('Duplicate or unplanned saved call; preserve and inspect the raw log.')
        seen.add(rid)
        if row.get('error'):
            raise ValueError('A failed call is preserved in the log. Record a deviation before a separate rerun.')
        if row.get('backend') != 'transformers_real_model' or row.get('phase') != phase:
            raise ValueError('Saved call is not real inference for the requested phase.')
        if any(row.get(k) != v for k, v in originals[rid].items()):
            raise ValueError('Saved stimulus differs from the frozen dataset.')
        if row.get('model_revision') != revision:
            raise ValueError('Saved call uses a different model revision.')
        if not isinstance(row.get('answer'), str) or row.get('correct') != score(row['answer'], row['expected']):
            raise ValueError('Saved answer/score is invalid.')
        tokens = row.get('generated_token_ids')
        if not isinstance(tokens, list) or any(type(t) is not int or t < 0 for t in tokens):
            raise ValueError('Missing or invalid generated token evidence.')
        if type(row.get('generated_tokens')) is not int or row['generated_tokens'] != len(tokens):
            raise ValueError('Generated token count differs from the saved token IDs.')
        if type(row.get('input_tokens')) is not int or row['input_tokens'] <= 0:
            raise ValueError('Missing or invalid input token count.')
        latency = row.get('latency_seconds')
        if not isinstance(latency, (int, float)) or not math.isfinite(latency) or latency < 0:
            raise ValueError('Missing or invalid latency.')
        if type(row.get('reached_token_limit')) is not bool:
            raise ValueError('Missing output-limit diagnostic.')
    return seen


def runtime_profile(torch, requested_device=None):
    import platform
    import os
    settings = read_json(ROOT / 'config/runtime.json')
    device = requested_device or settings['device']
    if device not in ('cpu', 'cuda') or type(settings['num_threads']) is not int or settings['num_threads'] < 1:
        raise ValueError('Runtime requires cpu/cuda and a positive integer thread count.')
    if device == 'cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA requested but unavailable; do not silently switch devices.')
    torch.set_num_threads(settings['num_threads'])
    cpu = platform.processor() or platform.machine()
    if os.name == 'nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            cpu = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
    return {'device':device, 'dtype':'torch.float32' if device == 'cpu' else 'torch.float16',
            'hardware':cpu if device == 'cpu' else torch.cuda.get_device_name(0),
            'num_threads':torch.get_num_threads(), 'attention':settings['attention'],
            'schedule_seed':settings['schedule_seed']}


from contextlib import contextmanager


@contextmanager
def exclusive_run(directory):
    """OS file lock is released on interruption; the empty lock file can remain."""
    import os
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.run.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('This run is already active in another process. Do not start it twice.') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
