// predicate_conformance.v0 — recompute a PIN-RECORD flow: precommit -> conformance-run -> (optional) repair-run.
//
// Origin: the trustless-ai damon-group PIN-RECORD thread (2026-08-17), converging Pavlo's
// authorship-disjointness-floor + precommit-as-consumed-input critique with Merlini's
// two-immutable-objects split. Two record types, each independently recomputable:
//
//   predicate-precommit.v0        — frozen BEFORE any run: the invariant, the mutant, the
//                                     predicate (A_i), and the disjointness claim. Its own
//                                     sha256(JCS(record)) IS precommit_hash — not a separate
//                                     sub-object, so there is exactly one hash to disagree about.
//   predicate-conformance-run.v0  — ONE per run. Consumes precommit_hash as an explicit INPUT
//                                     (never a timestamp/ordering claim), binds gate_commit
//                                     separately (the gate's own code identity, which may predate
//                                     the precommit and is NOT the ancestry anchor), and derives a
//                                     verdict by recomputing observed_hash and comparing it to the
//                                     precommit's own predicate.attribution_hash.
//   predicate-repair-run.v0       — same shape as a conformance-run, for the post-repair check.
//                                     A repair is a BOUND RUN that recomputes, never a stored
//                                     `restores_observed_eq_Ai: true` fact (C5).
//
// What this gate checks (pure recompute over the vector's raw inputs, per this repo's own
// convention — never verifies a caller's claimed hash, always recomputes independently):
//
//   C2  disjointness   mutant.author_identity !== predicate.oracle_author_identity. FIXED 2026-08-18
//                        (Pavlo, recomputed the head, PR #14 review): the prior wording said this
//                        "proves disjoint repository attribution" — overclaimed, since author_identity
//                        is a DECLARED string the vector supplies, never resolved against a real git
//                        repo (author_commit -> git author is not something this vectors-based gate can
//                        do, same structural reason C1 defers ancestry to a real CI step). What this
//                        actually proves: the two DECLARED identity strings differ — does_not_prove
//                        even repository attribution, let alone person/control/toolchain independence.
//                        A real authorship check needs the same real-repo CI step C1 is deferred to.
//   C3  hash recompute  mutant.hash = sha256(JCS(mutant.content)); predicate.attribution_hash =
//                        sha256(JCS({canon_id, value: canonicalize(canon_id, A_i.value)})) — A_i
//                        DECLARES its own canon_id (canon.set.v0 / canon.sequence.v0 /
//                        canon.scalar.v0), and that id is part of the hash preimage, so a change of
//                        canonicalization rule is a change of hash, never a silent re-canon across
//                        versions (Merlini, 2026-08-17). canon.set.v0: a value carrying duplicates
//                        is MALFORMED for a declared set and fails closed (UNRESOLVED/
//                        malformed_predicate) rather than being silently deduped — deduping a
//                        duplicate-bearing "set" hides the exact defect this thread's own
//                        collapsed-marker rule exists to catch; only a duplicate-free value is
//                        accepted, then sorted by JCS-byte order. canon.sequence.v0: order is
//                        significant, duplicates allowed, JCS directly, no sort. canon.scalar.v0:
//                        JCS directly. precommit_hash = sha256(JCS(the whole
//                        predicate-precommit.v0 record)).
//   C4  verdict enum    state in {PASS, CONFORMANCE_FAILED, UNRESOLVED}; reason REQUIRED iff
//                        UNRESOLVED. Disagreement (A_i and observed both exist and differ) and
//                        inability-to-determine (comparison could not complete) are DISTINCT
//                        terminal states with no merge path — collapsing them is exactly the
//                        review_unavailable-class defect this whole thread traces back to.
//                        FIXED 2026-08-18 (Pavlo, PR #14 review, two findings folded together):
//                        (a) malformed_predicate and malformed_observation are now distinct
//                        reasons — this rule's own implementation previously collapsed them, the
//                        exact defect the rule exists to catch; (b) the run objects below are now
//                        actually constructed and their consumes_precommit field checked against
//                        the freshly recomputed precommit_hash BEFORE comparing attribution
//                        hashes — reason precommit_not_consumed — so the suite proves a bound run
//                        consumed the frozen precommit, not just that hash comparison works.
//   C5  repair as a run repair_verdict is computed by the SAME recompute-and-compare path as the
//                        conformance verdict, against the post-repair observed_attribution — never
//                        a pre-asserted boolean.
//
// Deliberately OUT OF SCOPE (C1, git ancestry — "precommit-introducing-commit is a git ancestor
// of run.run_identity"): that is a fact about repository history, not about these JSON records in
// isolation, and belongs in a CI step that runs `git merge-base --is-ancestor` against a real
// repo, not a vectors-based gate. Encoding it here would either fake git operations against
// synthetic commit ids (worthless) or silently narrow the claim to "the vector SAYS it's an
// ancestor" (exactly the unearned-trust shape C1 exists to rule out). Named plainly rather than
// quietly skipped. The SAME real-CI step should also resolve mutant.author_commit and
// predicate.oracle_author_commit to their actual git authors (`git log --format=%an/%ae`) rather
// than trust the declared author_identity strings C2 compares here -- both are real-repo-dependent
// facts this vectors-based gate structurally cannot check, deferred together, not two separate gaps.
//
// Adapter contract for bin/conformance-suite: fixture JSON on stdin -> {name: result} on stdout.

