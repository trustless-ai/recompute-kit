"""Replay Echo's previously unwitnessed guards on exact old bytes, not prose."""
import copy,hashlib,importlib.util,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
repo,out=map(Path,sys.argv[1:]);out.mkdir(exist_ok=True)
p=repo/'research/chain-neutral-receipt-anchor-proof-v0';old='1afc4ab3e3649e3d987d54006a3f3508c9fd159f'
def blob(f):return subprocess.check_output(['git','show',old+':research/chain-neutral-receipt-anchor-proof-v0/'+f],cwd=repo)
original=json.loads(blob('vectors.json'));expanded=json.loads((p/'vectors.json').read_bytes())
spec=importlib.util.spec_from_file_location('candidate_mutations',p/'mutations.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
commands=[];results=[]
with tempfile.TemporaryDirectory(prefix='echo-source-controls-') as td:
 d=Path(td)
 for name in ('adapter.mjs','sources.mjs','SOURCE_PINS.json','slot_bridge.py'):(d/name).write_bytes(blob(name))
 source=d/'adapter.mjs';saved=source.read_bytes()
 def run(label,corpus):
  cmd=['node',str(source)]
  r=subprocess.run(cmd,input=json.dumps(corpus).encode(),capture_output=True,timeout=60)
  (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
  commands.append({'label':label,'argv':cmd,'exit':r.returncode,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'input_sha256':hashlib.sha256(json.dumps(corpus).encode()).hexdigest()})
  if r.returncode:raise RuntimeError(label+' process failure')
  actual=json.loads(r.stdout);expected={v['name']:v['expected'] for v in corpus['vectors']}
  assert set(actual)==set(expected)
  return actual,expected
 before,want=run('original43-baseline',original);assert before==want
 complete,wantall=run('expanded49-old-code',expanded);assert complete==wantall
 for name,path,a,b,killer in module.MUTATIONS[20:]:
  assert path=='adapter.mjs' and saved.decode().count(a)==1
  try:
   source.write_bytes(saved.decode().replace(a,b).encode())
   actual,expect=run(name+'-original43',original)
   assert actual==expect,'not a survivor on old corpus: '+name
   new,expectnew=run(name+'-expanded49',expanded)
   assert all(new[x]==expectnew[x] for x in module.POSITIVE)
   assert new[killer]!=expectnew[killer]
   results.append({'mutation':name,'applications':1,'old_43':'SURVIVED','expanded_49':'KILLED','required_killer':killer,
    'expected':expectnew[killer],'actual':new[killer],'positive_controls_preserved':True,
    'different_fields':[k for k in expectnew[killer] if new[killer].get(k)!=expectnew[killer][k]]})
  finally:source.write_bytes(saved)
 restored,expect=run('restored-original43',original);assert restored==expect and source.read_bytes()==saved
summary={'old_head':old,'cases_before':43,'cases_after':49,'old_code_baselines_reproduce':True,'mutations':results,'restored':True}
(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
