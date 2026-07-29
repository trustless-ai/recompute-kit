// aggregate_budget.v0 — root-keyed conservation for ERC-8312, recomputed from the Drawn event LOG.
//
// The conserved carrier is ONE root-keyed meter: for a pinned (rootId, periodIndex),
//   admittedSum = Σ { amount : e.rootId = rootId ∧ e.periodIndex = periodIndex ∧ e.admitted }
//   conserves   = admittedSum ≤ cap
// Edge/node is attribution — a label on each draw — NEVER the conserved quantity. A per-edge
// counter treated as the aggregate is the non-conformant counterexample (the `fanout-exceeds-root-cap`
// vector): each edge is individually under cap, but the root-keyed sum is not. --tamper computes by
// exactly that wrong method (max per-edge subtotal as the aggregate), so the fan-out (and every
// multi-edge) vector fails — the vectors pin the PREDICATE + method, not just the numbers.
//
// Adapter contract for bin/conformance-suite: fixture JSON on stdin -> {name: result} on stdout.

type Draw = { rootId: string; periodIndex: number; edge: string; amount: string; admitted: boolean };
type Vector = { name: string; rootId: string; periodIndex: number; cap: string; log: Draw[]; expected: unknown };

const inScope = (e: Draw, v: Vector) =>
  e.admitted && e.rootId.toLowerCase() === v.rootId.toLowerCase() && e.periodIndex === v.periodIndex;

// Honest: the conserved carrier is the ROOT-keyed sum of admitted in-scope draws.
function rootKeyedSum(v: Vector): bigint {
  return v.log.filter((e) => inScope(e, v)).reduce((a, e) => a + BigInt(e.amount), 0n);
}

// Wrong (the counterexample method): treat the largest single-edge subtotal as the "aggregate".
// A fan-out spreads draws across fresh edges so no edge alone exceeds the cap — this walks past it.
function maxEdgeSubtotal(v: Vector): bigint {
  const byEdge = new Map<string, bigint>();
  for (const e of v.log) if (inScope(e, v)) byEdge.set(e.edge, (byEdge.get(e.edge) ?? 0n) + BigInt(e.amount));
  let max = 0n;
  for (const s of byEdge.values()) if (s > max) max = s;
  return max;
}

function valueFor(v: Vector, tamper: boolean): { admittedSum: string; conserves: boolean } {
  const sum = tamper ? maxEdgeSubtotal(v) : rootKeyedSum(v);
  return { admittedSum: sum.toString(), conserves: sum <= BigInt(v.cap) };
}

if (import.meta.main) {
  const tamper = Bun.argv.includes("--tamper");
  if (Bun.argv.includes("--grade")) {
    const fx = JSON.parse(await Bun.stdin.text());
    const out: Record<string, unknown> = {};
    for (const v of fx.vectors as Vector[]) out[v.name] = valueFor(v, tamper);
    console.log(JSON.stringify(out));
    process.exit(0);
  }
  // Standalone self-check: recompute each vector and diff against its pinned expected.
  const fx = JSON.parse(await Bun.file(`${import.meta.dir}/aggregate-budget-v0.vectors.json`).text());
  let fails = 0;
  for (const v of fx.vectors as Vector[]) {
    const got = valueFor(v, tamper);
    const ok = JSON.stringify(got) === JSON.stringify(v.expected);
    if (!ok) fails++;
    console.log(`${ok ? "✓" : "✗"} ${v.name.padEnd(34)} sum=${got.admittedSum.padStart(5)} cap=${String(v.cap).padStart(5)} conserves=${got.conserves}`);
  }
  console.log(`${fx.vectors.length - fails}/${fx.vectors.length} reproduced${tamper ? " (tamper: wrong per-edge method — mismatches are expected)" : ""}`);
  process.exit(fails ? 1 : 0);
}
