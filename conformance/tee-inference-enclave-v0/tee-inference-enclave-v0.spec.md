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

The full binding: **live response ← signed by → `0xA46EA4` ← attested by → the enclave's TDX quote
(`report_data`, MRTD, RTMR chain) ← declared by → the on-chain 0G provider registry.** Every arrow recomputed.

## Vectors

`tee-inference-enclave-v0.vectors.json` — 9 vectors, every `expected` recomputed from the artifact: 6
`verified` (signer, request, response, RTMR replay, signer↔enclave, provider↔registry) + 3 `rejected` (a
one-byte preimage tamper, a tampered response body → digest breaks, a tampered event digest → RTMR breaks).
Conformant iff an implementation reproduces every verdict + derived value.

```sh
bin/conformance-suite --suite conformance/tee-inference-enclave-v0
```

## Out of scope (v0)

- **Intel PCS quote signature** (dcap-qvl) — the quote's ECDSA signature + PCK cert-chain to Intel's root.
  The RTMR replay + report_data binding prove internal consistency + the signer link; the Intel-sig check is
  the additional hardware root, a residual trust root until added.
- **Known-good image** — whether MRTD / `os_image_hash` matches 0G's *published* glm-5.2 enclave image
  (needs the expected measurement from 0G's registry/manifest).
- The **model call itself** is attested by the enclave, never recomputed — that's the whole point of the
  fusion. Everything *around* it is recomputed here.
