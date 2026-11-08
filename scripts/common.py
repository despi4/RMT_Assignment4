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
    if strict_environment and (frozen['environment']['packages'] != current['packages'] or frozen['environment']['python'] != current['python']):
        raise ValueError('Environment differs from the frozen environment. Use original environment or declare deviation.')
    return frozen
