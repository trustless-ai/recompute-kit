#!/usr/bin/env python3
"""dex-calldata.v0 — recompute Uniswap v3 SwapRouter02 exactInputSingle calldata.

The candidate is admissible only if the calldata it builds is byte-identical to the one the public
ABI independently dictates. Nothing is quoted, resolved, or defaulted from live state, so the output
is a pure function of the parameters and the whole thing is recomputable by anyone.

  calldata = 0x04e45aaf || abi.encode((address,address,uint24,address,uint256,uint256,uint160))

All seven members are static, so the tuple encodes inline as seven 32-byte words with no head/tail
split and no offset word.

The spec suggests deriving the reference with foundry `cast calldata`. This gate does not, on
purpose. A suite whose gate shells out to an external binary cannot run hermetically, which is
exactly why `communication-chain-v0` sits in `uncovered.json` under `requires_live` and is skipped
by CI rather than passed. The encoding rule here is small enough to implement directly, so the
independence that matters (a second encoder, not the candidate's own) is kept while the suite stays
runnable in CI with nothing on PATH.

Adapter contract: fixture JSON on stdin (--grade) -> {name: result} on stdout.
"""
import sys, json, os, re

SELECTOR = "0x04e45aaf"

# (name, bit width) for the exactInputSingle params tuple, in ABI order.
PARAMS = [
    ("tokenIn", 160),
    ("tokenOut", 160),
    ("fee", 24),
    ("recipient", 160),
    ("amountIn", 256),
    ("amountOutMinimum", 256),
    ("sqrtPriceLimitX96", 160),
]


def _word(value, bits):
    """Left-pad a static value to one 32-byte word, rejecting anything that does not fit.

    An out-of-range value is a defect in the vector or the candidate, not something to truncate
    quietly. Silent masking is how a wrong fee packing survives a conformance run.
    """
    if isinstance(value, str):
        v = int(value, 16) if value.lower().startswith("0x") else int(value, 10)
    else:
        v = int(value)
    if v < 0:
        raise ValueError("negative value")
    if v >= 1 << bits:
        raise ValueError("value exceeds uint%d" % bits)
    return "%064x" % v


def recompute(vec):
    inp = vec["input"]
    words = "".join(_word(inp[name], bits) for name, bits in PARAMS)
    return {"calldata": SELECTOR + words}


def _hex_tokens(text, minlen=8):
    return set(m.group(0).lower() for m in re.finditer(r"[0-9a-fA-F]{%d,}" % minlen, text))


def lint_spec(here):
    """Same failure class the pq-key-binding gate guards: a pinned spec can cite a digest that no
    current vector produces. Hash-pinning the spec proves the prose is unaltered, never correct."""
    spec_p = os.path.join(here, "dex-calldata-v0.spec.md")
    vec_p = os.path.join(here, "dex-calldata-v0.vectors.json")
    if not os.path.exists(spec_p):
        return 0
    universe = _hex_tokens(open(vec_p).read())
    cited = _hex_tokens(open(spec_p).read())
    orphans = [t for t in cited if not any(u.startswith(t) or t.startswith(u) for u in universe)]
    for t in sorted(orphans):
        print("SPEC-ORPHAN  %s…  cited in spec but resolves to NO current vector/artifact" % t[:16])
    if not orphans:
        print("spec-lint OK — all %d cited digests resolve to a current pinned artifact" % len(cited))
    return len(orphans)


if __name__ == "__main__":
    if "--grade" in sys.argv:
        fx = json.load(sys.stdin)
        print(json.dumps({v["name"]: recompute(v) for v in fx["vectors"]}))
        sys.exit(0)
    here = os.path.dirname(os.path.abspath(__file__))
    fx = json.load(open(os.path.join(here, "dex-calldata-v0.vectors.json")))
    fails = 0
    for v in fx["vectors"]:
        got, exp = recompute(v), v["expected"]
        ok = got["calldata"].lower() == exp["calldata"].lower()
        fails += not ok
        print("%s %-22s %d bytes  %s…" % ("OK " if ok else "BAD", v["name"],
                                          (len(got["calldata"]) - 2) // 2, got["calldata"][:18]))
        if not ok:
            print("     expected %s" % exp["calldata"])
            print("     got      %s" % got["calldata"])
    print("%d/%d reproduced" % (len(fx["vectors"]) - fails, len(fx["vectors"])))
    orphans = lint_spec(here)
    sys.exit(1 if (fails or orphans) else 0)
