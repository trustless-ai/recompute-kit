// Seam 4 (ERC-8294 ↔ ERC-8275/WYRIWE) — attestation-envelope alignment vector.
//
// Claim under test (from ERC-8275 §"Composition with ERC-8294", seam 4):
//   "ERC-8294 validators emit EIP-712 attestations; 8275 mesh nodes emit
//    WYRIWE/8274 commitments ... the two envelopes SHOULD align on their
//    committed fields so a single verifier checks both."
//
// This proves it in recomputable bytes: ONE generic EIP-712 verifier
// (verifyEnvelope) recovers the signer for BOTH envelope types from public
// fields + signature, and the shared field `agentId` aligns across them
// (8294 uint256  ↔  WYRIWE bytes32(uint256(id)), the ERC-8299 §"agentId" rule).
//
// Throwaway deterministic test key — NOT a real key. Anyone re-derives all
// values below with ethers stdlib alone.
import { ethers } from "ethers";

const PK = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"; // well-known anvil #1
const w = new ethers.Wallet(PK);
const SIGNER = w.address;
const AGENT_ID = 860n; // one agent, expressed two ways below

// --- ONE generic verifier for both envelope classes ---
// Given an EIP-712 (domain, types, message) + signature, recompute the digest
// and recover the signer. Identical code path for VNI and WYRIWE.
function verifyEnvelope(domain, types, message, sig) {
  const digest = ethers.TypedDataEncoder.hash(domain, types, message);
  const recovered = ethers.recoverAddress(digest, sig);
  return { digest, recovered };
}

// === Envelope A — ERC-8294 VNI Attestation ===
const domainVNI = { name: "ERC8004ValidationNetwork", version: "1", chainId: 1,
  verifyingContract: "0x000000000000000000000000000000000000A294" };
const typesVNI = { Attestation: [
  { name: "requestHash",  type: "bytes32" },
  { name: "agentId",      type: "uint256" },
  { name: "validator",    type: "address" },
  { name: "verdict",      type: "uint8"   },
  { name: "evidenceHash", type: "bytes32" },
  { name: "issuedAt",     type: "uint64"  },
  { name: "challengeKind",type: "bytes32" },
  { name: "nonceHash",    type: "bytes32" },
] };
const msgVNI = {
  requestHash:  ethers.id("vni-request-1"),
  agentId:      AGENT_ID,                       // uint256
  validator:    SIGNER,
  verdict:      100,
  evidenceHash: ethers.id("canonical-evidence-payload"),
  issuedAt:     1751430000n,
  challengeKind: ethers.id("rpc-equivalence"),
  nonceHash:    ethers.id("network-nonce-1"),
};

// === Envelope B — WYRIWE / 8274 WyriweAttestation ===
const domainWY = { name: "ERC8004AttestationGateway", version: "1", chainId: 1,
  verifyingContract: "0x000000000000000000000000000000000000A299" };
const typesWY = { WyriweAttestation: [
  { name: "agentId",                  type: "bytes32" },
  { name: "registry",                 type: "address" },
  { name: "modelHash",                type: "bytes32" },
  { name: "rawInputHash",             type: "bytes32" },
  { name: "sanitizationPipelineHash", type: "bytes32" },
  { name: "inputHash",                type: "bytes32" },
  { name: "outputHash",               type: "bytes32" },
  { name: "timestamp",                type: "uint256" },
] };
const agentIdBytes32 = ethers.zeroPadValue(ethers.toBeHex(AGENT_ID), 32); // bytes32(uint256(id)) — ERC-8299 rule
const msgWY = {
  agentId:                  agentIdBytes32,     // bytes32
  registry:                 "0xe61f5a6783ae09949b9a1b6821b68f89c0d7bb2d",
  modelHash:                ethers.id("model-manifest-v1"),
  rawInputHash:             ethers.id("raw_user_input"),
  sanitizationPipelineHash: ethers.id("sanitization-pipeline"),
  inputHash:                ethers.id("sanitized_input"),
  outputHash:               ethers.id("model_output"),   // aligns with VNI.evidenceHash role: the graded artifact
  timestamp:                1751430000n,
};

// --- sign both with the SAME key (a node that is both a VNI validator and a mesh node) ---
const sigVNI = await w.signTypedData(domainVNI, typesVNI, msgVNI);
const sigWY  = await w.signTypedData(domainWY,  typesWY,  msgWY);

// --- ONE verifier, BOTH envelopes ---
const A = verifyEnvelope(domainVNI, typesVNI, msgVNI, sigVNI);
const B = verifyEnvelope(domainWY,  typesWY,  msgWY,  sigWY);

const okA = A.recovered === SIGNER;
const okB = B.recovered === SIGNER;
// field alignment: the one agent, both encodings, must reconcile
const alignA = BigInt(msgVNI.agentId);
const alignB = BigInt(msgWY.agentId);
const aligned = alignA === alignB && alignA === AGENT_ID;

console.log("Seam 4 — one verifier, both envelopes");
console.log("─".repeat(52));
console.log("VNI  (ERC-8294)   digest:", A.digest);
console.log("VNI  recovered signer   :", A.recovered, okA ? "✓" : "✗");
console.log("WYRIWE (8274)     digest:", B.digest);
console.log("WYRIWE recovered signer :", B.recovered, okB ? "✓" : "✗");
console.log("agentId alignment       : 8294 uint256", alignA, "== WYRIWE bytes32", msgWY.agentId, "→", aligned ? "✓" : "✗");

// --- MUST-fail leg: tamper one committed field on each, keep the original sig ---
// A conformant verifier MUST reject — the recovered signer no longer matches.
const tA = verifyEnvelope(domainVNI, typesVNI, { ...msgVNI, verdict: 0 }, sigVNI);      // flip verdict 100→0
const tB = verifyEnvelope(domainWY,  typesWY,  { ...msgWY, outputHash: ethers.id("forged_output") }, sigWY);
const rejectA = tA.recovered !== SIGNER; // tampered VNI attestation rejected
const rejectB = tB.recovered !== SIGNER; // tampered WYRIWE attestation rejected
console.log("tamper VNI.verdict      : recover ≠ signer →", rejectA ? "✓ rejected" : "✗ ACCEPTED");
console.log("tamper WYRIWE.outputHash: recover ≠ signer →", rejectB ? "✓ rejected" : "✗ ACCEPTED");
console.log("─".repeat(52));

const pass = okA && okB && aligned && rejectA && rejectB;
console.log(pass
  ? "✓ SEAM 4 HOLDS — one EIP-712 verifier accepts both authentic envelopes, rejects both tampered; agentId aligns"
  : "✗ SEAM 4 FAILED");
process.exit(pass ? 0 : 1);
