"""recompute-kit-verify — recompute a recompute-kit receipt on your own machine. Trust no one.

    from recompute_kit_verify import verify_object
    verify_object(json.load(open("receipt.json")))   # -> {"status": "verified-good", ...}

Or the CLI:  recompute-verify receipt.json   (exit 0=good, 1=bad, 2=unverifiable)

Stdlib only — no network, no dependency on us.
"""
from .verify import verify_object, GOOD, BAD, UNVERIFIABLE
from .canon import receipt_root, jcs

__all__ = ["verify_object", "receipt_root", "jcs", "GOOD", "BAD", "UNVERIFIABLE"]
__version__ = "0.1.0"
