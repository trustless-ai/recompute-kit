#!/usr/bin/env python3
"""recompute-kit MCP server — the recompute-don't-trust verbs as MCP tools.

Wraps bin/recompute-repo, bin/verify-claim, bin/recheck-ci and returns COMPACT
structured results ({pass, ref, evidence}), so the heavy work (clone/compile/test,
PDF extraction, CI fetch) runs here on the host — off the chat — and only the verdict
plus a short evidence tail crosses the wire. Streamable-HTTP on :7079.
"""
import os
import re
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"

# the verbs shell out to git/gh/forge/pdftotext/curl — forge lives in ~/.foundry/bin,
# the rest in /opt/homebrew/bin; a launchd/nohup service won't inherit those, so pin PATH.
ENV = dict(os.environ)
ENV["PATH"] = os.pathsep.join([
    str(Path.home() / ".foundry" / "bin"),
    str(Path.home() / ".bun" / "bin"),  # bun — conformance-suite adapters (e.g. the chronicle gate)
    "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin",
    ENV.get("PATH", ""),
])

mcp = FastMCP("recompute-kit", host="0.0.0.0", port=7079)


def _run(script: str, *args: str, timeout: int = 1200):
    cmd = [str(BIN / script), *map(str, args)]
    p = subprocess.run(cmd, capture_output=True, text=True, env=ENV, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def _tail(text: str, n: int = 25) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


def _verdict(rc: int, reversible: bool = False) -> dict:
    """Tri-state verdict from a recipe exit code (recompute-step convention):
    0 verified-good · 1 verified-bad · 2 UNVERIFIABLE (couldn't run: fetch/RPC/tool/timeout).
    'couldn't check' is its own verdict, never a pass — so an unverifiable result on an
    IRREVERSIBLE action fail-closes (defer/deny); on a reversible one it annotates."""
    v = {0: "verified-good", 1: "verified-bad", 2: "unverifiable"}.get(rc, "error")
    gate = {
        "verified-good": "proceed",
        "verified-bad": "deny",
        "unverifiable": "annotate" if reversible else "fail-closed (defer/deny)",
    }.get(v, "error")
    return {"verdict": v, "pass": rc == 0, "gate": gate}


@mcp.tool()
def recompute_repo(git_url: str, ref: str, test_cmd: str = "forge test") -> dict:
    """Clone a repo at an EXACT ref (commit SHA / branch / tag) and run its tests
    yourself — the atomic recomputation. Green only counts when it ran here.

    Args:
        git_url: clone URL of the repo.
        ref: the exact ref to pin (SHA preferred; branch/tag ok).
        test_cmd: command to run in the repo (default "forge test"; shell operators ok).
    Returns {pass, sha, git_url, ref, command, evidence}.
    """
    rc, out, err = _run("recompute-repo", git_url, ref, test_cmd)
    m = re.search(r"@ ([0-9a-f]{7,40})", out)
    return {
        "pass": rc == 0,
        "sha": m.group(1) if m else None,
        "git_url": git_url, "ref": ref, "command": test_cmd,
        "evidence": _tail(out + ("\n" + err if err.strip() else "")),
    }


@mcp.tool()
def verify_claim(source: str, terms: list[str], reversible: bool = False) -> dict:
    """Fetch a primary source (URL or local PDF/file) and report which claim-terms
    actually appear in it, with context — recompute a citation against the source.

    Args:
        source: a URL, a .pdf path, or a text file path.
        terms: claim-terms to look for (case-insensitive).
        reversible: governs the UNVERIFIABLE gate (source unfetchable) — False (default)
            fail-closes, True annotates.
    Returns {verdict, pass, gate, all_present, source, found, missing, evidence}.
    verdict ∈ verified-good / verified-bad (a term is missing) / unverifiable (couldn't fetch).
    """
    rc, out, err = _run("verify-claim", source, *terms)
    found = {}
    for line in out.splitlines():
        mc = re.match(r"^✓\s+(.+?)\s+(\d+)x$", line.strip())
        if mc:
            found[mc.group(1).strip()] = int(mc.group(2))
    # derive missing from the input terms — robust to any output/locale variance
    missing = [t for t in terms if t not in found] if rc != 2 else None
    return {
        **_verdict(rc, reversible), "all_present": rc == 0,
        "source": source, "found": found, "missing": missing,
        "evidence": out.strip()[-1500:] or err.strip()[-500:],
    }


@mcp.tool()
def recheck_ci(repo: str, pr: int, config_path: str = "") -> dict:
    """Pull the REAL CI verdict for a PR (gh pr checks) instead of trusting a pasted
    summary, and optionally fetch a lint/CI config from the PR head to re-derive a rule.

    Args:
        repo: "owner/repo".
        pr: PR number.
        config_path: optional path in the head repo to fetch (e.g. "config/eipw.toml").
    Returns {all_pass, repo, pr, checks:[{name,status}], config?, evidence}.
    """
    args = [repo, str(pr)] + ([config_path] if config_path else [])
    rc, out, err = _run("recheck-ci", *args)
    checks, config = [], None
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].strip() in ("pass", "fail", "pending", "skipping"):
            checks.append({"name": parts[0].strip(), "status": parts[1].strip()})
    if config_path and "read the source" in out:
        config = out.split("read the source", 1)[1]
    result = {
        "all_pass": bool(checks) and all(c["status"] == "pass" for c in checks),
        "repo": repo, "pr": pr, "checks": checks,
        "evidence": out.strip()[-2000:],
    }
    if config:
        result["config"] = config[-3000:]
    return result


