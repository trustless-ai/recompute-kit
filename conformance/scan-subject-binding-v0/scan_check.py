#!/usr/bin/env python3
"""scan_subject_binding.v0 -- what a clean poisoning scan establishes about the data a decision actually consumed.

Standard library only. Recomputes every Merkle root, inclusion proof, Ed25519 signature (RFC 8032 reference verify) and answer
from the vector bytes, then runs two verifiers side by side:
  result_only_check    reads only poisoning_scan.result (the shape of Agent Manifest v0.2 s3.2.5 at 0a2513df)
  subject_bound_check  NO_FINDING only when the scan names a subject_digest that is the consumed effective dataset, or is the
                       corpus root with RECORDWISE (hereditary) scanner semantics and an inclusion proof for every consumed
                       leaf; otherwise CANNOT_ESTABLISH. Frozen to k=1 (root(retrieved) is unordered).
  evidence_grade       AUTHENTICATED_REPORT = a signed scanner claim over a bound subject that the checker did NOT rerun;
                       REPRODUCED = the checker reran the published deterministic scanner over the subject bytes (and may then
                       report CONTRADICTED against a signed "clean").
NO_FINDING never means POISONING_ABSENT; that word is outside this checker's vocabulary.
    python3 scan_check.py vectors.json    -> JSON {results, total, reproduced}; exit 0 iff every case reproduces."""
import hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILE = "scan_subject_binding.v0"
VOCAB = ("NO_FINDING", "CANNOT_ESTABLISH", "CONTRADICTED", "NOT_VALID")

