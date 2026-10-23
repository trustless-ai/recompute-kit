// Fixture construction only. Expected relations below are authored before running
// adapter.mjs and never obtained by calling evaluate/report/any verifier.
import {writeFileSync} from 'node:fs';
import {createPrivateKey,createPublicKey,sign} from 'node:crypto';
import {resolve} from 'node:path';
import {strict,capsule,anchor,HERE} from './sources.mjs';
const {canonicalize:C,sha256:H}=strict;
const R='agent-action.subject-record.v0', A='receiptos.manifest-proof.v0', B='invinoveritas.decision_receipt.slot_log.v1';
const E='chain-neutral.anchor-proof-envelope.v0', P='chain-neutral.verifier-policy.v0';
// Public, reproducible LAB seeds; NEVER an operational credential/trust authority.
const key=n=>createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),Buffer.alloc(32,n)]),format:'der',type:'pkcs8'});
const policyKey=key(51), logKey=key(52), publicKey=k=>createPublicKey(k).export({type:'spki',format:'der'}).toString('base64');
const clone=x=>structuredClone(x), b64=x=>Buffer.from(x).toString('base64'), z='0'.repeat(64), one='1'.repeat(64);
const commitment={sha256:H(Buffer.from('synthetic declared commitment'))};
function receipt(metadata={}) {return {profile:R,canonicalization:'receiptos.verify.canonical-json.v1',phase:'pre_action',claim:commitment,subject:commitment,action:commitment,scope:commitment,input:commitment,output:null,evidence:[],metadata};}
function checkpoint(tree,sequence=0,previous=null) {
 const body={schema:anchor.LOG_PROFILE,log_id:'lab/receiptos',sequence,tree_size:tree.manifest.length,merkle_root:tree.merkleRoot,previous_checkpoint_id:previous};
 return {body,id:anchor.checkpointIdentity(body),key_id:'lab-log-key',signature_base64:sign(null,anchor.checkpointBytes(body),logKey).toString('base64')};
}
function setup(which,metadata={}) {
 const raw=C(receipt(metadata)), id='0x'+H(raw);
 let proof,checkpointId;
 if(which===A) {
  const tree=capsule.buildManifest([{id:'receipt/'+id.slice(2),bytes:Buffer.from(id)},{id:'zz/other',bytes:Buffer.from('other')},{id:'zz/third',bytes:Buffer.from('third')}]);
  const cp=checkpoint(tree); checkpointId=cp.id;
  proof={profile:anchor.LOG_PROFILE,leaf:anchor.receiptLeaf(id),proof:tree.proofs[0],checkpoint:cp};
 } else {
  const line={slot:one,scope:'decider',event_ids:['lab-event'],taken_at:1,claim_sha256:H(C({subject_profile:R,subject_id:id})),decider_sig:'opaque-not-authenticated',conflicts:[]};
  const older={...clone(line),slot:z,claim_sha256:H(C({old:'slot'}))};
  const previous=snapshot([older],'2026-01-01',z);
  const current=snapshot([older,line],'2026-01-02',previous.root);
  checkpointId=current.root;
  proof={snapshot:current.text,previous:previous.text,index:1,count:2,inclusion:{line,leaf:H(C(line)),merkle_path:[{side:'L',hash:H(C(older))}],header:current.header,log_root:current.root}};
 }
 const env={profile:E,subject_profile:R,subject_id:id,proof_profile:which,log_id:which===A?'lab/receiptos':'lab/slot',checkpoint_id:checkpointId,anchor_mechanism:which===A?'local-ed25519':'snapshot-digest',policy_ref:'',proof,timestamp:null};
 const policy={body:{profile:P,subject_profile:R,proof_profile:which,log_id:env.log_id,checkpoint_id:checkpointId,anchor_mechanism:env.anchor_mechanism,require_chain:which===B,require_timestamp:false,checkpoint_keys:which===A?[{id:'lab-log-key',public_key_spki_base64:publicKey(logKey)}]:[]},authority_id:'lab-policy-authority',signature:''};
 const context={policy_id:'',authorities:{'lab-policy-authority':publicKey(policyKey)}};
 const v={raw,env,policy,context}; authorize(v); return v;
}
function authorize(v) {
 v.context.policy_id=H(C(v.policy.body));v.env.policy_ref=v.context.policy_id;
 v.policy.signature=sign(null,Buffer.concat([Buffer.from(P+'\0'),C(v.policy.body)]),policyKey).toString('base64');
}
// Independent data producer, not verifier: exact ASCII-hex pair convention.
function snapshot(lines,date,prev) {
 let leaves=lines.map(x=>H(C(x)));
 while(leaves.length>1) {const next=[];for(let i=0;i<leaves.length;i+=2)next.push(H(Buffer.from(leaves[i]+(leaves[i+1]||leaves[i]))));leaves=next;}
 const header={schema:B,date,cutoff:Date.parse(date+'T00:00:00Z')/1000+86400,prev_root:prev,n_slots:lines.length,merkle_root:leaves[0]||H(Buffer.from(B+'|empty')),rules:'Synthetic canonical slot lines; native ASCII-hex pair hashing; duplicate odd final node.'};
 return {header,root:H(C(header)),text:[header,...lines].map(x=>C(x).toString()).join('\n')+'\n'};
}
const nativeA=(status='VERIFIED',reason='LOCAL_CHECKPOINT_INCLUSION_VERIFIED')=>({profile:anchor.LOG_PROFILE,status,reason});
const nativeB=(status='VERIFIED',reason='SLOT_NATIVE_VERIFIED')=>({profile:B,status,reason});
const expected=(status,reason,native=null,assurance='ANCHOR_UNCHECKED')=>({projection:'chain-neutral.result.v0',proof_validity:status,anchor_assurance:assurance,reason,native});
const goodA=expected('VERIFIED','BOUNDED_INCLUSION_VERIFIED',nativeA());
const goodB=expected('VERIFIED','BOUNDED_INCLUSION_VERIFIED',nativeB(),'CHAIN_CONSISTENT');
const vectors=[];
function add(name,which,change,want,guarantee) {
 const v=setup(which); if(change)change(v);
 const raw=Buffer.from(v.raw), env=C(v.env);
 vectors.push({name,guarantee,input:{subject_base64:b64(raw),envelope_base64:b64(env),policy:v.policy},context:v.context,
   commitments:{subject_bytes_sha256:H(raw),envelope_bytes_sha256:H(env),policy_sha256:H(C(v.policy))},expected:want});
}
add('A_VALID',A,null,goodA,'native count-bound binary Merkle inclusion');
add('B_VALID_CHAIN',B,null,goodB,'native slot inclusion and two snapshots');
add('WRONG_RECEIPT',A,v=>v.env.subject_id='0x'+z,expected('REFUTED','RECEIPT_IDENTITY_MISMATCH'),'receipt identity');
add('WRONG_LEAF',A,v=>v.env.proof.leaf.digest=z,expected('REFUTED','RECEIPT_LOG_LEAF_MISMATCH',nativeA('REFUTED','RECEIPT_LOG_LEAF_MISMATCH')),'leaf binding');
add('WRONG_ROOT',A,v=>v.env.proof.checkpoint.body.merkle_root=z,expected('REFUTED','MERKLE_INCLUSION_INVALID',nativeA('REFUTED','MERKLE_INCLUSION_INVALID')),'root');
add('CORRUPT_SIBLING',A,v=>v.env.proof.proof.siblings[0].hash=z,expected('REFUTED','MERKLE_INCLUSION_INVALID',nativeA('REFUTED','MERKLE_INCLUSION_INVALID')),'path');
add('WRONG_INDEX',A,v=>v.env.proof.proof.index=1,expected('REFUTED','MERKLE_INCLUSION_INVALID',nativeA('REFUTED','MERKLE_INCLUSION_INVALID')),'position');
add('WRONG_COUNT',A,v=>v.env.proof.proof.leafCount=2,expected('REFUTED','CHECKPOINT_TREE_SIZE_MISMATCH',nativeA('REFUTED','CHECKPOINT_TREE_SIZE_MISMATCH')),'count');
add('UNKNOWN_PROFILE',A,v=>v.env.proof_profile='unknown.v0',expected('UNVERIFIABLE','PROOF_PROFILE_UNSUPPORTED'),'dispatch');
add('WRONG_LOG',A,v=>v.env.log_id='other',expected('REFUTED','LOG_IDENTITY_MISMATCH'),'policy log');
add('MISSING_POLICY',A,v=>v.policy=null,expected('UNVERIFIABLE','POLICY_MISSING'),'explicit policy required');
add('SELF_SUPPLIED_TRUST',A,v=>{v.context.authorities={};v.env.untrusted_authorities={'lab-policy-authority':publicKey(policyKey)};},expected('UNVERIFIABLE','POLICY_AUTHORITY_UNKNOWN'),'proof cannot grant trust');
add('BAD_POLICY_SIGNATURE',A,v=>v.policy.signature=b64(Buffer.alloc(64)),expected('UNVERIFIABLE','POLICY_SIGNATURE_INVALID'),'authenticate policy');
add('WRONG_CHECKPOINT',A,v=>{const cp=v.env.proof.checkpoint;cp.body.sequence=1;cp.id=anchor.checkpointIdentity(cp.body);cp.signature_base64=sign(null,anchor.checkpointBytes(cp.body),logKey).toString('base64');v.env.checkpoint_id=cp.id;},expected('REFUTED','SELECTED_CHECKPOINT_MISMATCH'),'different valid signed checkpoint cannot substitute');
add('CONFLICTING_HISTORY',B,v=>{const prev=JSON.parse(v.env.proof.previous.split('\n')[0]);prev.date='2026-01-03';prev.cutoff=Date.parse(prev.date+'T00:00:00Z')/1000+86400;v.env.proof.previous=C(prev)+'\n'+v.env.proof.previous.split('\n').slice(1).join('\n');},expected('REFUTED','SLOT_CHAIN_INVALID',nativeB('REFUTED','SLOT_CHAIN_INVALID')),'supplied history conflict');
add('BROKEN_PREV_ROOT',B,v=>{const p=v.env.proof;const h=clone(p.inclusion.header);h.prev_root=z;p.snapshot=C(h)+'\n'+p.snapshot.split('\n').slice(1).join('\n');p.inclusion.header=h;p.inclusion.log_root=H(C(h));v.env.checkpoint_id=p.inclusion.log_root;v.policy.body.checkpoint_id=v.env.checkpoint_id;authorize(v);},expected('REFUTED','SLOT_CHAIN_INVALID',nativeB('REFUTED','SLOT_CHAIN_INVALID')),'chain continuity despite valid current root');
for(const [name,modify] of [['DROPPED_SLOT',lines=>lines.slice(1)],['MODIFIED_HISTORY',lines=>{lines[0].decider_sig='changed';return lines;}]]) {
 add(name,B,v=>{const p=v.env.proof;let lines=p.snapshot.trim().split('\n').slice(1).map(JSON.parse);lines=modify(lines);const s=snapshot(lines,'2026-01-02',p.inclusion.header.prev_root);p.snapshot=s.text;p.inclusion.header=s.header;p.inclusion.log_root=s.root;p.index=lines.length-1;p.count=lines.length;p.inclusion.merkle_path=lines.length===1?[]:[{side:'L',hash:H(C(lines[0]))}];v.env.checkpoint_id=s.root;v.policy.body.checkpoint_id=s.root;authorize(v);},expected('REFUTED','SLOT_CHAIN_INVALID',nativeB('REFUTED','SLOT_CHAIN_INVALID')),'old slots preserved, even when current root republished');
}
add('INVALID_CHECKPOINT_SIGNATURE',A,v=>v.env.proof.checkpoint.signature_base64=b64(Buffer.alloc(64)),expected('REFUTED','CHECKPOINT_SIGNATURE_INVALID',nativeA('REFUTED','CHECKPOINT_SIGNATURE_INVALID')),'checkpoint signature');
add('MISSING_TIMESTAMP',A,v=>{v.policy.body.require_timestamp=true;authorize(v);},expected('UNVERIFIABLE','TIMESTAMP_EVIDENCE_MISSING',nativeA()),'required timestamp missing');
add('UNANCHORED_VALID',B,v=>{v.env.proof.previous=null;v.policy.body.require_chain=false;authorize(v);},expected('VERIFIED','BOUNDED_INCLUSION_VERIFIED',nativeB()),'valid inclusion does not imply anchoring');
add('CLAIMED_OTS',A,v=>v.env.timestamp={ots_status:'confirmed'},expected('UNVERIFIABLE','TIMESTAMP_VERIFIER_NOT_AVAILABLE',nativeA()),'OTS label not verification');
add('UNSUPPORTED_VERSION',A,v=>v.env.profile=E+'.1',expected('UNVERIFIABLE','PROOF_PROFILE_UNSUPPORTED'),'version');
add('NON_CANONICAL',A,v=>v.raw=Buffer.from(v.raw+'\n'),expected('UNVERIFIABLE','NON_CANONICAL_RECEIPT'),'raw canonical byte admission');
add('MALFORMED_JSON',A,v=>v.raw=Buffer.from('{'),expected('UNVERIFIABLE','MALFORMED_JSON'),'malformed differs from refuted');
add('DUPLICATE_MEMBER',A,v=>v.raw=Buffer.from('{"profile":"x",'+v.raw.toString().slice(1)),expected('UNVERIFIABLE','DUPLICATE_JSON_KEY'),'duplicates before decoding');
add('NEGATIVE_ZERO',A,v=>v.raw=Buffer.from(v.raw.toString().replace('"metadata":{}','"metadata":{"n":-0}')),expected('UNVERIFIABLE','UNSAFE_JSON_NUMBER'),'negative zero');
add('UNSAFE_INTEGER',A,v=>v.raw=Buffer.from(v.raw.toString().replace('"metadata":{}','"metadata":{"n":9007199254740992}')),expected('UNVERIFIABLE','UNSAFE_JSON_NUMBER'),'safe integer upper boundary');
add('LONE_SURROGATE',A,v=>v.raw=Buffer.from(v.raw.toString().replace('"metadata":{}','"metadata":{"text":"\\ud800"}')),expected('UNVERIFIABLE','INVALID_UNICODE'),'Unicode scalar requirement');
add('NON_ASCII_KEY',A,v=>v.raw=Buffer.from(v.raw.toString().replace('"metadata":{}','"metadata":{"π":0}')),expected('UNVERIFIABLE','INVALID_JSON_KEY'),'bounded common key domain');
add('INVALID_UTF8',A,v=>v.raw=Buffer.from([0xc0,0xaf]),expected('UNVERIFIABLE','INVALID_UTF8'),'raw UTF8');
add('OTHER_MERKLE_CONVENTION',A,v=>{
 const d=Buffer.from('receiptos.verify.capsule-merkle.v1\0');
 let top=H(Buffer.concat([d,Buffer.from([0]),C(v.env.proof.leaf)]));
 for(const sibling of v.env.proof.proof.siblings)top=H(Buffer.from(sibling.side==='left'?sibling.hash+top:top+sibling.hash));
 const count=Buffer.alloc(4);count.writeUInt32BE(v.env.proof.proof.leafCount);
 v.env.proof.checkpoint.body.merkle_root=H(Buffer.concat([d,Buffer.from([2]),count,Buffer.from(top,'hex')]));
},expected('REFUTED','MERKLE_INCLUSION_INVALID',nativeA('REFUTED','MERKLE_INCLUSION_INVALID')),'same leaf/siblings/count, only internal-pair convention changed');
add('SLOT_WRONG_RECEIPT',B,v=>{const other=setup(B,{other:true});v.env.proof=other.env.proof;v.env.checkpoint_id=other.env.checkpoint_id;v.policy.body.checkpoint_id=v.env.checkpoint_id;authorize(v);},expected('REFUTED','SLOT_RECEIPT_BINDING_MISMATCH'),'valid slot proof for a different receipt cannot substitute');
add('VALID_PROOF_OTHER_RECEIPT',A,v=>{const other=setup(A,{other:true});v.env.proof=other.env.proof;v.env.checkpoint_id=other.env.checkpoint_id;v.policy.body.checkpoint_id=v.env.checkpoint_id;authorize(v);},expected('REFUTED','RECEIPT_LOG_LEAF_MISMATCH',nativeA('REFUTED','RECEIPT_LOG_LEAF_MISMATCH')),'valid manifest proof for a different receipt cannot substitute');
add('CHAIN_REQUIRED',B,v=>v.env.proof.previous=null,expected('UNVERIFIABLE','CHAIN_EVIDENCE_MISSING'),'required chain');
add('SLOT_WRONG_POSITION',B,v=>v.env.proof.index=0,expected('REFUTED','SLOT_POSITION_INVALID',nativeB('REFUTED','SLOT_POSITION_INVALID')),'full snapshot binds leaf position');
add('SAFE_BOUNDARIES_UNICODE',A,v=>Object.assign(v,setup(A,{maximum:9007199254740991,minimum:-9007199254740991,text:'π 😀 é',nested:{b:false,a:null}})),goodA,'safe boundary, Unicode values and ordering');
function manifestChain(v,conflict=false) {
 const first={id:'receipt/'+v.env.subject_id.slice(2),bytes:Buffer.from(v.env.subject_id)};
 const current=[first,{id:'zz/other',bytes:Buffer.from('other')},{id:'zz/third',bytes:Buffer.from('third')}];
 const old=checkpoint(capsule.buildManifest([first]));
 const cp=checkpoint(capsule.buildManifest(current),1,conflict?z:old.id);
 v.env.proof.checkpoint=cp;v.env.checkpoint_id=cp.id;v.policy.body.checkpoint_id=cp.id;v.policy.body.require_chain=true;authorize(v);
 const records=rs=>rs.map(r=>({id:r.id,bytes_base64:b64(r.bytes)}));
 v.env.proof.consistency={profile:'agent-action.full-manifest-extension.v0',previous_checkpoint:old,previous_records:records([first]),current_records:records(current)};
}
add('A_CHAIN_VALID',A,v=>manifestChain(v),expected('VERIFIED','BOUNDED_INCLUSION_VERIFIED',nativeA(),'CHAIN_CONSISTENT'),'native count-bound full-manifest extension');
add('A_CHAIN_CONFLICT',A,v=>manifestChain(v,true),expected('REFUTED','CONSISTENCY_CHECKPOINT_CONFLICT',nativeA('REFUTED','CONSISTENCY_CHECKPOINT_CONFLICT')),'signed current checkpoint does not waive supplied history conflict');
// Self-review witnesses: literal expected refusals, independent of the verifier.
add('NUMERIC_LOG_ID',B,v=>{v.env.log_id=7;v.policy.body.log_id=7;authorize(v);},expected('UNVERIFIABLE','LOG_IDENTITY_MALFORMED'),'authenticated policy bytes do not waive the nonempty-string log identity contract');
add('POLICY_NOT_SELECTED',A,v=>v.context.policy_id=z,expected('UNVERIFIABLE','POLICY_SELECTION_MISMATCH'),'a valid policy signature cannot replace caller-selected policy identity');
add('POLICY_REF_WRONG',A,v=>v.env.policy_ref=z,expected('UNVERIFIABLE','POLICY_BINDING_MISMATCH'),'envelope references the exact selected authenticated policy');
add('POLICY_PROFILE_DIFFERENT',A,v=>{v.policy.body.proof_profile=B;authorize(v);},expected('UNVERIFIABLE','POLICY_BINDING_MISMATCH'),'authenticated policy selects the same proof profile as the envelope');
writeFileSync(resolve(HERE,'vectors.json'),JSON.stringify({profile:'chain-neutral.research-vectors.v0',vectors},null,2)+'\n');
console.log('Authored '+vectors.length+' expectations without invoking a verifier.');