@mcp.tool()
def recompute_onchain(rpc_url: str, block: str, address: str, sig: str, expect: str,
                      args: list[str] = [], reversible: bool = False) -> dict:
    """Recompute a fact FROM CHAIN: cast-call a view function at a PINNED block and
    compare the result to a claimed value. The block number is the immutable ref (the
    on-chain analog of a commit SHA) — prefer a real block over "latest".

    Args:
        rpc_url: JSON-RPC endpoint.
        block: block number to pin at (or "latest", not a pin).
        address: contract address.
        sig: cast return-typed signature, e.g. "totalSupply()(uint256)".
        expect: the claimed value to check against.
        args: call arguments, if any.
        reversible: governs the UNVERIFIABLE gate (RPC unreachable / call reverted) —
            False (default) fail-closes, True annotates.
    Returns {verdict, pass, gate, match, block, address, sig, expected, evidence}.
    verdict ∈ verified-good / verified-bad (value ≠ claim) / unverifiable (couldn't read chain).
    """
    rc, out, err = _run("recompute-onchain", rpc_url, block, address, sig, expect, *args)
    return {
        **_verdict(rc, reversible), "match": rc == 0, "block": block, "address": address, "sig": sig,
        "expected": expect,
        "evidence": _tail(out + ("\n" + err if err.strip() else ""), 12),
    }


@mcp.tool()
def recompute_storage_proof(rpc_url: str, block: str, address: str, slot: str,
                            expect: str = "", reversible: bool = False) -> dict:
    """Recompute a contract storage value the TRUSTLESS way — not a `cast call` that trusts
    the RPC's state, but an `eth_getProof` Merkle-Patricia inclusion verified against the
    block's committed stateRoot (account → stateRoot, slot → account.storageRoot). A lying or
    mis-structured RPC can't fake a value: the proof must root to the canonical header.

    Args:
        rpc_url: JSON-RPC endpoint (recent block; archive needs an archive node).
        block: block number (or hex) to pin at.
        address: contract address.
        slot: 32-byte storage slot (hex).
        expect: optional claimed value to check the proven value against.
        reversible: governs the UNVERIFIABLE gate (RPC/proof unreachable).
    Returns {verdict, pass, gate, block, address, slot, evidence}.
    """
    a = [rpc_url, block, address, slot] + ([expect] if expect else [])
    rc, out, err = _run("recompute-storage-proof", *a)
    return {
        **_verdict(rc, reversible), "block": block, "address": address, "slot": slot,
        "evidence": _tail(out + ("\n" + err if err.strip() else ""), 12),
    }


