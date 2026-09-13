// profile-amendment.v0 — executable reference for the AUTHORIZED-transition logic: is a change from
// verification profile A to profile B a co-signed amendment, or an unauthorized swap? Sibling to
// companion-envelope-v0.reference.mjs. Cross-language control for amendment_gate.py: a hand-written
// recursive jcs (not JSON.stringify of a sorted object) reproduces the same pinned vectors byte-for-byte,
// so agreement is between two independent implementations, not one implementation checked against itself.
// Run with bun (the suite's runtime) or node; no deps beyond node:crypto.
//
// Scope: this reference checks the BINDING (an authorization is bound iff signed_digest === amendment_cc,
// exactly as companion-envelope checks content_address === verdict_core_cc). Signature cryptography
// (ML-DSA / ECDSA validity) rides the separate signature lane and is intentionally not recomputed here.
import { createHash } from "node:crypto";
import { readFileSync, realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

function jcs(v) {
  if (Array.isArray(v)) return "[" + v.map(jcs).join(",") + "]";
  if (v && typeof v === "object")
    return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + jcs(v[k])).join(",") + "}";
  return JSON.stringify(v);
}
const sha256hex = (s) => createHash("sha256").update(Buffer.from(s, "utf8")).digest("hex");
const profileCc = (profile) => sha256hex(jcs(profile));

export function profileTransition(v) {
  const inForce = v.in_force_profile;
  const proposed = v.proposed_profile;
  const escrowRef = v.escrow_ref;
  const amendment = v.amendment ?? null;
  const authorizations = v.authorizations ?? {};
  const required = v.required_parties ?? ["buyer", "supplier"];

  const prior_profile_commitment = profileCc(inForce);
  const new_profile_commitment = profileCc(proposed);

  let amendment_cc = null;
  let amend_binds = false;
  if (amendment) {
    // recompute amendment_cc from the amendment's OWN declared fields (what its signers saw)
    const preimage = {
      schema: "profile-amendment.v0",
      prior_profile_commitment: amendment.prior_profile_commitment ?? null,
      new_profile_commitment: amendment.new_profile_commitment ?? null,
      escrow_ref: amendment.escrow_ref ?? null,
    };
    amendment_cc = sha256hex(jcs(preimage));
    amend_binds =
      amendment.prior_profile_commitment === prior_profile_commitment &&
      amendment.new_profile_commitment === new_profile_commitment &&
      amendment.escrow_ref === escrowRef;
  }

  const bound = (party) => {
    const a = authorizations[party];
    return !!(a && a.signed_digest && amendment_cc !== null && a.signed_digest === amendment_cc);
  };
  const all_authorized = amendment_cc !== null && required.every(bound);

  const permitted = !!(amend_binds && all_authorized);
  const transition_status = permitted ? "permitted" : "unresolved";
  // fail closed: an unauthorized change never takes effect; the in-force profile is unchanged.
  const effective_profile_commitment = permitted ? new_profile_commitment : prior_profile_commitment;
  return {
    prior_profile_commitment,
    new_profile_commitment,
    amendment_cc,
    transition_status,
    effective_profile_commitment,
  };
}

// --- runner: reproduce the pinned vectors, exit 1 on any mismatch ---
// Runs only when invoked directly, not when imported for composition (profile-commitment-loop-v0).
let _runDirectly = false;
try { _runDirectly = !!process.argv[1] && realpathSync(fileURLToPath(import.meta.url)) === realpathSync(process.argv[1]); } catch {}
if (_runDirectly) {
const KEYS = ["prior_profile_commitment", "new_profile_commitment", "amendment_cc",
  "transition_status", "effective_profile_commitment"];
const path = process.argv.find((a, i) => i >= 2 && !a.startsWith("-")) ||
  new URL("./profile-amendment-v0.vectors.json", import.meta.url).pathname;
const doc = JSON.parse(readFileSync(path, "utf8"));
let fails = 0;
for (const v of doc.vectors) {
  const got = profileTransition(v), exp = v.expect;
  const ok = KEYS.every((k) => got[k] === exp[k]);
  if (!ok) fails++;
  console.log(`${ok ? "OK " : "BAD"} ${v.name.padEnd(34)} status=${String(got.transition_status).padEnd(10)} amendment_cc=${String(got.amendment_cc).slice(0, 12)}`);
}
console.log(`${doc.vectors.length - fails}/${doc.vectors.length} vectors reproduced (JS reference == amendment_gate.py)`);
process.exit(fails ? 1 : 0);
}
