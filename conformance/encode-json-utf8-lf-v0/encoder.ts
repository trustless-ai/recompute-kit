#!/usr/bin/env bun
/** Independent TypeScript encoder for encode-json-utf8-lf.v0. */

import { createHash } from "node:crypto";

const SAFE_INTEGER = 9007199254740991;
const KNOWN_ERRORS = new Set([
  "INTEGER_OUT_OF_RANGE",
  "NEGATIVE_ZERO",
  "NON_FINITE_NUMBER",
  "NON_SCALAR_KEY",
  "NON_SCALAR_STRING",
  "NUMBER_NOT_EXACTLY_BINARY64",
]);

class DomainError extends Error {
  category: string;

  constructor(category: string) {
    if (!KNOWN_ERRORS.has(category)) throw new Error(`unknown domain-error category: ${category}`);
    super(category);
    this.category = category;
  }
}

type F64Value = { kind: "f64"; bits: bigint; value: number };
type IntegerValue = { kind: "integer"; value: bigint };
type ObjectValue = { kind: "object"; entries: Array<[string, AbstractValue]> };
type AbstractValue = null | boolean | string | F64Value | IntegerValue | ObjectValue | AbstractValue[];

type Transport = {
  type: string;
  value?: unknown;
  decimal?: string;
  hex?: string;
  items?: Transport[];
  entries?: Array<{ key: string; value: Transport }>;
};

type VectorDocument = {
  vectors: Array<{ id: string; input: Transport; expect?: AdapterResult }>;
};

type AdapterResult =
  | { status: "success"; bytes_hex: string; byte_length: number; sha256: string }
  | { status: "rejection"; error: string };

function scalarError(value: string, key: boolean): string | null {
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      if (index + 1 >= value.length) return key ? "NON_SCALAR_KEY" : "NON_SCALAR_STRING";
      const low = value.charCodeAt(index + 1);
      if (low < 0xdc00 || low > 0xdfff) return key ? "NON_SCALAR_KEY" : "NON_SCALAR_STRING";
      index += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      return key ? "NON_SCALAR_KEY" : "NON_SCALAR_STRING";
    }
  }
  return null;
}

function compareUtf16(left: string, right: string): number {
  const shared = Math.min(left.length, right.length);
  for (let index = 0; index < shared; index += 1) {
    const a = left.charCodeAt(index);
    const b = right.charCodeAt(index);
    if (a !== b) return a < b ? -1 : 1;
  }
  return left.length - right.length;
}

function escapeString(value: string, key = false): string {
  const invalid = scalarError(value, key);
  if (invalid) throw new DomainError(invalid);
  let out = '"';
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      out += value[index] + value[index + 1];
      index += 1;
      continue;
    }
    if (unit === 0x22) out += '\\"';
    else if (unit === 0x5c) out += "\\\\";
    else if (unit === 0x08) out += "\\b";
    else if (unit === 0x0c) out += "\\f";
    else if (unit === 0x0a) out += "\\n";
    else if (unit === 0x0d) out += "\\r";
    else if (unit === 0x09) out += "\\t";
    else if (unit <= 0x1f) out += `\\u${unit.toString(16).padStart(4, "0")}`;
    else out += value[index];
  }
  return out + '"';
}

function renderNumber(value: F64Value | IntegerValue): string {
  let number: number;
  if (value.kind === "integer") {
    const bound = 9007199254740991n;
    if (value.value < -bound || value.value > bound) throw new DomainError("INTEGER_OUT_OF_RANGE");
    number = Number(value.value);
    if (BigInt(number) !== value.value) throw new DomainError("NUMBER_NOT_EXACTLY_BINARY64");
  } else {
    number = value.value;
    if (!Number.isFinite(number)) throw new DomainError("NON_FINITE_NUMBER");
    if (Object.is(number, -0)) throw new DomainError("NEGATIVE_ZERO");
    if (Number.isInteger(number) && Math.abs(number) > SAFE_INTEGER) {
      throw new DomainError("INTEGER_OUT_OF_RANGE");
    }
  }
  // This call occurs only after the v0 domain has accepted the scalar. It is
  // the isolated ECMAScript/RFC 8785 section 3.2.2.3 number-rendering step.
  return JSON.stringify(number);
}

