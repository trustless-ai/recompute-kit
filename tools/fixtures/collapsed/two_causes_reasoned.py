"""POSITIVE CONTROL — the same two causes, fixed the agreed way.

One named state, kept as the vocabulary a consumer branches on, with a REQUIRED reason
travelling beside it so the next action stays legible. Not a fourth marker: splitting the
vocabulary earns a fifth entry next month, a reason field does not.

The checker MUST pass this file. If it reports this too, it is flagging the shape rather
than the defect, and would train people to ignore it.
"""

REVIEW_UNAVAILABLE = "review_unavailable"


def fetch_review(api_key, client):
    if not api_key:
        return {"status": REVIEW_UNAVAILABLE, "reason": "no_api_key"}
    try:
        return {"status": "ok", "body": client.get()}
    except TimeoutError:
        return {"status": REVIEW_UNAVAILABLE, "reason": "timeout"}
