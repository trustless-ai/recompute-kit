"""Read-only declared digest and original-file preservation verification."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def entries(value):
    if isinstance(value,dict):
        if 'path' in value and 'sha256' in value:yield value
        for child in value.values():yield from entries(child)
    elif isinstance(value,list):
        for child in value:yield from entries(child)


def run():
    bad=[];count=0
    manifests=list((ROOT/'conformance').glob('*/suite.json'))+[HERE/'suite.json']
    for manifest in manifests:
        for pin in entries(json.loads(manifest.read_bytes())):
            f=manifest.parent/pin['path'];count+=1
            if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=pin['sha256']:
                bad.append(str(f.relative_to(ROOT)))
    lock=json.loads((HERE/'SOURCE_PINS.json').read_bytes())
    listing=subprocess.check_output(['git','ls-tree','-rz','--full-tree',lock['base']],cwd=ROOT)
    preserved=0
    for row in listing.split(b'\0'):
        if not row:continue
        meta,name=row.split(b'\t',1);mode,kind,sha=meta.split()
        if kind!=b'blob':continue
        path=ROOT/name.decode();data=path.read_bytes() if path.is_file() else b''
        actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest().encode()
        if actual!=sha:bad.append(name.decode())
        else:preserved+=1
    version=importlib.metadata.version('rfc8785')
    if version!='0.1.4':bad.append('rfc8785 version '+version)
    import rfc8785
    module=Path(rfc8785.__file__).parent
    package={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(module.glob('*.py'))}
    pinned=lock.get('rfc8785_source_sha256')
    if pinned is not None and package!=pinned:bad.append('rfc8785 source digest drift')
    inventory=json.loads((HERE/'SHA256SUMS.json').read_bytes())
    for name,digest in inventory.items():
        file=HERE/name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:bad.append('research package drift: '+name)
    return dict(manifests=len(manifests),declared_digest_entries=count,base_files_preserved=preserved,package_files_verified=len(inventory),
                rfc8785_version=version,rfc8785_source_sha256=package,failures=bad)


if __name__=='__main__':
    doc=run();print(json.dumps(doc,sort_keys=True,indent=2));sys.exit(bool(doc['failures']))
