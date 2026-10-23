"""Physical one-site controls in temporary copies; no production byte mutation.

Runner grades complete results. A crash, missing result or unapplied edit is
reported separately and never counted as KILLED. External source edits are
validly repinned ONLY inside each disposable copy, avoiding drift-as-kill.
"""
import collections
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import run_conformance as canonical_runner
POSITIVE=('A_VALID','B_VALID_CHAIN','UNANCHORED_VALID','SAFE_BOUNDARIES_UNICODE','A_CHAIN_VALID')
NATIVE='receiptos/research/agent-action-browser-verify-v0/lib/anchor.mjs'
MUTATIONS=[
 ('profile-selection','adapter.mjs',"e.profile!==ENVELOPE||![MANIFEST,SLOT].includes(e.proof_profile)","false",'UNSUPPORTED_VERSION'),
 ('subject-identity','adapter.mjs',"e.subject_profile!==SUBJECT||e.subject_id!==id","false",'WRONG_RECEIPT'),
 ('policy-authentication','adapter.mjs',"pub.asymmetricKeyType!=='ed25519'||!verify(null,Buffer.concat([Buffer.from(DOMAIN),canonicalize(body)]),pub,Buffer.from(policy.signature,'base64'))","false",'BAD_POLICY_SIGNATURE'),
 ('policy-authority','adapter.mjs',"if(!key) throw new Error('POLICY_AUTHORITY_UNKNOWN');","if(!key) return {body,id};",'SELF_SUPPLIED_TRUST'),
 ('log-selection','adapter.mjs',"e.log_id!==p.body.log_id","false",'WRONG_LOG'),
 ('checkpoint-selection','adapter.mjs',"e.checkpoint_id!==p.body.checkpoint_id","false",'WRONG_CHECKPOINT'),
 ('slot-leaf-binding','adapter.mjs',"s.inclusion.line.scope!=='decider'||s.inclusion.line.claim_sha256!==sha256(canonicalize(claim))","false",'SLOT_WRONG_RECEIPT'),
 ('chain-required','adapter.mjs',"p.body.require_chain&&!s.previous","false",'CHAIN_REQUIRED'),
 ('timestamp-evidence','adapter.mjs',"e.timestamp!==null","false",'CLAIMED_OTS'),
 ('raw-admission','adapter.mjs',"!raw.equals(canonicalize(v))","false",'NON_CANONICAL'),
 ('native-result','adapter.mjs',"native.status!=='VERIFIED'","false",'INVALID_CHECKPOINT_SIGNATURE'),
 ('assurance-separation','adapter.mjs',"return answer(native.status,native.reason);","return answer('VERIFIED',native.reason,'ANCHOR_UNCHECKED');",'CORRUPT_SIBLING'),
 ('case-attribution','adapter.mjs',"const r=evaluate(v.input,v.context);","const r=evaluate(v.name==='WRONG_RECEIPT'?corpus.vectors[0].input:v.input,v.context);",'WRONG_RECEIPT'),
 ('manifest-leaf','external:'+NATIVE,"!equal(evidence.leaf,receiptLeaf(receiptRoot))","false",'VALID_PROOF_OTHER_RECEIPT'),
 ('merkle-verification','external:'+NATIVE,"!verifyInclusion(evidence.leaf,evidence.proof,c.body.merkle_root)","false",'CORRUPT_SIBLING'),
 ('slot-chain-continuity','slot_bridge.py',"slot.check_chain(h, lines, data['previous'].encode('utf-8'))","pass",'BROKEN_PREV_ROOT'),
 ('log-id-admission','adapter.mjs',"typeof e.log_id!=='string'||!e.log_id||typeof p.body.log_id!=='string'||!p.body.log_id","false",'NUMERIC_LOG_ID'),
 ('selected-policy','adapter.mjs',"id!==context.policy_id","false",'POLICY_NOT_SELECTED'),
 ('policy-reference','adapter.mjs',"e.policy_ref!==p.id","false",'POLICY_REF_WRONG'),
 ('policy-proof-profile','adapter.mjs',"p.body.proof_profile!==e.proof_profile","false",'POLICY_PROFILE_DIFFERENT'),
 ('slot-checkpoint-envelope','adapter.mjs',"s.inclusion.log_root!==e.checkpoint_id","false",'SLOT_UNSELECTED_ROOT'),
 ('policy-schema','adapter.mjs',"!body||body.profile!==POLICY","!body",'POLICY_SCHEMA_WRONG'),
 ('policy-mechanism-allowlist','adapter.mjs',"!['local-ed25519','snapshot-digest'].includes(body.anchor_mechanism)","false",'POLICY_MECHANISM_UNKNOWN'),
 ('envelope-mechanism-binding','adapter.mjs',"e.anchor_mechanism!==p.body.anchor_mechanism","false",'ENVELOPE_MECHANISM_MISMATCH'),
 ('timestamp-boolean','adapter.mjs',"typeof body.require_timestamp!=='boolean'","false",'POLICY_TIMESTAMP_NOT_BOOLEAN'),
 ('proof-supplied-checkpoint-keys','adapter.mjs',"trusted_keys:p.body.checkpoint_keys","trusted_keys:e.untrusted_checkpoint_keys??p.body.checkpoint_keys",'PROOF_SUPPLIED_CHECKPOINT_KEYS'),
]

