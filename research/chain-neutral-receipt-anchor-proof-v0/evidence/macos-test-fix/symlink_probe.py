"""External regression probe. No production or test-module modifications."""
import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
repo=Path(sys.argv[1]);want=sys.argv[2]
p=repo/'research/chain-neutral-receipt-anchor-proof-v0'
sys.path.insert(0,str(p))
spec=importlib.util.spec_from_file_location('test_research',p/'test_research.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
original=m.run_adapter;seen=[]
def observe(path,*args,**kwargs):
 seen.append({'path':str(path),'resolved':str(path.resolve()),'physical_resolved':str(path)==str(path.resolve()),'linked_parent_is_symlink':path.parent.is_symlink()})
 return original(path,*args,**kwargs)
m.run_adapter=observe
result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([m.ResearchTests('test_symlink_entrypoint_and_removal')]))
record={'tmpdir':tempfile.gettempdir(),'resolved_tmpdir':str(Path(tempfile.gettempdir()).resolve()),'observations':seen,'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'success':result.wasSuccessful()}
print(json.dumps(record,sort_keys=True))
assert record['tmpdir']!=record['resolved_tmpdir'],'probe requires a symlinked TMPDIR'
if want=='old':
 assert result.testsRun==1 and len(result.errors)==1 and not result.failures
 assert 'JSONDecodeError' in result.errors[0][1]
 assert any('/physical/' in r['path'] and not r['physical_resolved'] for r in seen)
else:
 assert result.wasSuccessful()
 assert all(r['physical_resolved'] for r in seen if '/physical/' in r['path'])
 assert any(r['linked_parent_is_symlink'] for r in seen)
