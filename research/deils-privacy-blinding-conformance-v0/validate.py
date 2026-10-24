"""Capture real commands/bytes/exit codes outside the checkout. Never rewrites evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--historical',action='store_true');args=ap.parse_args()
    out=args.out.resolve()
    if out.is_relative_to(ROOT) or out.exists():raise SystemExit('Evidence must use a new directory outside checkout')
    out.mkdir(parents=True)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
    # Select the same Python for manifest adapter.cmd and direct validation calls.
    env['PATH']=str(Path(sys.executable).parent)+os.pathsep+env.get('PATH','')
    commands=[]
    def run(label,cmd,data=None,cwd=ROOT):
        try:
            r=subprocess.run(cmd,cwd=cwd,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=900)
            rc,stdout,stderr=r.returncode,r.stdout,r.stderr
        except subprocess.TimeoutExpired as error:
            rc,stdout,stderr=124,error.stdout or b'',(error.stderr or b'')+b'\nTIMEOUT\n'
        (out/(label+'.stdout')).write_bytes(stdout);(out/(label+'.stderr')).write_bytes(stderr)
        item=dict(label=label,command=cmd,cwd=str(cwd),exit=rc,stdout_sha256=hashlib.sha256(stdout).hexdigest(),stderr_sha256=hashlib.sha256(stderr).hexdigest())
        commands.append(item);print(label,rc,flush=True)
        return stdout
    vector=(HERE/'vectors.json').read_bytes()
    outputs=[]
    for label,cmd in [('python-normal',[sys.executable,'-B',str(HERE/'verifier.py')]),('python-repeat',[sys.executable,'-B',str(HERE/'verifier.py')]),('python-optimized',[sys.executable,'-B','-O',str(HERE/'verifier.py')]),('node',['node',str(HERE/'verifier.mjs')])]:
        outputs.append(run(label,cmd,vector))
    for label,script,extra in [('tests-normal','test_research.py',[]),('tests-repeat','test_research.py',[]),('tests-optimized','test_research.py',['-O']),('mutations','mutations.py',[]),('experiments','experiments.py',[]),('pins','verify_pins.py',[]),('replay','replay.py',[])]:
        run(label,[sys.executable,'-B',*extra,str(HERE/script)])
    run('mutation-sentinels',[sys.executable,'-B',str(HERE/'mutations.py'),'--sentinels'])
    if args.historical:
        run('canonical',[sys.executable,'-B','tools/run_conformance.py'])
        for path in sorted((ROOT/'tools').glob('test_*.py')):
            run('existing-'+path.stem,[sys.executable,'-B',str(path)])
        for mode in ['test_mutation_inventory_nonempty.py','test_self_grading_nonempty.py','test_ungradable_expectations.py']:
            run('existing-optimized-'+mode[:-3],[sys.executable,'-B','-O',str(ROOT/'tools'/mode)])
    equal=all(x==outputs[0] for x in outputs)
    summary=dict(passed=all(x['exit']==0 for x in commands) and equal,commands=commands,complete_report_bytes_identical=equal,
                 report_sha256=hashlib.sha256(outputs[0]).hexdigest(),environment=dict(platform=platform.platform(),python=sys.version,node=subprocess.check_output(['node','--version']).decode().strip()),
                 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip())
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.iterdir()) if f.is_file()}
    (out/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8',newline='\n')
    return 0 if summary['passed'] else 1


if __name__=='__main__':sys.exit(main())
