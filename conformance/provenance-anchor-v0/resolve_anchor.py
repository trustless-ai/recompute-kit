#!/usr/bin/env python3
"""provenance-anchor.v0 — LIVE resolver (companion to provenance_gate.py).

The non-deterministic half: it actually fetches, and it ENFORCES the facts the gate checks so the model
inputs the gate consumes are honest. NOT part of the graded suite (network).

For each side it returns the facts, never a self-reported time:
  anchor: {content, witness_declared, witnessed_ts, subject_bound}
  thread: {witnessed, witnessed_ts}

Enforcement that lives HERE:
  * on-chain tx anchor — content = the tx is mined; witness = its block timestamp (consensus); the tx IS
    its own subject, so subject_bound = True.
  * git commit anchor — content = the commit hash resolves (bytes stable; the committer date is IGNORED).
    A witness is a SEPARATE object and must BIND to this commit:
      - onchain_commitment: fetch the commitment tx; witnessed_ts = its block timestamp ONLY IF the commit
        hash (40-hex, and its raw 20-byte form) appears in the tx calldata. Otherwise subject_bound = False
        and the block time is discarded — an unrelated tx is not a witness of the commit.
      - transparency_log / forge_event: NO backend is wired, so witnessed_ts = None (UNVERIFIABLE:
        witness_unresolved). We never read a caller-supplied time — that would be self-reported.
  * thread-open — a witnessed boundary, not a record field: forge_event resolves the ERC PR's GitHub-stamped
    created_at, AND binds it to the scored proposal by requiring the PR to touch that proposal's spec file
    (subject_bound) — otherwise a caller could point at a later, unrelated PR.

Usage:
  python3 resolve_anchor.py '<record-json>'          # prints {"anchor":{...},"thread":{...}}
  python3 resolve_anchor.py --rpc <url> '<record>'   # override the onchain RPC (archive node for old blocks)
"""
from __future__ import annotations
import datetime, json, sys, urllib.error, urllib.request
import anchor_binding as ab  # recompute the binding digest to check the anchor tx commits it

DEFAULT_RPC = {84532: "https://base-sepolia-rpc.publicnode.com"}
UA = "provenance-anchor-v0"


def _rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json", "user-agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _tx_block_and_input(tx_hash, chain, rpc=None):
    """Return (status, block_ts, calldata, signer). status in found|not_found|unavailable_pruned|unavailable_rpc."""
    url = rpc or DEFAULT_RPC.get(chain)
    if not url:
        return ("unavailable_rpc", None, None, None)
    try:
        tx = _rpc(url, "eth_getTransactionByHash", [tx_hash])
        if "error" in tx:
            return ("unavailable_rpc", None, None, None)
        result = tx.get("result")
        # A null response CANNOT prove absence — only that THIS node doesn't have it. Fail to
        # unavailable_rpc, never not_found, unless an independently complete source establishes absence.
        if result is None:
            return ("unavailable_rpc", None, None, None)
        calldata = (result.get("input") or "").lower()
        signer = result.get("from")
        if not result.get("blockNumber"):
            return ("not_found", None, calldata, signer)   # present but unmined = genuinely not anchored
        blk = _rpc(url, "eth_getBlockByNumber", [result["blockNumber"], False])
        if "error" in blk:
            msg = blk["error"].get("message", "").lower()
            return (("unavailable_pruned" if any(k in msg for k in ("pruned", "unavailable", "missing"))
                     else "unavailable_rpc"), None, calldata, signer)
        b = blk.get("result")
        if not b or not b.get("timestamp"):
            return ("unavailable_pruned", None, calldata, signer)
        return ("found", int(b["timestamp"], 16), calldata, signer)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return ("unavailable_rpc", None, None, None)


