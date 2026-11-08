"""Preserve the chosen checkpoint and record the actual execution environment."""
import argparse
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, environment, read_json, utc_now, write_json

def chosen_revision(model_id, existing, resolve):
    if existing:
        if existing['model_id'] != model_id:
            raise ValueError('Model ID differs from the lock; declare a design change first.')
        revision = existing['revision']
    else:
        revision = resolve(model_id)
    if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
        raise ValueError('Expected an immutable 40-character checkpoint SHA')
    return revision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Download the exact locked snapshot if not cached')
    args = parser.parse_args()
    if (ROOT / 'freeze/freeze.json').exists():
        raise SystemExit('Already frozen; preparation cannot overwrite metadata.')
    from huggingface_hub import model_info, snapshot_download
    import torch
    import transformers
    config = read_json(ROOT / 'config/experiment.json')
    path = ROOT / 'config/model_lock.json'
    existing = read_json(path) if path.exists() else None
    revision = chosen_revision(config['model_id'], existing, lambda name: model_info(name).sha)
    if args.download:
        snapshot_download(config['model_id'], revision=revision,
                          allow_patterns=['*.json', '*.safetensors', '*.txt', '*.model', '*.tiktoken'])
    write_json(ROOT / 'config/model_lock.json', {
        'model_id': config['model_id'], 'revision': revision,
        'resolved_at': existing['resolved_at'] if existing else utc_now(), 'environment': environment(),
    })
    lock = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    (ROOT / 'environment.lock.txt').write_text(lock, encoding='utf-8')
    print('Checkpoint preserved:', revision)
    print('Configured runtime:', read_json(ROOT / 'config/runtime.json'))
    print('Environment recorded. Run check and pilot before final inference.')
    print('After code changes, retain the original Appendix A and document docs/IMPLEMENTATION_UPDATE.json as a deviation.')

if __name__ == '__main__':
    main()
