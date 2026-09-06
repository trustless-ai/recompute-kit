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

## What this leaf may / may not assert
- **May:** the model call ran inside a genuine, measured enclave whose quote is hardware-rooted and bound to
  the recovered response signer (execution integrity).
- **May not:** that the model's *judgment* was correct, or that any part of the model call was independently
  *recomputed*. Those are Fede's review-boundary half and the recompute lane respectively.

## Conformance

`tee-attested-leaf-v0.vectors.json` — 6 vectors, standalone reference passes 6/6
(`node tee-attested-leaf-v0.reference.mjs tee-attested-leaf-v0.vectors.json`): 1 `PRESERVED` (well-formed) +
5 `VIOLATED` negatives that MUST fail — tag dropped · `INDEPENDENT_RECOMPUTATION` claimed for the enclave root ·
recompute-disclaimer omitted · authenticity conflated with image authorization · class not committed by the
content-address (won't survive the fold).

## Open / for Fede + review
- **Review-boundary section (Fede):** execution-integrity vs judgment — what an attested leaf may/may not assert.
- **Shared evidence-class enum:** converge `ENCLAVE_ATTESTED` + the `does_not_establish` classes with semantic-abi's set.
- **CI wiring:** the standalone reference passes; aligning the stdio adapter I/O to `bin/conformance-suite`'s
  contract is the one integration step left (see `suite.json`).
- **`bundle_digest`:** pin to the real `tee-inference-enclave.v0` bundle content-address (placeholder here).
