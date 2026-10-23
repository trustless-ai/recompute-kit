#!/usr/bin/env python3
"""Every hash and address quoted in a .md must be accounted for, offline.

A documented identifier is a claim like any other. Three of the convention hashes in
`BASIS_POINTS_CUTOVER_MATRIX.md` are DERIVED values -- `sha256` over a convention descriptor in
`mcp/conventions.py` -- so editing a descriptor silently invalidates the document that quotes the
old digest, and nothing noticed. That is the ordinary drift this repo exists to catch, in prose.

So each identifier must fall into exactly one declared account:

  DERIVED   a 32-byte hash that `mcp.conventions.resolve()` still resolves. Recomputed here from
            the descriptor, never read back from the document that quotes it.
  PINNED    a 32-byte HASH that appears in a tracked vectors/corpus file, so a suite compares
            against it. Hashes only, deliberately: a suite ENFORCES a hash by recomputing and
            comparing, whereas an address in a corpus is merely recorded. Letting an address count
            as "pinned" would be the containment-for-enforcement swap that this repo keeps paying
            for -- and it showed up here as a control that did not bite, because dropping the
            TruthAnchor's ONCHAIN entry silently reclassified it PINNED instead of reporting it.
  ONCHAIN   a fact no offline check can settle -- a transaction hash, a deployed address. Declared
            WITH the chain and block to check it against, because "we cannot verify this here" has
            to be written down rather than inferred from the absence of a check.

⚠ This test is deliberately OFFLINE. It does not reach an RPC: CI must not go red because a public
endpoint rate-limited us, and a network failure must not be able to look like a stale document.
The ONCHAIN entries below carry what a human needs to re-verify them by hand, and the one-off
verification done when this was written is recorded in each comment.

Found while sweeping the board item "stale contract addresses in READMEs -- 6 distinct addresses,
3 live on mainnet and 3 have no code". That count was wrong, and so was the conclusion: four of the
six were the first 40 hex characters of 32-byte HASHES, matched by an unanchored
`0x[a-fA-F0-9]{40}` and then queried as addresses. Of course they had no code. There are two
addresses and four hashes, and nothing was stale. The regexes here are `\\b`-anchored and classified
by length so that mistake cannot recur.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp"))
import conventions  # noqa: E402

HASH = re.compile(r"0x[0-9a-fA-F]{64}\b")
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\b")

# Identifiers that no offline check can settle. Each says where to verify it by hand.
ONCHAIN = {
    # Verified by hand 2026-10-14 against Ethereum mainnet: tx exists in block 25646404, to =
    # the TruthAnchor below, from = 0xFf9a176577Fb42b6bc9c19fd05a241e8fCd0ca14, status 1 (success).
    "0x469655a08accf0300def211bf0c9ebd463e65b89f4ede1ac372ed2796e7ba916":
        "Ethereum mainnet · anchor tx · block 25646404 · cast tx <hash>",
    # Verified by hand 2026-10-14: has code on Ethereum mainnet (cast code).
    "0x1e2a118a2bf1c240ae6fde187c07f905d360f094":
        "Ethereum mainnet · TruthAnchor (OCP record(bytes32)) · cast code <address>",
    # Verified by hand 2026-10-14 on 0G mainnet (evmrpc.0g.ai): EOA, no code, nonce 0 — consistent
    # with an off-chain 0G Compute RESPONSE SIGNER, which signs messages and need never transact.
    # The claim about it is a signature over a response, which tee-inference-enclave-v0's vectors
    # pin; it is not a claim about chain state.
    "0xa46ea4fc5889ad35a1487e1ed04dccfa872146b9":
        "0G mainnet · 0G Compute response signer (EOA, off-chain signer) · "
        "pinned by conformance/tee-inference-enclave-v0 vectors",
}


def tracked(pattern):
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", pattern],
                         capture_output=True, text=True, check=True).stdout.split()
    return [ROOT / p for p in out]


def pinned_in_a_corpus(identifier):
    """-> the tracked data files that carry this identifier, so a suite can enforce it."""
    hits = []
    for f in sorted(set(tracked("conformance/*") + tracked("conformance/*/*"))):
        if f.suffix not in (".json", ".txt") or not f.is_file():
            continue
        try:
            if identifier in f.read_text(encoding="utf-8", errors="replace").lower():
                hits.append(f.relative_to(ROOT))
        except OSError:
            continue
    return hits


def collect():
    found = {}
    for f in tracked("*.md"):
        text = f.read_text(encoding="utf-8", errors="replace")
        for pattern, kind in ((HASH, "hash"), (ADDRESS, "address")):
            for raw in pattern.findall(text):
                rec = found.setdefault(raw.lower(), {"kind": kind, "files": set()})
                rec["files"].add(str(f.relative_to(ROOT)))
    return found


fails = []
found = collect()
if not found:
    fails.append("no identifiers found in any tracked .md -- the sweep is broken, and a sweep that "
                 "finds nothing proves nothing")

derived = {h.lower() for h in conventions.CONVENTION_HASH.values()}
if not derived:
    fails.append("mcp/conventions.py derived no convention hashes; the DERIVED account cannot hold")

accounted = {"DERIVED": [], "PINNED": [], "ONCHAIN": []}
for ident, rec in sorted(found.items()):
    where = ", ".join(sorted(rec["files"]))
    if rec["kind"] == "hash" and ident in derived:
        # Recomputed from the descriptor, not read back from the doc that quotes it.
        resolved = conventions.resolve(ident) or conventions.resolve(
            next(h for h in conventions.CONVENTION_HASH.values() if h.lower() == ident))
        if not resolved:
            fails.append(f"{ident} matches a derived hash but resolve() returns None")
        accounted["DERIVED"].append((ident, resolved, where))
    elif ident in ONCHAIN:
        accounted["ONCHAIN"].append((ident, ONCHAIN[ident], where))
    else:
        # hashes only -- see the PINNED note in the docstring
        corpora = pinned_in_a_corpus(ident) if rec["kind"] == "hash" else []
        if corpora:
            accounted["PINNED"].append((ident, ", ".join(str(c) for c in corpora), where))
        else:
            fails.append(
                f"{ident} ({rec['kind']}) is quoted in {where} and is in NO account: it is not "
                "derivable from mcp/conventions.py, not pinned in a tracked corpus (hashes only), "
                "and not declared in ONCHAIN. Either pin it, derive it, or declare it with the "
                "chain and block someone can check it against. An ADDRESS can only be declared: "
                "nothing offline can establish that an address is the right one.")

# A derived hash that a document quotes must still be the hash that derives TODAY. The inverse
# direction: every convention this repo defines should be findable in the cutover matrix, or the
# document has fallen behind the code it describes.
matrix = (ROOT / "BASIS_POINTS_CUTOVER_MATRIX.md")
if matrix.is_file():
    text = matrix.read_text(encoding="utf-8", errors="replace").lower()
    for cid, h in conventions.CONVENTION_HASH.items():
        if h.lower() not in text:
            fails.append(f"convention {cid} derives {h} but BASIS_POINTS_CUTOVER_MATRIX.md does "
                         "not quote it -- the document has fallen behind mcp/conventions.py")

if fails:
    print(f"FAIL — documented identifiers ({len(fails)})")
    for f in fails:
        print("  - " + f)
    raise SystemExit(1)

print(f"OK — {len(found)} documented identifiers, all accounted for "
      f"({len(accounted['DERIVED'])} derived, {len(accounted['PINNED'])} pinned, "
      f"{len(accounted['ONCHAIN'])} declared on-chain)")
for account in ("DERIVED", "PINNED", "ONCHAIN"):
    for ident, detail, where in accounted[account]:
        print(f"  {account:8} {ident[:18]}…  {detail}")
