"""Export reproducible source and evidence without private receipts or reports."""
import argparse
import subprocess
import sys
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    target=Path(args.output).resolve()
    if target.exists():
        raise ValueError('Output already exists; choose a new filename to preserve the previous package.')
    tracked=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z']).decode().split('\0')
    paths={ROOT/p for p in tracked if p and (ROOT/p).is_file()}
    for folder in ['results/final','results/analysis','results/reproduction']:
        paths.update(p for p in (ROOT/folder).rglob('*') if p.is_file())
    for name in ['environment.lock.txt','freeze/freeze.json']:
        if (ROOT/name).is_file(): paths.add(ROOT/name)
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            relative=path.relative_to(ROOT)
            if path.resolve()==target or path.suffix.lower() in ('.docx','.pdf') or (path.name.startswith('.') and path.name not in ('.gitignore','.gitattributes')):
                continue
            if relative.parts[0]=='freeze' and path.name!='freeze.json':
                continue
            archive.write(path,relative.as_posix())
    print('Exported:',target)
    print('Private Moodle receipt and Appendix A document were excluded. Keep their originals privately.')


if __name__=='__main__':main()
