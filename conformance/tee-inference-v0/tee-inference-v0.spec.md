# tee-inference.v0 — recompute the shell around a TEE-attested LLM inference

Recompute proves everything *around* a model call; it can't re-derive the LLM call itself. A TEE
**attests** `model + input → output` in a sealed enclave — the one link recompute can't cover. Fused,
the chain is verifiable from **two evidence roots of different kinds**: publicly-recomputable + hardware-
attested. This profile pins the fusion for **0G TeeML** — and, crucially, keeps the checks **separated by
evidence class** so a hardware attestation is never silently promoted into a recomputation.

Converged against a **real captured inference** (primary artifact:
[gist `TMerlini/19d532bc…`](https://gist.github.com/TMerlini/19d532bcb627d3ea237c72003d550337) →
`teeml-sample.json`), from the SDK's actual verify path
(`@0gfoundation/0g-compute-ts-sdk` → `broker/response.js` → `broker/verifier.js`):

```js
const ResponseSignature = await Verifier.fetchSignatureByChatID(svc.url, chatID, svc.model); // -> { text, signature }
return Verifier.verifySignature(ResponseSignature.text, ResponseSignature.signature, signingAddress);
// verifySignature: recoverAddress(ethers.hashMessage(text), signature) === expectedAddress   // EIP-191
```

The signed `text` (preimage) is a structured commitment, **not** the answer:

```
H(request) : H(response) : providerType : providerIdentity : H(session)
```

## The four checks — each carries its own evidence class

A verifier reports **per check** (`verified` / `rejected` / `unverifiable`, fail-closed), tagging the
**evidence basis** — `recomputed` (re-derived from public data) vs `attested` (verified against an
externally-supplied policy, *not* re-derived). The checks are **never collapsed** into one pass/fail.

| check | evidence basis | rule |
| --- | --- | --- |
| `signature_recovery` | **recomputed** | `recoverAddress(hashMessage(preimage), signature) == claimed_signer` (EIP-191, 65-byte r,s,v) |
| `response_digest_binding` | **recomputed** | `sha256(response_canonical_string) == H(response)` from the preimage. **Broker canonicalization is `sha256(JSON(completion))`, NOT RFC-8785 JCS** |
| `anti_replay_binding` | **recomputed** | is `chatID` / `zg_res_key` bound *inside* the signed preimage? |
| `enclave_quote_parse` | **attested** | is a local-TEE (dstack) attestation report actually available to parse into an enclave measurement? |

## The findings this profile pins (from the real bytes)

1. **Signature recovery is genuinely independent.** `verify-check1.mjs` in the gist recovers the exact
   signer `0x83df…508cF` from the preimage + signature — an ecrecover the verifier runs itself, not a
   re-trust of the SDK's boolean. → `check1_signer_recovery_match = verified`; one-byte tampers of the
   preimage or the signature → `rejected`.

2. **The TEE signs its own hashes, in `sha256(JSON)` — not our JCS.** `H(response)` reproduces exactly as
   `sha256(JSON.stringify(completion))` (the completion carries the answer). Binding it with **RFC-8785
   JCS** instead yields a **false mismatch** — `check2_wrong_canonicalization_false_mismatch = rejected`.
   The recipe MUST bind through the broker's canonicalization. (Tamper the response → `rejected`.)

3. **chatID is not anti-replay.** The `chatID` / `zg_res_key` is only the fetch key for the signature; it
   is **absent from the signed preimage**. So `anti_replay_binding` is `unverifiable` (fail-closed):
   replay-binding here is transport-level, not cryptographic.

4. **"TeeML" ≠ "enclave-executed" for a relay provider.** The captured provider's
   `/v1/proxy/attestation/report` returns *"LLM attestation report is not available for this provider.
   This service forwards to an upstream API without local TEE attestation"* (headers confirm the model
   runs on **Alibaba Cloud DashScope**). A scan of the entire 0G Galileo TeeML population (2 providers)
   found **no enclave provider**. So `enclave_quote_parse` is `unverifiable` — a **fail-closed amber,
   never a green** — and the profile's `--tamper` models exactly the failure this guards against: an
   implementation that reports the enclave check `verified` with no quote in hand.

## Vectors

`tee-inference-v0.vectors.json` — 8 vectors, every `expected` value recomputed from the primary artifact,
never asserted: 2 `verified` (signer recovery, response digest), 4 `rejected` (two tampers + the wrong-
canonicalization false-mismatch), 2 `unverifiable` (chatID-not-bound, enclave-quote-unavailable). An
implementation is conformant iff it reproduces every per-check verdict + derived value.

```sh
bin/conformance-suite --suite conformance/tee-inference-v0
```

## Out of scope (v0)

- **A green `enclave_quote_parse`.** No live 0G Galileo TeeML provider emits a parseable dstack quote
  today (all forward upstream). When a genuine-enclave provider exists, add a vector that parses the raw
  quote into MRTD/RTMRs and binds the signer to the measurement — `attested` against an externally-
  resolved measurement policy, still *not* re-derived. Until then, `unverifiable` is the honest verdict.
- **Recomputing the model call.** By construction, the inference itself is attested, never recomputed —
  that is the whole point of the fusion.
- **The `H(request)` leg of `response_digest_binding`.** `H(request)` = `sha256(verbatim outgoing HTTP
  body)`; v0 pins the response leg (which carries the answer). The request leg lands when the capture
  records the exact wire body.