@mcp.tool()
def recompute_receipt_proof(rpc_url: str, block: str, target: str,
                            log_address: str = "", log_topic0: str = "",
                            reversible: bool = False) -> dict:
    """Recompute that a LOG/event is genuinely committed on-chain — events aren't contract-
    readable state, but the header commits them via receiptsRoot. Rebuilds the block's receipt
    Merkle-Patricia trie from `eth_getBlockReceipts` and checks the computed root ==
    header.receiptsRoot (so an indexer/cache can't serve a log that doesn't rebuild into the
    canonical root), then confirms the target tx's receipt carries the log. No trust in eth_getLogs.

    Args:
        rpc_url: JSON-RPC endpoint (needs eth_getBlockReceipts).
        block: block number (or hex).
        target: target transaction hash (0x… 32B) or transaction index.
        log_address: optional log emitter to require.
        log_topic0: optional event signature topic to require.
        reversible: governs the UNVERIFIABLE gate.
    Returns {verdict, pass, gate, block, target, log_address, log_topic0, evidence}.
    """
    a = [rpc_url, block, target] + ([log_address, log_topic0] if log_address else [])
    rc, out, err = _run("recompute-receipt-proof", *a)
    return {
        **_verdict(rc, reversible), "block": block, "target": target,
        "log_address": log_address or None, "log_topic0": log_topic0 or None,
        "evidence": _tail(out + ("\n" + err if err.strip() else ""), 14),
    }


@mcp.tool()
def recompute_commitment(scheme: str, expect: str, args: list[str]) -> dict:
    """Recompute a digest from PUBLIC inputs and compare to a committed value — the
    family's verify-step ("recompute from public data, no trusted party") as a tool.

    Args:
        scheme: "keccak" (keccak256 of a hex blob) or "abi-keccak"
                (keccak256(abi.encode(...)), e.g. bind(root,N)).
        expect: the committed digest to check against.
        args: for keccak → [hexdata]; for abi-keccak → ["<sig>", value, value, ...].
    Returns {match, scheme, expected, evidence}.
    """
    rc, out, err = _run("recompute-commitment", scheme, expect, *args)
    return {
        "match": rc == 0, "scheme": scheme, "expected": expect,
        "evidence": _tail(out + ("\n" + err if err.strip() else ""), 12),
    }


@mcp.tool()
def recompute_step(recipe: str = "list", args: list[str] = [], reversible: bool = False) -> dict:
    """Recompute a named step of the agent-standards flow from public inputs, composing
    the kit's primitives — the ERC-specific recompute recipe per step.

    Args:
        recipe: "list" to see recipes, or a recipe name. Seed recipes:
            wyriwe/raw, wyriwe/pipeline (input-provenance, ERC-8299);
            8004/agent-id (bytes32(uint256(registryId)) — the ERC-8004 registry identity, NOT a
            name hash); name/keccak-binding (keccak(utf8(label)) — a name→handle binding);
            ens/namehash (EIP-137 ENS node); scope/binding, scope/value-fidelity (completeness);
            scope/contest-verify (the four-guard + guard-7 contest() separation verdict —
            the materiality the completeness bond slashes on; tri-state via its guard-7 leg);
            8312/cap-conservation (reserved+confirmed ≤ cap, storage-proven vs stateRoot —
            the indexer-uncheatable audit half of the ERC-8312 cursor);
            8263/precedence, scope/bond-standing (precedence + Layer-3 defense).
        args: the recipe's inputs (see `list`).
        reversible: is the action being gated reversible? Governs the UNVERIFIABLE gate:
            False (default, safe) → fail-closed; True → annotate.
    Returns {recipe, verdict, pass, gate, evidence}. verdict ∈ verified-good /
    verified-bad / unverifiable — "couldn't check" is its own verdict, never a pass.
    """
    rc, out, err = _run("recompute-step", recipe, *args)
    v = _verdict(rc, reversible) if recipe != "list" else {"verdict": "n/a", "pass": rc == 0, "gate": "n/a"}
    return {
        "recipe": recipe, **v,
        "evidence": _tail(out + ("\n" + err if err.strip() else ""), 20),
    }