import { createHash } from "node:crypto";

type Json = null | boolean | number | string | Json[] | { [k: string]: Json };

// ---------- canonicalization ----------
// Plain-JCS-in-spirit: recursively key-sorted, compact JSON, UTF-8 — same convention already used
// by conformance/chronicle-checkpoint-continuity-v0/continuity_gate.ts in this repo.
export function jcs(o: Json): string {
  return JSON.stringify(sortKeys(o));
}
function sortKeys(o: Json): Json {
  if (Array.isArray(o)) return o.map(sortKeys);
  if (o && typeof o === "object") {
    const out: { [k: string]: Json } = {};
    for (const k of Object.keys(o).sort()) out[k] = sortKeys((o as any)[k]);
    return out;
  }
  return o;
}
export function sha256hex(s: string): string {
  return createHash("sha256").update(s, "utf8").digest("hex");
}

// A_i is a DECLARED, VERSIONED value: { canon_id, value }. canon_id names which canonicalization
// rule applies, and is itself part of the hash preimage (Merlini, 2026-08-17) — changing the rule
// changes the hash, never a silent re-canonicalization of old records under a new rule.
type CanonId = "canon.set.v0" | "canon.sequence.v0" | "canon.scalar.v0";
export type Attribution = { canon_id: CanonId; value: Json };

const VALID_CANON_IDS: ReadonlySet<string> = new Set([
  "canon.set.v0",
  "canon.sequence.v0",
  "canon.scalar.v0",
]);

type CanonResult = { ok: true; canonicalValue: Json } | { ok: false; reason: string };

// canon.set.v0: value MUST be an array with no duplicate members (by JCS-byte identity). A
// duplicate-bearing input is MALFORMED for a declared set and is REJECTED, not deduped — silently
// dropping the duplicate would hide the exact defect (an implementation feeding a "set" that isn't
// actually one) the same way folding distinct causes into one marker string does. A well-formed
// set is then sorted by JCS-byte order (member order is not semantic for a real set) and emitted
// as a JSON array.
// canon.sequence.v0: value MUST be an array; order IS semantic, duplicates are allowed, no sort.
// canon.scalar.v0: value is JCS'd directly (any non-array shape).
export function canonicalize(a: Attribution): CanonResult {
  if (!VALID_CANON_IDS.has(a.canon_id)) {
    return { ok: false, reason: `unknown canon_id: ${a.canon_id}` };
  }
  if (a.canon_id === "canon.set.v0") {
    if (!Array.isArray(a.value)) return { ok: false, reason: "canon.set.v0 requires an array value" };
    const byteReps = a.value.map((m) => jcs(m));
    const seen = new Set<string>();
    for (const r of byteReps) {
      if (seen.has(r)) return { ok: false, reason: "canon.set.v0: duplicate member — malformed for a declared set" };
      seen.add(r);
    }
    return { ok: true, canonicalValue: [...byteReps].sort().map((r) => JSON.parse(r)) };
  }
  if (a.canon_id === "canon.sequence.v0") {
    if (!Array.isArray(a.value)) return { ok: false, reason: "canon.sequence.v0 requires an array value" };
    return { ok: true, canonicalValue: a.value };
  }
  // canon.scalar.v0 — FIXED 2026-08-18 (Pavlo, PR #14 review): spec says non-array, but this
  // branch previously fell through and silently accepted an array too (a real spec/code mismatch).
  // Reject the shape it's not declared for, same fail-closed discipline as set.v0/sequence.v0.
  if (Array.isArray(a.value)) return { ok: false, reason: "canon.scalar.v0 requires a non-array value" };
  return { ok: true, canonicalValue: a.value };
}

