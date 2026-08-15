"""NEGATIVE CONTROL — two real causes, one marker, nothing to tell them apart.

This is the shape the checker exists to catch, written the way it actually occurs rather
than as a toy: two genuinely different failures, two genuinely different next actions for
the caller (supply a key / retry later), and one identical string reaching the consumer.

The checker MUST report this file. A run that passes it is not a passing check, it is a
broken one.
"""

REVIEW_UNAVAILABLE = "review_unavailable"


def fetch_review(api_key, client):
    if not api_key:
        # cause 1: misconfiguration — caller must supply a key. Permanent until fixed.
        return {"status": REVIEW_UNAVAILABLE}
    try:
        return {"status": "ok", "body": client.get()}
    except TimeoutError:
        # cause 2: transient — caller should retry. Same string, opposite next action.
        return {"status": REVIEW_UNAVAILABLE}
