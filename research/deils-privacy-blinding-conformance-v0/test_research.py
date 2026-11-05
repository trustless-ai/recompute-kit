"""Executable controls for the bounded research claim; no new grading framework."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import experiments
import mutations
import replay
import verifier

HERE=Path(__file__).resolve().parent
CORPUS=json.loads((HERE/'vectors.json').read_bytes())
EXPECTED={v['name']:v['expected'] for v in CORPUS['vectors']}


class Research(unittest.TestCase):
    def test_cli_symlink_and_removal(self):
        source=(HERE/'verifier.mjs').read_bytes()
        fixed=b'realpathSync(process.argv[1])===realpathSync(fileURLToPath(import.meta.url))'
        old=b'resolve(process.argv[1])===fileURLToPath(import.meta.url)'
        self.assertEqual(source.count(fixed),1)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve()  # macOS /var TMPDIR must really be physical.
            physical=root/'physical';physical.mkdir()
            script=physical/'verifier.mjs';script.write_bytes(source)
            linked=root/'linked';linked.symlink_to(physical,target_is_directory=True)
            file_link=root/'linked.mjs';file_link.symlink_to(script)
            self.assertTrue(linked.is_symlink());self.assertTrue(file_link.is_symlink())
            self.assertEqual(physical,physical.resolve())
            output=[]
            for path in [script,linked/'verifier.mjs',file_link]*2:
                rc,out,err=mutations.execute(path,CORPUS)
                self.assertEqual((rc,err),(0,b''));self.assertTrue(out)
                self.assertEqual(json.loads(out),EXPECTED);output.append(out)
                rc,out,err=mutations.execute(path,{'vectors':[]})
                self.assertEqual((rc,out),(2,b''));self.assertIn(b'REPORT_INPUT_UNGRADABLE',err)
            self.assertTrue(all(out==output[0] for out in output))
            # Restoring only the old entry guard restores the silent skip.
            script.write_bytes(b"import {resolve} from 'node:path';\n"+source.replace(fixed,old))
            rc,out,err=mutations.execute(script,CORPUS)
            self.assertEqual((rc,out,err),(0,output[0],b''))
            rc,out,err=mutations.execute(linked/'verifier.mjs',CORPUS)
            self.assertEqual((rc,out,err),(0,b'',b''))
            m=mutations.catalog()[0]
            self.assertEqual(mutations.classify(rc,out,err,CORPUS,m['controls'],m['witness'])[0],'MISSING_OUTPUT')
            script.write_bytes(source)
            self.assertEqual(mutations.execute(linked/'verifier.mjs',CORPUS),(0,output[0],b''))
        self.assertEqual((HERE/'verifier.mjs').read_bytes(),source)

    def test_import_has_no_cli_side_effects(self):
        p=subprocess.run(['node','--input-type=module','-e',"import './verifier.mjs';"],cwd=HERE,capture_output=True)
        self.assertEqual((p.returncode,p.stdout,p.stderr),(0,b'',b''))

    def test_missing_stdout_cannot_pass_runner(self):
        with tempfile.TemporaryDirectory() as td:
            dst=Path(td)/'research';shutil.copytree(HERE,dst)
            manifest=json.loads((dst/'suite.json').read_bytes())
            for check in manifest['checks']:
                check['adapter']['cmd']='node -e "process.exit(0)"'
            (dst/'suite.json').write_text(json.dumps(manifest),encoding='utf-8')
            results,rc=replay.run(dst)
            self.assertEqual(rc,2)
            self.assertTrue(all(not r.ok and r.kind=='REPORT_CONTRACT' for r in results),results)

    def test_csprng_generation_boundary(self):
        first,second=verifier.fresh_blinding(),verifier.fresh_blinding()
        self.assertRegex(first,r'\A[0-9a-f]{64}\Z');self.assertNotEqual(first,second)
        saved=verifier.secrets.token_bytes;draws=[]
        def deterministic_draw(n):draws.append(n);return b'\x42'*n
        verifier.secrets.token_bytes=deterministic_draw
        try:self.assertEqual(verifier.fresh_blinding(),'42'*32);self.assertEqual(draws,[32])
        finally:verifier.secrets.token_bytes=saved
        js="import {freshBlinding} from './verifier.mjs';const a=freshBlinding(),b=freshBlinding();console.log(/^[0-9a-f]{64}$/.test(a)&&a!==b);"
        p=subprocess.run(['node','--input-type=module','-e',js],cwd=HERE,capture_output=True)
        self.assertEqual((p.returncode,p.stdout.strip(),p.stderr),(0,b'true',b''))

    def test_complete_corpus(self):
        self.assertEqual(len(CORPUS['vectors']),52)
        self.assertEqual(len(EXPECTED),52)
        for file in ('verifier.py','verifier.mjs'):
            rc,out,err=mutations.execute(HERE/file,CORPUS)
            self.assertEqual((rc,err),(0,b''))
            self.assertEqual(json.loads(out),EXPECTED)

    def test_determinism_full_bytes(self):
        payload=json.dumps(CORPUS).encode()
        commands=[[sys.executable,'-B',str(HERE/'verifier.py')]]*2+[[sys.executable,'-B','-O',str(HERE/'verifier.py')],['node',str(HERE/'verifier.mjs')]]
        outputs=[]
        for cmd in commands:
            r=subprocess.run(cmd,input=payload,capture_output=True)
            self.assertEqual((r.returncode,r.stderr),(0,b''));outputs.append(r.stdout)
        self.assertTrue(all(x==outputs[0] for x in outputs))

    def test_oracle_is_independent_and_reproducible(self):
        import define_vectors
        self.assertEqual(define_vectors.build(),CORPUS)
        for v in CORPUS['vectors']:
            self.assertEqual(hashlib.sha256(v['input']['content_json'].encode()).hexdigest(),v['input_utf8_sha256'])
        self.assertNotIn('import verifier',(HERE/'define_vectors.py').read_text())

    def test_pre_hash_refusal_python(self):
        saved=verifier.hashlib.sha256
        def bomb(_):raise RuntimeError('CANONICAL_HASH_PATH_REACHED')
        verifier.hashlib.sha256=bomb
        try:
            for v in CORPUS['vectors']:
                if v['expected']['reason'] in ('blinding_malformed','RESEARCH_REQUIRED_BLINDING_ABSENT'):
                    self.assertEqual(verifier.verify(v['input']),v['expected'])
            with self.assertRaisesRegex(RuntimeError,'CANONICAL_HASH_PATH_REACHED'):
                verifier.verify(CORPUS['vectors'][0]['input'])
        finally:verifier.hashlib.sha256=saved

    def test_pre_hash_refusal_node(self):
        text=(HERE/'verifier.mjs').read_text()
        old="const sha=b=>createHash('sha256').update(b).digest('hex');"
        self.assertEqual(text.count(old),1)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'verifier.mjs';p.write_text(text.replace(old,"const sha=b=>{throw Error('CANONICAL_HASH_PATH_REACHED');};"),encoding='utf-8')
            subset={'vectors':[v for v in CORPUS['vectors'] if v['expected']['reason'] in ('blinding_malformed','RESEARCH_REQUIRED_BLINDING_ABSENT')]}
            rc,out,err=mutations.execute(p,subset)
            self.assertEqual((rc,err),(0,b''));self.assertEqual(json.loads(out),{v['name']:v['expected'] for v in subset['vectors']})
            rc,out,err=mutations.execute(p,{'vectors':CORPUS['vectors'][:1]})
            self.assertNotEqual(rc,0);self.assertIn(b'CANONICAL_HASH_PATH_REACHED',err)

    def test_canonical_grading(self):
        results,code=replay.run()
        self.assertEqual(code,0,results);self.assertEqual(len(results),2)
        self.assertTrue(all(r.ok and '52/52' in r.detail for r in results))

    def test_runner_negative_controls(self):
        # Repin only the copied corpus: valid semantic mismatches stay distinct from DRIFT.
        with tempfile.TemporaryDirectory() as td:
            dst=Path(td)/'research';shutil.copytree(HERE,dst)
            manifest=json.loads((dst/'suite.json').read_bytes())
            def check_doc(doc,repin=True):
                raw=(json.dumps(doc,ensure_ascii=True)+'\n').encode();(dst/'vectors.json').write_bytes(raw)
                m=copy.deepcopy(manifest)
                if repin:
                    m['vectors']['sha256']=hashlib.sha256(raw).hexdigest()
                    for check in m['checks']:check['vectors']['sha256']=hashlib.sha256(raw).hexdigest()
                (dst/'suite.json').write_text(json.dumps(m),encoding='utf-8')
                return replay.run(dst)
            bad=copy.deepcopy(CORPUS);bad['vectors'][0]['expected']['state']='wrong-established-relation'
            results,rc=check_doc(bad);self.assertEqual(rc,1);self.assertTrue(all(r.kind=='SUITE' and not r.ok for r in results))
            results,rc=check_doc(bad,False);self.assertEqual(rc,1);self.assertTrue(all(r.kind=='DRIFT' for r in results))
            for doc in [{'vectors':[]},{'vectors':[dict(name='missing',input={})]}]:
                results,rc=check_doc(doc);self.assertEqual(rc,2);self.assertTrue(all(r.kind=='REPORT_CONTRACT' for r in results))
            check_doc(CORPUS)
            m=json.loads((dst/'suite.json').read_bytes());m['runtime']['commands'].append('deils-deliberately-absent-runtime-734b')
            (dst/'suite.json').write_text(json.dumps(m),encoding='utf-8')
            results,rc=replay.run(dst);self.assertEqual(rc,2);self.assertTrue(all(r.kind=='RUNNER' for r in results))

    def test_physical_mutations(self):
        report=mutations.run()
        self.assertEqual(report['total'],16)
        self.assertEqual(report['totals']['KILLED'],16,report['totals'])
        self.assertTrue(all(r['applied_count']==1 and r['original_restored'] for r in report['results']))

    def test_non_kill_sentinels(self):
        sentinels=mutations.sentinels()
        self.assertEqual(sentinels['total'],6)
        self.assertEqual(sentinels['totals']['KILLED'],0)
        self.assertTrue(all(r['classification']==r['name'].split('/')[1] for r in sentinels['results']))
        m=mutations.catalog()[0];baseline=json.dumps(EXPECTED).encode()
        self.assertEqual(mutations.classify(0,baseline,b'',CORPUS,m['controls'],m['witness'])[0],'SURVIVED')
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.py'
            for src,want in [('raise RuntimeError("sentinel")','CRASHED'),('pass','MISSING_OUTPUT'),('print("{}")','MISSING_OUTPUT')]:
                p.write_text(src,encoding='utf-8');rc,out,err=mutations.execute(p,CORPUS)
                self.assertEqual(mutations.classify(rc,out,err,CORPUS,m['controls'],m['witness'])[0],want)
        broken=copy.deepcopy(EXPECTED);broken[m['controls'][0]]={}
        self.assertEqual(mutations.classify(0,json.dumps(broken).encode(),b'',CORPUS,m['controls'],m['witness'])[0],'CONTROL_BROKEN')
        self.assertEqual(mutations.classify(124,b'',b'TIMEOUT',CORPUS,m['controls'],m['witness'])[0],'CRASHED')

    def test_empty_duplicate_and_missing_output(self):
        for file in ('verifier.py','verifier.mjs'):
            for doc in [{'vectors':[]},{'vectors':[CORPUS['vectors'][0]]*2}]:
                rc,out,err=mutations.execute(HERE/file,doc);self.assertEqual(rc,2);self.assertEqual(out,b'')
        m=mutations.catalog()[0]
        for altered in [dict(EXPECTED,extra={}),{k:v for k,v in EXPECTED.items() if k!='matching_blinded'}]:
            self.assertEqual(mutations.classify(0,json.dumps(altered).encode(),b'',CORPUS,m['controls'],m['witness'])[0],'MISSING_OUTPUT')

    def test_privacy_experiment(self):
        x=experiments.privacy();self.assertEqual(x['candidates'],100)
        self.assertEqual(x['unblinded_matching_indices'],[42]);self.assertEqual(x['without_nonce_matching_indices'],[])
        self.assertEqual(x['disclosed_nonce_matching_indices'],[42])

    def test_size_bound_anchor(self):
        x=experiments.tree_size()
        self.assertTrue(x['root_only_actual']);self.assertTrue(x['root_only_restated'])
        self.assertFalse(x['wrong_root_control']);self.assertTrue(x['size_bound_actual']);self.assertFalse(x['size_bound_restated'])


if __name__=='__main__':unittest.main()
