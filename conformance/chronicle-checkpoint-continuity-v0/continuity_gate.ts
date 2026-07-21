// Independent (clean-room) implementation of the Chronicle Checkpoint Continuity v0 gate.
//
// Thesis in one line: the authority is the spec + vectors, never any one implementation.
// This is a *second* implementation, built ONLY from:
//   - docs/CHRONICLE_CHECKPOINT_CONTINUITY_V0.md  (the gate spec)
//   - docs/CHRONICLE.md                            (base v0 root derivation + local-verify scope)
//   - tests/fixtures/chronicle-root-golden-vectors.json  (pins canonicalization)
// all from pipavlo82/crystal-receipt @ 4ee5a8d0 (#98), and NOT from that repo's src/**,
// which was never opened. It is conformant iff it reproduces every `expected` from the same
// inputs. Divergence from the reference implementation would mean a bug or a spec ambiguity
// in one of the two — found in a single pass, which is the point.
//
// Run:  bun continuity_gate.ts
// Vectors (continuity-vectors.json, chronicle-root-golden-vectors.json) are Pavlo's, vendored
// here for runnability; the upstream fixtures remain the normative authority.

import { createHash } from "node:crypto";

// ---------- base v0 root derivation (from CHRONICLE.md + golden vectors) ----------
// root = "sha256:" + sha256( canonicalize({ canonical fields; ref arrays lexicographically sorted }) )
// canonicalize = deterministic JSON: recursively key-sorted, compact, UTF-8.
// Output/annotation fields (metadata, checkpoint_root, ...) are NOT part of the derivation.
const REF_KEYS = new Set(["entry_refs", "receipt_refs", "artifact_refs", "collection_refs"]);
const NONCANON = new Set(["metadata", "checkpoint_root", "receipt_root", "root"]);

function canon(o: unknown): unknown {
  if (Array.isArray(o)) return o.map(canon);
  if (o && typeof o === "object") {
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(o as Record<string, unknown>).sort()) {
      if (NONCANON.has(k)) continue;
      const v = (o as Record<string, unknown>)[k];
      out[k] = REF_KEYS.has(k) && Array.isArray(v) ? [...(v as string[])].sort() : canon(v);
    }
    return out;
  }
  return o;
}

function deriveRoot(cp: Record<string, unknown>): string {
  return "sha256:" + createHash("sha256").update(JSON.stringify(canon(cp)), "utf8").digest("hex");
}

// ---------- local checkpoint verify (CHRONICLE.md verification scope) ----------
// "does recomputation over the stored content in canonical form yield the stored root?"
//  + checkpoint additionally requires stored entry_refs to already be in canonical order.
function entryRefsCanonical(cp: any): boolean {
  const e: string[] = cp.entry_refs ?? [];
  for (let i = 1; i < e.length; i++) if (e[i - 1] > e[i]) return false;
  return true;
}
function localVerify(cp: any): boolean {
  return deriveRoot(cp) === cp.checkpoint_root && entryRefsCanonical(cp);
}

// ---------- shape rules (continuity spec, "Shape rules used by this profile") ----------
function shapeValid(cp: any): boolean {
  const s = cp.sequence;
  if (typeof s !== "number" || !Number.isInteger(s)) return false;   // MUST be an integer
  if (s < 0) return false;                                            // MUST be >= 0
  if (s === 0 && cp.prev_checkpoint !== null) return false;          // seq 0 requires prev null
  if (s > 0 && cp.prev_checkpoint === null) return false;           // seq > 0 requires non-null prev
  return true;
}

// ---------- result shape ----------
type Result = {
  evaluation_state: "evaluated" | "unverifiable" | "malformed" | "not_evaluated";
  verdict: "valid" | "invalid" | null;
  relation: "genesis" | "successor" | null;
  reason_code: string;
};
const R = (evaluation_state: any, verdict: any, relation: any, reason_code: string): Result =>
  ({ evaluation_state, verdict, relation, reason_code });

// ---------- the gate (continuity spec, "Normative evaluation order" + "Exact outcomes") ----------
function evaluate(current: any, predecessor: any | null): Result {
  // 1. validate current checkpoint shape
  if (!shapeValid(current)) return R("malformed", null, null, "current_shape_malformed");
  // 2. verify current checkpoint locally
  if (!localVerify(current)) return R("not_evaluated", null, null, "current_local_verifier_failed");
  // 3. classify genesis (short-circuits before predecessor resolution)
  if (current.sequence === 0 && current.prev_checkpoint === null)
    return R("evaluated", "valid", "genesis", "genesis");
  // 4. non-genesis: resolve predecessor candidate
  if (predecessor == null) return R("unverifiable", null, null, "predecessor_unknown");
  // 5. validate predecessor shape
  if (!shapeValid(predecessor)) return R("malformed", null, null, "predecessor_shape_malformed");
  // 6. verify predecessor locally
  if (!localVerify(predecessor)) return R("not_evaluated", null, null, "predecessor_local_verifier_failed");
  // 7. compare current.prev_checkpoint with predecessor.checkpoint_root (BEFORE sequence)
  if (current.prev_checkpoint !== predecessor.checkpoint_root)
    return R("evaluated", "invalid", null, "predecessor_ref_mismatch");
  // 8. classify the sequence relation (ref already matches)
  const ps = predecessor.sequence, cs = current.sequence;
  if (ps === cs - 1) return R("evaluated", "valid", "successor", "direct_successor");
  if (ps < cs - 1)   return R("evaluated", "invalid", null, "sequence_gap");
  if (ps === cs)     return R("evaluated", "invalid", null, "predecessor_same_sequence");
  return R("evaluated", "invalid", null, "predecessor_higher_sequence"); // ps > cs
}

export { deriveRoot, localVerify, shapeValid, evaluate };

// ---------- self-check canonicalization against golden roots, then run all vectors ----------
if (import.meta.main) {
  const golden = JSON.parse(await Bun.file(`${import.meta.dir}/chronicle-root-golden-vectors.json`).text());
  let gok = 0, gtot = 0;
  for (const cat of ["artifact", "collection", "portfolio", "checkpoint"] as const)
    for (const v of golden[cat]) { gtot++; if (deriveRoot(v.input) === v.expected_root) gok++; }
  console.log(`canonicalization self-check (golden roots): ${gok}/${gtot} ${gok === gtot ? "OK" : "MISMATCH"}`);

  const fixture = JSON.parse(await Bun.file(`${import.meta.dir}/continuity-vectors.json`).text());
  let pass = 0; const fails: string[] = [];
  console.log(`\nrunning ${fixture.vectors.length} continuity vectors:\n`);
  for (const v of fixture.vectors) {
    const got = evaluate(v.current, v.predecessor ?? null);
    const e = v.expected;
    const ok = got.evaluation_state === e.evaluation_state && got.verdict === e.verdict &&
               got.relation === e.relation && got.reason_code === e.reason_code;
    if (ok) pass++; else fails.push(v.name);
    console.log(`  ${ok ? "[PASS]" : "[FAIL]"}  ${v.name.padEnd(56)} -> ${got.reason_code}`);
    if (!ok) console.log(`          expected ${JSON.stringify(e)}\n          got      ${JSON.stringify(got)}`);
  }
  console.log(`\n=== ${pass}/${fixture.vectors.length} vectors agree with pinned expected ===`);
  if (fails.length) { console.log("FAILURES:", fails.join(", ")); process.exit(1); }
  console.log("Independent implementation agrees with the fixture on every vector.");
}
