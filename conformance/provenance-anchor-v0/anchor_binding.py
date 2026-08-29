#!/usr/bin/env python3
"""anchor-binding.v0 — the canonical object an origination anchor must commit.

Faisal/@zexoverz's finding: a free-standing transaction hash proves an anchor EXISTED before a proposal,
never that it COMMITTED to that proposal or its implementation artifact. This module defines the object
whose digest the anchor transaction must carry, so "origination" is a recomputable relationship, not a
coincidence of timing.

Canonical object (fixed key set, no extras):
  {
    "schema":   "anchor-binding.v0",
    "proposal": { "kind": "erc"|"eip", "id": <int>, "repo": "<owner/name>" },
    "artifact": { "repo": "<owner/name>", "commit": "<40-hex>" }
  }

Canonicalisation: RFC 8785 JCS is the receipt/envelope-family serializer (see the canonical-serializer
split). For THIS schema — all keys ASCII, all values ASCII strings or non-negative integers — JCS reduces
to: keys sorted as UTF-16 code units (identical to Unicode-scalar order for ASCII), minimal separators, no
insignificant whitespace, UTF-8. `canonical_bytes` produces exactly that and is the byte input to the digest.

  digest = sha256( canonical_bytes(object) )      # the 32 bytes the anchor tx MUST commit

The anchor is bound iff the anchor transaction's calldata contains `digest`. Optionally, if originator
authorship is claimed, the transaction signer MUST equal the declared originator address; otherwise the
claim narrows to proposal-specific pre-existence (this module makes no authorship claim on its own).
"""
from __future__ import annotations
import hashlib
import json
import re

SCHEMA = "anchor-binding.v0"
PROPOSAL_KINDS = {"erc", "eip", "repo"}
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def validate(obj):
    """Return None if obj is a well-formed anchor-binding.v0 object, else a reason string."""
    if not isinstance(obj, dict):
        return "not_an_object"
    if set(obj.keys()) != {"schema", "proposal", "artifact"}:
        return "extra_or_missing_keys"      # fixed key set — no ambiguity in what is committed
    if obj["schema"] != SCHEMA:
        return "schema"
    p = obj["proposal"]
    if not isinstance(p, dict) or set(p.keys()) != {"kind", "id", "repo"}:
        return "proposal_shape"
    if p["kind"] not in PROPOSAL_KINDS or not _is_int(p["id"]) or p["id"] < 0:
        return "proposal_values"
    if not (isinstance(p["repo"], str) and REPO_RE.match(p["repo"])):
        return "proposal_repo"
    a = obj["artifact"]
    if not isinstance(a, dict) or set(a.keys()) != {"repo", "commit"}:
        return "artifact_shape"
    if not (isinstance(a["repo"], str) and REPO_RE.match(a["repo"])):
        return "artifact_repo"
    if not (isinstance(a["commit"], str) and SHA_RE.match(a["commit"])):   # exact-case 40-hex, lowercase
        return "artifact_commit"
    return None


def canonical_bytes(obj):
    """JCS-equivalent canonical bytes for this constrained schema (ASCII keys, str/int values)."""
    bad = validate(obj)
    if bad is not None:
        raise ValueError(f"not a valid anchor-binding.v0 object: {bad}")
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(obj):
    """The 32-byte sha256 the anchor transaction must commit, as 0x-hex."""
    return "0x" + hashlib.sha256(canonical_bytes(obj)).hexdigest()


def build(kind, proposal_id, proposal_repo, artifact_repo, artifact_commit):
    return {
        "schema": SCHEMA,
        "proposal": {"kind": kind, "id": proposal_id, "repo": proposal_repo},
        "artifact": {"repo": artifact_repo, "commit": artifact_commit.lower()},
    }


if __name__ == "__main__":
    import sys
    obj = json.loads(sys.argv[1]) if len(sys.argv) > 1 else build(
        "erc", 0, "ethereum/ERCs", "trustless-ai/recompute-kit", "0" * 40)
    print("canonical:", canonical_bytes(obj).decode())
    print("digest:   ", digest(obj))
