"""Execute unchanged RVR APIs. No replacement receipt, canonicalizer or closure."""
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from bootstrap import verify_sources

def run():
    sources=Path(os.environ['CHAIN_PROOF_SOURCES'])
    verify_sources(sources)
    path=sources/'rvr/conformance/rvr-v0/adapter.py'
    spec=importlib.util.spec_from_file_location('frozen_rvr',path)
    r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    profile=r.load_json(r.PROFILE_PATH)
    schema_bytes=r.PROFILE_MANIFEST_SCHEMA_PATH.read_bytes()
    pd,_,pins=r.audit_profile(profile,r.parse_json_bytes(schema_bytes,'bootstrap'),schema_bytes)
    schema=r.parse_json_bytes(pins['rvr-schema'],'receipt-schema')
    raw=base64.b64decode(json.loads((HERE/'vectors.json').read_text(encoding='utf8'))['vectors'][0]['input']['subject_base64'])
    digest=hashlib.sha256(raw).hexdigest()
    case={'claim':{'schema':'rvr.claim.sha256-equals.v0','operation':'SHA256_EQUALS','evidenceMember':'action-subject','expectedDigest':digest},
          'evidenceSet':{'schema':'rvr.evidence-set.v0','members':[{'id':'action-subject','status':'PRESENT','mediaType':'application/json','byteLength':str(len(raw)),'digest':digest}]},
          'payloadsBase64':{'action-subject':base64.b64encode(raw).decode()}}
    bundle=r.make_bundle(case,profile,pd,schema)
    results={}
    def require(name,actual,expected):
        for k,v in expected.items():
            if k not in actual or actual[k]!=v:
                raise RuntimeError(name+': native result contradicts independent expected '+repr(expected))
        results[name]=actual
    require('subject-identity',r.recompute(bundle,case,pd,schema),{'verificationOutcome':'VERIFIED','recomputationStatus':'REPRODUCED','evaluationPerformed':True})
    safe_vector=next(v for v in json.loads((HERE/'vectors.json').read_text(encoding='utf8'))['vectors'] if v['name']=='SAFE_BOUNDARIES_UNICODE')
    safe_raw=base64.b64decode(safe_vector['input']['subject_base64']);safe_digest=hashlib.sha256(safe_raw).hexdigest()
    safe_case=copy.deepcopy(case);safe_case['claim']['expectedDigest']=safe_digest
    safe_case['evidenceSet']['members'][0].update(byteLength=str(len(safe_raw)),digest=safe_digest)
    safe_case['payloadsBase64']['action-subject']=base64.b64encode(safe_raw).decode()
    safe_bundle=r.make_bundle(safe_case,profile,pd,schema)
    require('safe-integers-in-raw-payload',r.recompute(safe_bundle,safe_case,pd,schema),{'verificationOutcome':'VERIFIED','recomputationStatus':'REPRODUCED','evaluationPerformed':True})
    try:r.require_schema(json.loads(raw),schema,label='RVR receipt')
    except r.GateRejection as error:results['subject-is-not-RVR']={'gate':'REJECTED','reasonCode':error.reason_code}
    else:raise RuntimeError('action subject accepted as RVR receipt')
    bad=copy.deepcopy(case);bad['claim']['expectedDigest']='0'*64
    negative=r.make_bundle(bad,profile,pd,schema)
    require('negative-result-reproduced',r.recompute(negative,bad,pd,schema),{'verificationOutcome':'REFUTED','recomputationStatus':'REPRODUCED','evaluationPerformed':True})
    unavailable=copy.deepcopy(case);unavailable['evidenceSet']['members']=[{'id':'action-subject','status':'UNAVAILABLE','reasonCode':'rvr.v0.evidence_unavailable'}];unavailable['payloadsBase64']={}
    unknown=r.make_bundle(unavailable,profile,pd,schema)
    require('unverifiable-reproduced',r.recompute(unknown,unavailable,pd,schema),{'verificationOutcome':'UNVERIFIABLE','recomputationStatus':'REPRODUCED','evaluationPerformed':True})
    require('normative-dependency-missing',r.recompute(bundle,case,pd,schema,unavailable_dependency_ids={'verification-specification'}),{'recomputationStatus':'CANNOT_RECOMPUTE','evaluationPerformed':False,'reasonCode':'rvr.recompute.normative_dependency_unavailable'})
    require('normative-dependency-wrong',r.recompute(bundle,case,pd,schema,candidate_dependency_bytes={'verification-specification':b'wrong'}),{'recomputationStatus':'CANNOT_RECOMPUTE','evaluationPerformed':False,'reasonCode':'rvr.recompute.normative_dependency_identity_mismatch'})
    for name,change in [('seventh-field',lambda x:x['receipt'].update(anchor={})),('contradictory-projection',lambda x:x['receipt'].update(outcome='REFUTED'))]:
        x=copy.deepcopy(bundle);change(x)
        try:r.validate_receipt_envelope(x,pd,schema)
        except r.GateRejection as error:results[name]={'gate':'REJECTED','reasonCode':error.reason_code}
        else:raise RuntimeError(name+' accepted')
    before=r.canonical_bytes(bundle['receipt'])
    wrapper={'subject':base64.b64encode(raw).decode(),'verification':bundle,'anchor':{'optional':True}}
    del wrapper['anchor']
    if before!=r.canonical_bytes(wrapper['verification']['receipt']):raise RuntimeError('anchor altered receipt')
    results['optional-envelope-independent']={'unchanged':True}
    common={'a':[True,None,'π']}
    if r.canonical_bytes(common)!=json.dumps(common,ensure_ascii=False,separators=(',',':')).encode():raise RuntimeError('canonical intersection')
    results['canonical-intersection']={'bytes_hex':r.canonical_bytes(common).hex()}
    for name,value in [('number-not-RVR',{'n':1}),('lone-surrogate',{'s':'\ud800'})]:
        try:r.canonical_bytes(value)
        except (r.CanonicalizationError,r.StrictJsonError):results[name]={'rejected':True}
        else:raise RuntimeError(name+' accepted')
    try:r.strict_json_loads('{"a":1,"a":2}')
    except r.StrictJsonError:results['duplicate-key']={'rejected':True}
    else:raise RuntimeError('duplicate accepted')
    results['scalar-key-domain']={'bytes_hex':r.canonical_bytes({'\ue000':None,'😀':None}).hex()}
    return {'profile_digest':pd,'receipt':bundle['receipt'],'canonical_result':bundle['canonicalResult'],'checks':results,'count':len(results),'scope':'SUBJECT_BYTE_IDENTITY_ONLY; NO_ACTION_EXECUTION'}

if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=True,indent=2,sort_keys=True))
