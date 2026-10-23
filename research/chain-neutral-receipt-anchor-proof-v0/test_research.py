"""Independent controls use literal invariants, not adapter-generated oracles."""
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import run_conformance as runner

def execute(doc, native=False):
    cmd=['node',str(HERE/'adapter.mjs')]+(['--native'] if native else [])
    return subprocess.run(cmd,input=json.dumps(doc).encode(),capture_output=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})

@contextmanager
def linked_directory(target, link):
    # Windows directory junctions require no symlink privilege; both exercise
    # realpath versus lexical argv. Linux/macOS use actual symbolic links.
    kind='symlink'
    try:
        link.symlink_to(target,target_is_directory=True)
    except OSError:
        if os.name!='nt':raise
        made=subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],capture_output=True)
        if made.returncode:raise RuntimeError(made.stderr.decode('utf8','replace'))
        kind='junction'
    try:yield kind
    finally:
        if kind=='junction':os.rmdir(link)
        else:link.unlink()

def copy_adapter(target):
    for name in ('adapter.mjs','sources.mjs','SOURCE_PINS.json','slot_bridge.py'):
        shutil.copyfile(HERE/name,target/name)

def run_adapter(path, doc, options=()):
    return subprocess.run(['node',*options,str(path)],input=json.dumps(doc).encode(),capture_output=True,
                          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=60)

