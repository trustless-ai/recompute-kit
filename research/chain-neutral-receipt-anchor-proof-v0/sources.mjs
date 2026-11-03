// External source reuse, not redistributed Apache-2.0 implementation code.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve, dirname} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
export const HERE=dirname(fileURLToPath(import.meta.url));
export const SOURCES=process.env.CHAIN_PROOF_SOURCES;
if(!SOURCES) throw new Error('SOURCE_DEPENDENCY_MISSING: set CHAIN_PROOF_SOURCES');
const pins=JSON.parse(readFileSync(resolve(HERE,'SOURCE_PINS.json')));
for(const repo of pins.repositories.filter(x=>x.runtime)) {
  for(const [file,expected] of Object.entries(repo.files)) {
    const actual=createHash('sha256').update(readFileSync(resolve(SOURCES,repo.directory,file))).digest('hex');
    if(actual!==expected) throw new Error('SOURCE_DRIFT: '+repo.directory+'/'+file);
  }
}
const load=p=>import(pathToFileURL(resolve(SOURCES,'receiptos',p)).href);
export const strict=await load('src/core/strict-json.mjs');
export const capsule=await load('src/core/capsule.mjs');
export const anchor=await load('research/agent-action-browser-verify-v0/lib/anchor.mjs');
