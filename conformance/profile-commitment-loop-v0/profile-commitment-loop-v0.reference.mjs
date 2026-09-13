// profile-commitment-loop.v0 — executable reference for the WHOLE loop, chaining the two shipped gates over
// the same task+escrow so the seam is a mechanical check, not a shared constant. Composition, not
// reimplementation: it imports profileTransition (#40) and verdictBinding (#41) and feeds the amendment's
// COMPUTED effective_profile_commitment as the resolution gate's task_effective — so the resolution gate's
// own profile-match predicate becomes the seam check. Cross-language control for loop_gate.py.
// Run with bun (the suite's runtime) or node; no deps beyond node:crypto (via the imported references).
import { readFileSync } from "node:fs";
import { profileTransition } from "../profile-amendment-v0/profile-amendment-v0.reference.mjs";
import { verdictBinding } from "../verdict-profile-binding-v0/verdict-profile-binding-v0.reference.mjs";

export function loop(v) {
  const transition = profileTransition({
    in_force_profile: v.in_force_profile,
    proposed_profile: v.proposed_profile,
    escrow_ref: v.escrow_ref,
    amendment: v.amendment ?? null,
    authorizations: v.authorizations ?? {},
    required_parties: v.required_parties ?? ["buyer", "supplier"],
  });
  // seam: feed the amendment's computed effective as the resolution gate's task_effective
  const binding = verdictBinding({
    verdict_core: v.verdict_core,
    task_effective_profile_commitment: transition.effective_profile_commitment,
    resolver_sig: v.resolver_sig ?? null,
  });
  const closed = transition.transition_status === "permitted" && binding.resolution_status === "bound";
  return {
    transition_status: transition.transition_status,
    resolution_status: binding.resolution_status,
    effective_profile_commitment: transition.effective_profile_commitment,
    bound_profile_commitment: binding.bound_profile_commitment,
    loop_status: closed ? "closed" : "open",
  };
}

// --- runner: reproduce the pinned vectors, exit 1 on any mismatch ---
const KEYS = ["transition_status", "resolution_status", "effective_profile_commitment",
  "bound_profile_commitment", "loop_status"];
const path = process.argv.find((a, i) => i >= 2 && !a.startsWith("-")) ||
  new URL("./profile-commitment-loop-v0.vectors.json", import.meta.url).pathname;
const doc = JSON.parse(readFileSync(path, "utf8"));
let fails = 0;
for (const v of doc.vectors) {
  const got = loop(v), exp = v.expect;
  const ok = KEYS.every((k) => got[k] === exp[k]);
  if (!ok) fails++;
  console.log(`${ok ? "OK " : "BAD"} ${v.name.padEnd(34)} loop=${String(got.loop_status).padEnd(7)} transition=${String(got.transition_status).padEnd(10)} resolution=${got.resolution_status}`);
}
console.log(`${doc.vectors.length - fails}/${doc.vectors.length} vectors reproduced (JS reference == loop_gate.py; composes #40 + #41)`);
process.exit(fails ? 1 : 0);