// The hash preimage is {canon_id, value: canonicalized-per-rule} — canon_id sits INSIDE what gets
// hashed, so it is literally part of the preimage, not just documentation alongside it.
export function attributionHash(a: Attribution): CanonResult & { hash?: string } {
  const c = canonicalize(a);
  if (!c.ok) return c;
  return { ...c, hash: sha256hex(jcs({ canon_id: a.canon_id, value: c.canonicalValue })) };
}

// ---------- record recomputation ----------

export type Precommit = {
  record: "predicate-precommit.v0";
  invariant: { definition_hash: string };
  mutant: { id: string; hash: string; author_commit: string; author_identity: string };
  predicate: {
    attribution: Attribution;
    attribution_hash: string | null; // null iff the declared attribution is malformed (C3 fails closed)
    oracle_author_commit: string;
    oracle_author_identity: string;
  };
  independence: { claim: string; checked: string; does_not_prove: string };
};

export function buildPrecommit(
  invariantDefinition: Json,
  mutantContent: Json,
  mutantId: string,
  mutantAuthorCommit: string,
  mutantAuthorIdentity: string,
  attribution: Attribution,
  oracleAuthorCommit: string,
  oracleAuthorIdentity: string
): Precommit {
  const ah = attributionHash(attribution);
  return {
    record: "predicate-precommit.v0",
    invariant: { definition_hash: sha256hex(jcs(invariantDefinition)) },
    mutant: {
      id: mutantId,
      hash: sha256hex(jcs(mutantContent)),
      author_commit: mutantAuthorCommit,
      author_identity: mutantAuthorIdentity,
    },
    predicate: {
      attribution,
      attribution_hash: ah.ok ? ah.hash! : null,
      oracle_author_commit: oracleAuthorCommit,
      oracle_author_identity: oracleAuthorIdentity,
    },
    independence: {
      claim: "disjoint_declared_identity",
      checked: "mutant.author_identity != predicate.oracle_author_identity",
      does_not_prove:
        "repository attribution (author_commit is never resolved against a real git repo -- these are DECLARED strings the vector supplies, not git-verified authors), let alone person / control / toolchain independence -- a checkable floor over declared data, strictly below anything real-repo-grounded. See C1's note on the deferred real-CI step, which should also resolve author_commit -> git author, not just ancestry.",
    },
  };
}

// precommit_hash is only computable when the declared attribution is well-formed — a malformed A_i
// means there is no valid predicate.attribution_hash to fold into the record, so the precommit
// itself cannot be frozen. Fails closed (null), never silently hashed around the gap.
export function precommitHash(p: Precommit): string | null {
  if (p.predicate.attribution_hash === null) return null;
  return sha256hex(jcs(p as unknown as Json));
}

export type Verdict = { state: "PASS" | "CONFORMANCE_FAILED" | "UNRESOLVED"; reason: string | null };

// FIXED 2026-08-18 (Pavlo, PR #14 review, two findings folded into one fix): (a) malformed_predicate
// vs malformed_observation are now DISTINCT reasons -- the prior version returned malformed_predicate
// for BOTH a malformed A_i and a malformed observed_attribution, the exact collapsed-marker defect
// this whole thread's own C4 rule exists to catch, now found inside the rule's own implementation.
// (b) precommit_not_consumed is new: a run whose bound consumes_precommit doesn't match the freshly
// recomputed precommit_hash cannot produce a meaningful verdict (see ConformanceRun/RepairRun below).
const VALID_UNRESOLVED_REASONS = new Set([
  "no_predicate",
  "no_observation",
  "malformed_predicate",
  "malformed_observation",
  "precommit_not_consumed",
  "gate_error",
  "comparison_incomplete",
  "other",
]);

