#!/usr/bin/env python3
"""Selected durable grant consumption: composition of unmodified landed evaluators."""

import json
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PROFILE = "permission_consumption_boundary.v0"
RECIPES = runpy.run_path(str(ROOT / "bin/conformance"))["recompute"]
AUTHORITY = runpy.run_path(str(HERE.parent / "captured-admission-v0/admission_check.py"))["authority"]
CAPACITY = runpy.run_path(str(HERE.parent / "consumption-time-state-binding-v0/binding_check.py"))
AXES = ("expiry", "lifecycle", "capacity")
STATUSES = ("satisfied", "violated", "cannot_establish")


def require(ok):
    if not ok:
        raise ValueError("invalid history")


def natural(value):
    return type(value) is int and value >= 0


def exact(obj, keys):
    require(isinstance(obj, dict) and set(obj) == set(keys.split()))


def identity(grant):
    return grant["grant_id"], grant["grant_epoch"]


def combine(parts):
    # A witnessed violation outranks missing evidence; neither is an authorization.
    values = parts.values()
    return ("violated" if "violated" in values else
            "cannot_establish" if "cannot_establish" in values else "satisfied")


def boolean_status(value):
    require(type(value) is bool)
    return "satisfied" if value else "violated"


def lifecycle(data, grant, at, anchor=None):
    """Adapter only: bind G/E into the existing epoch/claim contract.

    Expiry is deliberately evaluated by mcp/entitled, not twice. The authority
    call handles activation and terminal transitions; no local lifecycle rules.
    Equal capture/admission coordinates are constructed from supplied identity,
    not authenticated signatures or proof of completeness.
    """
    epoch = json.dumps(identity(grant), separators=(",", ":"))
    transitions = []
    for transition in data["lifecycle_transitions"]:
        if identity(transition) == identity(grant):
            transitions.append({"references_epoch": epoch, "kind": transition["kind"],
                                "at": transition["at"]})
    return AUTHORITY({
        "capture": {"object_hash": epoch},
        "admission": {"captured_object_hash": epoch, "epoch_id": epoch,
                      "activated_at": grant["activated_at"], "expiry": None},
        "as_of": at, "transitions": transitions,
        "claim": {"references_epoch": epoch, "anchor_time": at if anchor is None else anchor},
    })


def capacity_state(domain, at):
    state = domain["initial"]
    for transition in domain["transitions"]:
        if transition["at"] <= at:
            state = transition["state"]
    return state


def components(data, grant, at, evidence):
    expiry_time = at  # M2: current time, not the historical check time
    expiry = (boolean_status(RECIPES({"step": "mcp/entitled", "inputs": {
        "expiry": grant["expiry"], "now": expiry_time}}))
        if evidence["expiry"] else "cannot_establish")
    verdict = lifecycle(data, grant, at)[0] if evidence["lifecycle"] else None
    life = ("satisfied" if verdict == "attributed" else
            "violated" if verdict in {"out_of_authority", "epoch_not_yet_active"} else
            "cannot_establish")
    if grant["capacity_domain"] is None:
        cap = "satisfied"  # Explicit policy: this grant does not require a capacity domain.
    elif not evidence["capacity"]:
        cap = "cannot_establish"
    else:
        domains = [d for d in data["capacities"]
                   if d["domain_id"] == grant["capacity_domain"]]  # M7
        cap = (boolean_status(any(CAPACITY["predicate"](capacity_state(d, at), data["amount"])
                                  for d in domains)) if domains else "cannot_establish")
    return {"expiry": expiry, "lifecycle": life, "capacity": cap}


def validate(data):
    exact(data, "grant_id grant_epoch amount check_at grants lifecycle_transitions capacities consume")
    require(isinstance(data["grant_id"], str) and bool(data["grant_id"]))
    require(all(natural(data[k]) for k in ("grant_epoch", "amount", "check_at")))
    require(isinstance(data["grants"], list) and bool(data["grants"]))
    seen = set()
    for grant in data["grants"]:
        exact(grant, "grant_id grant_epoch activated_at expiry capacity_domain")
        require(isinstance(grant["grant_id"], str) and bool(grant["grant_id"]))
        require(all(natural(grant[k]) for k in ("grant_epoch", "activated_at", "expiry")))
        require(grant["expiry"] <= 2**64 - 1)
        require(grant["capacity_domain"] is None or
                isinstance(grant["capacity_domain"], str) and bool(grant["capacity_domain"]))
        require(identity(grant) not in seen)
        seen.add(identity(grant))
        require(RECIPES({"step": "mcp/entitled", "inputs": {
            "expiry": grant["expiry"], "now": grant["activated_at"]}}))
    require(isinstance(data["lifecycle_transitions"], list))
    for transition in data["lifecycle_transitions"]:
        exact(transition, "grant_id grant_epoch kind at")
        require(identity(transition) in seen and natural(transition["at"]))
        require(isinstance(transition["kind"], str))
    require(isinstance(data["capacities"], list))
    domain_ids = set()
    for domain in data["capacities"]:
        exact(domain, "domain_id initial transitions")
        require(isinstance(domain["domain_id"], str) and bool(domain["domain_id"]))
        require(domain["domain_id"] not in domain_ids)
        domain_ids.add(domain["domain_id"])
        require(CAPACITY["state_valid"](domain["initial"]))
        require(isinstance(domain["transitions"], list))
        previous, previous_at = domain["initial"], -1
        for transition in domain["transitions"]:
            exact(transition, "at state")
            require(natural(transition["at"]) and transition["at"] > previous_at)
            require(CAPACITY["state_valid"](transition["state"]))
            require(transition["state"]["state_version"] == previous["state_version"] + 1)
            previous, previous_at = transition["state"], transition["at"]
    consume = data["consume"]
    exact(consume, "grant_id grant_epoch capacity_domain at evidence observed_outcome")
    require(isinstance(consume["grant_id"], str) and bool(consume["grant_id"]))
    require(natural(consume["grant_epoch"]) and natural(consume["at"]))
    require(consume["at"] >= data["check_at"])
    require(consume["capacity_domain"] is None or
            isinstance(consume["capacity_domain"], str) and bool(consume["capacity_domain"]))
    exact(consume["evidence"], "expiry lifecycle capacity")
    require(all(type(v) is bool for v in consume["evidence"].values()))
    require(consume["observed_outcome"] in {"admit", "reject"})


