# recompute-kit MCP server

Exposes the three verbs as MCP tools — `recompute_repo`, `verify_claim`, `recheck_ci` —
each returning compact structured `{pass, ref, evidence}`. The heavy work (clone/compile/
test, PDF extraction, CI fetch) runs on the host, **off the chat**; only the verdict +
a short evidence tail crosses the wire. Streamable-HTTP on **:7079**.

## Run

```bash
cd recompute-kit
uv venv .venv && .venv/bin/python -m ensurepip -q
.venv/bin/uv pip install mcp        # or: pip install mcp
.venv/bin/python mcp/server.py      # → http://0.0.0.0:7079/mcp
```

The server pins `PATH` to include `~/.foundry/bin` + `/opt/homebrew/bin` so the verbs
find `forge`/`gh`/`pdftotext` even under a launchd/headless context.

## Always-on (macOS launchd)

```bash
cp mcp/com.echo.recompute-mcp.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.echo.recompute-mcp.plist   # RunAtLoad + KeepAlive
```

## Register with Claude Code

```bash
claude mcp add --scope user --transport http recompute-kit http://localhost:7079/mcp
```

## Health

A TCP listen on `:7079` means up. The Echo dashboard (`:7078`) probes it as
`recompute_mcp` and renders it under **MCP Servers → Recompute Kit (:7079)**.

## Tools

| tool | args | returns |
|---|---|---|
| `recompute_repo` | `git_url, ref, test_cmd="forge test"` | `{pass, sha, command, evidence}` |
| `verify_claim`   | `source, terms[]`                    | `{all_present, found{}, missing[], evidence}` |
| `recheck_ci`     | `repo, pr, config_path=""`           | `{all_pass, checks[], config?, evidence}` |
