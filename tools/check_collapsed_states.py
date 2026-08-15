#!/usr/bin/env python3
"""Collapsed-state checker — find markers that answer more than one question.

WHY THIS EXISTS. On 4 August the working group wrote down a rule: never let a collapsed
value hide which state produced it; the marker travels WITH the value. Between 14 and 15
August the rule was reintroduced five times, in two codebases, by the two people who wrote
it — including once inside the fix for the collapse itself (UNDETERMINED was introduced to
stop a two-way collapse and immediately collapsed two causes of its own).

That is not a discipline problem. A written rule has no failure mode: it cannot go red.
This is the rule expressed as something that can.

WHAT IT LOOKS FOR. A *collapsed marker* is one terminal value reachable from two or more
distinct causes, where nothing in the output distinguishes which cause occurred. The
canonical shape:

    if not api_key:          return "review_unavailable"
    except Timeout:          return "review_unavailable"
    except MalformedBody:    return "review_unavailable"

Three different next actions — get a key, retry, file a bug — printing one string. The fix
is never a fourth marker (splitting the vocabulary earns a fifth next month); it is a
required reason field travelling beside the marker:

    return {"status": "review_unavailable", "reason": "no_api_key"}
    return {"status": "review_unavailable", "reason": "timeout"}

WHAT IT DELIBERATELY DOES NOT DO. It analyses Python via AST, precisely. It does not
regex-scan other languages: a check that pattern-matches a language it cannot parse
reports clean because it understood nothing, which is the exact defect class this tool
exists to catch. Unparseable or non-Python inputs are reported NOT COVERED — never passed.

EXIT CODES — the kit's tri-state convention ("couldn't check is its own verdict"):
    0  verified-good  — files were analysed and no collapsed marker was found
    1  verified-bad   — at least one collapsed marker (determinate finding)
    2  UNVERIFIABLE   — nothing could be analysed (no inputs, all unparseable)
    64 usage error
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import sys
from collections import defaultdict
from dataclasses import dataclass, field

EXIT_GOOD, EXIT_BAD, EXIT_UNVERIFIABLE, EXIT_USAGE = 0, 1, 2, 64

# Keys whose value names the outcome a consumer branches on.
MARKER_KEYS = {"status", "verdict", "state", "marker", "outcome", "result", "lane"}
# Keys that carry WHY, and so keep two causes distinguishable.
REASON_KEYS = {"reason", "cause", "detail", "details", "error", "error_code",
               "why", "code", "kind", "because"}


@dataclass
class Site:
    """One syntactic place that produces a marker value."""
    file: str
    line: int
    reason: str | None          # the distinguishing reason travelling with it, if any
    context: str                # 'dict' | 'return' — how the marker was produced


@dataclass
class Report:
    analysed: list[str] = field(default_factory=list)
    not_covered: list[tuple[str, str]] = field(default_factory=list)
    # (file, marker) -> sites
    sites: dict[tuple[str, str], list[Site]] = field(default_factory=lambda: defaultdict(list))


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _module_string_consts(tree: ast.Module) -> dict[str, str]:
    """Module-level NAME = "literal", so `return REVIEW_UNAVAILABLE` resolves."""
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            val = _const_str(node.value)
            if val is None:
                continue
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = val
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            val = _const_str(node.value)
            if val is not None and isinstance(node.target, ast.Name):
                out[node.target.id] = val
    return out


def _resolve(node: ast.AST, consts: dict[str, str]) -> str | None:
    """A string literal, or a name bound to one at module level."""
    direct = _const_str(node)
    if direct is not None:
        return direct
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


def _scan_dict(node: ast.Dict, consts: dict[str, str]) -> tuple[str, str | None] | None:
    """A dict literal carrying a marker. Returns (marker_value, reason_value|None)."""
    marker = reason = None
    for k, v in zip(node.keys, node.values):
        key = _const_str(k) if k is not None else None
        if key is None:
            continue
        key_l = key.lower()
        if key_l in MARKER_KEYS and marker is None:
            marker = _resolve(v, consts)
        elif key_l in REASON_KEYS and reason is None:
            reason = _resolve(v, consts)
            # A reason present but non-constant (computed at runtime) still distinguishes.
            if reason is None:
                reason = f"<dynamic@{getattr(v, 'lineno', 0)}>"
    if marker is None:
        return None
    return marker, reason


def _scan_call(node: ast.Call, consts: dict[str, str]) -> tuple[str, str | None] | None:
    """Constructor/factory call with marker= and optionally reason= keywords."""
    marker = reason = None
    for kw in node.keywords:
        if kw.arg is None:
            continue
        arg_l = kw.arg.lower()
        if arg_l in MARKER_KEYS and marker is None:
            marker = _resolve(kw.value, consts)
        elif arg_l in REASON_KEYS and reason is None:
            reason = _resolve(kw.value, consts)
            if reason is None:
                reason = f"<dynamic@{getattr(kw.value, 'lineno', 0)}>"
    if marker is None:
        return None
    return marker, reason


def _is_test_scope(name: str) -> bool:
    n = name.lower()
    return n.startswith("test") or n.startswith("_test") or "selftest" in n \
        or n.startswith("_vec") or n.startswith("check_vector")


def _emitted_nodes(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[int]:
    """Nodes whose value actually LEAVES the function.

    A marker only matters if a caller can see it. A dict sitting in a local — a test
    fixture, a sample document, a lookup table — is not a state anybody branches on, and
    counting it flags the shape instead of the defect. So: dicts/calls returned directly,
    or bound to a name that is returned somewhere in the same function.
    """
    emitted: set[int] = set()
    returned_names: set[str] = set()

    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Name):
            returned_names.add(node.value.id)

    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and node.value is not None:
            emitted.add(id(node.value))
        elif isinstance(node, ast.Assign) and isinstance(node.value, (ast.Dict, ast.Call)):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in returned_names:
                    emitted.add(id(node.value))
    return emitted


def analyse_file(path: pathlib.Path, report: Report, explicit: bool = True) -> None:
    # Deliberate specimens are skipped when SWEPT (one is collapsed on purpose and would
    # redden every run), but analysed when named directly — which is how the control suite
    # drives this tool to its fail path. Reported either way: a check that quietly drops
    # files is the shape this tool exists to catch.
    if not explicit and "fixtures" in path.parts:
        report.not_covered.append(
            (str(path), "deliberate specimen — asserted by tools/test_check_collapsed_states.py"))
        return
    if not explicit and (_is_test_scope(path.stem) or path.stem.endswith("_test")):
        report.not_covered.append((str(path), "test scaffolding — fixtures are not emitted states"))
        return
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        report.not_covered.append((str(path), f"unreadable: {e.__class__.__name__}"))
        return
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        report.not_covered.append((str(path), f"unparseable: line {e.lineno}"))
        return

    consts = _module_string_consts(tree)
    report.analysed.append(str(path))

    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_test_scope(fn.name):
            continue
        emitted = _emitted_nodes(fn)

        for node in ast.walk(fn):
            if id(node) not in emitted:
                continue
            found = None
            ctx = ""
            if isinstance(node, ast.Dict):
                found, ctx = _scan_dict(node, consts), "dict"
            elif isinstance(node, ast.Call):
                found, ctx = _scan_call(node, consts), "call"
            else:
                val = _resolve(node, consts)
                # A bare returned string is a marker only if it looks like one: a token,
                # not prose. Prose is a message; a state is a word.
                if val and " " not in val and len(val) <= 48 and val.strip(" _-").isascii() \
                   and any(c.isalpha() for c in val) and "/" not in val:
                    found, ctx = (val, None), "return"
            if found:
                marker, reason = found
                report.sites[(str(path), marker)].append(
                    Site(file=str(path), line=getattr(node, "lineno", 0),
                         reason=reason, context=ctx))


def collapsed(report: Report) -> list[tuple[str, str, list[Site]]]:
    """A marker is collapsed when ≥2 sites produce it and the reasons do not tell them apart."""
    out = []
    for (path, marker), sites in sorted(report.sites.items()):
        if len(sites) < 2:
            continue
        distinct_reasons = {s.reason for s in sites if s.reason is not None}
        # Every site must carry a reason, AND the reasons must actually differ.
        if len(distinct_reasons) >= len(sites) and all(s.reason is not None for s in sites):
            continue
        out.append((path, marker, sites))
    return out


def gather(paths: list[str]) -> list[tuple[pathlib.Path, bool]]:
    """(path, explicit) — explicit means the user named this file, not a sweep found it."""
    files: list[tuple[pathlib.Path, bool]] = []
    for p in paths:
        path = pathlib.Path(p)
        if path.is_dir():
            files.extend((f, False) for f in sorted(path.rglob("*.py"))
                         if "node_modules" not in f.parts and "__pycache__" not in f.parts)
        else:
            files.append((path, True))
    return files


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Find markers reachable from >1 cause with no reason travelling with them.")
    ap.add_argument("paths", nargs="*", default=["."],
                    help="files or directories to analyse (default: .)")
    ap.add_argument("--quiet", action="store_true", help="findings only")
    args = ap.parse_args(argv)

    files = gather(args.paths or ["."])
    if not files:
        print("UNVERIFIABLE — no input files matched", file=sys.stderr)
        return EXIT_UNVERIFIABLE

    report = Report()
    for f, explicit in files:
        if f.suffix != ".py":
            report.not_covered.append((str(f), "not Python — this checker parses Python only"))
            continue
        analyse_file(f, report, explicit=explicit)

    if not report.analysed:
        print("UNVERIFIABLE — nothing could be analysed:", file=sys.stderr)
        for path, why in report.not_covered:
            print(f"    {path}: {why}", file=sys.stderr)
        return EXIT_UNVERIFIABLE

    findings = collapsed(report)

    if not args.quiet:
        print(f"analysed {len(report.analysed)} file(s)")
        if report.not_covered:
            print(f"NOT COVERED ({len(report.not_covered)}) — unrun, not passing:")
            for path, why in report.not_covered:
                print(f"    {path}: {why}")

    if not findings:
        if not args.quiet:
            print("no collapsed markers found")
        return EXIT_GOOD

    print(f"\nCOLLAPSED MARKERS ({len(findings)}) — one value, several causes, no reason carried:")
    for path, marker, sites in findings:
        named = sum(1 for s in sites if s.reason is not None)
        print(f"\n  {path}: {marker!r} produced at {len(sites)} sites, "
              f"{named} carrying a reason")
        for s in sites:
            tail = f"reason={s.reason!r}" if s.reason else "NO REASON"
            print(f"      line {s.line:>5}  ({s.context})  {tail}")
        print("      fix: one named state + a REQUIRED reason field, not another marker")
    return EXIT_BAD


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(EXIT_UNVERIFIABLE)
