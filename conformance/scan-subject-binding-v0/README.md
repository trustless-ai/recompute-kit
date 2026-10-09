# scan_subject_binding.v0

What does a clean poisoning scan establish about the data a decision **actually consumed**?

A signed, replayable RAG decision can pass every integrity check and still rest on poisoned data. Corpus B is corpus A plus one
inserted document; signatures, Merkle roots and exact replay all verify for both, and the answer flips from `10000 USD` to
`1000000 USD` (c0). PROVENANCE VERIFIED is not POISONING ABSENT.

## Two verifiers, side by side

- `result_only_check` reads only `poisoning_scan.result`. This is the shape of Agent Manifest v0.2 s3.2.5 at
  [`0a2513df`](https://github.com/agentrust-io/agent-manifest/blob/0a2513df6c84d1c35599c9f7b8bdf976f11746bf/spec/agent-manifest-spec-v0.2.md),
  where `poisoning_scan` = {scanner_version, scanned_at, result} carries no digest of what was scanned.
- `subject_bound_check` returns NO_FINDING only when the scan names a `subject_digest` that is the consumed effective dataset, or
  is the corpus root **and** the scanner declares `recordwise` semantics **and** every consumed leaf has an RFC 9162 inclusion
  proof to it. Otherwise CANNOT_ESTABLISH.

## Evidence grade: a scan assertion is not a scan execution

Only NO_FINDING and CONTRADICTED carry an `evidence_grade`: the checker refuses any other verdict that comes back with one (CANNOT_ESTABLISH, NOT_VALID, and any future refusal), at the common `evaluate()` boundary, so a refusal path cannot earn a grade without a vector of its own (mutants M10a-g). c7 is the non-clean control: a signed `flagged` result, the one case where `result_only` must say NOT_VALID (mutant M11).

Every NO_FINDING carries an `evidence_grade`, and the two grades claim different things:

- **AUTHENTICATED_REPORT**: the checker verified an authenticated, manifest-carried assertion over a bound subject. It did
  **not** rerun the scanner, so scanner-origin execution is not established: what is proven is that someone signed "nothing
  found" over these bytes under this declared `scanner_version`, not that the named scanner actually produced that result. Do
  not read this grade as stronger evidence than that.
- **REPRODUCED**: the checker **reran** a published deterministic scanner (`toy_scan` in `vectors.json`) over the subject bytes
  itself and got the same answer. Only this grade says the scan result follows from the data. A rerun can also disagree: in c4b
  the signed result is `clean`, the rerun over the bound subject finds the inserted document, and the verdict is CONTRADICTED,
  while a result-only verifier still says VALID.

NO_FINDING means "this named scanner found nothing in this named subject". It is never POISONING_ABSENT, which matches the reading
Agent Manifest itself requires of a clean scan; that word is outside the checker's vocabulary (mutant M2).

## Cases (`vectors.json`, 12)

| case | point |
|---|---|
| c0 | answer flips while every binding verifies |
| c1 / c1b | scan of A carried with root B, without / with a subject_digest -> CANNOT_ESTABLISH (result-only: VALID) |
| c2 | scan bound to the consumed effective dataset -> NO_FINDING, AUTHENTICATED_REPORT |
| c3 / c3b | scan bound to the corpus root, consumed subset with / without inclusion proofs -> NO_FINDING / CANNOT_ESTABLISH |
| c3c | c3's bytes, scanner declares `corpus_statistical` (not hereditary) -> CANNOT_ESTABLISH |
| c4 / c4b | published deterministic scanner rerun -> NO_FINDING / CONTRADICTED, both REPRODUCED |
| c5 | k=2: `effective_dataset_digest = root(retrieved)` is unordered, profile frozen to k=1 -> CANNOT_ESTABLISH |
| c6 | c2 with one manifest-signature byte flipped: `check_decision()` must refuse it on `signature` and nothing else (end-to-end control; the primitive controls alone cannot see a deleted guard) |
| c7 | c2 with the signed scan result `flagged`: the only case where `result_only` must say NOT_VALID; `subject_bound` refuses with NOT_VALID and no grade (non-clean control, mutants M10b, M11) |

## Run

    python3 scan_check.py vectors.json   # 12/12 reproduced, exit 0 (standard library only)
    python3 mutation_check.py            # 17 one-site mutants, each killed by its named case(s); Ed25519 primitive controls

`scan_check.py` recomputes every Merkle root (Agent Manifest s3.2.5.1), inclusion proof, Ed25519 signature (RFC 8032 reference
verify, stdlib) and answer from the vector bytes. The signing key is a public test key derived from a fixed seed.

## Upstream, kept narrow

The proposed Agent Manifest change is only a required `poisoning_scan.subject_digest` compared to `rag_corpus.merkle_root`.
Effective-set binding, inclusion-proof transfer, scanner semantics and evidence grading are verifier-side rules shown here, not
proposed as manifest fields.

Provenance: built with Pavlo (receiptos) as the first executable witness for the effective-dataset subject-binding case;
first published at babyblueviper1/preaction-governance-conformance@ead6446 (examples/scan-subject-binding), reshaped here as a
recompute-kit profile after his review.
