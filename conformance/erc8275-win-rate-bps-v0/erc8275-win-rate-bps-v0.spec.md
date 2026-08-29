# erc8275-win-rate-bps.v0

This profile is the prospective issuance contract for the ERC-8275 win-rate
quantity after the coordinated basis-points cutover.

## Convention identity

Every issued vector carries:

```text
governing_convention_hash = 0x0501b75db8e9ef4ef67c74efcfbe2a200b0a7e5aea5ca62f778c91c119e68daf
```

That value is `0x || SHA-256(JCS(convention_spec))`, where
`convention_spec` is carried in the vector artifact. A missing or unknown
pointer is unverifiable; a verifier MUST NOT guess the current convention.

## Recompute

For non-negative integer `wins` and `losses`:

```text
total = wins + losses
winRateBps = (wins * 20000 + total) // (2 * total)
```

`total == 0` is outside the computable domain. The output is an integer in
`0..10000`. The formula is exact integer arithmetic and rounds half up; it
never uses a language float round.

## Migration boundary

This profile is prospective. It does not modify, relabel, or reinterpret the
historical `8275/reputation` float-4dp vectors in `agent-flow.vectors.json`.
Those artifacts remain governed by the convention they declared at issuance.
New bps artifacts use this profile and carry the bps convention hash.