@mcp.tool()
def conformance_run(suite: str, adapter_cmd: str = "", vectors_sha256: str = "",
                    reversible: bool = False) -> dict:
    """Grade a candidate against a HASH-PINNED golden-vector suite — the machine gate as a verb.

    Recomputes SHA-256 over the suite's exact vector bytes and **fail-closes on a mismatch**
    (unverifiable, never a pass), then runs every vector through the candidate `adapter` and
    compares each result to its `expected`. Conformant iff every expected is reproduced — not
    iff it matches a reference SDK. The run is itself recomputable.

    Args:
        suite: path to a suite dir containing `suite.json` (profile, vectors{path,sha256}, adapter).
        adapter_cmd: override the suite's adapter — a shell cmd that reads the vectors JSON on
            stdin and writes {name: result} JSON on stdout (any language qualifies by honoring
            the contract). Runs with cwd = the suite dir.
        vectors_sha256: override/require the declared vectors hash (for a bare vectors path).
        reversible: governs the UNVERIFIABLE gate (hash mismatch / adapter couldn't run) —
            False (default, safe) fail-closes, True annotates.
    Returns {suite, verdict, pass, gate, reproduced, total, evidence}. verdict ∈ verified-good /
    verified-bad (a vector mismatched) / unverifiable (hash mismatch or adapter failure).
    """
    a = ["--suite", suite]
    if adapter_cmd:
        a += ["--adapter-cmd", adapter_cmd]
    if vectors_sha256:
        a += ["--vectors-sha256", vectors_sha256]
    rc, out, err = _run("conformance-suite", *a)
    m = re.search(r"(\d+)/(\d+) reproduced", out)
    return {
        "suite": suite, **_verdict(rc, reversible),
        "reproduced": int(m.group(1)) if m else None,
        "total": int(m.group(2)) if m else None,
        "evidence": _tail(out + ("\n" + err if err.strip() else ""), 24),
    }


# ── HTTP face for the conformance gate (so the marketplace gateway / any caller can invoke it
#    over plain HTTP, not only as an MCP tool). Same engine (bin/conformance-suite), same tri-state.
from starlette.requests import Request
from starlette.responses import JSONResponse
import json as _json
import tempfile
import hashlib

# ── portable conformance RECEIPT (crystal-receipt / ReceiptOS compatible) ──────────────────────
# A submitter's run is minted as a self-contained receiptos.evidence_capsule.v0 they can DOWNLOAD
# and re-verify OFFLINE, no trust in this gate: the root recomputes by the receiptos-c14n-v0 rule
# and every vector carries its rule + expected + got so the verdict is independently re-derivable.
def _receipt_root(receipt: dict) -> str:
    # receiptos-c14n-v0: "0x" + sha256(JCS(receipt \ {anchor, receipt_root}))
    content = {k: v for k, v in receipt.items() if k not in ("anchor", "receipt_root")}
    c = _json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "0x" + hashlib.sha256(c.encode("utf-8")).hexdigest()