// predicate-conformance-run.v0 / predicate-repair-run.v0 (Merlini, 2026-08-17), now actually
// CONSTRUCTED and CHECKED, not just documented in prose -- FIXED 2026-08-18 (Pavlo, PR #14 review:
// "the run objects are specified but not mechanically exercised... evaluate() currently builds the
// precommit and calls deriveVerdict() directly"). consumes_precommit is the run's own BOUND claim
// about which precommit it consumed; gate_commit/run_identity are carried for completeness (real
// binding/witnessing of those is C1's real-repo-CI job, out of scope here, same as ever) but
// consumes_precommit IS checked here, against the freshly recomputed precommit_hash -- a run that
// doesn't correctly bind to the precommit it claims to consume cannot produce a meaningful verdict.
//
// SCHEMA-COMPLETED 2026-08-18 (Pavlo, second review round: "the spec's predicate-conformance-run.v0
// contains observed_hash and verdict, but the implemented ConformanceRun type contains neither...
// 'the specified run object is now mechanically constructed' still rounds up past what the
// implementation builds"). observed_hash and verdict are now real fields ON the constructed
// object, not values computed separately and left off the record -- see buildConformanceRun /
// buildRepairRun below, which compute both and attach them, matching predicate-conformance-v0.spec.md's
// own JSON shape exactly. verdict here is the SAME value as the top-level conformance_verdict/
// repair_verdict evaluate() returns (one computation, attached in both places it belongs) -- not a
// second independent derivation to keep in sync.
export type ConformanceRun = {
  record: "predicate-conformance-run.v0";
  consumes_precommit: string | null;
  gate_commit: string;
  run_identity: string;
  observed_attribution: Attribution;
  observed_hash: string | null;
  verdict: Verdict;
};

export type RepairRun = {
  record: "predicate-repair-run.v0";
  consumes_precommit: string | null;
  gate_commit: string;
  run_identity: string;
  repaired_mutant_commit: string;
  observed_attribution: Attribution;
  observed_hash: string | null;
  verdict: Verdict;
};

// C4: derive a verdict by recompute-and-compare, never by trusting a caller's claim. Disagreement
// (both sides exist and differ) and inability-to-determine (either side missing/malformed, or the
// run isn't bound to the precommit it claims) are distinct terminal states — never merged into one.
// precommitHashComputed is the FRESH recompute (never the vector's own claimed precommit_hash) --
// the binding check below would be worthless if it compared a claim against itself.
export function deriveVerdict(
  precommit: Precommit,
  precommitHashComputed: string | null,
  run: { consumes_precommit: string | null; observed_attribution?: Attribution } | undefined
): Verdict {
  const attribution = precommit.predicate.attribution;
  if (attribution === undefined || attribution === null) {
    return { state: "UNRESOLVED", reason: "no_predicate" };
  }
  const attrResult = attributionHash(attribution);
  if (!attrResult.ok) {
    return { state: "UNRESOLVED", reason: "malformed_predicate" };
  }
  if (run === undefined) {
    return { state: "UNRESOLVED", reason: "no_observation" };
  }
  // BINDING CHECK, new: a run whose consumes_precommit doesn't match what was actually just
  // recomputed cannot be trusted to have consumed THIS precommit -- checked before comparing
  // attribution hashes, since comparing against the wrong precommit's frozen predicate would be
  // meaningless even if the byte comparison happened to succeed.
  if (run.consumes_precommit !== precommitHashComputed) {
    return { state: "UNRESOLVED", reason: "precommit_not_consumed" };
  }
  const observed = run.observed_attribution;
  if (observed === undefined || observed === null) {
    return { state: "UNRESOLVED", reason: "no_observation" };
  }
  const obsResult = attributionHash(observed);
  if (!obsResult.ok) {
    return { state: "UNRESOLVED", reason: "malformed_observation" };
  }
  return attrResult.hash === obsResult.hash
    ? { state: "PASS", reason: null }
    : { state: "CONFORMANCE_FAILED", reason: null };
}

function verdictValid(v: Verdict): boolean {
  if (!["PASS", "CONFORMANCE_FAILED", "UNRESOLVED"].includes(v.state)) return false;
  if (v.state === "UNRESOLVED") return v.reason !== null && VALID_UNRESOLVED_REASONS.has(v.reason);
  return v.reason === null;
}

// ---------- vector shape ----------

