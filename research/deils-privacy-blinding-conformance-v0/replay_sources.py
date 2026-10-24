"""Fetch/replay public pinned historical fixtures outside the repository, unchanged.

Private source is never fetched or redistributed here. An optional already-authorized
private cache can be hash-checked separately with --private-cache.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--private-cache',type=Path);args=ap.parse_args()
    cache=args.cache.resolve()
    if cache.is_relative_to(ROOT):raise SystemExit('External cache must stay outside repository')
    cache.mkdir(parents=True,exist_ok=True)
    pins=json.loads((HERE/'SOURCE_PINS.json').read_bytes())['sources'];checked=[];commands=[]
    for pin in pins:
        repo=pin.get('repository',pin.get('repo'));private=pin.get('visibility','').startswith('private')
        if private:
            if not args.private_cache:
                checked.append(dict(path=pin['path'],status='PRIVATE_SOURCE_NOT_REPLAYED'));continue
            file=args.private_cache/pin['path']
        else:
            file=cache/pin['path']
            if not file.exists():
                url=f"https://raw.githubusercontent.com/{repo}/{pin['revision']}/{pin['path']}"
                data=urllib.request.urlopen(url,timeout=60).read()
                if hashlib.sha256(data).hexdigest()!=pin['sha256']:raise SystemExit('DRIFT '+url)
                file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
        actual=hashlib.sha256(file.read_bytes()).hexdigest()
        if actual!=pin['sha256']:raise SystemExit('DRIFT '+str(file))
        checked.append(dict(path=pin['path'],status='PIN_MATCH',sha256=actual))
    cmds=[[sys.executable,'-B',str(cache/'examples/deils-leg2/check_deils_leg2.py')]]
    cmds += [[sys.executable,'-B',str(ROOT/'conformance/deils-leg2-reveal-v0/reveal_check.py'),str(ROOT/'conformance/deils-leg2-reveal-v0'/f)] for f in ['selftest_stored_hash.json','vectors_invinoveritas_blindhit.json']]
    if args.private_cache:cmds.append([sys.executable,'-B',str(args.private_cache/'conformance/deils-reveal-v0/reveal_check.py')])
    for cmd in cmds:
        r=subprocess.run(cmd,capture_output=True);commands.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout.decode('utf-8'),stderr=r.stderr.decode('utf-8')))
    print(json.dumps(dict(pins=checked,commands=commands),ensure_ascii=True,indent=2))
    return int(any(x['exit'] for x in commands))


if __name__=='__main__':sys.exit(main())