def _build_receipt(run: dict, candidate: dict) -> dict:
    ok = bool(run.get("pass"))
    rep, tot = run.get("reproduced"), run.get("total")
    receipt = {
        "schema": "receiptos.evidence_capsule.v0",
        "action": {
            "summary": f"Conformance grade: {candidate.get('label', 'MCP')} against {run.get('profile')}",
            "source_fields": ["candidate.endpoint", "capsule.suite.vectors_sha256"],
        },
        "evidence": {
            "summary": (f"{rep}/{tot} golden vectors reproduced — the MCP's output matched the "
                        "recompute-kit's independent derivation from public rules"
                        if ok else f"{rep}/{tot} reproduced — the MCP did not build what the rules dictate"),
            "source_fields": ["capsule.results[].expected", "capsule.results[].got"],
            "status": "present",
        },
        "verifier_result": {"ok": ok, "status": "verified" if ok else "rejected"},
        "capsule": {
            "profile": run.get("profile"),
            "suite": {"vectors_sha256": run.get("vectors_sha256"),
                      "spec_sha256": run.get("spec_sha256"),
                      "recompute": run.get("recompute")},
            "candidate": candidate,
            "verdict": {"pass": ok, "reproduced": rep, "total": tot},
            "results": run.get("results", []),
        },
        "anchor": {"ran_at": run.get("ran_at"), "runner": run.get("runner", "recompute-kit/conformance-suite")},
    }
    root = _receipt_root(receipt)
    receipt["receipt_root"] = {"stored": root, "computed": root, "match": True, "status": "verified",
                               "derivation": "receiptos-c14n-v0 — 0x + sha256(JCS(receipt \\ {anchor, receipt_root}))"}
    return receipt

