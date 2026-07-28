// tee-inference-enclave.v0 CANDIDATE adapter — the fully-recomputed genuine-enclave case. Every check is
// re-derived from the vector's PUBLIC bytes, with NO reliance on 0G's `tee_verified` router flag:
//
//   signature_recovery  recoverAddress(hashMessage(preimage), signature) == claimed_signer   (EIP-191)
//   request_digest      sha256(canonical) == the signed H(request)      (client-recomputable — genuine enclave)
//   response_digest     sha256(canonical) == the signed H(response)
//   rtmr_replay         SHA-384-extend the RTMR event log == the quote's RTMR0-3
//   equality            report_data == recovered signer · registry teeSignerAddress == report_data
//   dcap_quote_sig      the quote's HARDWARE root of trust (dcap-qvl core): the PCK cert chain verified up to
//                       the Intel SGX Root CA (PINNED), the QE-report sig, the att-key↔QE binding, the TD-quote sig
//
// The suite's `expected` is the value pulled from the PRIMARY ARTIFACT (a real mainnet glm-5.2 inference:
// provider 0x7DCFe6…, signer 0xA46EA4…). --tamper models a broken impl. Adapter contract for
// bin/conformance-suite: fixture JSON on stdin -> {name: {…verdict}} on stdout.
import { ethers } from "ethers";
import { X509Certificate, createPublicKey, verify, createHash } from "node:crypto";

const sha256 = (s: string) => createHash("sha256").update(s, "utf8").digest("hex");
const sha384 = (b: Buffer) => createHash("sha384").update(b).digest();

// Intel SGX Root CA, pinned by SHA-256 of its DER — the anchor the whole quote chains to.
const INTEL_SGX_ROOT_SHA256 = "44a0196b2b99f889b8e149e95b807a350e7424964399e885a7cbb8ccfab674d3";

// Recompute the TDX quote's hardware root of trust from the raw quote bytes (dcap-qvl core). Returns each
// sub-check so a tamper is legible, plus the overall verdict. No vendor SDK — Node crypto only.
function dcapVerify(quoteHex: string) {
  try {
    const raw = Buffer.from(quoteHex, "hex");
    const sub = (a: number, b: number) => raw.subarray(a, b);
    const pems = [...raw.toString("latin1").matchAll(/-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----/g)].map((m) => m[0]);
    const [leaf, inter, root] = pems.map((p) => new X509Certificate(p));
    const chain = leaf.verify(inter.publicKey) && inter.verify(root.publicKey) && root.verify(root.publicKey);
    const root_pinned = createHash("sha256").update(root.raw).digest("hex") === INTEL_SGX_ROOT_SHA256;
    const ver = (key: any, sig: Buffer, data: Buffer) => verify("sha256", data, { key, dsaEncoding: "ieee-p1363" as const }, sig);
    const qe_sig = ver(leaf.publicKey, sub(1154, 1218), sub(770, 1154));
    const authLen = raw.readUInt16LE(1218);
    const bind = createHash("sha256").update(Buffer.concat([sub(700, 764), sub(1220, 1220 + authLen)])).digest();
    const att_binding = bind.equals(sub(770 + 320, 770 + 320 + 32));
    const attKey = createPublicKey({ key: { kty: "EC", crv: "P-256", x: sub(700, 732).toString("base64url"), y: sub(732, 764).toString("base64url") }, format: "jwk" });
    const quote_sig = ver(attKey, sub(636, 700), sub(0, 632));
    return { ok: chain && root_pinned && qe_sig && att_binding && quote_sig, chain, root_pinned, qe_sig, att_binding, quote_sig };
  } catch {
    return { ok: false, chain: false, root_pinned: false, qe_sig: false, att_binding: false, quote_sig: false };
  }
}

function rtmrReplay(log: { imr: number | string; digest: string }[], quoteRtmrs: string[]): boolean[] {
  return [0, 1, 2, 3].map((imr) => {
    let acc = Buffer.alloc(48);
    for (const e of log) if (Number(e.imr) === imr && e.digest) acc = sha384(Buffer.concat([acc, Buffer.from(e.digest, "hex")]));
    return acc.toString("hex") === quoteRtmrs[imr];
  });
}

function verdict(v: any): Record<string, unknown> {
  const i = v.inputs;
  switch (v.check) {
    case "signature_recovery": {
      let recovered = "0xINVALID";
      try { recovered = ethers.verifyMessage(i.preimage, i.signature); } catch {}
      const ok = recovered.toLowerCase() === String(i.claimed_signer).toLowerCase();
      return { status: ok ? "verified" : "rejected", evidence_basis: "recomputed", recovered };
    }
    case "request_digest":
    case "response_digest": {
      const h = sha256(String(i.canonical));
      return { status: h === i.attested_hash ? "verified" : "rejected", evidence_basis: "recomputed", recomputed_hash: h };
    }
    case "rtmr_replay": {
      const matched = rtmrReplay(i.event_log, i.quote_rtmrs);
      return { status: matched.every(Boolean) ? "verified" : "rejected", evidence_basis: "recomputed", matched };
    }
    case "equality":
      return { status: String(i.a).toLowerCase() === String(i.b).toLowerCase() ? "verified" : "rejected", evidence_basis: "recomputed" };
    case "dcap_quote_sig": {
      const d = dcapVerify(String(i.quote_hex));
      return { status: d.ok ? "verified" : "rejected", evidence_basis: "recomputed", chain: d.chain, root_pinned: d.root_pinned, qe_sig: d.qe_sig, att_binding: d.att_binding, quote_sig: d.quote_sig };
    }
    default:
      return { status: "unverifiable", evidence_basis: "recomputed" };
  }
}

if (import.meta.main) {
  if (Bun.argv.includes("--grade")) {
    const fx = JSON.parse(await Bun.stdin.text());
    const out: Record<string, unknown> = {};
    for (const v of fx.vectors) out[v.name] = verdict(v);
    console.log(JSON.stringify(out));
    process.exit(0);
  }
  const fx = JSON.parse(await Bun.file(`${import.meta.dir}/tee-inference-enclave-v0.vectors.json`).text());
  for (const v of fx.vectors) {
    const got = JSON.stringify(verdict(v)), exp = JSON.stringify(v.expected);
    console.log(`${got === exp ? "✓" : "✗"} ${v.name}`);
  }
}
