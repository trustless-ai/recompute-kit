# provenance-anchor.v0

The build-first origination gate: a proposal brought with a pre-built implementation declares the anchor
(commit / on-chain tx) that existed **before** its discussion thread, and this lane verifies that claim by
recomputation. **Witnessed** temporal + existence only — never semantic identity.

Five facts, each independently established: **content identity**, **existence witness** (independent of the
object's self-reported time), **anchor subject binding** (the anchor witness references this anchor),
**thread subject binding** (the thread witness is this proposal's *opening* PR — it ADDs the proposal's spec
file), and **witnessed precedence** (witnessed anchor time precedes witnessed *thread-open* time, both
witnessed facts). Three-state verdict (PASS / FAIL:reason / UNVERIFIABLE:reason); no silent green.

## Run

```
# deterministic verdict logic (graded suite — CI-safe, no network). 26 vectors: 3 PASS / 12 FAIL / 11 UNVERIFIABLE
python3 provenance_gate.py provenance-anchor-v0.vectors.json

# live resolution of a declared record → the resolution the gate consumes (fetches + ENFORCES the facts)
python3 resolve_anchor.py '{"thread_open":{"witness":{"kind":"forge_event","repo":"ethereum/ERCs","pr":1932}},"anchor":{"kind":"onchain_tx","chain_id":84532,"tx":"0x…"}}'
python3 resolve_anchor.py --rpc <archive-url> '{…}'   # old blocks need an archive node
```

## What it is / isn't
- **Is:** a recomputable check that an origination artifact was independently witnessed to predate the
  proposal — with each witness bound to its subject, and thread-open witnessed via the PR that *adds* the
  proposal's spec file.
- **Isn't:** proof the artifact is the spec's primitive (human review); a contribution-metric (a
  complementary, decoupled surface); and it does not accept self-reported times on either side.

See `provenance-anchor-v0.spec.md` for the four-fact contract, closed reason enumerations, the anchor-kind
witness authority, and the real-vs-fixture disclosure.