export type Vector = {
  name: string;
  invariant_definition: Json;
  mutant: { id: string; content: Json; author_commit: string; author_identity: string };
  predicate: { attribution: Attribution; oracle_author_commit: string; oracle_author_identity: string };
  observed_attribution?: Attribution | null;
  // Test-only escape hatch for the precommit_not_consumed negative vector: normally the run's
  // consumes_precommit is auto-bound to the freshly recomputed precommit_hash (undefined here
  // means "use the real value"); a vector may override it to a deliberately WRONG hash to prove
  // the binding check actually catches a mis-bound run, not just document that it should.
  run_consumes_precommit_override?: string | null;
  repair?: {
    observed_attribution_after_repair: Attribution;
    repair_consumes_precommit_override?: string | null;
  };
  expected: {
    disjointness_holds: boolean;
    precommit_hash: string | null;
    conformance_verdict: Verdict;
    repair_verdict: Verdict | null;
  };
};

// Computes observed_hash the exact same way attribution_hash is computed (C3's own recipe) --
// null iff the declared observed attribution is malformed, same fail-closed rule as everywhere
// else in this file.
function observedHash(observed: Attribution | undefined | null): string | null {
  if (observed === undefined || observed === null) return null;
  const r = attributionHash(observed);
  return r.ok ? r.hash! : null;
}

export function evaluate(v: Vector) {
  const precommit = buildPrecommit(
    v.invariant_definition,
    v.mutant.content,
    v.mutant.id,
    v.mutant.author_commit,
    v.mutant.author_identity,
    v.predicate.attribution,
    v.predicate.oracle_author_commit,
    v.predicate.oracle_author_identity
  );
  const disjointness_holds =
    precommit.mutant.author_identity !== precommit.predicate.oracle_author_identity;
  const pHash = precommitHash(precommit);

  const hasObservation = v.observed_attribution !== undefined && v.observed_attribution !== null;
  const conformanceConsumes =
    v.run_consumes_precommit_override !== undefined ? v.run_consumes_precommit_override : pHash;
  const conformance_verdict = deriveVerdict(
    precommit,
    pHash,
    hasObservation
      ? { consumes_precommit: conformanceConsumes, observed_attribution: v.observed_attribution as Attribution }
      : undefined
  );
  // Full predicate-conformance-run.v0 object, matching the spec's own JSON shape exactly --
  // observed_hash and verdict are real fields on the record, not values computed separately and
  // left off it (Pavlo, PR #14 second review round).
  const conformanceRun: ConformanceRun | undefined = hasObservation
    ? {
        record: "predicate-conformance-run.v0",
        consumes_precommit: conformanceConsumes,
        gate_commit: "test-gate-commit",
        run_identity: `${v.name}-run`,
        observed_attribution: v.observed_attribution as Attribution,
        observed_hash: observedHash(v.observed_attribution),
        verdict: conformance_verdict,
      }
    : undefined;

  const repairConsumes = v.repair
    ? v.repair.repair_consumes_precommit_override !== undefined
      ? v.repair.repair_consumes_precommit_override
      : pHash
    : null;
  const repair_verdict = v.repair
    ? deriveVerdict(precommit, pHash, {
        consumes_precommit: repairConsumes,
        observed_attribution: v.repair.observed_attribution_after_repair,
      })
    : null;
  const repairRun: RepairRun | undefined = v.repair
    ? {
        record: "predicate-repair-run.v0",
        consumes_precommit: repairConsumes,
        gate_commit: "test-gate-commit",
        run_identity: `${v.name}-repair-run`,
        repaired_mutant_commit: "test-repaired-mutant-commit",
        observed_attribution: v.repair.observed_attribution_after_repair,
        observed_hash: observedHash(v.repair.observed_attribution_after_repair),
        verdict: repair_verdict as Verdict,
      }
    : undefined;

  return {
    disjointness_holds,
    precommit_hash: pHash,
    conformance_verdict,
    repair_verdict,
    conformance_run: conformanceRun,
    repair_run: repairRun,
    // exposed for debugging / self-check readability, not part of the pinned `expected` shape
    _precommit: precommit,
  };
}

function matchesExpected(got: ReturnType<typeof evaluate>, expected: Vector["expected"]): boolean {
  if (got.disjointness_holds !== expected.disjointness_holds) return false;
  if (got.precommit_hash !== expected.precommit_hash) return false;
  if (JSON.stringify(got.conformance_verdict) !== JSON.stringify(expected.conformance_verdict))
    return false;
  if (JSON.stringify(got.repair_verdict) !== JSON.stringify(expected.repair_verdict)) return false;
  if (!verdictValid(got.conformance_verdict)) return false;
  if (got.repair_verdict && !verdictValid(got.repair_verdict)) return false;
  return true;
}

