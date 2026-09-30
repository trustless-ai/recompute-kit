# mutation-survival-v0

Conformance for the `recompute-mutation-survival` primitive: it proves a suite's tests are
**load-bearing** (would fail if the code were wrong), not decorative (execute the code, assert nothing
that can fail). This is the automated form of the house rule *prove the check can fail* — the one thing
line-coverage and CRAP structurally cannot see, because a decorative test is 100% covered.

**Lineage.** Two disciplines, automated into one gate:
- *prove the check can fail* — a check that cannot fail is not evidence.
- *declared vs demonstrated* (from the TSEI thread) — a passing suite **declares** coverage; a killed
  mutant **demonstrates** it. Only the demonstration is verification; the declaration is agreement.

## From code-coverage to spec-conformance

Tag each mutation with the specification obligation it guards (`must`), and build the mutation set so
that **every normative `MUST` maps to a guard mutant that must be KILLED**. Then a green run is not
"the code is covered" — it is "the specification's obligations are demonstrably load-bearing in this
implementation." The gate becomes a **conformance property of the specification itself**: for each
`MUST`, break the code that satisfies it and the suite must notice. A survived guard names exactly which
obligation the tests only *claim* to enforce.

Worked example: `trustless-ai/ccip-router` maps the ERC-8309 §Deduplication MUSTs — divergence is
retained, never collapsed, never shown as agreement; observation-identical still collapses — each to a
mutant the suite must kill.

## Verdict contract
- `0` **verified-good** — baseline green AND every declared `guard` mutation was KILLED.
- `1` **verified-bad** — a `guard` mutation SURVIVED (a test that should catch it does not).
- `2` **UNVERIFIABLE** — baseline not green, an anchor not found, or the suite could not run.

`probe` mutations are informational: survivors are reported as the coverage backlog, not a verdict.

## The vector (gates the gate)
Two fixtures share the same module (`is_even`) and the same guard mutation (make it always true). Only
the test differs:
- `fixtures/load-bearing` — the test asserts the negative case too, so the mutation is **KILLED** → verified-good.
- `fixtures/decorative`  — the test asserts only the positive case, so the mutation **SURVIVES** → verified-bad.

If the primitive returned the same verdict for both, it could not distinguish real coverage from
decorative coverage and would be useless; `check` fails in that case.

## Run
```
conformance/mutation-survival-v0/check
```

## Note on the target's test command
The `test_cmd` clears `__pycache__` because CPython can re-run a cached `.pyc` when a mutation lands in
the same filesystem-mtime second, hiding the mutation (a false SURVIVED). Compiled/transpiled suites
(e.g. `node --test` via `tsx`) recompile per run and don't need this; native Python targets do.
