// communication_chain.v0 — the recomputable communication act in the grammar humans use:
// Who · Said what · Through which channel · To whom · With what effect. Four links are authentic
// Ethereum hashes (keccak256 / ENS namehash via `cast`); the fifth ("effect") is recomputed from a
// LIVE ENS MCP tool call (ens_set_addr) — the capability's OWN output is what gets re-derived, so a
// compliant capability reproduces all five. --tamper misreports "said what" so that link fails live.
//
// Adapter contract for bin/conformance-suite: fixture JSON on stdin -> {name: {value}} on stdout.

const GW = process.env.CONFORMANCE_GATEWAY_URL || "https://gateway.ensub.org";
const TAMPER_ADDR = "0x000000000000000000000000000000000000dEaD"; // a misreported target

function cast(...args: string[]): string {
  const p = Bun.spawnSync(["cast", ...args]);
  if (p.exitCode !== 0) throw new Error(`cast ${args[0]} failed: ${new TextDecoder().decode(p.stderr)}`);
  return new TextDecoder().decode(p.stdout).trim();
}
const keccakUtf8 = (s: string) => cast("keccak", cast("from-utf8", s));

// Live MCP tool call: ask the ENS MCP to build the (deterministic) setAddr calldata, then recompute
// keccak256 over exactly the bytes it returned. If the capability is honest, this reproduces the
// pinned value; a capability that returned different bytes would not.
async function ensMcpKeccak(name: string, address: string): Promise<string> {
  const r = await fetch(`${GW}/mcp/ens`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call",
      params: { name: "ens_set_addr", arguments: { name, address } } }),
    signal: AbortSignal.timeout(20_000),
  });
  const d: any = await r.json();
  const calldata = JSON.parse(d.result.content[0].text).setAddrTx.data;
  return cast("keccak", calldata);
}

async function valueFor(v: any, tamper: boolean): Promise<string> {
  if (v.kind === "namehash") return cast("namehash", v.input);
  if (v.kind === "ens-mcp-setaddr") return ensMcpKeccak(v.mcp.name, v.mcp.address); // live; honest link
  // keccak-utf8 — a non-compliant capability misreports the instruction it acted on
  const input = tamper && v.name === "said_what"
    ? v.input.replace(/0x[0-9a-fA-F]{40}/, TAMPER_ADDR)
    : v.input;
  return keccakUtf8(input);
}

if (import.meta.main) {
  const tamper = Bun.argv.includes("--tamper");
  if (Bun.argv.includes("--grade")) {
    const fx = JSON.parse(await Bun.stdin.text());
    const out: Record<string, unknown> = {};
    for (const v of fx.vectors) out[v.name] = { value: await valueFor(v, tamper) };
    console.log(JSON.stringify(out));
    process.exit(0);
  }
  const fx = JSON.parse(await Bun.file(`${import.meta.dir}/communication-chain-v0.vectors.json`).text());
  for (const v of fx.vectors) {
    const got = await valueFor(v, false);
    console.log(`${got === v.expected.value ? "✓" : "✗"} ${v.w.padEnd(24)} ${v.name.padEnd(11)} ${got}`);
  }
}
