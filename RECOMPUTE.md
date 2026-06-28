# Recompute, don't trust

The house method. Verification is **re-deriving a result yourself from the primary
artifact, pinned to an exact reference** — not reading a summary and nodding.

If you can't point at *what* you recomputed (a commit SHA, a paper, a config file)
and *how* (the command you ran, the lines you matched), you haven't verified anything —
you've agreed.

## The unit: a pinned reference

Every recomputation names the exact thing it ran against. In practice that's almost
always a **commit SHA**. "Looks good" is worthless; "recomputed `c4100e5`, 12/12 green"
is a claim someone else can independently reproduce. The same holds for a paper
(arXiv id + the lines), a spec (the raw gist), or a CI rule (the config file).

## The four disciplines

1. **Pin to a ref.** Pull the exact SHA / branch / tag the author cited, not "latest",
   not your memory of it. The ref *is* the claim.
2. **Run their artifact yourself.** Don't accept "tests pass" — clone it and run the
   tests. Green only counts when *you* saw it green.
3. **Read the source, not the summary.** The config, not the diagnosis. The paper
   body, not the abstract. The raw gist, not its description. Summaries are where
   errors hide — a wrong pasted diagnosis cost a real debugging detour; the actual
   `config/eipw.toml` had the answer in two lines.
4. **Prove, don't assert.** A guarantee you claim is a guarantee you can break in a
   test. Write the *non-vacuous* test that fails if the property doesn't hold (commit
   a resolution over 3 of 4 coords → the contest must revert), not one that passes
   trivially.

## The toolchain

| Recompute… | with |
|---|---|
| **code / a leg** | `git clone`/`gh pr checkout` @ SHA → `forge test` / `forge build`; a second-language reference (`python3` + pycryptodome) to cross-check the hashing/merkle logic line-for-line |
| **a spec / claim** | `gh gist view --raw`, `gh api …/comments/<id>` for the exact text; `curl` / `WebFetch` for the primary source |
| **a paper citation** | `pdftotext` (poppler) + `grep` over the body — confirm the mechanism the citation claims is actually in the paper |
| **a CI / lint failure** | read the repo's lint config and re-derive the rule by hand; `gh pr checks` for the real verdict |

This repo wraps the three most common moves as runnable scripts — see `bin/`.

## Worked examples (real sessions)

- **A collaborator's PR.** Pulled `damonzwicker/scope-contestation-value-fidelity-`
  + a contributor's PR onto our base @ `236b66a`, ran `forge test` → 12/12 green.
  Greenlit only after recomputing, never on "it passes on my side."
- **A paper citation.** A suggested reference said a protocol used "Merkle-committed
  hidden states + VRF recompute." The *abstract* didn't say so. `pdftotext` + `grep`
  on the body found `rᵢ = Merkle(Hᵢ)` and VRF-selected verification indices — citation
  confirmed before committing it to a standard.
- **A CI failure.** A pasted diagnosis blamed the wrong lines. Reading the actual
  `config/eipw.toml` showed the two real rules (allowlist of relative links; first
  EIP/ERC mention must be a link) — fixed precisely in one commit, CI green.

## Why this is the whole pitch

The standards family this came out of is defined by recomputability: a verdict you
trust because anyone can re-derive it from public data, with no trusted party. The
verification *practice* has to hold itself to the same bar the specs demand. A tool
whose entire job is "don't trust me — here's the recompute, here's the evidence" is
the natural MCP surface for that worldview.
