// companion-envelope.v0 — executable reference for the HASHING-RELEVANT logic of the gateway's
// companionEnvelope (vertice-gateway src/lib/pqAgent.ts: jcs, attestationContentAddress, companionEnvelope).
//
// This is a SEMANTICALLY-EQUIVALENT EXTRACTION, not a character-for-character copy: the TypeScript types,
// the gateway's fuller return metadata, and the gateway runtime context are intentionally not included —
// only the byte-producing construction. Run with bun (the gateway's runtime) or node; no deps beyond
// node:crypto.
//
// What it establishes: the Half B BYTE CONSTRUCTION. It reproduces this suite's pinned vectors byte-for-byte
// (committed case companion_cc 01e2d5fc…, envelope_cc b9d7c291…), cross-language with the Python gate
// (envelope_gate.py), and its hashing-relevant construction matches the reviewed gateway patch
// (sha256 97a2d1dc…). It is NOT an independent build of the private gateway, nor a deployed-code identity —
// that is the gateway operator's full private build/tests. (Scope per @pipavlo82's #33 review.)
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

// --- verbatim from pqAgent.ts ---
function jcs(v) {
  if (Array.isArray(v)) return "[" + v.map(jcs).join(",") + "]";
  if (v && typeof v === "object")
    return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + jcs(v[k])).join(",") + "}";
  return JSON.stringify(v);
}
const sha256hex = (s) => createHash("sha256").update(Buffer.from(s, "utf8")).digest("hex");

function attestationContentAddress(f) {
  const content = jcs({
    raw_input_hash: f.raw_input_hash ?? null,
    sanitization_pipeline_hash: f.sanitization_pipeline_hash ?? null,
    input_hash: f.input_hash ?? null,
    output_hash: f.output_hash ?? null,
    manifest_hash: f.manifest_hash ?? null,
    agent_id: f.agent_id ?? null,
    registry: (f.registry ?? "").toLowerCase() || null,
  });
  return sha256hex(content);
}

export function companionEnvelope(core, companion) {
  const verdict_core_cc = attestationContentAddress(core);
  let companion_cc = null;
  let companion_status = "unresolved";
  // content_address MUST be present AND === verdict_core_cc; absent is never back-filled (recompute-kit #32).
  const belongs = !!(companion && companion.pq_pubkey && companion.signature_hex &&
    companion.content_address && companion.content_address === verdict_core_cc);
  if (belongs && companion) {
    const companionObj = { signed_digest: verdict_core_cc, pq_pubkey: String(companion.pq_pubkey), ml_dsa_signature: String(companion.signature_hex) };
    companion_cc = sha256hex(jcs(companionObj));
    companion_status = "committed";
  }
  const envelope = { schema: "companion-envelope.v0", verdict_core_cc, companion_cc };
  const envelope_cc = sha256hex(jcs(envelope));
  return { verdict_core_cc, companion_cc, companion_status, envelope_cc };
}

// --- runner: reproduce the pinned vectors, exit 1 on any mismatch ---
const path = process.argv.find((a, i) => i >= 2 && !a.startsWith("-")) ||
  new URL("./companion-envelope-v0.vectors.json", import.meta.url).pathname;
const doc = JSON.parse(readFileSync(path, "utf8"));
let fails = 0;
for (const v of doc.vectors) {
  const got = companionEnvelope(v.core, v.companion ?? null), exp = v.expect;
  const ok = ["verdict_core_cc", "companion_cc", "companion_status", "envelope_cc"].every((k) => got[k] === exp[k]);
  if (!ok) fails++;
  console.log(`${ok ? "OK " : "BAD"} ${v.name.padEnd(34)} status=${String(got.companion_status).padEnd(10)} companion_cc=${String(got.companion_cc).slice(0, 12)}`);
}
console.log(`${doc.vectors.length - fails}/${doc.vectors.length} vectors reproduced (TS/JS reference == gateway companionEnvelope)`);
process.exit(fails ? 1 : 0);
