# nft-fulfill.v0 — Seaport NFT-fulfillment encoding MCP conformance profile

This profile grades an MCP that **encodes** a Seaport `fulfillBasicOrder` transaction (buy an NFT
listing) from **explicit** order parameters. It is **recompute-first**: the candidate is admissible
only if, for each covered input, the calldata it builds is **byte-identical** to the one the public
Seaport ABI independently dictates — derivable by anyone from the function signature and the
`BasicOrderParameters`, with no live read.

## Why a pure encoder (and not the live buy)

A buy tool fetches a **live order** from the OpenSea API (`/listings/fulfillment_data`) and then encodes
its calldata — the order (price, salt, signature, counter) is ephemeral, so the *fetch* is honestly
**Attested**. But the *encoding* — `BasicOrderParameters` → calldata — is a pure function of the order.
This profile grades that deterministic slice: an encoder whose order parameters are an explicit input.
(Same move as `og_root` vs `og_store`, or `uniswap_encode_swap` vs the live-quote swap.) The live fetch
stays Attested; the encoding is Recomputable.

## Question in scope

> For an explicit Seaport `function` signature + `BasicOrderParameters`, does the candidate build
> exactly the `fulfillBasicOrder` calldata the ABI requires?

## Recompute rule (independent derivation)

```
calldata = <fn> selector ‖ abi.encode( BasicOrderParameters )
BasicOrderParameters = ( considerationToken, considerationIdentifier, considerationAmount,
                         offerer, zone, offerToken, offerIdentifier, offerAmount,
                         basicOrderType, startTime, endTime, zoneHash, salt,
                         offererConduitKey, fulfillerConduitKey,
                         totalOriginalAdditionalRecipients,
                         AdditionalRecipient[] (uint256 amount, address recipient),
                         bytes signature )
```

- `<fn>` is `fulfillBasicOrder(...)` (selector `0xfb0f3ee1`) or the gas-optimized
  `fulfillBasicOrder_efficient_6GL6yc(...)` (selector `0x00000000`) — same struct, different name.
- the struct fields are taken **as given** (the exact shape OpenSea's `fulfillment_data.transaction`
  returns: `function` + `input_data.parameters`). Nothing is fetched or defaulted.

The reference derivation uses foundry `cast calldata` — a second, independent ABI encoder from the one
the candidate uses (ethers). The pinned vectors were captured from a **real** OpenSea
`listings/fulfillment_data` payload and cross-checked byte-for-byte against the live `opensea_buy_nft`
calldata.

## Admissibility

- **conformant** iff `candidate.calldata == independent.calldata` byte-for-byte, over the pinned
  vectors;
- **non-conformant** otherwise — wrong field order, wrong `additionalRecipients` array encoding, or a
  dropped `signature` is caught by the rule.

The suite lists the capability as **Recomputable** iff every covered input is conformant.

## Out of scope (v0)

- `opensea_buy_nft` — performs a **live OpenSea fetch** of the order, so Attested. Its calldata is
  checkable against this profile by re-encoding the same fetched `{function, parameters}` through the
  pure tool.
- `opensea_get_*` — live market reads (Attested).
- `fulfillOrder` / `fulfillAdvancedOrder` / `matchOrders` / criteria-based orders — not covered in v0;
  `fulfillBasicOrder` (basic listings) only.

## References

- Seaport `fulfillBasicOrder` / `fulfillBasicOrder_efficient_6GL6yc`, `BasicOrderParameters`; Solidity
  ABI encoding.
- Receipt export: `receiptos.evidence_capsule.v0`, root by `receiptos-c14n-v0`.
