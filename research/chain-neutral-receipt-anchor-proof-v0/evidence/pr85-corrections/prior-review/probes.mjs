// New review probes. No production code or stored fixture is edited.
import {readFileSync,writeFileSync} from 'node:fs';
import {createHash,createPrivateKey,sign} from 'node:crypto';
import {resolve} from 'node:path';
const [profile,out]=process.argv.slice(2);
const original=JSON.parse(readFileSync(resolve(profile,'vectors.json')));
const C=x=>Buffer.from(JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v));
const H=x=>createHash('sha256').update(x).digest('hex');
const labKey=createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),Buffer.alloc(32,51)]),format:'der',type:'pkcs8'});
const all=[];
function add(name,base,fn,requirement) {
 const v=structuredClone(original.vectors.find(x=>x.name===base));
 const e=JSON.parse(Buffer.from(v.input.envelope_base64,'base64'));
 fn(v,e);
 v.name=name; delete v.expected; delete v.commitments; delete v.guarantee;
 v.input.envelope_base64=C(e).toString('base64');
 all.push({...v,requirement});
}
function resign(v,e) {
 const body=C(v.input.policy.body);
 v.context.policy_id=H(body);e.policy_ref=v.context.policy_id;
 v.input.policy.signature=sign(null,Buffer.concat([Buffer.from('chain-neutral.verifier-policy.v0\0'),body]),labKey).toString('base64');
}
add('CONTROL_A','A_VALID',()=>{},'VERIFIED');
add('CONTROL_B','B_VALID_CHAIN',()=>{},'VERIFIED');
for (const field of ['profile','subject_profile','subject_id','proof_profile','log_id','checkpoint_id','anchor_mechanism','policy_ref','proof','timestamp'])
 add('MISSING_'+field,'A_VALID',(_,e)=>delete e[field],'NOT_VERIFIED');
add('POLICY_NOT_SELECTED','A_VALID',v=>v.context.policy_id='0'.repeat(64),'NOT_VERIFIED');
add('POLICY_REF_WRONG','A_VALID',(_,e)=>e.policy_ref='0'.repeat(64),'NOT_VERIFIED');
add('POLICY_PROFILE_DIFFERENT','A_VALID',(v,e)=>{v.input.policy.body.proof_profile='invinoveritas.decision_receipt.slot_log.v1';resign(v,e);},'NOT_VERIFIED');
add('POLICY_UNKNOWN_KEY','A_VALID',v=>v.context.authorities={},'NOT_VERIFIED');
add('POLICY_SIGNATURE_INVALID','A_VALID',v=>v.input.policy.signature=Buffer.alloc(64).toString('base64'),'NOT_VERIFIED');
add('POLICY_KEY_FROM_ENVELOPE','A_VALID',(v,e)=>{e.untrusted_authorities=v.context.authorities;v.context.authorities={};},'NOT_VERIFIED');
add('NUMERIC_LOG_ID','B_VALID_CHAIN',(v,e)=>{v.input.policy.body.log_id=7;e.log_id=7;resign(v,e);},'NOT_VERIFIED_SCHEMA');
for (const [name,base,mechanism] of [['SLOT_DECLARED_ED25519','B_VALID_CHAIN','local-ed25519'],['MANIFEST_DECLARED_SNAPSHOT','A_VALID','snapshot-digest']])
 add(name,base,(v,e)=>{e.anchor_mechanism=mechanism;v.input.policy.body.anchor_mechanism=mechanism;resign(v,e);},'INSPECT_MECHANISM_BINDING');
for (const side of ['L','R','INVALID','',0,false,null])
 add('SLOT_SIDE_'+JSON.stringify(side),'B_VALID_CHAIN',(_,e)=>e.proof.inclusion.merkle_path[0].side=side,side==='L'?'VERIFIED':side==='R'?'NOT_VERIFIED':'INSPECT_ADMISSION');
add('SLOT_SIDE_MISSING','B_VALID_CHAIN',(_,e)=>delete e.proof.inclusion.merkle_path[0].side,'NOT_VERIFIED');
add('SLOT_COUNT_WRONG','B_VALID_CHAIN',(_,e)=>e.proof.count=3,'NOT_VERIFIED');
add('SLOT_INDEX_WRONG','B_VALID_CHAIN',(_,e)=>e.proof.index=0,'NOT_VERIFIED');
add('SLOT_ROOT_WRONG','B_VALID_CHAIN',(_,e)=>e.proof.inclusion.log_root='0'.repeat(64),'NOT_VERIFIED');
add('SLOT_PATH_MISSING','B_VALID_CHAIN',(_,e)=>e.proof.inclusion.merkle_path=[],'NOT_VERIFIED');
add('SLOT_SIBLING_CORRUPT','B_VALID_CHAIN',(_,e)=>e.proof.inclusion.merkle_path[0].hash='0'.repeat(64),'NOT_VERIFIED');
add('SLOT_PREVIOUS_MISSING','B_VALID_CHAIN',(_,e)=>e.proof.previous=null,'NOT_VERIFIED');
add('TIMESTAMP_SELF_CONFIRMED','B_VALID_CHAIN',(_,e)=>e.timestamp={ots_status:'confirmed'},'NOT_VERIFIED');
writeFileSync(resolve(out,'probes-input.json'),JSON.stringify({vectors:all},null,2)+'\n');
writeFileSync(resolve(out,'probe-plan.json'),JSON.stringify(all.map(({name,requirement})=>({name,requirement})),null,2)+'\n');
console.log(JSON.stringify({count:all.length,expectations:'literal predicates authored before adapter execution'}));
