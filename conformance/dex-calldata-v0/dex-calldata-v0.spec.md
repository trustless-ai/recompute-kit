# dex-calldata.v0 — Uniswap v3 swap-encoding MCP conformance profile

This profile grades an MCP that **encodes** a Uniswap v3 swap (SwapRouter02 `exactInputSingle`) from
**explicit** parameters. It is **recompute-first**: the candidate is admissible only if, for each
covered input, the calldata it builds is **byte-identical** to the one the public ABI independently
dictates — derivable by anyone from the function signature and the parameters, with no live read.

## Why a pure encoder (and not the quoting swap)

A tool that quotes-and-swaps derives `amountOutMinimum` from a **live pool quote**, so its calldata is
not a function of its inputs alone — that tool is honestly **Attested**. This profile grades the
*deterministic slice*: an encoder whose `amountOutMinimum` (and every other field) is an explicit input,
so the output is a pure function of the parameters. (Same move as `og_root` vs `og_store`.) The live
quote stays Attested; the encoding is Recomputable.

## Question in scope

> For each explicit `(tokenIn, tokenOut, fee, recipient, amountIn, amountOutMinimum, sqrtPriceLimitX96)`,
> does the candidate build exactly the `exactInputSingle` calldata the ABI requires?

## Recompute rule (independent derivation)

```
calldata = exactInputSingle selector ‖ abi.encode( (tokenIn, tokenOut, fee, recipient,
                                                     amountIn, amountOutMinimum, sqrtPriceLimitX96) )
```

- signature: `exactInputSingle((address,address,uint24,address,uint256,uint256,uint160))` on
  **SwapRouter02** (selector `0x04e45aaf`). No `deadline` field (SwapRouter02 dropped it).
- the params are taken **as given** — addresses checksummed, `amountIn` / `amountOutMinimum` /
  `sqrtPriceLimitX96` as raw base units (wei). Nothing is quoted, resolved, or defaulted from live
  state.

The reference derivation uses foundry `cast calldata` — a second, independent ABI encoder from the one
the candidate uses (ethers). Byte-identity across the two is meaningful.

## Admissibility

For each covered input, over the vectors pinned in the accompanying file:

- **conformant** iff `candidate.calldata == independent.calldata` byte-for-byte;
- **non-conformant** otherwise — a wrong field order, wrong fee packing, or wrong ABI padding is caught
  by the rule.

The suite lists the capability as **Recomputable** iff every covered input is conformant.

## Out of scope (v0)

- `uniswap_quote` / `uniswap_swap_calldata` — depend on a **live QuoterV2 read** (price varies with pool
  state), so Attested. Their calldata is still checkable against this profile once you pin an explicit
  `amountOutMinimum` (i.e. re-encode it via the pure tool).
- `exactInput` (multi-hop path), `exactOutput*`, multicall wrappers (ETH refund / permit) — not covered
  in v0; a single-hop `exactInputSingle` only.

## References

- Uniswap v3 SwapRouter02 `exactInputSingle`; Solidity ABI encoding.
- Receipt export: `receiptos.evidence_capsule.v0`, root by `receiptos-c14n-v0`.
