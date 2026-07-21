// communication_chain.v0 — the recomputable communication act in the grammar humans use:
// Who · Said what · Through which channel · To whom · With what effect. Each link is an
// authentic Ethereum hash (keccak256 / ENS namehash via foundry `cast`), re-derivable from
// public inputs. A compliant capability reproduces all five; --tamper models a non-compliant
// one that misreports what was said, so one link fails to reproduce — live, in red.
//
// Adapter contract for bin/conformance-suite: fixture JSON on stdin -> {name: {value}} on stdout.

function cast(...args: string[]): string {
  const p = Bun.spawnSync(["cast", ...args]);
  if (p.exitCode !== 0) throw new Error(`cast ${args[0]} failed: ${new TextDecoder().decode(p.stderr)}`);
  return new TextDecoder().decode(p.stdout).trim();
}

// keccak256(utf8(input)) for a message/slug/address; ENS namehash for an identity.
function hashOf(kind: string, input: string): string {
  if (kind === "namehash") return cast("namehash", input);
  return cast("keccak", cast("from-utf8", input)); // keccak-utf8
}

if (import.meta.main) {
  const tamper = Bun.argv.includes("--tamper");
  if (Bun.argv.includes("--grade")) {
    const fx = JSON.parse(await Bun.stdin.text());
    const out: Record<string, unknown> = {};
    for (const v of fx.vectors) {
      // a non-compliant capability misreports the instruction it acted on
      const input = tamper && v.name === "said_what" ? v.input.replace("1 ETH", "10 ETH") : v.input;
      out[v.name] = { value: hashOf(v.kind, input) };
    }
    console.log(JSON.stringify(out));
    process.exit(0);
  }
  // human-readable self-run
  const fx = JSON.parse(await Bun.file(`${import.meta.dir}/communication-chain-v0.vectors.json`).text());
  for (const v of fx.vectors) {
    const got = hashOf(v.kind, v.input);
    const ok = got === v.expected.value;
    console.log(`${ok ? "✓" : "✗"} ${v.w.padEnd(24)} ${v.name.padEnd(11)} ${got}`);
  }
}
