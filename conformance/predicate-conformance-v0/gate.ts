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
//   C2  disjointness   mutant.author_identity !== predicate.oracle_author_identity.
//                        Proves disjoint REPOSITORY ATTRIBUTION only — does_not_prove person/
//                        control/toolchain independence, stated in the record itself, not hidden.
//   C3  hash recompute  mutant.hash = sha256(JCS(mutant.content)); predicate.attribution_hash =
//                        sha256(canonical(A_i)) (set-valued A_i: dedupe, sort members by their own
//                        JCS-byte order, THEN JCS the array — array order is semantic under plain
//                        JCS, scalars/objects canonicalize via JCS directly); precommit_hash =
//                        sha256(JCS(the whole predicate-precommit.v0 record)).
//   C4  verdict enum    state in {PASS, CONFORMANCE_FAILED, UNRESOLVED}; reason REQUIRED iff
//                        UNRESOLVED. Disagreement (A_i and observed both exist and differ) and
//                        inability-to-determine (comparison could not complete) are DISTINCT
//                        terminal states with no merge path — collapsing them is exactly the
//                        review_unavailable-class defect this whole thread traces back to.
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
// quietly skipped.
//
// Adapter contract for bin/conformance-suite: fixture JSON on stdin -> {name: result} on stdout.

import { createHash } from "node:crypto";

type Json = null | boolean | number | string | Json[] | { [k: string]: Json };

// ---------- canonicalization ----------
// Plain-JCS-in-spirit: recursively key-sorted, compact JSON, UTF-8 — same convention already used
// by conformance/chronicle-checkpoint-continuity-v0/continuity_gate.ts in this repo.
function jcs(o: Json): string {
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
function sha256hex(s: string): string {
  return createHash("sha256").update(s, "utf8").digest("hex");
}

// canonical(A_i): set-valued (array) -> dedupe, sort members by their OWN JCS-byte order, emit as
// a JSON array, then JCS the whole thing. Scalar/object A_i -> JCS directly. This is the exact
// fix for the load-bearing counterexample Merlini named: plain JCS fixes object-KEY order but
// leaves ARRAY order semantic, so two logically-identical sets in different member order would
// otherwise hash differently.
function canonicalAttribution(a: Json): string {
  if (Array.isArray(a)) {
    const byteReps = a.map((m) => jcs(m));
    const dedupedSorted = [...new Set(byteReps)].sort();
    return dedupedSorted.join(","); // stable, order-independent representation, then hash below
  }
  return jcs(a);
}
function attributionHash(a: Json): string {
  return sha256hex(canonicalAttribution(a));
}

// ---------- record recomputation ----------

type Precommit = {
  record: "predicate-precommit.v0";
  invariant: { definition_hash: string };
  mutant: { id: string; hash: string; author_commit: string; author_identity: string };
  predicate: {
    attribution: Json;
    attribution_hash: string;
    oracle_author_commit: string;
    oracle_author_identity: string;
  };
  independence: { claim: string; checked: string; does_not_prove: string };
};

function buildPrecommit(
  invariantDefinition: Json,
  mutantContent: Json,
  mutantId: string,
  mutantAuthorCommit: string,
  mutantAuthorIdentity: string,
  attribution: Json,
  oracleAuthorCommit: string,
  oracleAuthorIdentity: string
): Precommit {
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
      attribution_hash: attributionHash(attribution),
      oracle_author_commit: oracleAuthorCommit,
      oracle_author_identity: oracleAuthorIdentity,
    },
    independence: {
      claim: "disjoint_repository_attribution",
      checked: "mutant.author_identity != predicate.oracle_author_identity",
      does_not_prove:
        "person / control / toolchain independence — the parties can still fail the same way; a checkable floor, strictly below independently-grounded.",
    },
  };
}

function precommitHash(p: Precommit): string {
  return sha256hex(jcs(p as unknown as Json));
}

type Verdict = { state: "PASS" | "CONFORMANCE_FAILED" | "UNRESOLVED"; reason: string | null };

const VALID_UNRESOLVED_REASONS = new Set([
  "no_predicate",
  "no_observation",
  "malformed_predicate",
  "gate_error",
  "comparison_incomplete",
  "other",
]);

// C4: derive a verdict by recompute-and-compare, never by trusting a caller's claim. Disagreement
// (both sides exist and differ) and inability-to-determine (either side missing/malformed) are
// distinct terminal states — never merged into one.
function deriveVerdict(attribution: Json | undefined, observed: Json | undefined): Verdict {
  if (attribution === undefined || attribution === null) {
    return { state: "UNRESOLVED", reason: "no_predicate" };
  }
  if (observed === undefined || observed === null) {
    return { state: "UNRESOLVED", reason: "no_observation" };
  }
  const attrHash = attributionHash(attribution);
  const obsHash = attributionHash(observed);
  return attrHash === obsHash
    ? { state: "PASS", reason: null }
    : { state: "CONFORMANCE_FAILED", reason: null };
}

function verdictValid(v: Verdict): boolean {
  if (!["PASS", "CONFORMANCE_FAILED", "UNRESOLVED"].includes(v.state)) return false;
  if (v.state === "UNRESOLVED") return v.reason !== null && VALID_UNRESOLVED_REASONS.has(v.reason);
  return v.reason === null;
}

// ---------- vector shape ----------

type Vector = {
  name: string;
  invariant_definition: Json;
  mutant: { id: string; content: Json; author_commit: string; author_identity: string };
  predicate: { attribution: Json; oracle_author_commit: string; oracle_author_identity: string };
  observed_attribution?: Json;
  repair?: { observed_attribution_after_repair: Json };
  expected: {
    disjointness_holds: boolean;
    precommit_hash: string;
    conformance_verdict: Verdict;
    repair_verdict: Verdict | null;
  };
};

function evaluate(v: Vector) {
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
  const conformance_verdict = deriveVerdict(v.predicate.attribution, v.observed_attribution);
  const repair_verdict = v.repair
    ? deriveVerdict(v.predicate.attribution, v.repair.observed_attribution_after_repair)
    : null;

  return {
    disjointness_holds,
    precommit_hash: pHash,
    conformance_verdict,
    repair_verdict,
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
// precommit by naive concatenation of the child hashes instead of JCS-object hashing. This is the
// exact collision surface Merlini named — sha256(a + b + c) has no delimiter, so a‖bc == ab‖c is a
// live risk once field boundaries aren't structurally fixed (predicate.oracle_author_commit in
// particular is a variable-length git commit id, not a fixed-width hash). Since the correct method
// hashes a structured JSON object (real delimiters: braces, quotes, commas) and the tampered
// method hashes bare concatenation, the two preimages differ in EVERY vector, not just a
// specially-constructed one — precommit_hash mismatches across the whole fixture under --tamper,
// which is itself the honest finding: the flaw corrupts every record built this way, not an edge
// case a narrow counterexample could isolate.
function precommitHashTampered(p: Precommit): string {
  return sha256hex(p.invariant.definition_hash + p.mutant.hash + p.predicate.attribution_hash);
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
        ? " (tamper: naive hash concatenation — EVERY vector's precommit_hash mismatches by design, not just one; the flaw corrupts every record, not an edge case)"
        : ""
    }`
  );
  process.exit(fails ? 1 : 0);
}
