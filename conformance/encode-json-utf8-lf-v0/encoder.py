#!/usr/bin/env python3
"""Independent Python encoder for encode-json-utf8-lf.v0.

The object serializer is local to this contract. Only the scalar binary64
rendering rule is aligned with RFC 8785 section 3.2.2.3 / ECMAScript. Python's
json.dumps float rendering and Python's native code-point key ordering are not
used for normative output.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import pathlib
import struct
import sys
from typing import Any


SAFE_INTEGER = 9007199254740991
KNOWN_ERRORS = {
    "INTEGER_OUT_OF_RANGE",
    "NEGATIVE_ZERO",
    "NON_FINITE_NUMBER",
    "NON_SCALAR_KEY",
    "NON_SCALAR_STRING",
    "NUMBER_NOT_EXACTLY_BINARY64",
}


class DomainError(ValueError):
    def __init__(self, category: str):
        if category not in KNOWN_ERRORS:
            raise ValueError(f"unknown domain-error category: {category}")
        super().__init__(category)
        self.category = category


@dataclass(frozen=True)
class F64Value:
    bits: int
    value: float


@dataclass(frozen=True)
class IntegerValue:
    value: int


@dataclass(frozen=True)
class ObjectValue:
    entries: tuple[tuple[str, Any], ...]


def _is_scalar_string(value: str) -> bool:
    return all(not 0xD800 <= ord(ch) <= 0xDFFF for ch in value)


def _utf16_units(value: str) -> tuple[int, ...]:
    if not _is_scalar_string(value):
        raise DomainError("NON_SCALAR_KEY")
    raw = value.encode("utf-16-be")
    return tuple(int.from_bytes(raw[i : i + 2], "big") for i in range(0, len(raw), 2))


def _escape_string(value: str, *, key: bool = False, allow_surrogate: bool = False) -> str:
    out = ['"']
    short = {8: "\\b", 9: "\\t", 10: "\\n", 12: "\\f", 13: "\\r"}
    for ch in value:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            if allow_surrogate:
                out.append(f"\\u{cp:04x}")
                continue
            raise DomainError("NON_SCALAR_KEY" if key else "NON_SCALAR_STRING")
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif cp in short:
            out.append(short[cp])
        elif cp <= 0x1F:
            out.append(f"\\u{cp:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _ecmascript_number(value: float) -> str:
    """Render one already-validated binary64 value using ECMAScript spelling.

    CPython's repr supplies the shortest round-tripping coefficient. This code
    independently applies ECMAScript's fixed/exponent thresholds and exponent
    syntax; json.dumps is deliberately not involved.
    """
    if value == 0.0:
        return "0"
    sign = "-" if value < 0 else ""
    text = repr(abs(value)).lower()
    exponent = 0
    if "e" in text:
        mantissa, exponent_text = text.split("e", 1)
        exponent = int(exponent_text)
    else:
        mantissa = text
    if "." in mantissa:
        first, last = mantissa.split(".", 1)
    else:
        first, last = mantissa, ""
    if last == "0":
        last = ""
    if "e" not in text:
        return sign + first + ("." + last if last else "")
    if 0 < exponent < 21:
        digits = first + last
        zero_count = exponent + 1 - len(digits)
        if zero_count >= 0:
            return sign + digits + ("0" * zero_count)
        split = exponent + 1
        return sign + digits[:split] + "." + digits[split:]
    if -7 < exponent < 0:
        return sign + "0." + ("0" * (-exponent - 1)) + first + last
    exponent_sign = "+" if exponent >= 0 else "-"
    return sign + first + ("." + last if last else "") + "e" + exponent_sign + str(abs(exponent))


def _render_number(value: F64Value | IntegerValue, fault: str | None) -> str:
    permit_unsafe = fault == "permit_unsafe_integer"
    if isinstance(value, IntegerValue):
        if not permit_unsafe and abs(value.value) > SAFE_INTEGER:
            raise DomainError("INTEGER_OUT_OF_RANGE")
        number = float(value.value)
        if int(number) != value.value:
            raise DomainError("NUMBER_NOT_EXACTLY_BINARY64")
    else:
        number = value.value
        if not math.isfinite(number):
            raise DomainError("NON_FINITE_NUMBER")
        if number == 0.0 and value.bits >> 63:
            if fault != "permit_negative_zero":
                raise DomainError("NEGATIVE_ZERO")
        if number.is_integer() and not permit_unsafe and abs(number) > SAFE_INTEGER:
            raise DomainError("INTEGER_OUT_OF_RANGE")
    if fault == "python_native_numbers":
        return repr(number)
    return _ecmascript_number(number)


def _serialize(value: Any, fault: str | None = None) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (F64Value, IntegerValue)):
        return _render_number(value, fault)
    if isinstance(value, str):
        return _escape_string(value, allow_surrogate=fault == "permit_lone_surrogate")
    if isinstance(value, list):
        return "[" + ",".join(_serialize(item, fault) for item in value) + "]"
    if isinstance(value, ObjectValue):
        seen: set[str] = set()
        for key, _ in value.entries:
            if key in seen:
                raise ValueError("fixture transport contains duplicate object key")
            seen.add(key)
            if not _is_scalar_string(key) and fault != "permit_lone_surrogate":
                raise DomainError("NON_SCALAR_KEY")
        if fault == "codepoint_sort":
            entries = sorted(value.entries, key=lambda entry: entry[0])
        elif fault == "permit_lone_surrogate":
            entries = sorted(value.entries, key=lambda entry: tuple(ord(c) for c in entry[0]))
        else:
            entries = sorted(value.entries, key=lambda entry: _utf16_units(entry[0]))
        return "{" + ",".join(
            _escape_string(key, key=True, allow_surrogate=fault == "permit_lone_surrogate")
            + ":"
            + _serialize(item, fault)
            for key, item in entries
        ) + "}"
    raise TypeError(f"unsupported abstract value: {type(value).__name__}")


def encode(value: Any, fault: str | None = None) -> bytes:
    body = _serialize(value, fault).encode("utf-8")
    return body if fault == "missing_terminal_lf" else body + b"\n"


def decode_transport(node: dict[str, Any]) -> Any:
    kind = node.get("type")
    if kind == "null":
        return None
    if kind == "boolean":
        return bool(node["value"])
    if kind == "string":
        return node["value"]
    if kind == "integer":
        decimal = node["decimal"]
        if not isinstance(decimal, str) or not decimal or decimal in {"+", "-"}:
            raise ValueError("invalid integer carrier")
        return IntegerValue(int(decimal, 10))
    if kind == "f64_bits":
        raw_hex = node["hex"]
        if not isinstance(raw_hex, str) or len(raw_hex) != 16:
            raise ValueError("invalid f64_bits carrier")
        raw = bytes.fromhex(raw_hex)
        return F64Value(int.from_bytes(raw, "big"), struct.unpack(">d", raw)[0])
    if kind == "array":
        return [decode_transport(item) for item in node["items"]]
    if kind == "object":
        return ObjectValue(tuple((entry["key"], decode_transport(entry["value"])) for entry in node["entries"]))
    raise ValueError(f"unknown fixture transport type: {kind!r}")


def run_vectors(document: dict[str, Any], fault: str | None = None) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for vector in document["vectors"]:
        vector_id = vector["id"]
        try:
            encoded = encode(decode_transport(vector["input"]), fault)
            results[vector_id] = {
                "status": "success",
                "bytes_hex": encoded.hex(),
                "byte_length": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
        except DomainError as error:
            results[vector_id] = {"status": "rejection", "error": error.category}
    return results


def _self_grade(document: dict[str, Any], results: dict[str, dict[str, Any]]) -> list[str]:
    failures = []
    expected_ids = {vector["id"] for vector in document["vectors"]}
    if set(results) != expected_ids:
        failures.append("result id set does not match vector id set")
    for vector in document["vectors"]:
        if results.get(vector["id"]) != vector.get("expect"):
            failures.append(vector["id"])
    return failures


def main() -> int:
    grade = "--grade" in sys.argv
    fault = None
    if "--negative-control" in sys.argv:
        index = sys.argv.index("--negative-control")
        fault = sys.argv[index + 1]
    if grade:
        document = json.load(sys.stdin)
    else:
        path = pathlib.Path(__file__).with_name("encode-json-utf8-lf-v0.vectors.json")
        document = json.loads(path.read_text(encoding="utf-8"))
    results = run_vectors(document, fault)
    if grade:
        print(json.dumps(results, ensure_ascii=True, separators=(",", ":")))
        return 0
    failures = _self_grade(document, results)
    successes = sum(result["status"] == "success" for result in results.values())
    rejections = len(results) - successes
    print(f"Python adapter: {len(results) - len(failures)}/{len(results)} vectors; {successes} success; {rejections} rejection")
    if failures:
        for vector_id in failures:
            print(f"FAIL {vector_id}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
