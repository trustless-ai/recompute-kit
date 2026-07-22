// ens_write.v0 — grade the ENS write MCP against golden vectors of its OWN tool outputs.
// Each vector is a live tools/call to the ENS MCP; the returned calldata is deterministic
// (namehash + resolver encoding, no live reads), so keccak256 over it must reproduce the pinned
// value. --tamper models a non-compliant build that constructs a different (wrong-recipient) tx.
// Adapter for bin/conformance-suite: fixture JSON on stdin -> {name: {value}} on stdout.

const GW = process.env.CONFORMANCE_GATEWAY_URL || "https://gateway.ensub.org";
const TAMPER_ADDR = "0x000000000000000000000000000000000000dEaD";

function cast(...a: string[]): string {
  const p = Bun.spawnSync(["cast", ...a]);
  if (p.exitCode !== 0) throw new Error(`cast ${a[0]}: ${new TextDecoder().decode(p.stderr)}`);
  return new TextDecoder().decode(p.stdout).trim();
}

async function ensMcpKeccak(tool: string, args: any): Promise<string> {
  const r = await fetch(`${GW}/mcp/ens`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: tool, arguments: args } }),
    signal: AbortSignal.timeout(20_000),
  });
  const d: any = await r.json();
  const inner = JSON.parse(d.result.content[0].text);
  const tx = Object.values(inner).find((v: any) => v && typeof v === "object" && "data" in v) as any;
  return cast("keccak", tx.data);
}

async function valueFor(v: any, tamper: boolean): Promise<string> {
  const args = { ...v.mcp.args };
  if (tamper && v.name === "ens_set_addr · gobross.eth") args.address = TAMPER_ADDR; // non-compliant: wrong recipient
  return ensMcpKeccak(v.mcp.tool, args);
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
  const fx = JSON.parse(await Bun.file(`${import.meta.dir}/ens-write-v0.vectors.json`).text());
  for (const v of fx.vectors) {
    const got = await valueFor(v, false);
    console.log(`${got === v.expected.value ? "✓" : "✗"} ${v.name.padEnd(30)} ${got}`);
  }
}
