"""Preflight and progress without test inference or model weight loading."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, assert_frozen, environment, read_json, read_jsonl, sha256


def inspect():
    checks = []
    def check(label, action):
        try:
            detail = action()
            checks.append({'check':label,'ok':True,'detail':str(detail)})
        except Exception as exc:
            checks.append({'check':label,'ok':False,'detail':str(exc)})
    config = read_json(ROOT/'config/experiment.json')
    lock = read_json(ROOT/'config/model_lock.json')
    def data():
        manifest = read_json(ROOT/'data/manifest.json')
        for filename, digest in manifest['files'].items():
            if sha256(ROOT/'data'/filename) != digest:
                raise ValueError('Dataset hash mismatch: '+filename)
        for split,count in [('dev',config['dev_facts']),('test',config['test_facts'])]:
            rows = read_jsonl(ROOT/f'data/{split}.jsonl')
            if len(rows) != count*len(config['conditions'])*len(config['context_seeds']):
                raise ValueError('Incorrect planned call count: '+split)
        return '30 dev facts / 120 test facts; 2520 final calls; hashes match'
    def software():
        actual = environment()
        if actual != lock['environment']:
            raise ValueError('Environment differs from model_lock. Before freezing run prepare.py in this Python environment.')
        return actual['python'].split()[0]+'; package versions match lock'
    def runtime():
        import torch
        from common import runtime_profile
        return runtime_profile(torch)
    def cache():
        from huggingface_hub import snapshot_download
        folder = Path(snapshot_download(lock['model_id'],revision=lock['revision'],local_files_only=True))
        if not (folder/'config.json').is_file() or not (folder/'tokenizer_config.json').is_file():
            raise ValueError('Model/tokenizer configuration missing. Run prepare.py --download.')
        index = folder/'model.safetensors.index.json'
        weights = set(read_json(index)['weight_map'].values()) if index.exists() else {'model.safetensors'}
        if not all((folder/name).is_file() for name in weights):
            raise ValueError('Model weights incomplete. Run prepare.py --download.')
        return str(folder)
    check('dataset',data)
    check('environment',software)
    check('runtime',runtime)
    check('model_cache',cache)
    frozen = (ROOT/'freeze/freeze.json').exists()
    if frozen:
        check('freeze',lambda: (assert_frozen() and 'Source, model, environment and receipt match'))
    progress = {}
    for phase in ('pilot','final','reproduction'):
        base = ROOT/'results'/phase
        if base.exists():
            for raw in sorted(base.rglob('raw.jsonl')):
                try:
                    rows = read_jsonl(raw)
                    meta = read_json(raw.parent/'metadata.json')
                    progress[raw.parent.relative_to(ROOT).as_posix()] = {
                        'saved':len(rows),'planned':meta['planned_calls'],
                        'technical_errors':sum(bool(r.get('error')) for r in rows)}
                except Exception as exc:
                    progress[raw.parent.relative_to(ROOT).as_posix()] = {'error':str(exc)}
    return {'checks':checks,'freeze_recorded':frozen,'progress':progress,
            'ready_for_final':frozen and all(c['ok'] for c in checks),
            'next_step':'Run final' if frozen else 'Pilot, then freeze using the actual Appendix A and Moodle receipt'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--require-final-ready',action='store_true')
    args=parser.parse_args()
    result=inspect()
    if args.json:
        print(json.dumps(result,indent=2,ensure_ascii=False))
    else:
        for check in result['checks']:
            print(('OK   ' if check['ok'] else 'FAIL ')+check['check']+': '+check['detail'])
        print('Freeze:', 'recorded' if result['freeze_recorded'] else 'not recorded; final is blocked')
        for path,progress in result['progress'].items():
            print(path+': '+str(progress))
        print('Next:',result['next_step'])
    if any(not c['ok'] for c in result['checks']) or (args.require_final_ready and not result['ready_for_final']):
        raise SystemExit(1)


if __name__=='__main__': main()