# ---- Ed25519 verify, RFC 8032 section 6 reference (standard library only) ----
_p = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_I = pow(2, (_p - 1) // 4, _p)
def _xrecover(y):
    xx = (y * y - 1) * pow(_d * y * y + 1, _p - 2, _p)
    x = pow(xx, (_p + 3) // 8, _p)
    if (x * x - xx) % _p: x = x * _I % _p
    return _p - x if x % 2 else x
_By = 4 * pow(5, _p - 2, _p) % _p
_B = (_xrecover(_By) % _p, _By % _p, 1, _xrecover(_By) * _By % _p)
def _add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _p; Bv = (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C = 2 * P[3] * Q[3] * _d % _p; D = 2 * P[2] * Q[2] % _p
    E, F, G, H = Bv - A, D - C, D + C, Bv + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)
def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s:
        if s & 1: Q = _add(Q, P)
        P = _add(P, P); s >>= 1
    return Q
def _eq(P, Q):
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0
def _decode(b):
    if len(b) != 32: return None
    y = int.from_bytes(b, "little"); sign = y >> 255; y &= (1 << 255) - 1
    if y >= _p: return None
    x = _xrecover(y)
    if (x * x * (_d * y * y + 1) - (y * y - 1)) % _p: return None
    if x == 0 and sign: return None
    if (x & 1) != sign: x = _p - x
    return (x, y, 1, x * y % _p)
def ed25519_verify(pub, sig, msg):
    A = _decode(pub)
    if A is None or len(sig) != 64: return False
    R = _decode(sig[:32]); s = int.from_bytes(sig[32:], "little")
    if R is None or s >= _L: return False
    h = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
    return _eq(_mul(s, _B), _add(R, _mul(h, A)))

# ---- Merkle construction: Agent Manifest v0.2 s3.2.5.1 ----
def H(b): return hashlib.sha256(b).digest()
def leaf(d): return H(b"\x00" + d["id"].encode() + b"\x00" + d["content"].encode())
def mth(ls):
    if len(ls) == 1: return ls[0]
    k = 1
    while k * 2 < len(ls): k *= 2
    return H(b"\x01" + mth(ls[:k]) + mth(ls[k:]))
def root(docs): return "sha256:" + mth(sorted(leaf(d) for d in docs)).hex()
def canon(v): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
def verify_inclusion(lf, index, size, path, want_root):   # RFC 9162 s2.1.3.2
    if index >= size: return False
    fn, sn, r = index, size - 1, lf
    for p in path:
        if sn == 0: return False
        if fn & 1 or fn == sn:
            r = H(b"\x01" + p + r)
            if not fn & 1:
                while fn & 1 == 0 and fn != 0: fn >>= 1; sn >>= 1
        else:
            r = H(b"\x01" + r + p)
        fn >>= 1; sn >>= 1
    return sn == 0 and "sha256:" + r.hex() == want_root

def retrieve(docs, q, k=1):
    qt = set(q.lower().split())
    return sorted(docs, key=lambda d: (len(qt & set(d["content"].lower().replace(",", "").replace(".", "").split())), d["id"]),
                  reverse=True)[:k]
def answer(ret): return re.search(r"is (\d+) USD", ret[0]["content"]).group(1) + " USD"

def load(path):
    V = json.loads(Path(path).read_text(encoding="utf-8"))
    return V, bytes.fromhex(V["test_public_key_ed25519"]), V["toy_scan"]

def sig_ok(pub, m):
    return ed25519_verify(pub, bytes.fromhex(m["sig"]), b"scan-subject-binding-v0\n" + canon(m["body"]))

def check_decision(pub, corpus, man, dec):
    f = []
    if not sig_ok(pub, man): f.append("signature")
    if man["body"]["rag_corpus"]["merkle_root"] != root(corpus): f.append("manifest root != corpus")
    if dec["corpus_root"] != root(corpus): f.append("decision corpus_root != corpus")
    ret = retrieve(corpus, dec["query"], dec.get("k", 1))
    if ret != dec["retrieved"]: f.append("retrieval recompute")
    if dec["effective_dataset_digest"] != root(dec["retrieved"]): f.append("effective digest")
    if answer(ret) != dec["answer"]: f.append("answer recompute")
    return f

def result_only(man): return "VALID" if man["body"]["rag_corpus"]["poisoning_scan"]["result"] == "clean" else "NOT_VALID"

def subject_bound(corpus, man, dec, toy):
    """Returns (verdict, evidence_grade)."""
    s = man["body"]["rag_corpus"]["poisoning_scan"]
    if s.get("result") != "clean": return "NOT_VALID", None
    subj = s.get("subject_digest")
    if subj is None: return "CANNOT_ESTABLISH", None                       # scan names no subject
    if dec.get("k", 1) != 1 or len(dec["retrieved"]) != 1:
        return "CANNOT_ESTABLISH", None                                      # unordered effective digest: frozen to k=1
    if subj == dec["effective_dataset_digest"]:
        subject_docs = dec["retrieved"]
    elif subj == root(corpus) == dec["corpus_root"]:
        if s.get("semantics") != "recordwise":
            return "CANNOT_ESTABLISH", None                                  # corpus -> subset needs a hereditary scanner
        cons = {leaf(d).hex() for d in dec["retrieved"]}
        proved = {p["leaf"] for p in dec["inclusion_proofs"]
                  if verify_inclusion(bytes.fromhex(p["leaf"]), p["index"], p["tree_size"],
                                      [bytes.fromhex(x) for x in p["path"]], subj)}
        if not (cons and cons <= proved): return "CANNOT_ESTABLISH", None
        subject_docs = corpus
    else:
        return "CANNOT_ESTABLISH", None
    if s.get("scanner_version") == toy["scanner_version"]:
        found = [d["id"] for d in subject_docs if toy["pattern"] in d["content"].lower()]
        return ("CONTRADICTED" if found else "NO_FINDING"), "REPRODUCED"
    return "NO_FINDING", "AUTHENTICATED_REPORT"                            # signed report over a bound subject, not rerun

def evaluate(name, c, pub, toy):
    if name.startswith("c0"):
        fa = check_decision(pub, c["corpus_A"], c["manifest_A"], c["decision_A"])
        fb = check_decision(pub, c["corpus_B"], c["manifest_B"], c["decision_B"])
        got = {"signatures": "valid" if not fa and not fb else "FAIL", "answer_A": c["decision_A"]["answer"],
               "answer_B": c["decision_B"]["answer"]}
        return got, all(got[k] == c["expect"][k] for k in got)
    f = check_decision(pub, c["corpus"], c["manifest"], c["decision"])
    verdict, grade = subject_bound(c["corpus"], c["manifest"], c["decision"], toy)
    got = {"replay_bindings": "valid" if not f else "FAIL", "result_only_check": result_only(c["manifest"]),
           "subject_bound_check": verdict, "evidence_grade": grade}
    e = c["expect"]
    if "replay_failures" in e:                     # a case that MUST be refused by check_decision(), on exactly these checks
        got["replay_failures"] = f
        return got, f == e["replay_failures"]
    ok = (not f and verdict in VOCAB and
          all(got[k] == e[k] for k in ("result_only_check", "subject_bound_check", "evidence_grade") if k in e))
    return got, ok

def main():
    V, pub, toy = load(sys.argv[1] if len(sys.argv) > 1 else HERE / "vectors.json")
    results = []
    for name, c in sorted(V["cases"].items()):
        got, ok = evaluate(name, c, pub, toy)
        results.append({"case_id": name, "reproduced": ok, "result": got})
    reproduced = sum(r["reproduced"] for r in results)
    print(json.dumps({"profile": PROFILE, "results": results, "total": len(results), "reproduced": reproduced},
                     sort_keys=True, indent=2))
    return 0 if reproduced == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
