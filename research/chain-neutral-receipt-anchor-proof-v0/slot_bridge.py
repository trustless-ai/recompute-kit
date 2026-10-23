"""Invoke the pinned original slot checker; no replacement Merkle implementation."""
import importlib.util
import json
import os
from pathlib import Path
import sys

path = Path(os.environ['CHAIN_PROOF_SOURCES']) / 'invino/examples/decision-receipt/slot_log_check.py'
spec = importlib.util.spec_from_file_location('original_slot_log', path)
slot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slot)
data = json.load(sys.stdin)
stage = 'snapshot'
try:
    # Bounded subset of the published integer/scalar slot domain. This does not
    # silently extend its Python json serializer into a general JCS engine.
    def domain(value):
        if value is None or isinstance(value,str):
            if isinstance(value,str):
                value.encode('utf-8',errors='strict')
            return
        if type(value) is int and abs(value)<=9007199254740991:
            return
        if isinstance(value,list):
            for item in value:domain(item)
            return
        if isinstance(value,dict) and all(k.isascii() for k in value):
            for item in value.values():domain(item)
            return
        raise ValueError('outside bounded slot JSON domain')
    for raw in [data['snapshot']]+([data['previous']] if data.get('previous') is not None else []):
        for line in raw.splitlines():domain(json.loads(line))
    h, lines, root = slot.check_file(data['snapshot'].encode('utf-8'))
    stage = 'inclusion'
    included = slot.check_inclusion(data['inclusion'])
    if included != root or data['inclusion']['header'] != h:
        raise slot.Bad('inclusion checkpoint differs from snapshot')
    stage = 'position'
    index = data['index']
    if type(index) is not int or not 0 <= index < len(lines) or lines[index] != data['inclusion']['line']:
        raise slot.Bad('selected leaf position differs from snapshot')
    if type(data['count']) is not int or data['count'] != len(lines):
        raise slot.Bad('selected count differs from snapshot')
    stage = 'chain'
    if data.get('previous') is not None:
        slot.check_chain(h, lines, data['previous'].encode('utf-8'))
    print(json.dumps({'status':'VERIFIED','reason':'SLOT_NATIVE_VERIFIED','stage':'complete','log_root':root}))
except slot.Bad as error:
    print(json.dumps({'status':'REFUTED','reason':'SLOT_'+stage.upper()+'_INVALID','stage':stage,'detail':str(error)}))
except (KeyError, ValueError, TypeError) as error:
    print(json.dumps({'status':'UNVERIFIABLE','reason':'SLOT_MALFORMED','stage':stage,'detail':str(error)}))
