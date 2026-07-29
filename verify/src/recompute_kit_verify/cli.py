"""recompute-verify — CLI. Exit codes ARE the tri-state: 0 verified-good, 1 verified-bad, 2 UNVERIFIABLE."""
import sys
import json
from .verify import verify_object, GOOD, BAD


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    src = argv[0] if argv else "-"
    if src in ("-h", "--help"):
        print("usage: recompute-verify <receipt.json | ->   # recompute the root locally; trust no one")
        return 0
    try:
        data = json.load(sys.stdin if src == "-" else open(src, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"status": "UNVERIFIABLE", "reason": f"could not read JSON: {e}"}))
        return 2
    res = verify_object(data)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res["status"] == GOOD else (1 if res["status"] == BAD else 2)


if __name__ == "__main__":
    raise SystemExit(main())
