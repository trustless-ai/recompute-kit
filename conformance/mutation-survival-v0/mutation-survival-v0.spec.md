# mutation-survival-v0

Conformance for the `recompute-mutation-survival` primitive: it proves a suite's tests are
**load-bearing** (would fail if the code were wrong), not decorative (execute the code, assert nothing
that can fail). This is the automated form of the house rule *prove the check can fail* — the one thing
line-coverage and CRAP structurally cannot see, because a decorative test is 100% covered.

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
