"""Use the existing canonical runner's manifest/grading implementation unchanged."""
import importlib.util
import json
import os
import shutil
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT / 'tools'))
import run_conformance as runner

def run():
    from bootstrap import verify_sources
    try:
        if not os.environ.get('CHAIN_PROOF_SOURCES'):raise FileNotFoundError('CHAIN_PROOF_SOURCES not configured')
        verify_sources(Path(os.environ['CHAIN_PROOF_SOURCES']))
        interpreter=shutil.which(os.environ.get('CHAIN_PYTHON',sys.executable))
        if interpreter is None:raise FileNotFoundError('Selected Python interpreter unavailable')
        os.environ['CHAIN_PYTHON']=interpreter
    except FileNotFoundError:
        print(json.dumps([{'name':HERE.name,'ok':False,'kind':'RUNNER','detail':'External pinned source dependency unavailable; no adapter executed'}]))
        return 2
    except ValueError as error:
        print(json.dumps([{'name':HERE.name,'ok':False,'kind':'DRIFT','detail':str(error)}]))
        return 1
    results = runner.run_suite(HERE)
    document = [{'name':r.name,'ok':r.ok,'kind':r.kind,'detail':r.detail} for r in results]
    print(json.dumps(document,sort_keys=True,indent=2))
    return runner.exit_code_for_failures([r for r in results if not r.ok]) if any(not r.ok for r in results) else 0

if __name__ == '__main__':
    sys.exit(run())
