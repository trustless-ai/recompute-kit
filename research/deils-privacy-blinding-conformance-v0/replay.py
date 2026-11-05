"""Reuse recompute-kit's existing reporter grading relation, without changing its runner."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import run_conformance as runner


def run(directory=HERE):
    results=runner.run_suite(directory)
    return results,runner.exit_code_for_failures([r for r in results if not r.ok]) if any(not r.ok for r in results) else 0


if __name__=='__main__':
    results,code=run()
    print(json.dumps([dict(name=r.name,ok=r.ok,kind=r.kind,detail=r.detail) for r in results],sort_keys=True,indent=2))
    sys.exit(code)