def _github_json(path):
    req = urllib.request.Request(f"https://api.github.com/{path}",
                                 headers={"accept": "application/vnd.github+json", "user-agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def resolve_anchor_fact(anchor, rpc=None):
    kind = anchor.get("kind")
    if kind == "onchain_tx":
        status, ts, calldata, signer = _tx_block_and_input(anchor["tx"], anchor["chain_id"], rpc)
        # anchor→proposal binding (origination): the tx must commit the digest of the canonical binding.
        bound = None
        b = anchor.get("binding")
        if isinstance(b, dict) and calldata:
            try:
                d = ab.digest(b)[2:].lower()      # 32-byte digest, no 0x
                bound = d in calldata
            except ValueError:
                bound = False
        if status == "found":
            return {"content": "confirmed", "witness_declared": True, "witnessed_ts": ts,
                    "subject_bound": True, "bound": bound, "signer": signer}
        if status == "not_found":
            return {"content": "not_found", "witness_declared": True, "witnessed_ts": None,
                    "subject_bound": False, "bound": None, "signer": signer}
        return {"content": status, "witness_declared": True, "witnessed_ts": None,
                "subject_bound": False, "bound": None, "signer": signer}

    if kind == "git_commit":
        # Fact 1 — content identity (bytes stable). committer date deliberately ignored.
        try:
            _github_json(f"repos/{anchor['repo']}/commits/{anchor['commit']}")
            content = "confirmed"
        except urllib.error.HTTPError as e:
            content = "not_found" if e.code == 404 else "unavailable_source"
        except (urllib.error.URLError, TimeoutError, ValueError):
            content = "unavailable_source"
        base = {"content": content, "witness_declared": False, "witnessed_ts": None, "subject_bound": False}
        if content != "confirmed":
            return base
        w = anchor.get("witness")
        if not w:
            return base                                   # bare commit -> no witness
        base["witness_declared"] = True
        if w.get("kind") == "onchain_commitment":
            status, ts, calldata, _ = _tx_block_and_input(w["tx"], w["chain_id"], rpc)
            sha = anchor["commit"].lower()
            # Fact 3 — the commitment must actually carry this commit hash (40-hex, or raw 20 bytes).
            bound = bool(calldata) and (sha in calldata)
            if status == "found":
                # Report the resolved block time either way, but only bind it if the commitment tx
                # actually carries the commit hash. subject_bound=False -> gate: witness_not_bound
                # (distinct from witness_unresolved, which is a witness that didn't resolve at all).
                base.update(witnessed_ts=ts, subject_bound=bound)
            return base
        # transparency_log / forge_event — no backend wired: unresolved, never a self-reported time.
        return base


# A proposal opens in exactly one canonical repository, at one exact-case path.
CANONICAL_REPO = {"erc": "ethereum/ERCs", "eip": "ethereum/EIPs"}


def _proposal_files(proposal):
    """The EXACT-CASE canonical spec path whose 'added' status proves a PR opens THIS proposal."""
    if not isinstance(proposal, dict) or not isinstance(proposal.get("id"), int):
        return ()
    n = proposal["id"]
    if proposal.get("kind") == "erc":
        return (f"ERCS/erc-{n}.md",)
    if proposal.get("kind") == "eip":
        return (f"EIPS/eip-{n}.md",)
    return ()


def _github_pr_files(repo, pr):
    """Every changed file (filename, status) across ALL pages, or None if it couldn't be fully fetched.
    GitHub returns 30 files by default; relying on that could miss the proposal file on a later page, so
    we paginate at 100/page and fail closed (None) on any error rather than under-reading."""
    out, page = [], 1
    while True:
        try:
            data = _github_json(f"repos/{repo}/pulls/{pr}/files?per_page=100&page={page}")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            return None
        if not isinstance(data, list):
            return None
        out += [(f.get("filename") or "", f.get("status")) for f in data]  # EXACT case — paths are case-sensitive
        if len(data) < 100:
            return out
        page += 1
        if page > 50:            # safety bound; fail closed rather than loop
            return None


def resolve_thread_fact(thread_open, proposal, rpc=None):
    w = (thread_open or {}).get("witness") or {}
    if w.get("kind") == "forge_event":
        try:
            data = _github_json(f"repos/{w['repo']}/pulls/{w['pr']}")
            iso = data["created_at"].replace("Z", "+00:00")   # GitHub-stamped, not author-controlled
            ts = int(datetime.datetime.fromisoformat(iso).timestamp())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError):
            return {"witnessed": False, "witnessed_ts": None, "subject_bound": False}
        # Fact 4 — thread subject binding. Two conditions, both required:
        #  (a) the witness repo is the proposal's CANONICAL repo (a spoof repo adding the same path is not
        #      the opening), compared case-insensitively as GitHub treats repo names;
        #  (b) the PR ADDs the proposal's EXACT-CASE spec path (a modify, or a case-variant path, is not the
        #      opening). All file pages read, or fail closed.
        kind = proposal.get("kind") if isinstance(proposal, dict) else None
        canon = CANONICAL_REPO.get(kind)
        if not canon or str(w.get("repo", "")).lower() != canon.lower():
            return {"witnessed": True, "witnessed_ts": ts, "subject_bound": False}
        wanted = _proposal_files(proposal)
        files = _github_pr_files(w["repo"], w["pr"])
        bound = bool(wanted) and files is not None and any(
            fn in wanted and st == "added" for fn, st in files)
        return {"witnessed": True, "witnessed_ts": ts, "subject_bound": bound}
    if w.get("kind") == "onchain_commitment":
        status, ts, _, _ = _tx_block_and_input(w["tx"], w["chain_id"], rpc)
        # An on-chain thread commitment would carry the proposal id; not wired here, so unbound.
        return {"witnessed": status == "found", "witnessed_ts": ts if status == "found" else None,
                "subject_bound": False}
    return {"witnessed": False, "witnessed_ts": None, "subject_bound": False}


def resolve(record, rpc=None):
    return {"anchor": resolve_anchor_fact(record["anchor"], rpc),
            "thread": resolve_thread_fact(record.get("thread_open"), record.get("proposal"), rpc)}


if __name__ == "__main__":
    args = sys.argv[1:]
    rpc = None
    if args and args[0] == "--rpc":
        rpc, args = args[1], args[2:]
    record = json.loads(args[0])
    if "anchor" not in record:            # accept a bare anchor for quick checks
        record = {"anchor": record, "thread_open": None}
    print(json.dumps(resolve(record, rpc)))
