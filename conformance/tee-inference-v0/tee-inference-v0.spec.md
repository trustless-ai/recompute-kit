# tee-inference.v0 — evidence classes of a 0G TeeML signed inference (relay-provider vantage)

Recompute proves everything *around* a model call; it can't re-derive the LLM call itself. A TEE
**attests** `model + input → output` in a sealed enclave — the one link recompute can't cover. The intent
of the fusion is a chain verifiable from **two evidence roots of different kinds**: publicly-recomputable +
hardware-attested.

**This profile is deliberately framed as a *relay-provider evidence-class vector*, not a successful
TEE-attestation vector.** The one live captured 0G Galileo TeeML provider is a **signing relay in front of
Alibaba Cloud DashScope** — it emits no enclave quote. So this profile pins *exactly what is and isn't
established* when the label "TeeML" is attached to a relay, keeping every check **separated by evidence
class** so a broker signature is never silently promoted into enclave-executed evidence.

> **Core finding.** A verified broker signature over request/response commitments does **not** promote the
> inference into enclave-executed evidence. (Named by the working group; the vector is the artifact.)

## Provenance (converged against source, not inferred)

Primary artifact: [gist `TMerlini/19d532bc…`](https://gist.github.com/TMerlini/19d532bcb627d3ea237c72003d550337)
→ `teeml-sample.json` (0G Galileo provider `0xa48f`, signer `0x83df`). Two independent recoveries of
check 1 agree cross-language (ethers.js + Python `eth_account`).

- **Client verify path** — `@0gfoundation/0g-compute-ts-sdk` `broker/response.js` + `broker/verifier.js`:
  `recoverAddress(ethers.hashMessage(text), signature) === signer` (EIP-191).
- **Server construction** — `0gfoundation/0g-serving-broker` `api/inference/internal/ctrl/signing.go`
  (`signCentralizedRoutingProof`) + `api/common/tee/tls.go` `FormatRoutingProofText`:

  ```
  text = requestSha256 : responseSha256 : providerType : providerIdentity : tlsCertFingerprint
  sig  = crypto.Sign(accounts.TextHash([]byte(text)), providerSigner)     // EIP-191
  ```

  - `requestSha256`  = `sha256(reqBody)` — **reqBody is the body the broker forwards UPSTREAM** (DashScope), bytes only the enclave sees.
  - `responseSha256` = `sha256(respData)` = `sha256(JSON(completion))`.
  - `tlsCertFingerprint` = `SHA256(upstream leaf TLS cert)` — a **routing proof**, constant across inferences, **not a nonce**.

## The evidence ledger (this provider)

| # | check | evidence basis | verdict |
| --- | --- | --- | --- |
| 1 | `signature_recovery` — `ecrecover(EIP-191(preimage)) == signer` | **recomputed** | **established** (cross-language) |
| 2 | `response_digest_binding` — `sha256(JSON(completion)) == H(response)` | **recomputed** | **established** |
| 3 | `request_binding` — `H(request)` over the broker-forwarded upstream body | **attested** | **not client-recomputable** — enclave-internal bytes |
| 4 | `provider_binding` — recovered signer == on-chain registry signer for `0xa48f` | **recomputed** | **established** |
| 5 | `enclave_quote_parse` — a parseable dstack MRTD/RTMR quote | **attested** | **unavailable** (relay) |
| 6 | `anti_replay_binding` — `chatID` in the preimage / a per-call nonce | **recomputed** | **none** — transport-level only |

`enclave execution: not established.` `independent enclave attestation: unavailable for this relay
provider.` `cryptographic replay binding: not established` — `chatID` is a temporary transport fetch key,
and `hash3` is a constant TLS fingerprint, so neither binds replay.

## What each vector pins (all `expected` recomputed from the artifact, never asserted)

1. **Signature recovery is genuinely independent** — recovers `0x83df…508cF` from preimage + signature;
   one-byte tampers of the preimage or the signature → `rejected`.
2. **The TEE signs `sha256(JSON)`, not RFC-8785 JCS** — `H(response)` reproduces as
   `sha256(JSON.stringify(completion))`; binding it with **JCS** yields a **false mismatch** (`rejected`).
   Tamper the response → `rejected`.
3. **Request binding is attested, not client-recomputable** — no client canonicalization reproduces
   `hash1` (it's over the enclave's forwarded upstream body), so `request_binding` is `unverifiable` from
   the client vantage, tagged `attested`. Green request-recompute is impossible for a relay by construction.
4. **Provider binding** — the recovered signer equals the address the on-chain 0G provider registry
   declares for `0xa48f` → `verified`.
5. **No enclave quote** — the provider's `/v1/proxy/attestation/report` returns *"LLM attestation report
   is not available for this provider. This service forwards to an upstream API without local TEE
   attestation"* (headers confirm Alibaba DashScope); a scan of the whole Galileo TeeML population (2
   providers) found no enclave provider. `enclave_quote_parse` = `unverifiable` — a **fail-closed amber,
   never a green**. `--tamper` models an impl that greenlights it with no quote → **caught**.
6. **No cryptographic replay binding** — `chatID` is absent from the preimage; `hash3` is the constant
   upstream TLS fingerprint (routing proof). `anti_replay_binding` = `unverifiable`.

## Vectors

`tee-inference-v0.vectors.json` — 10 vectors: 3 `verified` (signer recovery, response digest, provider
binding), 4 `rejected` (two tampers + the wrong-canonicalization false-mismatch), 3 `unverifiable`
(chatID-not-bound, request-not-client-recomputable, enclave-quote-unavailable). Conformant iff an
implementation reproduces every per-check verdict + derived value.

```sh
bin/conformance-suite --suite conformance/tee-inference-v0
```

## Out of scope (v0)

- **A green `enclave_quote_parse`.** No live Galileo TeeML provider emits a parseable dstack quote (all
  relay upstream). When a genuine-enclave provider exists, add a vector that parses the raw quote into
  MRTD/RTMRs and binds the signer to the measurement — `attested` against an externally-resolved policy,
  still not re-derived. Until then, `unverifiable` is the honest verdict.
- **A green `request_binding`.** For a centralized/relay provider the request digest is over enclave-
  internal bytes; only a non-relay provider (or a server that hashes the verbatim client request) makes it
  client-recomputable.
- **Recomputing the model call**, by construction.
- **ERC-7857.** Kept out of this artifact; a separate follow-up once 0G identifies or deploys a genuine
  enclave-capable provider.
