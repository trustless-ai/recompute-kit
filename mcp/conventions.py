"""governing_convention_hash — pin-at-issuance, resolve-at-verification for versioned
computation conventions.

When a signed value is persisted, it records WHICH convention produced it (its
`governing_convention_hash`). A verifier later resolves that hash to the exact rule and recomputes
under THAT convention — never assuming the current default. So when a convention evolves — e.g. the
ERC-8275 win-rate's `float-4dp` → `basis-points` cutover — a value signed under the old convention
stays recomputable, because its governing convention is pinned at issuance, not inferred at
verification.

A convention's identity is **content-addressed over its exact spec** (formula + representation +
**rounding mode**), because number formatting and rounding are precisely where two honest
implementations diverge without ever disagreeing on the plain-English description. Two conventions that
compute the "same" quantity two ways are two hashes — and the pointer distinguishes them.
"""
import json
import hashlib


def _canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash(o) -> str:
    return "0x" + hashlib.sha256(_canon(o)).hexdigest()


# ── the ERC-8275 win-rate conventions (the two that genuinely exist as of Jimmy's bps cutover) ──
def _win_rate_float_4dp(wins: int, losses: int):
    if wins == 0 and losses == 0:
        raise ValueError("cannot compute win rate: both wins and losses are zero")
    return round(wins / (wins + losses), 4)          # Python round = round-half-to-even (banker's)


def _win_rate_bps(wins: int, losses: int):
    if wins == 0 and losses == 0:
        raise ValueError("cannot compute win rate: both wins and losses are zero")
    return round(wins * 10000 / (wins + losses))     # integer basis points 0..10000, round-half-to-even


CONVENTIONS = {
    "win_rate.float-4dp.v0": {
        "spec": {
            "id": "win_rate.float-4dp.v0",
            "quantity": "erc8275.win_rate",
            "formula": "winRate = gated_wins / (gated_wins + gated_losses)",
            "representation": "float in [0,1], 4 decimal places",
            "rounding_mode": "round-half-to-even",
            "erc": "ERC-8275",
            "source": "trustless-ai/agent-sdk reputation/erc8275/recompute.py compute_win_rate",
        },
        "compute": _win_rate_float_4dp,
    },
    "win_rate.bps.v0": {
        "spec": {
            "id": "win_rate.bps.v0",
            "quantity": "erc8275.win_rate",
            "formula": "winRateBps = gated_wins * 10000 / (gated_wins + gated_losses)",
            "representation": "integer basis points, 0..10000",
            "rounding_mode": "round-half-to-even",
            "erc": "ERC-8275",
            "note": "computed directly from integers (not float-then-scale) to avoid double-rounding",
            "source": "basis-points cutover (agent-sdk#5); winRateBps live on babyblueviper /ledger",
        },
        "compute": _win_rate_bps,
    },
}

# content-addressed identity per convention — these ARE the governing_convention_hash values
CONVENTION_HASH = {cid: _hash(c["spec"]) for cid, c in CONVENTIONS.items()}
BY_HASH = {h: cid for cid, h in CONVENTION_HASH.items()}


def resolve(governing_convention_hash: str):
    """hash → convention id, or None. Unknown → the verifier must fail closed (unverifiable)."""
    return BY_HASH.get(governing_convention_hash)


def verify(value, governing_convention_hash: str, wins: int, losses: int) -> dict:
    """Tri-state, fail-closed: 'verified' | 'rejected' | 'unverifiable'.

    Recompute the value under the PINNED convention (resolved from the hash), never the current
    default. Unknown convention → unverifiable, never a silent pass.
    """
    cid = resolve(governing_convention_hash)
    if cid is None:
        return {"status": "unverifiable", "reason": "unknown governing_convention_hash",
                "governing_convention_hash": governing_convention_hash}
    expected = CONVENTIONS[cid]["compute"](wins, losses)
    return {"status": "verified" if expected == value else "rejected",
            "convention": cid, "governing_convention_hash": governing_convention_hash,
            "expected": expected, "got": value}
