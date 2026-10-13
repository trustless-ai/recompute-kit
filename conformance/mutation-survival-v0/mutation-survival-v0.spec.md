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
- `2` **UNVERIFIABLE** — baseline not green, an anchor not found or applied other than exactly once,
  a `guard` with no declared `kill_witness`, a `guard` that **CRASHED**, or an **empty mutation
  inventory**.

An inventory with **no `guard`** MUST NOT be verified-good. Only a guard gates the verdict, so with
no guard "no guard survived" is vacuously true and `killed 0 / survived 0` would certify coverage by
the absence of any evidence about it. The tool refuses with `ZERO_MUTANTS` and exit `2`. The token is
deliberately the same one the mutation harnesses use, so one condition has one name across the kit.

⚠ **An empty list is not the only way to have no guard.** The first cut of this tested `not muts`,
which an **all-probe** inventory walks straight past: a decorative test plus a surviving probe
returned verified-good and exit 0. The condition is *no gating mutation*, not *no mutation*. One
status carries a required **`reason`** — `empty_inventory` or `no_guard_mutations` — because a marker
reachable from two causes with nothing distinguishing them is the collapse
`tools/check_collapsed_states.py` exists to catch, and the fix for that is never a second marker.

This guard lives at **this tool's own boundary** rather than in the repo-wide sweep, because that
sweep discovers suites by the presence of a `mutation_check.py` and this suite does not have one — it
would be exempt by construction. A sweep should land an enforcement, not a list.

## The kill relation — CRASH is not a KILL

A `guard` mutation is **KILLED** only when both hold:

1. the mutation applied **exactly once** — `find` occurs once in the file. Zero occurrences is
   `not_applied`, more than one is `ambiguous_application`; both are UNVERIFIABLE, because
   `replace(..., 1)` would otherwise mutate the first site, which need not be the site `must`
   refers to;
2. the suite failed **and** the mutation's declared `kill_witness` appears in the output.

A non-zero exit on its own is only evidence that the harness stopped. A crash, an import error,
a syntax error or a usage error all satisfy it without any assertion having observed anything,
so counting them as kills lets a mutation set certify coverage it does not have. That failure
is **CRASHED** — a class of its own, never a kill, and UNVERIFIABLE for a guard.

`kill_witness` is REQUIRED on a `guard`; its absence is UNVERIFIABLE. There is deliberately no
inference from the exit code or the output shape — the same discipline `run_conformance` applies
to `adapter.contract`. A witness already present in the green baseline is also UNVERIFIABLE,
since a string that is there before the mutation proves nothing by being there after it.

`probe` mutations are informational: survivors are reported as the coverage backlog, not a verdict.

## The vectors (they gate the gate)
Two fixtures share the same module (`is_even`) and the same guard mutation (make it always true). Only
the test differs:
- `fixtures/load-bearing` — the test asserts the negative case too, so the mutation is **KILLED** → verified-good.
- `fixtures/decorative`  — the test asserts only the positive case, so the mutation **SURVIVES** → verified-bad.

If the primitive returned the same verdict for both, it could not distinguish real coverage from
decorative coverage and would be useless; `check` fails in that case.

Five more vectors each exist to red if a specific guard is removed:
- `fixtures/crashing` — a mutant that dies without its witness is **CRASHED**, never a kill.
- `fixtures/stale-bytecode` — execution freshness, below. Both of its mutants are pinned, not one:
  pinning only the survivor would let a run that got the first mutant wrong still pass.
- `fixtures/zero-mutants` — an empty inventory is `ZERO_MUTANTS` / exit 2, not verified-good.
- `fixtures/not-applied` — an anchor absent from the file was never applied, so the run says nothing
  about the suite; grading it either way would be fabricating evidence. UNVERIFIABLE.
- `fixtures/red-baseline` — the suite already fails, so no later failure can be attributed to a
  mutant and every mutation would score as KILLED by a failure it did not cause. UNVERIFIABLE
  before the first mutant is applied.

`check` itself refuses an empty vector list with `ZERO_CASES` / exit 2, for the same reason: a
self-grading check with nothing to grade reports CONFORMANT otherwise.

## Self-application (`self-check`) — are these vectors load-bearing?

The vectors prove the primitive behaves correctly on crafted inputs. They do not prove the converse,
which is the claim that actually matters: **that a broken guard would be noticed.** A vector set can
be green and decorative, which is the exact defect this primitive exists to detect — so it has to
hold itself to it.

`self-check` applies the primitive to its own source. Each guard in
`bin/recompute-mutation-survival` is a mutant in `self/mutations.json`, whose `kill_witness` is the
name of the vector that must red when that guard is disabled:

| guard disabled | vector that must red |
|---|---|
| per-run isolation | `stale-bytecode` |
| `ZERO_MUTANTS` | `zero-mutants` |
| kill relation degraded to any non-zero exit | `crashing` |
| SURVIVED / KILLED branches swapped | `load-bearing` |
| applied-exactly-once precondition | `not-applied` |
| baseline-green precondition | `red-baseline` |

