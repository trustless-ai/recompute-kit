"""Evidence capture, not a new grader. Existing runner/native tests own grading."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--historical',action='store_true');args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1','CHAIN_PYTHON':sys.executable}
    sources=Path(env['CHAIN_PROOF_SOURCES'])
    records=[]
    def command(name,argv,input_bytes=None,extra=None,cwd=ROOT):
        p=subprocess.run(argv,cwd=cwd,input=input_bytes,capture_output=True,env={**env,**(extra or {})},timeout=600)
        (out/(name+'.stdout')).write_bytes(p.stdout);(out/(name+'.stderr')).write_bytes(p.stderr)
        record={'name':name,'argv':argv,'cwd':str(cwd),'exit':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
        records.append(record);print(name,p.returncode,flush=True)
        (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf8',newline='\n')
        return p
    corpus=(HERE/'vectors.json').read_bytes()
    command('source-pins',[sys.executable,'-B',str(HERE/'bootstrap.py'),str(sources)])
    command('original-slot-vectors',[sys.executable,'-B',str(sources/'invino/examples/decision-receipt/slot_log_check.py'),'--vectors',str(sources/'invino/examples/decision-receipt/slot_log_vectors.json')])
    command('original-rvr',[sys.executable,'-B',str(sources/'rvr/conformance/rvr-v0/adapter.py'),'--check'])
    for mode in ('normal','repeat','optimized'):
        options=['-B']+(['-O'] if mode=='optimized' else [])
        extra={'PYTHONOPTIMIZE':'1'} if mode=='optimized' else {'PYTHONOPTIMIZE':'0'}
        command(mode+'-report',['node',str(HERE/'adapter.mjs')],corpus,extra)
        command(mode+'-native',['node',str(HERE/'adapter.mjs'),'--native'],corpus,extra)
        for name in ('test_research','rvr_boundary','mutations','replay'):
            command(mode+'-'+name,[sys.executable,*options,str(HERE/(name+'.py'))],extra=extra)
    deterministic={}
    for family in ('report','native','rvr_boundary','mutations','replay'):
        a=(out/('normal-'+family+'.stdout')).read_bytes()
        deterministic[family]=all(a==(out/(mode+'-'+family+'.stdout')).read_bytes() for mode in ('repeat','optimized'))
    if args.historical:
        command('canonical',[sys.executable,'-B',str(ROOT/'tools/run_conformance.py')])
        command('runner-unit-tests',[sys.executable,'-B','-m','unittest','discover','-s','tools','-p','test_run_conformance_*.py'])
        for name in ('test_mutation_inventory_nonempty','test_self_grading_nonempty','test_ungradable_expectations','test_scan_subject_binding_ungradable'):
            path=ROOT/'tools'/(name+'.py')
            for mode in ('normal','optimized'):
                command(name+'-'+mode,[sys.executable,'-B',*(['-O'] if mode=='optimized' else []),str(path)])
    summary={'commands':len(records),'nonzero':[r['name'] for r in records if r['exit']!=0],
             'complete_machine_outputs_byte_identical':deterministic,
             'note':'Unittest stderr includes measured timing; byte equality applies only to the named machine reports.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(summary,indent=2))
    return 1 if summary['nonzero'] or not all(deterministic.values()) else 0

if __name__=='__main__':sys.exit(main())
