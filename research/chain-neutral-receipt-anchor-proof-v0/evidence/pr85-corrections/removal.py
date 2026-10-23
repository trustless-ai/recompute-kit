"""Physical removal of only the scalar assertion, in a disposable copy."""
import hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
root,out=map(Path,sys.argv[1:]);p=root/'research/chain-neutral-receipt-anchor-proof-v0';out.mkdir(exist_ok=True,parents=True)
records=[]
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','CHAIN_PYTHON':sys.executable}
def run(name,args,cwd):
 r=subprocess.run(args,cwd=cwd,capture_output=True,env=env,timeout=180)
 for stream in ('stdout','stderr'):(out/(name+'.'+stream)).write_bytes(getattr(r,stream))
 records.append({'name':name,'argv':list(map(str,args)),'cwd':str(cwd),'exit':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()})
 (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
 return r
with tempfile.TemporaryDirectory(prefix='pr85-scalar-removal-') as td:
 repo=Path(td)/'repo'
 for directory in ('tools','bin'):shutil.copytree(root/directory,repo/directory)
 work=repo/'research/chain-neutral-receipt-anchor-proof-v0';work.mkdir(parents=True)
 for f in p.iterdir():
  if f.is_file():shutil.copyfile(f,work/f.name)
 file=work/'rvr_boundary.py';saved=file.read_bytes()
 old="require('scalar-key-domain',{'bytes_hex':r.canonical_bytes({'\\ue000':None,'😀':None}).hex()},\n            {'bytes_hex':'7b22ee8080223a6e756c6c2c22f09f9880223a6e756c6c7d'})".encode()
 new="results['scalar-key-domain']={'bytes_hex':r.canonical_bytes({'\\ue000':None,'😀':None}).hex()}".encode()
 count=saved.count(old)
 if count!=1:raise RuntimeError('NOT_APPLIED')
 command=[sys.executable,'-B',str(work/'test_research.py'),'ResearchTests.test_scalar_order_is_asserted']
 good=run('guard-present',command,repo)
 positive=run('positive-before',[sys.executable,'-B',str(file)],repo)
 file.write_bytes(saved.replace(old,new))
 removed=run('guard-removed',command,repo)
 positive_removed=run('positive-without-guard',[sys.executable,'-B',str(file)],repo)
 file.write_bytes(saved)
 restored=run('guard-restored',command,repo)
 if good.returncode or restored.returncode or positive.returncode or positive_removed.returncode:raise RuntimeError('baseline/control failure')
 if removed.returncode!=1 or b'RuntimeError not raised' not in removed.stderr or b'FAILED (failures=1)' not in removed.stderr:raise RuntimeError('not the intended assertion failure')
 if positive.stdout!=positive_removed.stdout or saved!=file.read_bytes():raise RuntimeError('positive changed or not restored')
 result={'applications':count,'status':'KILLED_BY_ASSERTION_WITNESS','original_refusal_guard_exit':good.returncode,'removed_guard_test_exit':removed.returncode,'test_failure':'RuntimeError not raised; 1 assertion failure, 0 errors','restored_guard_exit':restored.returncode,'positive_native_output_byte_identical':True,'source_restored':True,'not_part_of_proof_mutation_count':True}
 (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