def result(historical, current, observed, historical_parts, current_parts, reasons):
    required = "admit" if current == "satisfied" and historical == "satisfied" else "reject"
    return {"historical_check_status": historical, "current_authorization_status": current,
            "observed_consumption_outcome": observed, "required_consumption_outcome": required,
            "consumption_conformance_status": "satisfied" if observed == required else "violated",
            "historical_components": historical_parts, "current_components": current_parts,
            "reason_codes": sorted(reasons)}


def evaluate(case):
    data = case.get("inputs") if isinstance(case, dict) else None
    # Validation errors are evidence insufficiency, never a successful authorization.
    try:
        validate(data)
    except (ValueError, TypeError, KeyError):
        consume = data.get("consume") if isinstance(data, dict) else None
        observed = consume.get("observed_outcome", "none") if isinstance(consume, dict) else "none"
        if observed not in {"admit", "reject"}:
            observed = "none"
        return result("cannot_establish", "cannot_establish", observed, {}, {}, ["INVALID_HISTORY"])
    selected = next((g for g in data["grants"] if identity(g) == identity(data)), None)
    consume = data["consume"]
    observed = consume["observed_outcome"]
    if selected is None:
        return result("cannot_establish", "cannot_establish", observed, {}, {}, ["CHECKED_GRANT_MISSING"])
    historical = components(data, selected, data["check_at"], dict.fromkeys(AXES, True))
    historical_status = combine(historical)
    if historical_status != "satisfied":
        return result(historical_status, "cannot_establish", observed, historical, {},
                      ["HISTORICAL_AUTHORIZATION_NOT_ESTABLISHED", "CURRENT_AUTHORIZATION_NOT_EVALUATED"])
    if identity(consume) != identity(selected):  # M9
        return result("satisfied", "violated", observed, historical, {}, ["GRANT_IDENTITY_MISMATCH"])
    if consume["capacity_domain"] != selected["capacity_domain"]:  # M10
        return result("satisfied", "violated", observed, historical, {}, ["CAPACITY_DOMAIN_MISMATCH"])
    candidates = [g for g in data["grants"]
                  if g["grant_id"] == selected["grant_id"]  # M5
                  and g["grant_epoch"] == selected["grant_epoch"]]  # M4
    evaluated = []
    for grant in candidates:
        current = components(data, grant, consume["at"], consume["evidence"])  # current composition
        evaluated.append(current)
    current = next((c for c in evaluated if combine(c) == "satisfied"), evaluated[0])
    status = combine(current)  # M8
    reasons = ["HISTORICAL_AUTHORIZATION_ESTABLISHED"]
    reasons += [f"CURRENT_{axis.upper()}_{value.upper()}" for axis, value in current.items()]
    return result(historical_status, status, observed, historical, current, reasons)


def load_cases(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    require(document["profile"] == PROFILE and bool(document["cases"]))
    cases = document["cases"]
    require(len({c["case_id"] for c in cases}) == len(cases))
    return cases


def assertions(cases):
    p5 = next(c for c in cases if c["case_id"] == "P5_REVOKED_SELECTED_EPOCH")
    actual = evaluate(p5)
    data = p5["inputs"]
    grant = next(g for g in data["grants"] if identity(g) == identity(data))
    attributed, reasons = lifecycle(data, grant, data["consume"]["at"], anchor=data["check_at"])
    return {"P6_HISTORICAL_ATTRIBUTION_PRESERVED_AFTER_REVOCATION":
            actual["historical_check_status"] == "satisfied"
            and actual["current_authorization_status"] == "violated"
            and attributed == "attributed" and "lifecycle_state_now=revoked" in reasons}


def main():
    cases = load_cases(sys.argv[1] if len(sys.argv) > 1 else HERE / "vectors.json")
    results = [{"case_id": c["case_id"], "result": evaluate(c)} for c in cases]
    reproduced = sum(r["result"] == c["expected"] for r, c in zip(results, cases))
    checks = assertions(cases)
    counts = {axis: {s: sum(r["result"][axis] == s for r in results) for s in values}
              for axis, values in (("historical_check_status", STATUSES),
                                   ("current_authorization_status", STATUSES),
                                   ("observed_consumption_outcome", ("admit", "reject", "none")),
                                   ("required_consumption_outcome", ("admit", "reject")))}
    print(json.dumps({"results": results, "counts": counts, "total": len(cases),
                      "reproduced": reproduced, "assertions": checks}, sort_keys=True, indent=2))
    return 0 if reproduced == len(cases) and all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