class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads((HERE/'vectors.json').read_text(encoding='utf8'))

    def test_every_complete_result(self):
        p=execute(self.doc);self.assertEqual(p.returncode,0,p.stderr.decode())
        self.assertEqual(json.loads(p.stdout),{v['name']:v['expected'] for v in self.doc['vectors']})

    def test_exact_commitments(self):
        for v in self.doc['vectors']:
            for k in ('subject','envelope'):
                self.assertEqual(hashlib.sha256(base64.b64decode(v['input'][k+'_base64'])).hexdigest(),v['commitments'][k+'_bytes_sha256'])

    def test_repeat_and_native_retention(self):
        a,b=execute(self.doc),execute(self.doc)
        self.assertEqual(a.returncode,0);self.assertEqual(a.stdout,b.stdout);self.assertEqual(a.stderr,b.stderr)
        native=json.loads(execute(self.doc,True).stdout)
        self.assertEqual(native['A_VALID']['native_details']['native']['inclusion'],'VERIFIED')
        self.assertEqual(native['B_VALID_CHAIN']['native_details']['stage'],'complete')

    def test_report_contract_and_refutation(self):
        # Temporary manifests use the SAME current canonical reporter grader.
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);v={'vectors':[{'name':'x','expected':{'ok':True}}]}
            (d/'vectors.json').write_text(json.dumps(v))
            for text,kind in [('{}','REPORT_CONTRACT'),('{"x":{"ok":false}}','SUITE'),('{"x":{"ok":true},"extra":{}}','REPORT_CONTRACT'),('','REPORT_CONTRACT')]:
                (d/'report.py').write_text('print('+repr(text)+')')
                m={'vectors':{'path':'vectors.json'},'adapter':{'kind':'stdio','contract':'reporter','cmd':'"'+sys.executable+'" report.py'}}
                r=runner._run_one(d,m,'control');self.assertFalse(r.ok);self.assertEqual(r.kind,kind)
            v['vectors'][0].pop('expected');(d/'vectors.json').write_text(json.dumps(v))
            self.assertEqual(runner._run_one(d,m,'control').kind,'REPORT_CONTRACT')

    def test_empty_and_duplicate_cases(self):
        self.assertEqual(execute({'vectors':[]}).returncode,2)
        d=copy.deepcopy(self.doc);d['vectors'].append(d['vectors'][0]);self.assertEqual(execute(d).returncode,2)

    def test_missing_runtime_is_runner(self):
        with tempfile.TemporaryDirectory() as td:
            m={'adapter':{'contract':'self_grading','cmd':'node unused.js'},'runtime':{'commands':['definitely-absent-chain-proof-command']}}
            r=runner._run_one(Path(td),m,'control');self.assertEqual(r.kind,'RUNNER');self.assertFalse(r.ok)

    def test_native_process_failure_is_not_a_case_refutation(self):
        with patch.dict(os.environ,{'CHAIN_PYTHON':'definitely-absent-chain-proof-python'}):
            p=execute(self.doc);self.assertEqual(p.returncode,2)
            self.assertIn(b'NATIVE_PROCESS_UNAVAILABLE',p.stderr)
            p=subprocess.run([sys.executable,'-B',str(HERE/'replay.py')],capture_output=True)
            self.assertEqual(p.returncode,2)
            self.assertEqual(json.loads(p.stdout)[0]['kind'],'RUNNER')
        # One-site removal, disposable bytes only. Positive results must remain
        # identical with a usable runtime. The absent-runtime witness is separate
        # from semantic proof mutations and is not counted as a crash-as-kill.
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            for name in ('adapter.mjs','sources.mjs','SOURCE_PINS.json','slot_bridge.py'):
                shutil.copyfile(HERE/name,d/name)
            source=d/'adapter.mjs';saved=source.read_bytes();guard=b'if(error.executionFailure) throw error;'
            self.assertEqual(saved.count(guard),1)
            source.write_bytes(saved.replace(guard,b''))
            def run_local(extra=None):
                return subprocess.run(['node',str(source)],input=json.dumps(self.doc).encode(),capture_output=True,env={**os.environ,**(extra or {})})
            normal=run_local();self.assertEqual(normal.returncode,0)
            self.assertEqual(json.loads(normal.stdout),{v['name']:v['expected'] for v in self.doc['vectors']})
            fault={'CHAIN_PYTHON':'definitely-absent-chain-proof-python'}
            removed=run_local(fault);self.assertEqual(removed.returncode,0)
            self.assertEqual(json.loads(removed.stdout)['B_VALID_CHAIN']['proof_validity'],'UNVERIFIABLE')
            source.write_bytes(saved);restored=run_local(fault);self.assertEqual(restored.returncode,2)
            self.assertEqual(source.read_bytes(),saved)
            print(json.dumps({'runtime_refusal_removal':{'positive_complete_results_preserved':True,'removed_guard_fault_exit':removed.returncode,'restored_guard_fault_exit':restored.returncode,'restored':True}},sort_keys=True))

    def test_drift_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'vectors.json').write_text('{}')
            m={'vectors':{'path':'vectors.json','sha256':'0'*64},'adapter':{'contract':'reporter','cmd':'node unused.js'}}
            self.assertEqual(runner._run_one(p,m,'control').kind,'DRIFT')

    def test_cross_runtime_canonical_bytes(self):
        # Python RFC8785 is independent of the upstream JS strict serializer.
        import rfc8785
        for v in self.doc['vectors']:
            if v['name'] in ('A_VALID','B_VALID_CHAIN','SAFE_BOUNDARIES_UNICODE'):
                raw=base64.b64decode(v['input']['subject_base64'])
                self.assertEqual(rfc8785.dumps(json.loads(raw)),raw)
                self.assertEqual('0x'+hashlib.sha256(raw).hexdigest(),json.loads(base64.b64decode(v['input']['envelope_base64']))['subject_id'])

    def test_raw_size_limit(self):
        d=copy.deepcopy(self.doc);d['vectors']=d['vectors'][:1]
        d['vectors'][0]['input']['subject_base64']=base64.b64encode(b' '* (4*1024*1024+1)).decode()
        p=execute(d);self.assertEqual(p.returncode,0)
        r=json.loads(p.stdout)['A_VALID'];self.assertEqual(r['proof_validity'],'UNVERIFIABLE');self.assertEqual(r['reason'],'INPUT_TOO_LARGE')

    def test_mutation_classifications(self):
        import mutations
        controls=[
            ('crash','adapter.mjs','const r=evaluate(v.input,v.context);',"throw new Error('deliberate harness crash');",'WRONG_RECEIPT'),
            ('not-applied','adapter.mjs','absent original source site','unused','WRONG_RECEIPT'),
            ('equivalent-survivor','adapter.mjs',"native.status!=='VERIFIED'","(native.status!=='VERIFIED')",'CORRUPT_SIBLING')]
        result=mutations.run(controls)
        self.assertEqual(result['counts'],{'CRASHED':1,'NOT_APPLIED':1,'SURVIVED':1})
        with self.assertRaisesRegex(RuntimeError,'ZERO_MUTANTS'):mutations.run([])

    def test_rvr_boundary(self):
        import rvr_boundary
        result=rvr_boundary.run()
        self.assertEqual(result['count'],15)
        self.assertEqual(len(result['receipt']),6)

    def test_log_identity_admission(self):
        original=next(v for v in self.doc['vectors'] if v['name']=='B_VALID_CHAIN')
        cases=[]
        # The signed policy remains valid; only the envelope identifier is malformed.
        for i,value in enumerate((None,False,0,7,[],{},'')):
            v=copy.deepcopy(original);v['name']='malformed-log-'+str(i)
            envelope=json.loads(base64.b64decode(v['input']['envelope_base64']))
            envelope['log_id']=value
            v['input']['envelope_base64']=base64.b64encode(json.dumps(envelope).encode()).decode()
            cases.append(v)
        # Independently valid signature over a numeric policy log id must also fail
        # admission when the envelope's own log id is a valid string.
        v=copy.deepcopy(next(v for v in self.doc['vectors'] if v['name']=='NUMERIC_LOG_ID'))
        v['name']='malformed-policy-log'
        envelope=json.loads(base64.b64decode(v['input']['envelope_base64']))
        envelope['log_id']='lab/slot'
        v['input']['envelope_base64']=base64.b64encode(json.dumps(envelope).encode()).decode()
        cases.append(v)
        p=execute({'vectors':cases});self.assertEqual(p.returncode,0,p.stderr.decode())
        expected={'projection':'chain-neutral.result.v0','proof_validity':'UNVERIFIABLE',
                  'anchor_assurance':'ANCHOR_UNCHECKED','reason':'LOG_IDENTITY_MALFORMED','native':None}
        self.assertEqual(json.loads(p.stdout),{v['name']:expected for v in cases})

    def test_scalar_order_is_asserted(self):
        import rvr_boundary
        original_spec=rvr_boundary.importlib.util.spec_from_file_location
        target={'\ue000':None,'😀':None}
        calls=[]
        def wrong_order_spec(*args,**kwargs):
            spec=original_spec(*args,**kwargs)
            execute_module=spec.loader.exec_module
            def instrument(module):
                execute_module(module)
                canonical=module.canonical_bytes
                def wrong_order(value):
                    if value==target:
                        calls.append('scalar-order-witness')
                        return '{"😀":null,"\ue000":null}'.encode('utf-8')
                    return canonical(value)
                module.canonical_bytes=wrong_order
            spec.loader.exec_module=instrument
            return spec
        # No frozen source edit: substitute a wrong-order native result only for
        # this witness and require the boundary assertion to notice it.
        with patch.object(rvr_boundary.importlib.util,'spec_from_file_location',side_effect=wrong_order_spec):
            with self.assertRaisesRegex(RuntimeError,'scalar-key-domain: native result contradicts'):
                rvr_boundary.run()
        self.assertEqual(calls,['scalar-order-witness'])

    def test_symlink_entrypoint_and_removal(self):
        expected={v['name']:v['expected'] for v in self.doc['vectors']}
        with tempfile.TemporaryDirectory(prefix='chain proof path ') as td:
            root=Path(td).resolve();work=root/'physical';work.mkdir();copy_adapter(work)
            source=work/'adapter.mjs';saved=source.read_bytes()
            old=b'realpathSync(process.argv[1])===realpathSync(fileURLToPath(import.meta.url))'
            self.assertEqual(saved.count(old),1)
            with linked_directory(work,root/'linked') as kind:
                path=root/'linked'/'adapter.mjs'
                for options in ((),('--preserve-symlinks-main',)):
                    result=run_adapter(path,self.doc,options)
                    self.assertEqual(result.returncode,0,result.stderr.decode())
                    self.assertTrue(result.stdout.strip(),'CLI must emit a report through a linked path')
                    self.assertEqual(json.loads(result.stdout),expected)
                empty=run_adapter(path,{'vectors':[]})
                self.assertEqual(empty.returncode,2);self.assertIn(b'ZERO_CASES',empty.stderr)
                try:
                    source.write_bytes(saved.replace(old,b'resolve(process.argv[1])===fileURLToPath(import.meta.url)'))
                    real=run_adapter(source,self.doc)
                    self.assertEqual(real.returncode,0);self.assertEqual(json.loads(real.stdout),expected)
                    removed=run_adapter(path,self.doc)
                    self.assertEqual(removed.returncode,0);self.assertEqual(removed.stdout,b'')
                finally:source.write_bytes(saved)
                restored=run_adapter(path,self.doc)
                self.assertEqual(restored.returncode,0);self.assertEqual(json.loads(restored.stdout),expected)
                self.assertEqual(source.read_bytes(),saved)
                print(json.dumps({'entrypoint_removal':{'link_kind':kind,'removed_exit':removed.returncode,
                      'removed_stdout_bytes':len(removed.stdout),'restored':True,'positive_controls_preserved':True,
                      'applications':1,'original_sha256':hashlib.sha256(saved).hexdigest(),
                      'mutant_sha256':hashlib.sha256(saved.replace(old,b'resolve(process.argv[1])===fileURLToPath(import.meta.url)')).hexdigest()}},sort_keys=True))

    def test_import_is_not_cli_and_empty_report_refuses(self):
        # Programmatic evaluate/report imports must not consume stdin or emit CLI output.
        module=(HERE/'adapter.mjs').as_uri()
        imported=subprocess.run(['node','--input-type=module','-e','await import('+json.dumps(module)+');'],capture_output=True)
        self.assertEqual(imported.returncode,0,imported.stderr.decode());self.assertEqual(imported.stdout,b'')
        with tempfile.TemporaryDirectory() as td:
            work=Path(td);copy_adapter(work);source=work/'adapter.mjs';saved=source.read_bytes()
            self.assertEqual(saved.count(b'return results;'),1)
            source.write_bytes(saved.replace(b'return results;',b'return undefined;'))
            result=run_adapter(source,self.doc)
            self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,b'');self.assertIn(b'REPORT_EMPTY',result.stderr)
            source.write_bytes(saved);self.assertEqual(source.read_bytes(),saved)

    def test_unselected_slot_is_internally_valid(self):
        v=next(v for v in self.doc['vectors'] if v['name']=='SLOT_UNSELECTED_ROOT')
        e=json.loads(base64.b64decode(v['input']['envelope_base64']))
        self.assertEqual(e['checkpoint_id'],v['input']['policy']['body']['checkpoint_id'])
        self.assertNotEqual(e['proof']['inclusion']['log_root'],e['checkpoint_id'])
        native=subprocess.run([os.environ.get('CHAIN_PYTHON',sys.executable),'-B',str(HERE/'slot_bridge.py')],
                              input=json.dumps(e['proof']).encode(),capture_output=True)
        self.assertEqual(native.returncode,0,native.stderr.decode())
        self.assertEqual(json.loads(native.stdout),{'status':'VERIFIED','reason':'SLOT_NATIVE_VERIFIED',
                         'stage':'complete','log_root':e['proof']['inclusion']['log_root']})
        actual=execute({'vectors':[v]},True);self.assertEqual(actual.returncode,0)
        result=json.loads(actual.stdout)[v['name']]
        self.assertEqual(result['result'],{'projection':'chain-neutral.result.v0','proof_validity':'REFUTED',
                         'anchor_assurance':'ANCHOR_UNCHECKED','reason':'CHECKPOINT_COMMITMENT_MISMATCH','native':None})
        self.assertIsNone(result['native_details'])

    def test_native_checkpoint_binding_and_removal(self):
        # A controlled native-report fault exercises the independent second check.
        # It is not described as an authentic alternate proof or upstream defect.
        v=copy.deepcopy(next(v for v in self.doc['vectors'] if v['name']=='B_VALID_CHAIN'))
        v['name']='NATIVE_CHECKPOINT_REPORT_FAULT';doc={'vectors':[v]}
        expected={'projection':'chain-neutral.result.v0','proof_validity':'REFUTED','anchor_assurance':'ANCHOR_UNCHECKED',
                  'reason':'CHECKPOINT_COMMITMENT_MISMATCH','native':{'profile':'invinoveritas.decision_receipt.slot_log.v1',
                  'status':'VERIFIED','reason':'SLOT_NATIVE_VERIFIED'}}
        with tempfile.TemporaryDirectory() as td:
            work=Path(td);copy_adapter(work);source=work/'adapter.mjs';bridge=work/'slot_bridge.py'
            saved=source.read_bytes();original_bridge=bridge.read_bytes()
            guard=b'native.log_root!==e.checkpoint_id';root=b"'log_root':root"
            self.assertEqual(saved.count(guard),1);self.assertEqual(original_bridge.count(root),1)
            baseline=run_adapter(source,self.doc)
            self.assertEqual(baseline.returncode,0)
            try:
                bridge.write_bytes(original_bridge.replace(root,b"'log_root':'0'*64"))
                guarded=run_adapter(source,doc);self.assertEqual(guarded.returncode,0)
                self.assertEqual(json.loads(guarded.stdout),{v['name']:expected})
                source.write_bytes(saved.replace(guard,b'false'))
                removed=run_adapter(source,doc);self.assertEqual(removed.returncode,0)
                self.assertEqual(json.loads(removed.stdout)[v['name']],v['expected'])
                # All ordinary positives and negative cases remain unchanged when
                # the bridge fault is absent, even with this one guard removed.
                bridge.write_bytes(original_bridge)
                positive=run_adapter(source,self.doc)
                self.assertEqual(positive.returncode,0);self.assertEqual(positive.stdout,baseline.stdout)
                source.write_bytes(saved);bridge.write_bytes(original_bridge.replace(root,b"'log_root':'0'*64"))
                restored=run_adapter(source,doc);self.assertEqual(restored.stdout,guarded.stdout)
                bridge.write_bytes(original_bridge.replace(root,b"'log_root':None"))
                malformed=run_adapter(source,doc)
                self.assertEqual(malformed.returncode,2);self.assertIn(b'NATIVE_REPORT_MALFORMED',malformed.stderr)
                self.assertEqual(malformed.stdout,b'')
            finally:
                source.write_bytes(saved);bridge.write_bytes(original_bridge)
            final=run_adapter(source,self.doc);self.assertEqual(final.stdout,baseline.stdout)
            self.assertEqual(source.read_bytes(),saved);self.assertEqual(bridge.read_bytes(),original_bridge)
            print(json.dumps({'native_checkpoint_removal':{'guarded':expected,'removed':v['expected'],
                  'positive_controls_preserved':True,'source_restored':True,'status':'KILLED_BY_SEMANTIC_WITNESS',
                  'applications':1,'original_sha256':hashlib.sha256(saved).hexdigest(),
                  'mutant_sha256':hashlib.sha256(saved.replace(guard,b'false')).hexdigest(),
                  'bridge_fault_sha256':hashlib.sha256(original_bridge.replace(root,b"'log_root':'0'*64")).hexdigest(),
                  'input_sha256':hashlib.sha256(json.dumps(doc).encode()).hexdigest()}},sort_keys=True))

if __name__=='__main__':
    unittest.main(verbosity=2)