// A deliberately-wrong reference method, matching this repo's own "--tamper" convention: hash the
// precommit by naive concatenation of the child fields instead of JCS-object hashing.
//
// CLAIM CORRECTED 2026-08-18 (Pavlo, second PR #14 review round, recomputed d596a14..dcbdfcd
// himself): the 2026-08-18 fix above added oracle_author_commit to the concatenation, but that
// does NOT demonstrate the "a‖bc == ab‖c" delimiter-collision Merlini originally named. Pavlo's
// exact, correct point: the preimage here is fixed64 ‖ fixed64 ‖ fixed64 ‖ variable_tail — three
// SHA-256 hex fields of KNOWN, FIXED length (64 chars each), with the one variable-length field
// LAST. That arrangement is always unambiguously parseable (split at byte 192, the remainder is
// oracle_author_commit) — there is no live boundary ambiguity in THIS specific field order, no
// matter what oracle_author_commit's own bytes are. A genuine a‖bc == ab‖c collision needs either
// two adjacent variable-length fields, or a variable-length field NOT pinned to a fixed position
// — neither is true of predicate-precommit.v0's actual four fields as concatenated here.
//
// The corrected, honest claim: this is a STRUCTURED-COMMITMENT argument, not a demonstrated
// collision. Hashing the structured JSON object (real delimiters: braces, quotes, commas) is the
// right construction on principle — it doesn't depend on the current field count/order/width
// holding forever (a future schema change, e.g. an inserted field or a second variable-length
// field, could reintroduce real ambiguity in a naive concatenation; JCS-object hashing is immune
// to that by construction, not just today). --tamper still demonstrates that the naive method
// produces a DIFFERENT hash than the correct method across every well-formed vector (confirming
// the two constructions aren't accidentally equivalent), which is real and worth checking — it
// just isn't evidence of the specific collision risk the original framing claimed.
function precommitHashTampered(p: Precommit): string | null {
  if (p.predicate.attribution_hash === null) return null; // same fail-closed rule as the correct method
  return sha256hex(
    p.invariant.definition_hash + p.mutant.hash + p.predicate.attribution_hash + p.predicate.oracle_author_commit
  );
}

function evaluateTampered(v: Vector) {
  const got = evaluate(v);
  const precommit = got._precommit as Precommit;
  return { ...got, precommit_hash: precommitHashTampered(precommit) };
}

if (import.meta.main) {
  const tamper = Bun.argv.includes("--tamper");
  if (Bun.argv.includes("--grade")) {
    const fx = JSON.parse(await Bun.stdin.text());
    const out: Record<string, unknown> = {};
    for (const v of fx.vectors as Vector[]) {
      const got = tamper ? evaluateTampered(v) : evaluate(v);
      const { _precommit, ...pub } = got;
      out[v.name] = pub;
    }
    console.log(JSON.stringify(out));
    process.exit(0);
  }
  // Standalone self-check: recompute each vector and diff against its pinned expected.
  const fx = JSON.parse(
    await Bun.file(`${import.meta.dir}/predicate-conformance-v0.vectors.json`).text()
  );
  let fails = 0;
  for (const v of fx.vectors as Vector[]) {
    const got = tamper ? evaluateTampered(v) : evaluate(v);
    const ok = matchesExpected(got, v.expected);
    if (!ok) fails++;
    console.log(
      `${ok ? "✓" : "✗"} ${v.name.padEnd(34)} disjoint=${got.disjointness_holds} ` +
        `verdict=${got.conformance_verdict.state}${got.conformance_verdict.reason ? "/" + got.conformance_verdict.reason : ""}`
    );
  }
  console.log(
    `${fx.vectors.length - fails}/${fx.vectors.length} reproduced${
      tamper
        ? " (tamper: naive hash concatenation — every WELL-FORMED vector's precommit_hash mismatches by design, not just one; the flaw corrupts every real record, not an edge case. A malformed-attribution vector correctly still matches: precommit_hash is null under both methods, since neither can hash a record that was never built.)"
        : ""
    }`
  );
  process.exit(fails ? 1 : 0);
}
