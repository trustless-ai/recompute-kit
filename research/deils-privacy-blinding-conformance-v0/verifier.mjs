// Independently written Node reporter; JCS over this research's safe-integer domain.
import {createHash,randomBytes} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const PRIVACY='research.deils-privacy-blinding.v0', LEGACY='research.deils-legacy-integer-replay.v0';
const sha=b=>createHash('sha256').update(b).digest('hex');
export function freshBlinding(){return randomBytes(32).toString('hex');}

// Parse JSON without losing duplicate keys, unsafe integers or lone surrogates.
// Fraction/exponent tokens are outside this experiment, not forbidden by RFC 8785.
export function parseContent(text) {
  if(typeof text!=='string') throw Error('content string required');
  let p=0;
  const ws=()=>{while(p<text.length && /[\x20\t\r\n]/.test(text[p]))p++;};
  function string() {
    const start=p++;
    while(p<text.length){const c=text[p++];if(c==='\\'){p++;continue;}if(c==='"'){
      const s=JSON.parse(text.slice(start,p));
      for(let i=0;i<s.length;i++){const u=s.charCodeAt(i);if(u>=0xd800&&u<=0xdbff){const v=s.charCodeAt(++i);if(!(v>=0xdc00&&v<=0xdfff))throw Error('surrogate');}else if(u>=0xdc00&&u<=0xdfff)throw Error('surrogate');}
      return s;
    }}throw Error('string');
  }
  function value(){ws();const c=text[p];
    if(c==='"')return string();
    if(c==='{'){p++;ws();const o=Object.create(null);if(text[p]==='}'){p++;return o;}while(true){ws();if(text[p]!=='"')throw Error('key');const k=string();if(Object.hasOwn(o,k))throw Error('duplicate');ws();if(text[p++]!==':')throw Error('colon');o[k]=value();ws();const t=text[p++];if(t==='}')return o;if(t!==',')throw Error('object');}}
    if(c==='['){p++;ws();const a=[];if(text[p]===']'){p++;return a;}while(true){a.push(value());ws();const t=text[p++];if(t===']')return a;if(t!==',')throw Error('array');}}
    for(const [literal,v] of [['true',true],['false',false],['null',null]])if(text.startsWith(literal,p)){p+=literal.length;return v;}
    const m=/^-?(?:0|[1-9][0-9]*)/.exec(text.slice(p));if(!m)throw Error('number');p+=m[0].length;
    const n=Number(m[0]);if(!Number.isSafeInteger(n))throw Error('unsafe integer');return n;
  }
  const v=value();ws();if(p!==text.length)throw Error('trailing/unsupported token');return v;
}
export function canonical(v){
  if(v===null||typeof v!=='object')return JSON.stringify(v);
  if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';
  return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';
}
function result(status,state=null,reason=null,stage='validation',bytes=null){return {
  status,state,reason,stage,hash_evaluated:bytes!==null,
  canonical_utf8_hex:bytes===null?null:bytes.toString('hex'),
  recomputed_commitment:bytes===null?null:'sha256:'+sha(bytes)
};}
export function verify(inp){
  const profile=inp.profile;
  if(![PRIVACY,LEGACY].includes(profile))return result('UNVERIFIABLE',null,'RESEARCH_PROFILE_UNSUPPORTED','admission');
  if(inp.disclosed===false)return result('UNVERIFIABLE','content_withheld',null,'disclosure');
  let c;try{c=parseContent(inp.content_json);}catch{return result('UNVERIFIABLE',null,'RESEARCH_CONTENT_INVALID','admission');}
  if(c===null&&profile===LEGACY)return result('UNVERIFIABLE','content_withheld',null,'disclosure');
  if(profile===PRIVACY){
    if(c===null||typeof c!=='object'||Array.isArray(c))return result('UNVERIFIABLE',null,'RESEARCH_CONTENT_OBJECT_REQUIRED');
    if(!Object.hasOwn(c,'blinding'))return result('UNVERIFIABLE',null,'RESEARCH_REQUIRED_BLINDING_ABSENT'); // GUARD_REQUIRED
    if(Object.hasOwn(c,'blinding')){
      const b=c.blinding;
      if(!(typeof b==='string'&&/^[0-9a-f]{64}$/.test(b)))return result('UNVERIFIABLE',null,'blinding_malformed'); // GUARD_FORMAT
    }
  }
  const schema=inp.content_schema??'json-integers';
  if(schema==='gps-integers-research.v0'){
    const bounds={latE7:[-900000000,900000000],lonE7:[-1800000000,1800000000],accuracyCm:[0,Number.MAX_SAFE_INTEGER]};
    if(c===null||typeof c!=='object'||Array.isArray(c)||Object.entries(bounds).some(([k,[lo,hi]])=>!Number.isSafeInteger(c[k])||c[k]<lo||c[k]>hi))return result('UNVERIFIABLE',null,'RESEARCH_GPS_RANGE_OR_TYPE');
  }else if(schema!=='json-integers')return result('UNVERIFIABLE',null,'RESEARCH_SCHEMA_UNSUPPORTED');
  if(typeof inp.commitment!=='string'||!/^sha256:[0-9a-f]{64}$/.test(inp.commitment))return result('UNVERIFIABLE',null,'malformed_commitment');
  const preimage=c; // GUARD_PREIMAGE
  const bytes=Buffer.from(canonical(preimage),'utf8');
  const equal='sha256:'+sha(bytes)===inp.commitment; // GUARD_COMPARE
  return result(equal?'VERIFIED':'REFUTED',equal?'content_bound':'content_commitment_mismatch',null,'commitment',bytes);
}
export function report(doc){
  if(!Array.isArray(doc.vectors)||doc.vectors.length===0)throw Error('ZERO_CASES or invalid corpus');
  const out=Object.create(null);
  for(const v of doc.vectors){if(typeof v.name!=='string'||!v.name||Object.hasOwn(out,v.name))throw Error('invalid/duplicate case identity');out[v.name]=verify(v.input);}
  return out;
}
// Stable reporting is separate from the JCS content preimage, and uses only ASCII values here.
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{process.stdout.write(canonical(report(JSON.parse(readFileSync(0,'utf8'))))+'\n');}
  catch(e){process.stderr.write('REPORT_INPUT_UNGRADABLE: '+e.message+'\n');process.exitCode=2;}
}
