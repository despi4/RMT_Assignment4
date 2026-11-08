"""Record a student-declared Moodle upload; not independent verification of Moodle."""
import argparse
from datetime import datetime, timezone
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, environment, read_json, sha256, source_hashes, utc_now, write_json, runtime_profile

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--uploaded-at', required=True, help='Actual Moodle upload ISO timestamp with timezone')
    p.add_argument('--evidence', required=True, help='Path to Moodle receipt/screenshot/PDF saved by student')
    p.add_argument('--declarant', required=True, help='Student who declares the upload')
    p.add_argument('--protocol', required=True, help='Exact Appendix A document that was uploaded')
    a = p.parse_args()
    stamp = datetime.fromisoformat(a.uploaded_at)
    if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
        raise ValueError('Use an actual past upload timestamp including timezone')
    if not Path(a.evidence).is_file():
        raise ValueError('Save the real Moodle receipt first')
    if not Path(a.protocol).is_file():
        raise ValueError('Supply the exact uploaded Appendix A document')
    if not a.declarant.strip():
        raise ValueError('Name the actual declarant')
    if (ROOT / 'freeze/freeze.json').exists():
        raise ValueError('Already frozen. Preserve this freeze; record deviations rather than overwrite it.')
    if (ROOT/'results/final/raw.jsonl').exists():
        raise ValueError('Final outcomes already exist; a prospective freeze cannot be created afterwards.')
    lock = read_json(ROOT / 'config/model_lock.json')
    if lock['environment'] != environment():
        raise ValueError('Environment changed since preparation')
    import torch
    profile = runtime_profile(torch)
    evidence_dir = ROOT / 'freeze'
    evidence_dir.mkdir(exist_ok=True)
    evidence = evidence_dir / ('moodle_upload' + Path(a.evidence).suffix)
    evidence.write_bytes(Path(a.evidence).read_bytes())
    protocol = evidence_dir / ('protocol_document' + Path(a.protocol).suffix)
    protocol.write_bytes(Path(a.protocol).read_bytes())
    write_json(evidence_dir / 'freeze.json', {
        'frozen_at': utc_now(), 'moodle_uploaded_at': stamp.isoformat(),
        'upload_evidence': evidence.name, 'upload_evidence_sha256': sha256(evidence),
        'declarant': a.declarant, 'evidence_status': 'Student declaration; instructor verifies Moodle timestamp',
        'protocol_document':protocol.name, 'protocol_sha256':sha256(protocol),
        'implementation_update':read_json(ROOT/'docs/IMPLEMENTATION_UPDATE.json'),
        'runtime_profile':profile,
        'source_hashes': source_hashes(), 'model_lock': lock,
        'environment': environment(),
    })
    print('Frozen. Keep Moodle receipt private if it contains personal information.')

if __name__ == '__main__':
    main()
