# recompute-kit

**Don't trust — recompute.** A tiny toolchain for verifying others' work the way it
should be verified: re-derived yourself from the primary artifact, pinned to an exact
reference, with the evidence attached.

The method is in **[RECOMPUTE.md](./RECOMPUTE.md)** — read that first; it's the point.
The scripts in `bin/` just wrap the three most common moves.

## The three verbs

```bash
# 1. recompute a leg / repo — clone @ an exact ref, run its tests YOURSELF
bin/recompute-repo https://github.com/owner/repo <sha|branch> forge test

# 2. verify a claim / citation — does the source actually say it?
bin/verify-claim https://arxiv.org/abs/2509.24257 "publicly verifiable" "1%"
bin/verify-claim ./paper.pdf Merkle VRF "hidden state"

# 3. recheck a CI / lint failure — the real verdict + the actual config
bin/recheck-ci ethereum/ERCs 1810 config/eipw.toml

# 4. recompute a fact FROM CHAIN — cast-call at a PINNED block vs a claim
bin/recompute-onchain https://ethereum-rpc.publicnode.com 19000000 \
    0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 "decimals()(uint8)" 18

# 5. recompute a COMMITMENT — keccak / keccak256(abi.encode(...)) vs a committed digest
bin/recompute-commitment abi-keccak 0x<digest> "f(bytes32,uint256)" 0x<root> 4
```

Each prints **pass/fail + the evidence** (the resolved SHA, the test output, the matched
lines, the block, the recomputed digest) — so the output is itself a recomputation anyone
can reproduce. Verbs 1–3 recompute *others' artifacts* (repos, claims, CI); verbs 4–5
recompute the *on-chain + cryptographic facts* the work rests on — the standards family's
own verify-step ("recompute from public data, no trusted party") made callable, on `cast`.

## Install

```bash
git clone <this-repo> && cd recompute-kit
export PATH="$PWD/bin:$PATH"   # or symlink bin/* into your path
```

Dependencies (only what each verb needs):
- `git` + [`gh`](https://cli.github.com) — clone/pin, PR checks, config fetch
- [`foundry`](https://getfoundry.sh) — `forge test` (or any test command you pass)
- `curl` + [`poppler`](https://poppler.freedesktop.org) (`pdftotext`) — fetch URLs / extract PDFs
- `python3` + [`ots`](https://opentimestamps.org) (`pip install opentimestamps-client`) — OTS precedence recompute (8263/precedence)

## Roadmap

These verbs are designed to become **MCP tools** (`recompute_repo`,
`verify_claim`, `recheck_ci`) — each returning structured `{pass, ref, evidence}` —
so an agent can hold itself to recompute-don't-trust automatically.

CC0 — see [LICENSE](./LICENSE).
