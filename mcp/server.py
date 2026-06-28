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
def verify_claim(source: str, terms: list[str]) -> dict:
    """Fetch a primary source (URL or local PDF/file) and report which claim-terms
    actually appear in it, with context — recompute a citation against the source.

    Args:
        source: a URL, a .pdf path, or a text file path.
        terms: claim-terms to look for (case-insensitive).
    Returns {all_present, source, found:{term:count}, missing:[...], evidence}.
    """
    rc, out, err = _run("verify-claim", source, *terms)
    found = {}
    for line in out.splitlines():
        mc = re.match(r"^✓\s+(.+?)\s+(\d+)x$", line.strip())
        if mc:
            found[mc.group(1).strip()] = int(mc.group(2))
    # derive missing from the input terms — robust to any output/locale variance
    missing = [t for t in terms if t not in found]
    return {
        "all_present": rc == 0,
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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