**This is bounded, not circular.** A mutant that breaks the tool badly enough to stop it running
reports CRASHED / UNVERIFIABLE, never a pass — which is what the CRASH-is-not-a-KILL relation buys.
So self-application cannot launder a broken tool green. Neither can it certify one from nothing, and
it is not offered as doing so.

**One guard is declared `probe`, not `guard`: baseline isolation.** Baseline staleness requires
bytecode left behind by a *previous invocation*, and no single-run vector can set that up. It
therefore shows as a named survivor in the coverage backlog rather than being counted as covered —
the same honesty the primitive demands of its targets. A guard nothing can witness is a coverage gap
with a name, not a passing check.

`self-check` carries its own positive and negative controls
(`tools/test_mutation_survival_self_check.py`): remove the vector that witnesses a guard, and that
guard must come back SURVIVED with exit 1. A self-check that cannot fail is the decorative test it
exists to detect, one level up.

## Run
```
conformance/mutation-survival-v0/check
```

## Observation (normative)

**A mutation result means nothing unless the suite READS the mutated file.** If it does not, the
mutant survives trivially, and reporting SURVIVED asserts *"a fault the suite cannot see"* — a claim
about the suite's **assertions**. The real finding is that the suite never loaded the file, and the
very same test may be one that would kill the mutant the moment it saw it.

Execution freshness does not reach this. The classic case is a test that imports a **vendored copy**,
and per-run isolation cannot help because the copy travels with the workspace.

So, once per file in the inventory, in its own throwaway copy: **destroy the file and run the suite.**

| destroyed file → suite | conclusion |
|---|---|
| **RED** | the suite observes the file; grade its mutations normally |
| **GREEN** | the suite never reads it; every mutation on it is `UNVERIFIABLE` / `not_observed` |

`not_observed` is a **reason on UNVERIFIABLE**, not a fifth verdict, because the vocabulary already
distinguishes causes by a reason travelling beside the marker and splitting it earns a sixth next
month.

The payload is NUL bytes — invalid in Python source, JSON and Solidity alike — so the control does
not quietly assume the target is Python. A red for an unrelated reason reads as *observed* and
grading proceeds, which is the conservative direction: it risks doing the work, not skipping it.

## Precedence (normative)

**`verified-bad` outranks `UNVERIFIABLE`.** A SURVIVED guard is a proven coverage gap; an
UNVERIFIABLE row is the *absence* of a result, and absence must not outrank evidence. Before this was
fixed, a guard that survived alongside a stale anchor reported UNVERIFIABLE and exit `2` **while
printing the survivor underneath it** — the human-readable output carried the refutation and the
machine-readable answer hid it. The UNVERIFIABLE rows stay in the artifact either way.

## Execution freshness (normative)

**The bytes written MUST be the bytes executed.** A mutant that did not run is not evidence, and the
tool cannot tell the difference from the outside: a run of stale bytecode produces an ordinary exit
code and an ordinary output.

CPython validates a timestamp `.pyc` on `(source mtime in whole seconds, source size)`. Two
same-length mutants written inside one second therefore match a previous run's cache, and the second
one executes the first one's bytecode. Both directions are wrong, and they are not equally bad:

- **false SURVIVED** — the mutation never took effect. Loud: it reports a coverage gap that is not
  there.
- **false KILLED** — the previous mutant's failure, and its witness, reappear. **Silent: a real
  coverage gap is laundered into verified-good / exit 0.** This is the direction that matters.

Earlier revisions of this spec discharged the obligation by having each target's `test_cmd` clear
`__pycache__`. That is the wrong place for it twice over: it puts a correctness precondition in
per-suite configuration where omitting it fails open, and it covers only one of several ways stale
code reaches the interpreter. A PEP 552 **unchecked-hash** `.pyc` is never revalidated against its
source at all, so no amount of mtime or size change invalidates it; and any build or runner cache a
`--test-cmd` touches is outside the mechanism entirely.

The obligation is therefore discharged **structurally**: every run — baseline included — executes in
a disposable copy of `--dir`, with bytecode and runner caches excluded from the copy rather than
inherited (`copytree` preserves mtimes, so copying a stale cache would carry the staleness in).
Nothing can outlive a single mutant, the suite tree is never written to, and there is no restore
path to fail. A `--test-cmd` MUST therefore be self-contained within `--dir`.

An implementation MAY discharge the obligation differently — per-write mtime uniqueness is sufficient
for CPython timestamp invalidation alone — but it MUST state which mechanism it uses and what that
mechanism does not cover. `fixtures/stale-bytecode` is the control: its test command pins a fixed
mtime so that neither size nor mtime can discriminate, which makes the failure deterministic rather
than dependent on which second the writes land in.
