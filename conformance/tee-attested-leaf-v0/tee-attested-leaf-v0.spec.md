# tee-attested-leaf.v0 — a genuine-enclave leaf, class-preserving through the 8281 fold

**First cut — Tiago's half of the TeeML fusion joint note** (Fede owns the review-boundary half:
execution-integrity vs judgment). Shoot at it.

The companion to [`tee-inference-enclave.v0`](../tee-inference-enclave-v0/). That profile *recomputes*
everything **around** a live enclave inference (signer recovery, request/response digests, RTMR replay,
`report_data`↔signer, on-chain registry binding, dcap hardware root) — but, in its own words, *"the model
call itself is attested by the enclave, never recomputed — that's the whole point of the fusion."*

This profile pins the other half: **how that attested leaf enters an ERC-8281 anchored manifest without
losing its evidence class.** It is an *evidence-class-tagged* entry — **attested, not recomputed** — and the
tag is load-bearing: when the manifest chain folds this leaf, a verifier recomputing the manifest sees
*"this link's evidence root is a genuine-enclave TDX quote — independently verifiable but hardware-attested"*
and can never mistake it for a publicly-recomputable step.

Same vocabulary as [`trustless-ai/semantic-abi`](https://github.com/trustless-ai/semantic-abi): an
`EvidenceClaim` with an `authority_class` and an explicit `does_not_establish` set. This leaf's class is
`ENCLAVE_ATTESTED`; it explicitly does **not** establish `INDEPENDENT_RECOMPUTATION` (Pavlo's rule — the
disclaimer is what makes a downstream authority-upgrade a detectable TYPE ERROR).

## The manifest entry

```json
{
  "leaf_kind":         "tee_enclave_inference",
  "evidence_class":    "ENCLAVE_ATTESTED",
  "claim_type":        "model_inference_result",
  "scope":             "0g:glm-5.2:action:<id>",
  "does_not_establish":["INDEPENDENT_RECOMPUTATION","SEMANTIC_VERIFICATION"],
  "tee_subclaims":     { "hardware_authentic": true, "image_authorized": null, "pcs_fresh": null },
  "bundle_digest":     "<content-address of the frozen tee-inference-enclave.v0 evidence bundle>",
  "leaf_digest":       "<sha256 of the canonical committed subset — see below>"
}
```

## Fold mechanics (why the class survives)

`leaf_digest = sha256(canonical({leaf_kind, evidence_class, claim_type, scope, does_not_establish,
tee_subclaims, bundle_digest}))`. The **evidence class is part of what the content-address commits.** ERC-8281
anchors the manifest root over these `leaf_digest`s — so the root covers the class, and the class travels
through the fold. A leaf whose `leaf_digest` was computed over a class-less preimage (folded as a plain step)
fails: the class would not survive the anchor. *The tag is not metadata beside the evidence — it is inside
what gets anchored.*

## The three TEE claims stay separate

Carried straight from `tee-inference-enclave.v0`'s out-of-scope section — **authenticity ≠ authorization ≠
freshness**:
1. `hardware_authentic` — genuine Intel-provisioned TDX part (dcap root). *Recomputed in the bundle.*
2. `image_authorized` — MRTD matches 0G's published glm-5.2 measurement. *Honest residual — `null` until evidenced.*
3. `pcs_fresh` — TCB current/unrevoked vs Intel PCS collateral. *Separate liveness claim — `null` until evidenced.*

The schema keeps all three explicit. Asserting `image_authorized`/`pcs_fresh` = `true` **requires** an
accompanying evidence field; asserting it bare conflates authenticity with authorization/freshness and fails.

## Review boundary — execution-integrity vs judgment
*This section by @babyblueviper1 (from the PR review) — the review-boundary half of the joint note.*

**What an `ENCLAVE_ATTESTED` leaf may assert:** the model call executed inside a genuine, measured TEE, and the
response is cryptographically bound to that execution (`hardware_authentic`, recomputed from real dcap/RTMR
evidence in the companion `tee-inference-enclave.v0` bundle). This is **execution-integrity** — a claim about
*where and how* the computation ran, fully mechanical, independently checkable from the enclave's own quote.

**What it may not assert:** that the model's output was *correct* — semantically sound, policy-compliant, safe
to act on. That is **judgment**, structurally a different kind of claim: it needs an evaluator with the
authority and context to say "this specific output was right," and no amount of hardware attestation touches
that question. A TEE can attest that an unmodified model ran the input through — it cannot attest that the
answer was good. Collapsing the two is the exact authority-upgrade `does_not_establish` exists to block, on the
*judgment* axis instead of the *recomputation* axis.

**Concrete precedent (not just a definition):** invinoveritas's own `/review` verdict already carries this split
under a different name — every verdict binds a `source_class` and a mechanically-derived `vantage_limitation`,
computed as a pure function of `(source_class, artifact_type)`
(`services/proof_signing.py::_compute_vantage_limitation`) so a verifier recomputes it rather than trusting a
free-text string. The parallel: `does_not_establish` discloses what an *execution-integrity* leaf doesn't
cover; `vantage_limitation` discloses what a *judgment* verdict's vantage doesn't cover. Same discipline, both
sides of the same boundary — which is why `SEMANTIC_VERIFICATION` sits in `does_not_establish` with the same
weight as `INDEPENDENT_RECOMPUTATION`.

## Evidence-class enum (v0 — shared with semantic-abi)
Pinned string values, identical to `trustless-ai/semantic-abi`'s `authority_class` set:
- `ENCLAVE_ATTESTED` — execution-integrity via a genuine, measured enclave (this leaf's class).
- `INDEPENDENT_RECOMPUTATION` — re-derived from public bytes (disclaimed by this leaf).
- `SEMANTIC_VERIFICATION` — the output judged correct (disclaimed by this leaf).

A joint note with semantic-abi will pin the full shared set; these three strings are fixed.

## Conformance

`tee-attested-leaf-v0.vectors.json` — 7 vectors, standalone reference passes 7/7
(`node tee-attested-leaf-v0.reference.mjs tee-attested-leaf-v0.vectors.json`): 1 `PRESERVED` (well-formed) +
6 `VIOLATED` negatives that MUST fail — tag dropped · `INDEPENDENT_RECOMPUTATION` claimed for the enclave root ·
recompute-disclaimer omitted · **semantic-verification-disclaimer omitted** · authenticity conflated with image
authorization · class not committed by the content-address (won't survive the fold).

> The `SEMANTIC_VERIFICATION` gate (+ its negative vector) was added after @babyblueviper1 ran the mirror case
> against this checker in review: it disclaimed the *recomputation* axis but not the *judgment* axis, so a leaf
> omitting the "not judged correct" disclaimer passed — the exact green-but-adjacent hole this profile catches,
> in our own checker. Execution integrity ≠ judgment: both axes are now gated with equal weight.

## Open / next
- [x] **Review boundary** — execution-integrity vs judgment (folded in above, @babyblueviper1).
- [x] **Shared evidence-class enum** — the three strings pinned; full shared set → joint note with semantic-abi.
- [ ] **CI wiring:** align the stdio adapter I/O to `bin/conformance-suite`'s contract (standalone reference passes 7/7).
- [ ] **`bundle_digest`:** pin to the real `tee-inference-enclave.v0` bundle content-address (placeholder here).
