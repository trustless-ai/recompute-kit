// verdict-profile-binding.v0 — executable reference for the RESOLUTION-end binding: did the resolver's
// verdict actually commit, in its signed preimage, to the verification profile it resolved under?
// The companion of profile-amendment-v0 (amendment end). Cross-language control for verdict_binding_gate.py:
// a hand-written recursive jcs (not JSON.stringify of a sorted object) reproduces the same pinned vectors
// byte-for-byte. Run with bun (the suite's runtime) or node; no deps beyond node:crypto.
//
// Scope: checks the binding (resolver signed_digest === verdict_core_cc), not signature cryptography.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

function jcs(v) {
  if (Array.isArray(v)) return "[" + v.map(jcs).join(",") + "]";
  if (v && typeof v === "object")
    return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + jcs(v[k])).join(",") + "}";
  return JSON.stringify(v);
}
const sha256hex = (s) => createHash("sha256").update(Buffer.from(s, "utf8")).digest("hex");

export function verdictBinding(v) {
  const core = v.verdict_core;
  const taskEffective = v.task_effective_profile_commitment;
  const resolver = v.resolver_sig ?? null;

  const verdict_core_cc = sha256hex(jcs(core));
  const coreProfile = core.effective_profile_commitment ?? null;

  const profile_bound = coreProfile !== null && coreProfile === taskEffective;
  const signed_here = !!(resolver && resolver.signed_digest && resolver.signed_digest === verdict_core_cc);

  const bound = !!(profile_bound && signed_here);
  const resolution_status = bound ? "bound" : "unresolved";
  const bound_profile_commitment = bound ? coreProfile : null;
  return { verdict_core_cc, resolution_status, bound_profile_commitment };
}

// --- runner: reproduce the pinned vectors, exit 1 on any mismatch ---
const KEYS = ["verdict_core_cc", "resolution_status", "bound_profile_commitment"];
const path = process.argv.find((a, i) => i >= 2 && !a.startsWith("-")) ||
  new URL("./verdict-profile-binding-v0.vectors.json", import.meta.url).pathname;
const doc = JSON.parse(readFileSync(path, "utf8"));
let fails = 0;
for (const v of doc.vectors) {
  const got = verdictBinding(v), exp = v.expect;
  const ok = KEYS.every((k) => got[k] === exp[k]);
  if (!ok) fails++;
  console.log(`${ok ? "OK " : "BAD"} ${v.name.padEnd(34)} status=${String(got.resolution_status).padEnd(10)} verdict_core_cc=${got.verdict_core_cc.slice(0, 12)}`);
}
console.log(`${doc.vectors.length - fails}/${doc.vectors.length} vectors reproduced (JS reference == verdict_binding_gate.py)`);
process.exit(fails ? 1 : 0);
