"""Physical disposable-copy controls. A crash, absent report or broken control is not a kill."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KINDS = ("KILLED", "SURVIVED", "CRASHED", "NO_OP", "NOT_APPLIED", "MISSING_OUTPUT", "CONTROL_BROKEN")


def catalog():
    py_format = 'if not (isinstance(b, str) and re.fullmatch(r"[0-9a-f]{64}", b)):'
    js_format = "if(!(typeof b==='string'&&/^[0-9a-f]{64}$/.test(b)))"
    controls = ["matching_blinded", "other_valid_blinding_positive", "legacy_unblinded"]
    entries = []
    def pair(name, py_old, py_new, js_old, js_new, witness, keep=controls):
        for file, old, new in [("verifier.py",py_old,py_new),("verifier.mjs",js_old,js_new)]:
            entries.append(dict(name=name+('/python' if file.endswith('.py') else '/node'),file=file,old=old,new=new,witness=witness,controls=keep))
    pair('skip-format',py_format,'if False:',js_format,'if(false)', 'blinding_nonhex')
    pair('uppercase', '[0-9a-f]{64}', '[0-9a-fA-F]{64}', '^[0-9a-f]{64}$','^[0-9a-fA-F]{64}$','blinding_uppercase')
    # Target the format expression, not the commitment-reference validation.
    entries[-2]['old']=py_format;entries[-2]['new']=py_format.replace('[0-9a-f]','[0-9a-fA-F]')
    entries[-1]['old']=js_format;entries[-1]['new']=js_format.replace('[0-9a-f]','[0-9a-fA-F]')
    pair('wrong-length',py_format,py_format.replace('{64}','{62,66}'),js_format,js_format.replace('{64}','{62,66}'),'blinding_short')
    pair('malformed-as-mismatch','return result("UNVERIFIABLE", reason="blinding_malformed")','return result("REFUTED", "content_commitment_mismatch")',"return result('UNVERIFIABLE',null,'blinding_malformed')","return result('REFUTED','content_commitment_mismatch')",'blinding_nonhex')
    pair('omit-blinding','preimage = content  # GUARD_PREIMAGE','preimage = {k:v for k,v in content.items() if k != "blinding"} if isinstance(content, dict) else content  # GUARD_PREIMAGE',
         'const preimage=c; // GUARD_PREIMAGE',"const preimage=c&&typeof c==='object'&&!Array.isArray(c)?Object.fromEntries(Object.entries(c).filter(([k])=>k!=='blinding')):c; // GUARD_PREIMAGE",'blinding_omitted_preimage',['legacy_unblinded','withheld'])
    pair('skip-required','if "blinding" not in content:  # GUARD_REQUIRED','if False:  # GUARD_REQUIRED',"if(!Object.hasOwn(c,'blinding'))return",'if(false)return','required_blinding_missing')
    pair('gps-sign','preimage = content  # GUARD_PREIMAGE','preimage = dict(content, latE7=abs(content["latE7"])) if isinstance(content, dict) and "latE7" in content else content  # GUARD_PREIMAGE',
         'const preimage=c; // GUARD_PREIMAGE',"const preimage=c&&Object.hasOwn(c,'latE7')?{...c,latE7:Math.abs(c.latE7)}:c; // GUARD_PREIMAGE",'gps_sign_preimage')
    pair('skip-comparison','equal = computed == inp["commitment"]  # GUARD_COMPARE','equal = True  # GUARD_COMPARE',"const equal='sha256:'+sha(bytes)===inp.commitment; // GUARD_COMPARE",'const equal=true; // GUARD_COMPARE','wrong_valid_blinding')
    return entries


def command(file):
    return [sys.executable, '-B', str(file)] if file.suffix == '.py' else ['node',str(file)]


def execute(file, corpus):
    try:
        p = subprocess.run(command(file), input=json.dumps(corpus).encode(), capture_output=True,
                           timeout=30, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1'))
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, b'', b'TIMEOUT (not a kill)'


def classify(rc, stdout, stderr, corpus, controls, witness):
    if rc != 0:
        return 'CRASHED', None
    try:
        got = json.loads(stdout)
    except (ValueError, UnicodeError):
        return 'MISSING_OUTPUT', None
    expected = {v['name']:v['expected'] for v in corpus['vectors']}
    if not isinstance(got,dict) or set(got) != set(expected):
        return 'MISSING_OUTPUT', got
    if any(got[n] != expected[n] for n in controls):
        return 'CONTROL_BROKEN', got
    return ('KILLED' if got[witness] != expected[witness] else 'SURVIVED'), got


def run(inventory=None):
    corpus = json.loads((HERE/'vectors.json').read_bytes())
    results=[]
    for m in (catalog() if inventory is None else inventory):
        original=(HERE/m['file']).read_bytes()
        rc,out,err=execute(HERE/m['file'],corpus)
        expected={v['name']:v['expected'] for v in corpus['vectors']}
        if rc or json.loads(out)!=expected:
            raise RuntimeError('BASELINE_FAILED: '+m['file'])
        old,new=m['old'].encode(),m['new'].encode()
        count=original.count(old)
        record={k:v for k,v in m.items() if k not in ('old','new')}
        record.update(original_expression=m['old'],mutated_expression=m['new'],applied_count=count,
                      source_sha256=hashlib.sha256(original).hexdigest())
        if count != 1:
            record['classification']='NOT_APPLIED'
        elif old == new:
            record['classification']='NO_OP'
        else:
            mutated=original.replace(old,new,1)
            with tempfile.TemporaryDirectory(prefix='deils-mutation-') as td:
                path=Path(td)/m['file'];path.write_bytes(mutated)
                rc,out,err=execute(path,corpus)
            kind,got=classify(rc,out,err,corpus,m['controls'],m['witness'])
            record.update(classification=kind,exit=rc,stdout=out.decode('utf-8','replace'),stderr=err.decode('utf-8','replace'),
                          mutant_sha256=hashlib.sha256(mutated).hexdigest(),
                          differing_cases=[] if not isinstance(got,dict) else sorted(n for n in expected if got.get(n)!=expected[n]))
        record['original_restored']=(HERE/m['file']).read_bytes()==original
        results.append(record)
    totals={k:sum(r['classification']==k for r in results) for k in KINDS}
    return dict(total=len(results),totals=totals,results=results)


def sentinels():
    seed=catalog()[0]
    base=dict(file='verifier.py',witness=seed['witness'],controls=seed['controls'])
    format_old=seed['old']
    write='''sys.stdout.buffer.write((json.dumps(output, sort_keys=True, separators=(",", ":"),
                                          ensure_ascii=True) + "\\n").encode("ascii"))'''
    cases=[('NO_OP',format_old,format_old),('NOT_APPLIED','ABSENT_MUTATION_ANCHOR','pass'),
           ('SURVIVED','# GUARD_FORMAT','# GUARD_FORMAT unchanged semantic sentinel'),
           ('CRASHED','profile = inp.get("profile")','raise RuntimeError("PHYSICAL_CRASH_SENTINEL")'),
           ('MISSING_OUTPUT',write,'pass'),
           ('CONTROL_BROKEN','equal = computed == inp["commitment"]  # GUARD_COMPARE','equal = False  # GUARD_COMPARE')]
    return run([dict(base,name='sentinel/'+kind,old=old,new=new) for kind,old,new in cases])


if __name__=='__main__':
    doc=sentinels() if '--sentinels' in sys.argv else run()
    sys.stdout.buffer.write((json.dumps(doc,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode())
    if '--sentinels' in sys.argv:
        sys.exit(0 if all(r['classification']==r['name'].split('/')[1] for r in doc['results']) else 1)
    sys.exit(0 if doc['total'] and doc['totals']['KILLED']==doc['total'] else 1)
