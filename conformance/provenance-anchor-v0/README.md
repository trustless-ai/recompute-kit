# provenance-anchor.v0

The build-first origination gate: a proposal brought with a pre-built implementation declares the anchor
(commit / deploy / on-chain tx) that existed **before** its discussion thread, and this lane verifies that
claim by recomputation. Temporal + existence only — never semantic identity. Three-state verdict
(PASS / FAIL:reason / UNVERIFIABLE:reason); no silent green.

## Run

```
# deterministic verdict logic (graded suite — CI-safe, no network)
python3 provenance_gate.py provenance-anchor-v0.vectors.json

# live resolution of a declared anchor → a resolution object the gate consumes
python3 resolve_anchor.py '{"anchor":{"kind":"onchain_tx","chain_id":84532,"tx":"0x…"}}'
python3 resolve_anchor.py --rpc <archive-url> '{"anchor":{…}}'   # old blocks need an archive node
```

## What it is / isn't
- **Is:** a recomputable check that an origination artifact is real and predates the thread.
- **Isn't:** proof that the artifact is the spec's primitive (human review), and not a contribution-metric
  (a complementary, decoupled surface — see the WG note).

See `provenance-anchor-v0.spec.md` for the full verdict rules, the closed reason enumerations, and the
three real positive anchors.
