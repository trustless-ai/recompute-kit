#!/usr/bin/env python3
"""Cross-language conformance gate for encode-json-utf8-lf.v0."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
SUITE_PATH = HERE / "suite.json"
KNOWN_ERRORS = {
    "INTEGER_OUT_OF_RANGE",
    "NEGATIVE_ZERO",
    "NON_FINITE_NUMBER",
    "NON_SCALAR_KEY",
    "NON_SCALAR_STRING",
    "NUMBER_NOT_EXACTLY_BINARY64",
}
NEGATIVE_CONTROLS = (
    "codepoint_sort",
    "python_native_numbers",
    "permit_negative_zero",
    "permit_unsafe_integer",
    "missing_terminal_lf",
    "permit_lone_surrogate",
)


class GateFailure(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_and_verify(stdin_bytes: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
    if suite.get("contract_id") != "encode-json-utf8-lf.v0":
        raise GateFailure("suite contract_id is not encode-json-utf8-lf.v0")
    for key in ("spec", "vectors"):
        pin = suite.get(key)
        if not isinstance(pin, dict) or not pin.get("path") or not pin.get("sha256"):
            raise GateFailure(f"suite is missing the {key} path or SHA-256 pin")
        path = HERE / pin["path"]
        if not path.is_file():
            raise GateFailure(f"pinned {key} file is missing: {pin['path']}")
        actual = sha256_bytes(path.read_bytes())
        if actual != pin["sha256"]:
            raise GateFailure(f"{key} digest mismatch: {actual} != {pin['sha256']}")
    implementations = suite.get("implementations")
    if not isinstance(implementations, list) or len(implementations) != 2:
        raise GateFailure("suite must identify exactly two independent implementations")
    seen_languages = set()
    for implementation in implementations:
        language = implementation.get("language")
        path_text = implementation.get("path")
        pinned = implementation.get("sha256")
        if language not in {"python", "typescript"} or language in seen_languages:
            raise GateFailure("suite implementation language identities are incomplete or duplicated")
        if not isinstance(path_text, str) or not isinstance(pinned, str):
            raise GateFailure(f"suite implementation pin is incomplete for {language!r}")
        path = HERE / path_text
        if not path.is_file():
            raise GateFailure(f"pinned implementation is missing: {path_text}")
        actual = sha256_bytes(path.read_bytes())
        if actual != pinned:
            raise GateFailure(f"implementation digest mismatch for {path_text}: {actual} != {pinned}")
        seen_languages.add(language)
    vector_bytes = (HERE / suite["vectors"]["path"]).read_bytes()
    if stdin_bytes is not None and stdin_bytes and stdin_bytes != vector_bytes:
        raise GateFailure("stdin vectors differ byte-for-byte from the pinned vector file")
    return suite, vector_bytes


def run_adapter(name: str, command: list[str], vector_bytes: bytes) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=HERE,
        input=vector_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if process.returncode != 0:
        diagnostic = process.stderr.decode("utf-8", "replace").strip()
        raise GateFailure(f"{name} adapter exited {process.returncode}: {diagnostic[-500:]}")
    try:
        result = json.loads(process.stdout.decode("utf-8"))
    except Exception as error:
        raise GateFailure(f"{name} adapter returned invalid result JSON: {error}") from error
    if not isinstance(result, dict):
        raise GateFailure(f"{name} adapter result is not an object")
    return result


def check_results(document: dict[str, Any], results: dict[str, Any], adapter: str) -> list[str]:
    failures: list[str] = []
    vectors = document.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        return ["vector document has no vectors"]
    expected_ids = [vector.get("id") for vector in vectors]
    if any(not isinstance(vector_id, str) or not vector_id for vector_id in expected_ids):
        return ["vector with missing id"]
    if len(set(expected_ids)) != len(expected_ids):
        return ["duplicate vector id"]
    missing = sorted(set(expected_ids) - set(results))
    extra = sorted(set(results) - set(expected_ids))
    if missing:
        failures.append(f"missing results: {', '.join(missing)}")
    if extra:
        failures.append(f"unknown results: {', '.join(extra)}")
    for vector in vectors:
        vector_id = vector["id"]
        expected = vector.get("expect")
        if not isinstance(expected, dict) or expected.get("status") not in {"success", "rejection"}:
            failures.append(f"{vector_id}: unclassified vector")
            continue
        actual = results.get(vector_id)
        if not isinstance(actual, dict):
            continue
        if actual.get("status") not in {"success", "rejection"}:
            failures.append(f"{vector_id}: {adapter} returned unknown status")
            continue
        if actual.get("status") == "rejection" and actual.get("error") not in KNOWN_ERRORS:
            failures.append(f"{vector_id}: {adapter} returned unknown rejection category {actual.get('error')!r}")
        if actual.get("status") == "success":
            try:
                raw = bytes.fromhex(actual["bytes_hex"])
            except Exception:
                failures.append(f"{vector_id}: {adapter} returned invalid bytes_hex")
                continue
            if actual.get("bytes_hex") != raw.hex():
                failures.append(f"{vector_id}: {adapter} bytes_hex is not lowercase canonical hex")
            if actual.get("byte_length") != len(raw):
                failures.append(f"{vector_id}: {adapter} byte_length mismatch")
            if actual.get("sha256") != sha256_bytes(raw):
                failures.append(f"{vector_id}: {adapter} SHA-256 does not match its bytes")
        if actual != expected:
            failures.append(f"{vector_id}: {adapter} result differs from normative expectation")
    return failures


def cross_check(document: dict[str, Any], python_results: dict[str, Any], ts_results: dict[str, Any]) -> list[str]:
    failures = []
    for vector in document["vectors"]:
        vector_id = vector["id"]
        if python_results.get(vector_id) != ts_results.get(vector_id):
            failures.append(f"{vector_id}: adapters disagree")
    return failures


def negative_controls(vector_bytes: bytes, document: dict[str, Any]) -> list[str]:
    failures = []
    for fault in NEGATIVE_CONTROLS:
        results = run_adapter(
            f"Python negative control {fault}",
            [sys.executable, "encoder.py", "--grade", "--negative-control", fault],
            vector_bytes,
        )
        detected = check_results(document, results, f"negative-control/{fault}")
        if not detected:
            failures.append(f"negative control stayed green: {fault}")
        else:
            print(f"NEGATIVE CONTROL RED {fault}")
    return failures


def main() -> int:
    only_controls = "--negative-controls" in sys.argv
    stdin_bytes = None if sys.stdin.isatty() else sys.stdin.buffer.read()
    try:
        _, vector_bytes = load_and_verify(stdin_bytes)
        document = json.loads(vector_bytes.decode("utf-8"))
        if only_controls:
            control_failures = negative_controls(vector_bytes, document)
            if control_failures:
                raise GateFailure("; ".join(control_failures))
            print(f"PASS negative controls: {len(NEGATIVE_CONTROLS)}/{len(NEGATIVE_CONTROLS)} went red")
            return 0
        python_results = run_adapter("Python", [sys.executable, "encoder.py", "--grade"], vector_bytes)
        ts_results = run_adapter("TypeScript", ["bun", "encoder.ts", "--grade"], vector_bytes)
        python_failures = check_results(document, python_results, "Python")
        ts_failures = check_results(document, ts_results, "TypeScript")
        agreement_failures = cross_check(document, python_results, ts_results)
        print(f"Python adapter: {len(document['vectors']) - len(set(f.split(':', 1)[0] for f in python_failures))}/{len(document['vectors'])} vectors")
        print(f"TypeScript adapter: {len(document['vectors']) - len(set(f.split(':', 1)[0] for f in ts_failures))}/{len(document['vectors'])} vectors")
        print(f"Cross-language agreement: {len(document['vectors']) - len(agreement_failures)}/{len(document['vectors'])} vectors")
        failures = python_failures + ts_failures + agreement_failures
        failures.extend(negative_controls(vector_bytes, document))
        if failures:
            raise GateFailure("\n".join(failures))
        success_count = sum(vector["expect"]["status"] == "success" for vector in document["vectors"])
        appendix = [vector for vector in document["vectors"] if vector.get("source") == "rfc8785-appendix-b"]
        appendix_success = sum(vector["expect"]["status"] == "success" for vector in appendix)
        print(f"PASS encode-json-utf8-lf.v0: {success_count} success, {len(document['vectors']) - success_count} rejection")
        print(f"PASS RFC 8785 Appendix B classified: {appendix_success} success, {len(appendix) - appendix_success} rejection")
        return 0
    except (GateFailure, json.JSONDecodeError) as error:
        print(f"FAIL encode-json-utf8-lf.v0: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
