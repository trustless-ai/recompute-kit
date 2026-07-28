# tee-inference-enclave.v0 — a fully-recomputed genuine-enclave TeeML inference

The companion to [`tee-inference.v0`](../tee-inference-v0/) (the *relay* evidence-class vector). Where a
relay provider only lets you recover a broker signature over its own commitments, a **genuine enclave** lets
you recompute the **entire chain of a live inference** from public bytes — with **no reliance on the
provider's `tee_verified` flag.** This profile pins that: a live **glm-5.2** action on **0G Compute mainnet**,
every check re-derived.

> **The distinction that matters.** 0G's Router API returns `tee_verified: true` — a *verdict*. This profile
> recovers the enclave signer **ourselves** from the raw response signature (broker path, `processResponse`),
> so nothing trusts a flag. *Don't trust — recompute*, applied to the provider's own attestation.

Converged against the primary artifact (0G Compute mainnet, provider `0x7DCFe6…`, signer
`0xA46EA4FC5889AD35A1487e1Ed04dCcfa872146B9`, answer `"recompute"`). Genuine enclave ⇒ the signed preimage is
the plain 2-field `H(request):H(response)` (`signChatWithKey`), **not** the relay's 5-field routing proof — so
*both* digests are client-recomputable.

## The chain, recomputed

| check | rule | evidence basis |
| --- | --- | --- |
| `signature_recovery` | `recoverAddress(hashMessage(preimage), signature) == signer` (EIP-191) | **recomputed** |
| `request_digest` | `sha256(JSON(reqBody)) == H(request)` | **recomputed** (relay: broker-asserted) |
| `response_digest` | `sha256(JSON(completion)) == H(response)` | **recomputed** |
| `rtmr_replay` | SHA-384-extend the RTMR event log == the TDX quote's RTMR0-3 | **recomputed** |
| `equality` — signer↔enclave | quote `report_data` == the recovered response signer | **recomputed** |
| `equality` — provider registry | on-chain 0G registry `teeSignerAddress` == quote `report_data` | **recomputed** |
| `dcap_quote_sig` — hardware root | PCK cert chain → **pinned** Intel SGX Root CA + QE sig + att-key↔QE binding + TD-quote sig | **recomputed** |

The full binding: **live response ← signed by → `0xA46EA4` ← attested by → the enclave's TDX quote
(`report_data`, MRTD, RTMR chain) ← rooted in → a genuine Intel-provisioned TDX part (dcap-qvl, chained to
Intel's pinned root) ← declared by → the on-chain 0G provider registry.** Every arrow recomputed.

The `dcap_quote_sig` check runs the **dcap-qvl core** over the raw quote bytes, with **no vendor SDK**: it
parses the embedded PCK cert chain (leaf ← PCK Platform CA ← Intel SGX Root CA), verifies each signature,
**pins the root** to Intel's known DER (`SHA-256 44a0196b…74d3`), verifies the QE-report signature under the
PCK leaf, the attestation-key↔QE binding (`report_data == sha256(attpub‖auth)`), and the TD-quote signature
under the attestation key. It runs identically in Node (`node:crypto`) and in the browser (`@peculiar/x509` +
Web Crypto) on the live `/verify` panel.

## Vectors

`tee-inference-enclave-v0.vectors.json` — 11 vectors, every `expected` recomputed from the artifact: 7
`verified` (signer, request, response, RTMR replay, signer↔enclave, provider↔registry, **dcap quote sig**) + 4
`rejected` (a one-byte preimage tamper, a tampered response body → digest breaks, a tampered event digest →
RTMR breaks, **a one-byte tamper in the TD-quote signed body → the TD-quote signature no longer verifies while
the cert chain / QE / binding still hold**). Conformant iff an implementation reproduces every verdict +
derived value.

```sh
bin/conformance-suite --suite conformance/tee-inference-enclave-v0
```

## Out of scope (v0)

Three *distinct* claims sit around the quote — they are not the same claim, and only the first is recomputed here:

1. **Hardware authenticity** — the quote is signed by a genuine Intel-provisioned TDX part. **In scope, recomputed**
   (`dcap_quote_sig`: PCK chain → pinned Intel root + QE sig + att-key binding + TD-quote sig).
2. **Expected-image authorization** — MRTD / `os_image_hash` matches 0G's *published* glm-5.2 enclave measurement.
   **Out of scope, the one honest residual** — needs the expected measurement from 0G's registry/manifest.
3. **PCS freshness** — the part's TCB is current/unrevoked against Intel's PCS *collateral* (TCBInfo, QE identity,
   revocation lists). **Out of scope** — a separate liveness claim, not a statement about hardware authenticity.

Conflating (1)/(2)/(3) is the failure this profile refuses: authenticity is not authorization is not freshness.
(2) is what remains amber on the live panel; (3) is a different kind of check entirely.

- The **model call itself** is attested by the enclave, never recomputed — that's the whole point of the
  fusion. Everything *around* it is recomputed here.