function serialize(value: AbstractValue): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return escapeString(value);
  if (Array.isArray(value)) return `[${value.map(serialize).join(",")}]`;
  if (value.kind === "f64" || value.kind === "integer") return renderNumber(value);
  const seen = new Set<string>();
  for (const [key] of value.entries) {
    const invalid = scalarError(key, true);
    if (invalid) throw new DomainError(invalid);
    if (seen.has(key)) throw new Error("fixture transport contains duplicate object key");
    seen.add(key);
  }
  const entries = [...value.entries].sort((a, b) => compareUtf16(a[0], b[0]));
  return `{${entries.map(([key, item]) => `${escapeString(key, true)}:${serialize(item)}`).join(",")}}`;
}

function encode(value: AbstractValue): Uint8Array {
  return new TextEncoder().encode(`${serialize(value)}\n`);
}

function decodeTransport(node: Transport): AbstractValue {
  if (node.type === "null") return null;
  if (node.type === "boolean") return Boolean(node.value);
  if (node.type === "string") return String(node.value);
  if (node.type === "integer") {
    if (typeof node.decimal !== "string" || !/^-?(0|[1-9][0-9]*)$/.test(node.decimal)) {
      throw new Error("invalid integer carrier");
    }
    return { kind: "integer", value: BigInt(node.decimal) };
  }
  if (node.type === "f64_bits") {
    if (typeof node.hex !== "string" || !/^[0-9a-f]{16}$/.test(node.hex)) {
      throw new Error("invalid f64_bits carrier");
    }
    const bits = BigInt(`0x${node.hex}`);
    const buffer = new ArrayBuffer(8);
    const view = new DataView(buffer);
    view.setBigUint64(0, bits, false);
    return { kind: "f64", bits, value: view.getFloat64(0, false) };
  }
  if (node.type === "array") return (node.items ?? []).map(decodeTransport);
  if (node.type === "object") {
    return {
      kind: "object",
      entries: (node.entries ?? []).map((entry) => [entry.key, decodeTransport(entry.value)]),
    };
  }
  throw new Error(`unknown fixture transport type: ${node.type}`);
}

function runVectors(document: VectorDocument): Record<string, AdapterResult> {
  const results: Record<string, AdapterResult> = {};
  for (const vector of document.vectors) {
    try {
      const bytes = encode(decodeTransport(vector.input));
      results[vector.id] = {
        status: "success",
        bytes_hex: Buffer.from(bytes).toString("hex"),
        byte_length: bytes.byteLength,
        sha256: createHash("sha256").update(bytes).digest("hex"),
      };
    } catch (error) {
      if (!(error instanceof DomainError)) throw error;
      results[vector.id] = { status: "rejection", error: error.category };
    }
  }
  return results;
}

function selfGrade(document: VectorDocument, results: Record<string, AdapterResult>): string[] {
  const expectedIds = document.vectors.map((vector) => vector.id).sort();
  const actualIds = Object.keys(results).sort();
  const failures: string[] = [];
  if (JSON.stringify(expectedIds) !== JSON.stringify(actualIds)) failures.push("result id set");
  for (const vector of document.vectors) {
    if (JSON.stringify(results[vector.id]) !== JSON.stringify(vector.expect)) failures.push(vector.id);
  }
  return failures;
}

async function main(): Promise<number> {
  const grade = Bun.argv.includes("--grade");
  const document = grade
    ? (JSON.parse(await Bun.stdin.text()) as VectorDocument)
    : (JSON.parse(await Bun.file(`${import.meta.dir}/encode-json-utf8-lf-v0.vectors.json`).text()) as VectorDocument);
  const results = runVectors(document);
  if (grade) {
    process.stdout.write(`${JSON.stringify(results)}\n`);
    return 0;
  }
  const failures = selfGrade(document, results);
  const successes = Object.values(results).filter((result) => result.status === "success").length;
  console.log(`TypeScript adapter: ${document.vectors.length - failures.length}/${document.vectors.length} vectors; ${successes} success; ${document.vectors.length - successes} rejection`);
  for (const vectorId of failures) console.log(`FAIL ${vectorId}`);
  return failures.length ? 1 : 0;
}

if (import.meta.main) process.exit(await main());

export { decodeTransport, encode, runVectors };
