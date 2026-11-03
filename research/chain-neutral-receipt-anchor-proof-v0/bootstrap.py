"""Fetch exact external sources outside the checkout; never substitute latest."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
def verify_sources(root):
    pins = json.loads((HERE / 'SOURCE_PINS.json').read_text())
    n = 0
    for repo in pins['repositories']:
        if not repo['runtime']:
            continue
        for path, expected in repo['files'].items():
            actual = hashlib.sha256((root / repo['directory'] / path).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError('SOURCE_DRIFT: '+repo['directory']+'/'+path)
            n += 1
    return n

if __name__ == '__main__':
    root = Path(sys.argv[1]).resolve()
    if root.is_relative_to(HERE.parents[1]):
        raise SystemExit('External sources must stay outside the repository')
    for repo in json.loads((HERE / 'SOURCE_PINS.json').read_text())['repositories']:
        if not repo['runtime']:
            continue
        target = root / repo['directory']
        if not target.exists():
            subprocess.run(['git','-c','core.autocrlf=false','clone','--no-checkout',repo['url'],str(target)],check=True)
            subprocess.run(['git','-C',str(target),'config','core.autocrlf','false'],check=True)
            subprocess.run(['git','-C',str(target),'checkout','--detach',repo['commit']],check=True)
        head = subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD']).decode().strip()
        if head != repo['commit']:
            raise SystemExit('SOURCE_HEAD_MISMATCH: '+repo['directory'])
    print('External file pins verified:',verify_sources(root))
