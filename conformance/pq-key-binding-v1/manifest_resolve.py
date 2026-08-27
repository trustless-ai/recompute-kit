#!/usr/bin/env python3
"""pq_key_binding.v1 — manifest-chain `governs_from` resolution (§10.2.1 of the spec).

`governs_from` is the anchor time of the EARLIEST manifest whose entries contain a binding. "Earliest"
is only meaningful against a complete, reconstructible manifest chain: a membership proof shows a root
CONTAINS an entry, never that no EARLIER root did. This checker recomputes each manifest's content
address and reconstructs the chain from the candidate container back to genesis (prev_manifest_cc =
null), and enforces the two fail-closed rules the spec states normatively:

  - Reconstruction is required. If any manifest required to close the chain from genesis through the
    candidate cannot be fetched and recomputed, `governs_from` is UNRESOLVED/UNVERIFIABLE — a verifier
    MUST NOT substitute the earliest VISIBLE manifest for the earliest ACTUAL one.
  - Canonical history. Two anchored manifests sharing a prev_manifest_cc are a manifest-layer fork; a
    verifier that depends on that segment MUST surface conflict/UNRESOLVED, never silently pick a branch.

`available` on a vector manifest models "the verifier can fetch and recompute it"; a referenced-but-
unavailable prev link is exactly the missing-history case. Membership is modelled as an explicit
`entries` list (the entries_root's contents) — Merkle membership is a separate, already-covered check;
this suite is the CHAIN-completeness half.

Verdict tokens: `resolved:<anchor_time>` | `unresolved:incomplete_history` |
`unresolved:manifest_fork` | `not_covered`. Run: python3 manifest_resolve.py [manifest-vectors.json]
-> exit 0 all reproduce, 1 otherwise.
"""
import sys, json, os, hashlib
from collections import defaultdict


def _jcs(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def cc_of(content):
    return hashlib.sha256(_jcs(content)).hexdigest()


def resolve(manifests, target):
    """Return the governs_from verdict token for `target` over the manifest set the verifier can see."""
    # 1. Recompute the content address of every AVAILABLE manifest. An unavailable manifest is one the
    #    verifier cannot fetch+recompute; it exists as a referenced cc but not as usable content.
    avail = {}
    for m in manifests:
        if not m.get("available", True):
            continue
        avail[cc_of(m["content"])] = m

    # 2. Fork detection: any prev_manifest_cc claimed by more than one available manifest is a fork.
    by_prev = defaultdict(list)
    for c, m in avail.items():
        by_prev[m["content"].get("prev_manifest_cc")].append(c)
    forks = {p for p, cs in by_prev.items() if len(cs) > 1}

    # 3. Containers: available manifests whose entries include the target binding.
    containers = [(c, m) for c, m in avail.items() if target in m["content"].get("entries", [])]
    if not containers:
        return "not_covered"

    # 4. Take the earliest-VISIBLE container, then PROVE it is the earliest by reconstructing its
    #    ancestry to genesis. Sorting by anchor_time only picks the starting candidate; the verdict is
    #    decided by whether the chain closes, never by visibility alone.
    containers.sort(key=lambda cm: cm[1]["anchor_time"])
    cc, m0 = containers[0]

    cur, seen = cc, set()
    while cur is not None:
        if cur in seen:
            return "unresolved:incomplete_history"          # cycle -> no canonical genesis chain
        seen.add(cur)
        node = avail.get(cur)
        if node is None:
            return "unresolved:incomplete_history"          # a required link cannot be recomputed
        prev = node["content"].get("prev_manifest_cc")
        if prev in forks:
            return "unresolved:manifest_fork"               # the predecessor branches -> ambiguous order
        cur = prev

    # 5. Chain closed to genesis with no fork on the path: the earliest-visible container is provably
    #    the earliest, because its whole ancestry was enumerated. governs_from is its anchor time.
    return f"resolved:{m0['anchor_time']}"


def run(path):
    fx = json.load(open(path))
    fails = 0
    for c in fx["cases"]:
        got, exp = resolve(c["manifests"], c["target"]), c["expected"]
        ok = got == exp
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {c['name']:<54} -> {got:<32} (want {exp})")
    print(f"{len(fx['cases']) - fails}/{len(fx['cases'])} cases reproduced")
    return fails


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    sys.exit(1 if run(arg or os.path.join(here, "pq-key-binding-v1.manifest-vectors.json")) else 0)
