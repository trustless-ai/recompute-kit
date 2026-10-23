// Thin finite-profile composition. Cryptography/Merkle algorithms remain upstream.
import {readFileSync} from 'node:fs';
import {createPublicKey,verify} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {strict,anchor,HERE} from './sources.mjs';
const {parseStrict,canonicalize,sha256}=strict;
export const SUBJECT='agent-action.subject-record.v0';
export const CANON='receiptos.verify.canonical-json.v1';
export const ENVELOPE='chain-neutral.anchor-proof-envelope.v0';
export const MANIFEST='receiptos.manifest-proof.v0';
export const SLOT='invinoveritas.decision_receipt.slot_log.v1';
export const POLICY='chain-neutral.verifier-policy.v0';
export const DOMAIN='chain-neutral.verifier-policy.v0\0';
const hex=x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x);
const exact=(x,fields)=>x&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).sort().join('|')===[...fields].sort().join('|');
const same=(a,b)=>canonicalize(a).equals(canonicalize(b));
const fields=['profile','canonicalization','phase','claim','subject','action','scope','input','output','evidence','metadata'];
export function admitSubject(raw) {
  const v=parseStrict(raw);
  if(!raw.equals(canonicalize(v))) throw new Error('NON_CANONICAL_RECEIPT'); // GUARD raw-admission
  if(!exact(v,fields)) throw new Error('RECEIPT_SHAPE');
  if(v.profile!==SUBJECT||v.canonicalization!==CANON) throw new Error('RECEIPT_PROFILE_UNSUPPORTED');
  if(!['pre_action','post_action_record'].includes(v.phase)) throw new Error('RECEIPT_PHASE');
  for(const k of ['claim','subject','action','scope','input','output']) {
    if(v[k]!==null&&(!exact(v[k],['sha256'])||!hex(v[k].sha256))) throw new Error('COMMITMENT_SHAPE');
  }
  if(!Array.isArray(v.evidence)||v.evidence.some(x=>!exact(x,['sha256'])||!hex(x.sha256))) throw new Error('EVIDENCE_SHAPE');
  return '0x'+sha256(raw); // no root-field exclusions; identity lives outside body
}
function authenticate(policy,context) {
  if(!policy||!context?.authorities) throw new Error('POLICY_MISSING');
  const body=policy.body;
  if(!body||body.profile!==POLICY) throw new Error('POLICY_PROFILE_UNSUPPORTED');
  const id=sha256(canonicalize(body));
  if(id!==context.policy_id) throw new Error('POLICY_SELECTION_MISMATCH');
  const key=context.authorities[policy.authority_id];
  if(!key) throw new Error('POLICY_AUTHORITY_UNKNOWN');
  const pub=createPublicKey({key:Buffer.from(key,'base64'),format:'der',type:'spki'});
  if(pub.asymmetricKeyType!=='ed25519'||!verify(null,Buffer.concat([Buffer.from(DOMAIN),canonicalize(body)]),pub,Buffer.from(policy.signature,'base64'))) // GUARD policy-authentication
    throw new Error('POLICY_SIGNATURE_INVALID');
  if(body.subject_profile!==SUBJECT||!hex(body.checkpoint_id)||!body.log_id||typeof body.require_chain!=='boolean'
    ||typeof body.require_timestamp!=='boolean'||!['local-ed25519','snapshot-digest'].includes(body.anchor_mechanism)) throw new Error('POLICY_SHAPE');
  return {body,id};
}
export function evaluate(input,context) {
  let native=null;
  const answer=(proof_validity,reason,anchor_assurance='ANCHOR_UNCHECKED')=>({
    result:{projection:'chain-neutral.result.v0',proof_validity,anchor_assurance,reason,
      native:native?{profile:native.profile,status:native.status,reason:native.reason}:null},native_details:native});
  try {
    const id=admitSubject(Buffer.from(input.subject_base64,'base64'));
    const e=parseStrict(Buffer.from(input.envelope_base64,'base64'));
    if(e.profile!==ENVELOPE||![MANIFEST,SLOT].includes(e.proof_profile)) // GUARD profile-selection
      return answer('UNVERIFIABLE','PROOF_PROFILE_UNSUPPORTED');
    if(e.subject_profile!==SUBJECT||e.subject_id!==id) // GUARD receipt-identity
      return answer('REFUTED','RECEIPT_IDENTITY_MISMATCH');
    const p=authenticate(input.policy,context);
    if(e.policy_ref!==p.id||p.body.proof_profile!==e.proof_profile) return answer('UNVERIFIABLE','POLICY_BINDING_MISMATCH');
    if(e.log_id!==p.body.log_id) // GUARD log-identity
      return answer('REFUTED','LOG_IDENTITY_MISMATCH');
    if(e.checkpoint_id!==p.body.checkpoint_id) // GUARD checkpoint-selection
      return answer('REFUTED','SELECTED_CHECKPOINT_MISMATCH');
    if(e.anchor_mechanism!==p.body.anchor_mechanism) return answer('UNVERIFIABLE','ANCHOR_MECHANISM_UNSUPPORTED');
    if(e.proof_profile===MANIFEST) {
      // Selection and checkpoint key are authenticated policy data, never proof-provided trust.
      const selection={profile:anchor.LOG_PROFILE,log_id:p.body.log_id,checkpoint_id:e.checkpoint_id,
        trusted_keys:p.body.checkpoint_keys,require_consistency:p.body.require_chain};
      native=anchor.verifyAnchor(id,e.proof,selection);
    } else {
      const s=e.proof, claim={subject_profile:SUBJECT,subject_id:id};
      if(s.inclusion.line.scope!=='decider'||s.inclusion.line.claim_sha256!==sha256(canonicalize(claim))) // GUARD slot-receipt-binding
        return answer('REFUTED','SLOT_RECEIPT_BINDING_MISMATCH');
      if(s.inclusion.log_root!==e.checkpoint_id) return answer('REFUTED','CHECKPOINT_COMMITMENT_MISMATCH');
      if(p.body.require_chain&&!s.previous) // GUARD chain-required
        return answer('UNVERIFIABLE','CHAIN_EVIDENCE_MISSING');
      const proc=spawnSync(process.env.CHAIN_PYTHON||'python3',['-B',resolve(HERE,'slot_bridge.py')],{input:JSON.stringify(s),encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},timeout:30000});
      if(proc.error||proc.status!==0) throw Object.assign(new Error('NATIVE_PROCESS_UNAVAILABLE'),{executionFailure:true});
      try {native={profile:SLOT,...JSON.parse(proc.stdout)};}
      catch {throw Object.assign(new Error('NATIVE_REPORT_MALFORMED'),{executionFailure:true});}
    }
    if(native.status!=='VERIFIED') // GUARD native-proof-validity
      return answer(native.status,native.reason);
    if(e.timestamp!==null) { // GUARD timestamp-evidence
      // v0 has no authenticated OTS verifier. A status field is never verification.
      return answer('UNVERIFIABLE','TIMESTAMP_VERIFIER_NOT_AVAILABLE');
    }
    if(p.body.require_timestamp) return answer('UNVERIFIABLE','TIMESTAMP_EVIDENCE_MISSING');
    const chained=e.proof_profile===MANIFEST?native.native.consistency==='LOCAL_MANIFEST_EXTENSION_VERIFIED':Boolean(e.proof.previous);
    return answer('VERIFIED','BOUNDED_INCLUSION_VERIFIED',chained?'CHAIN_CONSISTENT':'ANCHOR_UNCHECKED'); // GUARD assurance-separation
  } catch(error) {
    if(error.executionFailure) throw error;
    return answer('UNVERIFIABLE',error.code||error.message||'MALFORMED_INPUT');
  }
}
export function report(corpus,withNative=false) {
  if(!Array.isArray(corpus.vectors)||!corpus.vectors.length) throw new Error('ZERO_CASES');
  const results={};
  for(const v of corpus.vectors) {
    if(typeof v.name!=='string'||Object.hasOwn(results,v.name)) throw new Error('INVALID_CASE_ID');
    const r=evaluate(v.input,v.context);
    results[v.name]=withNative?r:r.result; // GUARD completeness
  }
  return results;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href) {
  try { console.log(JSON.stringify(report(JSON.parse(readFileSync(0,'utf8')),process.argv.includes('--native')))); }
  catch(error) {console.error(error.code||error.message);process.exitCode=2;}
}
