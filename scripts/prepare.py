"""Resolve immutable checkpoint and record environment before protocol upload."""
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, environment, read_json, utc_now, write_json

def main():
    if (ROOT / 'freeze/freeze.json').exists():
        raise SystemExit('Already frozen; preparation cannot overwrite metadata.')
    from huggingface_hub import model_info
    import torch
    import transformers
    config = read_json(ROOT / 'config/experiment.json')
    revision = model_info(config['model_id']).sha
    if not revision or len(revision) != 40:
        raise ValueError('Expected immutable 40-character checkpoint commit')
    write_json(ROOT / 'config/model_lock.json', {
        'model_id': config['model_id'], 'revision': revision,
        'resolved_at': utc_now(), 'environment': environment(),
    })
    lock = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    (ROOT / 'environment.lock.txt').write_text(lock, encoding='utf-8')
    print('Checkpoint:', revision)
    print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU (much slower)')
    print('Upload the completed Appendix A and config/model_lock.json with the dataset manifest BEFORE final runs.')

if __name__ == '__main__':
    main()