def run(inventory=None):
    inventory=MUTATIONS if inventory is None else inventory
    if not inventory:raise RuntimeError('ZERO_MUTANTS')
    vectors=json.loads((HERE/'vectors.json').read_text(encoding='utf8'))
    expected={v['name']:v['expected'] for v in vectors['vectors']}
    source=Path(os.environ['CHAIN_PROOF_SOURCES'])
    report=[]
    with tempfile.TemporaryDirectory(prefix='chain-proof-mutations-') as td:
        root=Path(td);work=root/'profile';work.mkdir();deps=root/'sources';deps.mkdir()
        # Only needed exact files, never modify source checkouts.
        pins=json.loads((HERE/'SOURCE_PINS.json').read_text())
        for repo in pins['repositories']:
            if repo['runtime']:
                for file in repo['files']:
                    target=deps/repo['directory']/file;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source/repo['directory']/file,target)
        for f in HERE.iterdir():
            if f.is_file():shutil.copyfile(f,work/f.name)
        env={**os.environ,'CHAIN_PROOF_SOURCES':str(deps),'PYTHONDONTWRITEBYTECODE':'1'}
        original_lock=(work/'SOURCE_PINS.json').read_bytes()
        def execute():
            return subprocess.run(['node',str(work/'adapter.mjs')],input=json.dumps(vectors).encode(),capture_output=True,env=env,timeout=60)
        baseline=execute()
        if baseline.returncode!=0 or json.loads(baseline.stdout)!=expected:raise RuntimeError('baseline failed')
        for name,path,old,new,killer in inventory:
            target=(deps/path.removeprefix('external:')) if path.startswith('external:') else work/path
            saved=target.read_bytes();text=saved.decode();count=text.count(old)
            item={'mutation':name,'path':path,'old':old,'new':new,'applications':count,'required_killer':killer}
            try:
                if count!=1:item['status']='NOT_APPLIED';report.append(item);continue
                target.write_bytes(text.replace(old,new).encode())
                if path.startswith('external:'):
                    changed=json.loads(original_lock)
                    directory,file=path.removeprefix('external:').split('/',1)
                    next(r for r in changed['repositories'] if r['directory']==directory)['files'][file]=hashlib.sha256(target.read_bytes()).hexdigest()
                    (work/'SOURCE_PINS.json').write_text(json.dumps(changed),encoding='utf8')
                p=execute();item.update(exit=p.returncode,stderr=p.stderr.decode('utf8','replace'),stdout_sha256=hashlib.sha256(p.stdout).hexdigest())
                if p.returncode!=0:item['status']='CRASHED'
                else:
                    actual=json.loads(p.stdout);item['changed_cases']=[n for n in expected if actual.get(n)!=expected[n]]
                    item['positive_controls']={n:actual.get(n)==expected[n] for n in POSITIVE}
                    if set(actual)!=set(expected):item['status']='NOT_COVERED'
                    elif not all(item['positive_controls'].values()):item['status']='CONTROL_FAILURE'
                    elif actual[killer]==expected[killer]:item['status']='SURVIVED'
                    else:
                        prior=os.environ.get('CHAIN_PROOF_SOURCES')
                        os.environ['CHAIN_PROOF_SOURCES']=str(deps)
                        try:
                            graded=canonical_runner._run_reporter(work,'node adapter.mjs',name,json.dumps(vectors).encode(),'vectors.json')
                        finally:
                            os.environ['CHAIN_PROOF_SOURCES']=prior
                        item['canonical_kind']=graded.kind
                        item['status']='KILLED' if not graded.ok and graded.kind=='SUITE' else 'NOT_COVERED'
                        item['witness_expected']=expected[killer];item['witness_actual']=actual[killer]
            except subprocess.TimeoutExpired:item['status']='TIMEOUT'
            except (ValueError,KeyError):item['status']='MALFORMED_REPORT'
            finally:
                target.write_bytes(saved);(work/'SOURCE_PINS.json').write_bytes(original_lock)
                item['restored']=target.read_bytes()==saved
            report.append(item)
        final=execute()
        if final.returncode!=0 or json.loads(final.stdout)!=expected:raise RuntimeError('restoration failed')
    return {'total':len(report),'counts':dict(collections.Counter(x['status'] for x in report)),'positive_controls':list(POSITIVE),'restored_baseline':True,'mutations':report}

if __name__=='__main__':
    result=run();print(json.dumps(result,indent=2,sort_keys=True))
    sys.exit(0 if result['counts']=={'KILLED':len(MUTATIONS)} else 1)
