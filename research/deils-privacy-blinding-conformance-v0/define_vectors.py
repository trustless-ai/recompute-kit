"""Reviewable synthetic oracle. Never imports either verifier or their JCS implementation.

Expected canonical TEXT is supplied explicitly by the fixture author; only standard
SHA-256/UTF-8 is applied to those literal strings. Not a runtime-output-to-oracle loop.
All blinding strings are PUBLIC TEST DATA, not production secrets or fresh randomness.
"""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
B = "00112233445566778899aabbccddeeff" * 2
C = "ffeeddccbbaa99887766554433221100" * 2
P = "research.deils-privacy-blinding.v0"
L = "research.deils-legacy-integer-replay.v0"


def gps(b=B, lat=123456789, lon=-987654321, accuracy=25):
    return '{"accuracyCm":' + str(accuracy) + ',"blinding":' + json.dumps(b) + ',"latE7":' + str(lat) + ',"lonE7":' + str(lon) + '}'


def digest(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def expected(status="VERIFIED", state="content_bound", reason=None, stage="commitment", text=None):
    return dict(status=status, state=state, reason=reason, stage=stage,
                hash_evaluated=text is not None,
                canonical_utf8_hex=None if text is None else text.encode("utf-8").hex(),
                recomputed_commitment=None if text is None else digest(text))


def build():
    vectors = []
    def add(name, raw, *, canonical=None, committed=None, reason=None, stage="validation", profile=P, schema="gps-integers-research.v0", mismatch=False, disclosed=True, state=None, commitment=None, guarantee=None):
        inp = dict(profile=profile, content_schema=schema, content_json=raw,
                   commitment=commitment or digest(committed or gps()), disclosed=disclosed)
        if reason or state:
            exp = expected("UNVERIFIABLE", state, reason, stage)
        else:
            exp = expected("REFUTED" if mismatch else "VERIFIED", "content_commitment_mismatch" if mismatch else "content_bound", text=canonical)
        vectors.append(dict(name=name, input=inp, expected=exp,
                            guarantee=guarantee or name,
                            input_utf8_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                            expectation_basis="reviewed literal canonical text and declared relation, never adapter output"))

    add("matching_blinded", gps(), canonical=gps())
    add("other_valid_blinding_positive", gps(C), committed=gps(C), canonical=gps(C))
    add("wrong_valid_blinding", gps(C), canonical=gps(C), mismatch=True)
    for name,b in [("short",B[:-2]),("long",B+'00'),("uppercase",B.upper()),("nonhex",'g'+B[1:]),("empty",''),("number",7),("boolean",True),("null",None),("array",[]),("object",{}),("trailing_newline",B+'\n')]:
        add("blinding_"+name, gps(b), reason="blinding_malformed")
    unblinded='{"accuracyCm":25,"latE7":123456789,"lonE7":-987654321}'
    add("required_blinding_missing",unblinded,committed=unblinded,reason="RESEARCH_REQUIRED_BLINDING_ABSENT")
    add("blinding_omitted_preimage",gps(),committed=unblinded,canonical=gps(),mismatch=True)
    add("gps_sign_preimage",gps(lat=-123456789),committed=gps(),canonical=gps(lat=-123456789),mismatch=True)
    for name,raw in [("latitude_changed",gps(lat=123456788)),("longitude_changed",gps(lon=-987654320)),("accuracy_changed",gps(accuracy=26))]:
        add(name,raw,canonical=raw,mismatch=True)
    add("coordinate_substitution",gps(lat=200,lon=100),committed=gps(lat=100,lon=200),canonical=gps(lat=200,lon=100),mismatch=True,
        guarantee="Literal latE7/lonE7 substitution with both values in range; field-name binding, not range rejection.")
    add("reuse_other_commitment",gps(lat=123456788),committed=gps(lat=123456788),canonical=gps(lat=123456788),guarantee="Single-commitment verification cannot establish blinding freshness; same public test nonce is deliberately reused.")
    add("reordered_members",'{ "lonE7": -987654321, "latE7":123456789, "blinding":"'+B+'", "accuracyCm":25 }',canonical=gps())
    add("legacy_unblinded",unblinded,canonical=unblinded,committed=unblinded,profile=L)
    add("withheld",'null',profile=L,state="content_withheld",stage="disclosure",disclosed=False)
    add("legacy_null_withheld",'null',profile=L,state="content_withheld",stage="disclosure")
    add("unsupported_profile",gps(),profile=P+'.wrong',reason="RESEARCH_PROFILE_UNSUPPORTED",stage="admission")
    add("commitment_from_other_field",gps(),commitment='sha256:'+'0'*64,canonical=gps(),mismatch=True)
    for name,raw in [("latitude_outside",gps(lat=900000001)),("longitude_outside",gps(lon=-1800000001)),("accuracy_negative",gps(accuracy=-1)),("gps_boolean",gps().replace('123456789','true'))]:
        add(name,raw,reason="RESEARCH_GPS_RANGE_OR_TYPE")
    for name,raw in [("gps_boundaries",gps(lat=-900000000,lon=1800000000,accuracy=0)),("accuracy_safe_max",gps(accuracy=9007199254740991))]:
        add(name,raw,canonical=raw,committed=raw)
    for name,n in [("safe_min",-9007199254740991),("safe_max",9007199254740991)]:
        raw='{"blinding":"'+B+'","n":'+str(n)+'}'
        add(name,raw,canonical=raw,committed=raw,schema="json-integers")
    for name,raw in [("unsafe_integer",'{"n":9007199254740992}'),("fraction_outside_domain",'{"n":0.9}'),("exponent_outside_domain",'{"n":1e0}'),("malformed_json",'{'),("duplicate_member",'{"a":1,"a":2}'),("invalid_unicode",'{"x":"\\ud800"}'),("nonfinite",'{"n":NaN}')]:
        add(name,raw,reason="RESEARCH_CONTENT_INVALID",stage="admission",schema="json-integers")
    for name,raw,canon in [
        ("negative_zero",'{"blinding":"'+B+'","n":-0}', '{"blinding":"'+B+'","n":0}'),
        ("escaped_unicode",'{"blinding":"'+B+'","note":"\\u00e9\\n\\t\\u000f"}', '{"blinding":"'+B+'","note":"é\\n\\t\\u000f"}'),
        ("utf16_key_order",'{"\ue000":2,"😀":1,"blinding":"'+B+'"}', '{"blinding":"'+B+'","😀":1,"\ue000":2}'),
        ("nested_types",'{"blinding":"'+B+'","x":[true,false,null,{"z":2,"a":1}]}','{"blinding":"'+B+'","x":[true,false,null,{"a":1,"z":2}]}'),
        ("decomposed_unicode",'{"blinding":"'+B+'","x":"e\u0301"}','{"blinding":"'+B+'","x":"e\u0301"}')]:
        add(name,raw,canonical=canon,committed=canon,schema="json-integers")
    composed='{"blinding":"'+B+'","x":"é"}'
    decomposed='{"blinding":"'+B+'","x":"e\u0301"}'
    add("unicode_not_normalized",composed,canonical=composed,committed=decomposed,mismatch=True,schema="json-integers")
    add("privacy_array_not_object",'[]',schema="json-integers",reason="RESEARCH_CONTENT_OBJECT_REQUIRED")
    add("ref_bad_prefix",gps(),commitment='0x'+'0'*64,reason="malformed_commitment")
    add("malformed_blinding_before_ref",gps('bad'),commitment='also-bad',reason="blinding_malformed")
    return {"schema":"research.deils-blinding-vectors.v0", "vectors":vectors}


if __name__ == '__main__':
    (HERE/'vectors.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
