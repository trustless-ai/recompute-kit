import hashlib,json,os,subprocess,sys
from pathlib import Path
root,out,prior=map(Path,sys.argv[1:]);p=root/'research/chain-neutral-receipt-anchor-proof-v0'
data=(prior/'probes-input.json').read_bytes();before=json.loads((prior/'probes-normal.stdout').read_text())
command=['node',str(p/'adapter.mjs'),'--native']
proc=subprocess.run(command,input=data,capture_output=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','CHAIN_PYTHON':sys.executable},timeout=120)
(out/'independent-probes.stdout').write_bytes(proc.stdout);(out/'independent-probes.stderr').write_bytes(proc.stderr)
if proc.returncode:raise RuntimeError('probe process failure')
after=json.loads(proc.stdout);changes={k:{'before':before[k],'after':v} for k,v in after.items() if before[k]!=v}
if set(changes)!={'NUMERIC_LOG_ID','MISSING_log_id'}:raise RuntimeError('unexpected result change')
for name in changes:
 if after[name]['result']!={'projection':'chain-neutral.result.v0','proof_validity':'UNVERIFIABLE','anchor_assurance':'ANCHOR_UNCHECKED','reason':'LOG_IDENTITY_MALFORMED','native':None}:raise RuntimeError('wrong corrected result')
summary={'argv':command,'exit':proc.returncode,'corpus_sha256':hashlib.sha256(data).hexdigest(),'cases':len(after),'unchanged_complete_results':len(after)-len(changes),'intentional_changes':changes}
(out/'independent-comparison.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
