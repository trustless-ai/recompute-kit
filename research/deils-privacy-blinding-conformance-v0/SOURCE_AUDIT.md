# Exact-source audit

Base recompute-kit main: b4537d73bda4e4df73c4b105ee516a43c351ba02, tree be1c808c7356157df4ccfb67de6fcb8613812e8a (the machine source lock records the authoritative tree). Existing DEILS directory remains declared uncovered and has no suite.json. No activation or historical repin occurs here.

DEILS working specification: trustless-ai/deils at c686d8e530c9136197dd0155b789736f83a80b60. Inspected spec/leg-2-privacy.md, conformance/deils-reveal-v0/deils-reveal-v0.spec.md, reveal_check.py and README. Repository is private, draft, without an advertised license. Only metadata and hashes are recorded here; private source bytes stay outside this repository. This revision establishes commitment/ref/reveal boundaries, but contains no blinding extension or missing-blinding error name. It refers ambiguously to RFC8785 / receiptos-c14n-v0, while its checker describes an integer/string subset and uses Python sorted-key serialization. The new research explicitly selects RFC8785, without rewriting that historical text.

Public pinned golden example: babyblueviper1/preaction-governance-conformance at df019b226e6ca79c0ce40eb37950ccaad421d2fe, examples/deils-leg2/{README.md,check_deils_leg2.py,vectors.json}. Current repo main observed 235aaabc45ebe6fa36dd02ca2cd6a44a69297d93; latest commit touching that directory remains df019b2. Six original vectors include floats (0.9,0.7,0.85); this contradicts treating all historical inputs as strictly integer-only. The original fixtures/checker are replayed externally unchanged. Their minimal serializer is not proof of complete JCS conformance (UTF-16 key order / -0 / float formatting require care).

Invinoveritas public main ce8c504f2ae4d9b389b53823fe16afec7fcf3bb3 was inspected. The historically referenced routes/execution.py was unavailable there (GitHub API 404; no matching tree path). Therefore current deployed /prove behavior, blinding support and client interoperability have NOT been independently verified. No service was exercised with real private content.

User-reported agreement from Echo/Federico/Tiago is a research requirement, not substituted for an adopted source publication. Missing normative extension/error name, public implementation availability, canonical numeric domain and client schema remain unresolved. Research tests can pass without resolving those adoption questions.

Open branches/PRs were inventoried before writing: #84 998dc12d, #81 30ec0ad1, #78 e32eea8f, #70 33c00027 and #17 fa68f66e. None is modified; this directory introduces no tools/ test registration or shared-workflow hunk.