@mcp.custom_route("/conformance/run", methods=["POST"])
async def conformance_http(request: Request):
    """POST { suite, adapter_cmd?, vectors_sha256? } -> the machine gate over HTTP.
    Returns { verdict, pass, reproduced, total, run, evidence }. Fail-closed on hash mismatch."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "expected JSON body"}, status_code=400)
    suite = (body or {}).get("suite")
    if not suite:
        return JSONResponse({"error": "missing 'suite'"}, status_code=400)
    a = ["--suite", suite]
    if body.get("adapter_cmd"):
        a += ["--adapter-cmd", body["adapter_cmd"]]
    if body.get("vectors_sha256"):
        a += ["--vectors-sha256", body["vectors_sha256"]]
    out_path = tempfile.mktemp(suffix=".json")
    a += ["--out", out_path]
    rc, out, err = _run("conformance-suite", *a)
    run = None
    try:
        run = _json.load(open(out_path)); os.unlink(out_path)
    except Exception:
        pass
    m = re.search(r"(\d+)/(\d+) reproduced", out)
    receipt = _build_receipt(run, body.get("candidate") or {}) if run else None
    return JSONResponse({
        **_verdict(rc, reversible=False),
        "suite": suite,
        "reproduced": int(m.group(1)) if m else None,
        "total": int(m.group(2)) if m else None,
        "run": run,
        "receipt": receipt,
        "evidence": _tail(out + ("\n" + err if err.strip() else ""), 30),
    })


# ── self-service: drop an MCP endpoint → detect its recomputable tools → grade → mint a receipt ──
import asyncio
import time
import urllib.request

def _cast(*args: str) -> str:
    p = subprocess.run(["cast", *args], capture_output=True, text=True, env=ENV)
    if p.returncode != 0:
        raise RuntimeError(f"cast {args[0]}: {p.stderr.strip()}")
    return p.stdout.strip()

def _mcp_post(endpoint: str, payload: dict) -> dict:
    req = urllib.request.Request(endpoint, method="POST", headers={
        "Content-Type": "application/json",
        # Cloudflare-fronted endpoints 403 the default python-urllib UA; present a normal client.
        "User-Agent": "Mozilla/5.0 (recompute-kit/introspect)",
        "Accept": "application/json",
    }, data=_json.dumps(payload).encode())
    with urllib.request.urlopen(req, timeout=20) as r:
        return _json.loads(r.read())

def _tool_calldata(endpoint: str, tool: str, args: dict):
    d = _mcp_post(endpoint, {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": tool, "arguments": args}})
    inner = _json.loads(d["result"]["content"][0]["text"])
    for v in inner.values():
        if isinstance(v, dict) and "data" in v:
            return v["data"]
    return None

# Recipe registry — how to INDEPENDENTLY derive a tool's output from public rules. A tool with no
# recipe here is not recomputable (→ Attested). The registry grows; each recipe added makes one more
# slice of any MCP auto-gradeable.
RECIPES = {
    "ens_set_addr":    {"desc": "setAddr(namehash(name), address)",
                        "sample": {"name": "dinamic.eth", "address": "0xFf9a176577Fb42b6bc9c19fd05a241e8fCd0ca14"},
                        "sig": "setAddr(bytes32,address)", "params": lambda a: [_cast("namehash", a["name"]), a["address"]]},
    "ens_set_text":    {"desc": "setText(namehash(name), key, value)",
                        "sample": {"name": "dinamic.eth", "key": "url", "value": "https://verticecriativo.pt"},
                        "sig": "setText(bytes32,string,string)", "params": lambda a: [_cast("namehash", a["name"]), a["key"], a["value"]]},
    "ens_set_primary": {"desc": "setName(name) [reverse registrar]",
                        "sample": {"name": "dinamic.eth"},
                        "sig": "setName(string)", "params": lambda a: [a["name"]]},
}

def _derive(recipe: dict, args: dict) -> str:
    return _cast("calldata", recipe["sig"], *recipe["params"](args))

@mcp.custom_route("/conformance/introspect", methods=["POST"])
async def introspect(request: Request):
    """POST { endpoint } → introspect an MCP (tools/list), match each tool against the recompute
    recipe registry, grade the recomputable ones against the INDEPENDENT rule-derivation, and mint a
    portable receipt over them. Tools with no recipe are reported Attested (not recomputable)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "expected JSON body"}, status_code=400)
    endpoint = (body or {}).get("endpoint")
    if not endpoint:
        return JSONResponse({"error": "missing 'endpoint'"}, status_code=400)

    def work():
        try:
            listing = _mcp_post(endpoint, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            tools = listing.get("result", {}).get("tools", [])
        except Exception as e:
            return {"error": f"could not introspect endpoint: {e}"}
        graded = []
        for t in tools:
            name = t.get("name"); recipe = RECIPES.get(name)
            if not recipe:
                graded.append({"tool": name, "lane": "attested", "reason": "no recompute recipe"})
                continue
            try:
                args = recipe["sample"]
                expected = _derive(recipe, args)
                got = _tool_calldata(endpoint, name, args)
                graded.append({"tool": name, "lane": "recomputable", "recompute": recipe["desc"],
                               "args": args, "expected": {"value": expected}, "got": {"value": got},
                               "ok": expected == got})
            except Exception as e:
                graded.append({"tool": name, "lane": "attested", "reason": f"recipe error: {e}"})
        rec = [g for g in graded if g["lane"] == "recomputable"]
        passed = len(rec) > 0 and all(g["ok"] for g in rec)
        run = {
            "profile": "mcp_introspect.v0", "vectors_sha256": None,
            "recompute": "per tool: independent derivation from public rules (recompute-kit recipe registry)",
            "runner": "recompute-kit/introspect", "ran_at": int(time.time()),
            "pass": passed, "reproduced": sum(1 for g in rec if g["ok"]), "total": len(rec),
            "results": [{"name": g["tool"], "recompute": g["recompute"],
                         "expected": g["expected"], "got": g["got"], "ok": g["ok"]} for g in rec],
        }
        receipt = _build_receipt(run, {"label": "Submitted MCP", "endpoint": endpoint}) if rec else None
        return {"endpoint": endpoint, "tools": graded,
                "recomputable": len(rec), "attested": len(graded) - len(rec),
                "pass": passed, "receipt": receipt}

    result = await asyncio.to_thread(work)
    return JSONResponse(result, status_code=(200 if "error" not in result else 502))


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
