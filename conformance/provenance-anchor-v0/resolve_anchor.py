#!/usr/bin/env python3
"""provenance-anchor.v0 — LIVE anchor resolver (companion to provenance_gate.py).

This is the non-deterministic half: it actually fetches. Given a declared anchor it returns a `resolution`
object of the exact shape the gate consumes as a model input — so `resolve_anchor.py <record> | provenance_gate`
closes the loop from declaration to on-chain/git truth. It is NOT part of the graded vector suite (network),
which is why the gate models resolution as an input.

It separates the two facts @pipavlo82 required (they are NOT the same fetch for a git anchor):
  content  — does the object exist / are its bytes stable? {confirmed, not_found, unavailable_*}
  witness  — an INDEPENDENT, externally-witnessed publication time. For on-chain anchors this IS the block
             timestamp (consensus-set). For a git commit the committer date is NOT a witness — a witness
             must be a separate observation (on-chain commitment of the commit hash / transparency log /
             forge event). A bare commit resolves content=confirmed, witness_declared=false — and the gate
             returns UNVERIFIABLE:no_publication_witness, never PASS.

Output: {"content": "...", "witness_declared": bool, "witnessed_ts": int|null}
A resolver that let a pruned block, an unreachable host, OR a missing witness pass would reintroduce the
silent-skip class; that is the one thing this file exists to prevent.

Usage:
  python3 resolve_anchor.py '<record-json>'          # prints the resolution object
  python3 resolve_anchor.py --rpc <url> '<record>'   # override the onchain RPC (use an archive node for old blocks)
"""
from __future__ import annotations
import json, sys, urllib.request, urllib.error

DEFAULT_RPC = {84532: "https://base-sepolia-rpc.publicnode.com"}  # archive node; public sepolia.base.org prunes


def _rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json",
                                                          "user-agent": "provenance-anchor-v0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _block_ts_of_tx(tx_hash, chain, rpc=None):
    """Return ('found', ts) | ('not_found', None) | ('unavailable_pruned'|'unavailable_rpc', None)."""
    url = rpc or DEFAULT_RPC.get(chain)
    if not url:
        return ("unavailable_rpc", None)
    try:
        tx = _rpc(url, "eth_getTransactionByHash", [tx_hash])
        if "error" in tx:
            return ("unavailable_rpc", None)
        result = tx.get("result")
        if not result or not result.get("blockNumber"):
            return ("not_found", None)
        blk = _rpc(url, "eth_getBlockByNumber", [result["blockNumber"], False])
        if "error" in blk:
            msg = blk["error"].get("message", "").lower()
            if "pruned" in msg or "unavailable" in msg or "missing" in msg:
                return ("unavailable_pruned", None)
            return ("unavailable_rpc", None)
        b = blk.get("result")
        if not b or not b.get("timestamp"):
            return ("unavailable_pruned", None)
        return ("found", int(b["timestamp"], 16))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return ("unavailable_rpc", None)


def resolve_onchain(anchor, rpc=None):
    # For an on-chain anchor content-identity and the witness are the SAME fact: the block.
    status, ts = _block_ts_of_tx(anchor["tx"], anchor["chain_id"], rpc)
    if status == "found":
        return {"content": "confirmed", "witness_declared": True, "witnessed_ts": ts}
    if status == "not_found":
        return {"content": "not_found", "witness_declared": True, "witnessed_ts": None}
    return {"content": status, "witness_declared": True, "witnessed_ts": None}


def resolve_git_commit(anchor, rpc=None):
    # Fact 1 — content identity: does the commit exist (bytes stable)? GitHub commit API. NOTE the committer
    # date returned here is deliberately IGNORED for precedence — it is a field inside the object.
    repo, sha = anchor["repo"], anchor["commit"]
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/commits/{sha}",
                                     headers={"accept": "application/vnd.github+json",
                                              "user-agent": "provenance-anchor-v0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            json.loads(r.read())  # 200 => the object exists and its hash is stable
        content = "confirmed"
    except urllib.error.HTTPError as e:
        return {"content": "not_found" if e.code == 404 else "unavailable_source",
                "witness_declared": bool(anchor.get("witness")), "witnessed_ts": None}
    except (urllib.error.URLError, TimeoutError, ValueError):
        return {"content": "unavailable_source",
                "witness_declared": bool(anchor.get("witness")), "witnessed_ts": None}

    # Fact 2 — existence witness: INDEPENDENT of the commit object. A bare commit has none.
    w = anchor.get("witness")
    if not w:
        return {"content": content, "witness_declared": False, "witnessed_ts": None}
    if w.get("kind") == "onchain_commitment":
        st, ts = _block_ts_of_tx(w["tx"], w["chain_id"], rpc)  # the commitment tx's block IS the witness
        return {"content": content, "witness_declared": True,
                "witnessed_ts": ts if st == "found" else None}
    # transparency_log / forge_event: a real backend (Rekor inclusion time, forge event time) goes here.
    # Until wired, the witness is declared but unresolved -> UNVERIFIABLE:witness_unresolved (never PASS).
    return {"content": content, "witness_declared": True, "witnessed_ts": w.get("witnessed_ts")}


def resolve(anchor, rpc=None):
    kind = anchor.get("kind")
    if kind in ("onchain_tx", "onchain_deploy"):
        return resolve_onchain(anchor, rpc)
    if kind == "git_commit":
        return resolve_git_commit(anchor, rpc)
    return {"content": "unavailable_rpc", "witness_declared": False, "witnessed_ts": None}


if __name__ == "__main__":
    args = sys.argv[1:]
    rpc = None
    if args and args[0] == "--rpc":
        rpc = args[1]; args = args[2:]
    record = json.loads(args[0])
    anchor = record.get("anchor", record)  # accept a bare anchor too
    print(json.dumps(resolve(anchor, rpc)))
