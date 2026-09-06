// tee-attested-leaf.v0 — reference checker (zero-dep, node:crypto).
//
// OUR HALF of the TeeML fusion joint note (Tiago; review-boundary half is Fede's).
// An enclave inference leaf (the frozen tee-inference-enclave.v0 bundle) enters an ERC-8281
// anchored manifest as an EVIDENCE-CLASS-TAGGED entry: "attested, not recomputed". This checker
// verifies the tag is well-formed AND is committed by the leaf's content-address, so the class
// SURVIVES the manifest fold (the anchored root covers it) and a verifier can never mistake an
// enclave-attested model call for a publicly-recomputable step.
//
// Same vocabulary as trustless-ai/semantic-abi: authority_class + does_not_establish, claim-scoped.
//
// Usage:  node tee-attested-leaf-v0.reference.mjs <vectors.json>   (standalone self-check)
//         node tee-attested-leaf-v0.reference.mjs --grade          (bin/conformance-suite adapter: fixture on stdin -> {results:{name:outcome}} on stdout)
//         node tee-attested-leaf-v0.reference.mjs --digest <leaf.json>   (authoring helper)
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const sha256hex = (s) => createHash("sha256").update(s).digest("hex");

// Recursively key-sorted JSON — the leaf's canonical committed form.
function canonical(v) {
  if (Array.isArray(v)) return "[" + v.map(canonical).join(",") + "]";
  if (v && typeof v === "object") {
    return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + canonical(v[k])).join(",") + "}";
  }
  return JSON.stringify(v);
}

// The fields that MUST be committed by the leaf content-address for the class to survive the fold.
const COMMITTED = ["leaf_kind", "evidence_class", "claim_type", "scope", "does_not_establish", "tee_subclaims", "bundle_digest"];

export function leafDigest(leaf) {
  const committed = {};
  for (const k of COMMITTED) committed[k] = leaf[k];
  return sha256hex(canonical(committed));
}

// Does this attested leaf preserve its evidence class through the anchor? PRESERVED | VIOLATED (+reason).
export function checkLeaf(leaf) {
  // 1. the class marker itself
  const cls = leaf.evidence_class;
  if (!cls) return v("attested tag dropped — no evidence_class; the anchor can't tell this is enclave-attested");
  if (cls === "INDEPENDENT_RECOMPUTATION" || cls === "RECOMPUTED" || cls === "SEMANTIC_VERIFICATION")
    return v(`claims '${cls}' for an enclave model-call root — the model call is attested, never recomputed`);
  if (cls !== "ENCLAVE_ATTESTED")
    return v(`unknown evidence_class '${cls}' for an enclave leaf`);

  // 2. must disclaim recomputation so a consumer can't read the enclave leaf as recomputed
  const dne = Array.isArray(leaf.does_not_establish) ? leaf.does_not_establish : [];
  if (!dne.includes("INDEPENDENT_RECOMPUTATION"))
    return v("does_not_establish omits INDEPENDENT_RECOMPUTATION — a consumer could read the attested model call as recomputed");
  // Execution-integrity ≠ judgment: an enclave attests HOW the call ran, never that its output was correct.
  // (Gap found by @babyblueviper1 running the mirror case against this checker — the judgment axis of the same boundary.)
  if (!dne.includes("SEMANTIC_VERIFICATION"))
    return v("does_not_establish omits SEMANTIC_VERIFICATION — a consumer could read the attested model call as judged correct");

  // 3. the THREE TEE claims stay separate (authenticity ≠ authorization ≠ freshness).
  const t = leaf.tee_subclaims || {};
  for (const k of ["hardware_authentic", "image_authorized", "pcs_fresh"])
    if (!(k in t)) return v(`tee_subclaims.${k} missing — the three TEE claims must be carried explicitly, never collapsed`);
  if (t.image_authorized === true && !leaf.image_authorization_evidence)
    return v("image_authorized asserted true without image_authorization_evidence — conflates hardware authenticity with expected-image authorization");
  if (t.pcs_fresh === true && !leaf.pcs_collateral_evidence)
    return v("pcs_fresh asserted true without pcs_collateral_evidence — conflates authenticity with PCS freshness");

  // 4. the class must be COMMITTED by the content-address, or it won't survive the manifest fold
  if (leaf.leaf_digest !== leafDigest(leaf))
    return v("evidence class is not committed by the leaf content-address — it would not survive the manifest fold (anchored root wouldn't cover the class)");

  return { outcome: "PRESERVED", reason: "attested class well-formed and committed by the content-address; survives the 8281 fold" };
}
const v = (reason) => ({ outcome: "VIOLATED", reason });

// --- CLI (only when run directly, not when imported) ---
if (import.meta.url === pathToFileURL(process.argv[1] || "").href) {
  const args = process.argv.slice(2);
  if (args[0] === "--digest") {
    console.log(leafDigest(JSON.parse(readFileSync(args[1], "utf8"))));
  } else if (args.includes("--grade")) {
    // bin/conformance-suite contract: fixture JSON on stdin -> {results:{name:outcome}} on stdout.
    // A PURE REPORTER — it reports what it recomputed and lets the suite do the judging (compare each
    // outcome to its `expected`), so a wrong outcome surfaces as a clean vector refutation, not as an
    // opaque "adapter exited". tools/run_conformance.py (which reads only the exit code) catches a
    // *tampered vectors file* via the pinned vectors.sha256 (DRIFT), so it stays meaningful too.
    const { vectors } = JSON.parse(readFileSync(0, "utf8"));
    const results = {};
    for (const vec of vectors) results[vec.name] = checkLeaf(vec.leaf).outcome;
    console.log(JSON.stringify({ results }));
    process.exit(0);
  } else if (args[0]) {
    const { vectors } = JSON.parse(readFileSync(args[0], "utf8"));
    let fails = 0;
    console.log("");
    for (const vec of vectors) {
      const got = checkLeaf(vec.leaf);
      const ok = got.outcome === vec.expected;
      if (!ok) fails++;
      console.log(`  ${ok ? "✓" : "✗"} ${vec.name.padEnd(26)} expected ${vec.expected.padEnd(9)} got ${got.outcome}`);
      if (!ok) console.log(`      reason: ${got.reason}`);
    }
    console.log(`\n  ${vectors.length - fails}/${vectors.length} vectors conform\n`);
    process.exit(fails ? 1 : 0);
  } else {
    console.error("usage: node tee-attested-leaf-v0.reference.mjs <vectors.json> | --grade (stdin) | --digest <leaf.json>");
    process.exit(2);
  }
}
