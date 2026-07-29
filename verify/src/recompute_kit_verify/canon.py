"""receiptos-c14n-v0 — the exact canonicalization the receipts are built with.

Kept byte-identical to recompute-kit `mcp/receiptos.py` so an independent verifier recomputes the same
root. RFC-8785-style: sorted keys, compact separators, UTF-8. Stdlib only — nothing to trust.
"""
import json
import hashlib


def jcs(obj) -> bytes:
    """RFC-8785-style canonical JSON bytes (sorted keys, compact, UTF-8)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def receipt_root(receipt: dict) -> str:
    'receiptos-c14n-v0: "0x" + sha256(JCS(receipt \\ {anchor, receipt_root})).'
    content = {k: v for k, v in receipt.items() if k not in ("anchor", "receipt_root")}
    return "0x" + hashlib.sha256(jcs(content)).hexdigest()
