// ens_write.v0 CANDIDATE adapter — the submitted MCP. For each vector the adapter calls the ENS
// MCP tool and returns the RAW calldata it built. The suite's `expected` is the recompute-kit's
// INDEPENDENT derivation of that transaction from public ENS rules (EIP-137 namehash + resolver
// ABI), so conformance = "the MCP built byte-for-byte what the rules dictate". --tamper models a
// non-compliant build that constructs a different transaction (wrong recipient) — caught by the rules.
// Adapter contract for bin/conformance-suite: fixture JSON on stdin -> {name: {value}} on stdout.

const GW = process.env.CONFORMANCE_GATEWAY_URL || "https://gateway.ensub.org";
const TAMPER_ADDR = "0x000000000000000000000000000000000000dEaD";

async function mcpCalldata(tool: string, args: any): Promise<string> {
  const r = await fetch(`${GW}/mcp/ens`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: tool, arguments: args } }),
    signal: AbortSignal.timeout(20_000),
  });
  const d: any = await r.json();
  const inner = JSON.parse(d.result.content[0].text);
  const tx = Object.values(inner).find((v: any) => v && typeof v === "object" && "data" in v) as any;
  return tx.data;
}

async function valueFor(v: any, tamper: boolean): Promise<string> {
  const args = { ...v.mcp.args };
  if (tamper && v.name === "ens_set_addr · gobross.eth") args.address = TAMPER_ADDR; // non-compliant build
  return mcpCalldata(v.mcp.tool, args);
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
    console.log(`${got === v.expected.value ? "✓" : "✗"} ${v.name}`);
  }
}
