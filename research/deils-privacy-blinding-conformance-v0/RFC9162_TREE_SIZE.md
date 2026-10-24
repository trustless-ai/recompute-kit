# RFC9162 tree size: non-normative laboratory note

The inclusion relation takes tree size as an input; that arithmetic is not authentication of the supplied size. RFC9162 signed tree heads bind size and root as part of their authenticated structure. This experiment does not allege a flaw in RFC9162, modify its implementation, or replace that signed-tree-head protocol.

experiments.py constructs leaves a,b,c with SHA256(0x00 || leaf) and SHA256(0x01 || left || right). For index 0, the siblings hash(b), hash(c) verify against the same root when the caller restates size 3 as 4. An opaque right sibling does not establish whether its subtree contains one or two leaves. This does NOT exhibit two fully materialized different-size trees with a hash collision.

The laboratory independently selected anchor contains exactly {batchId,treeHashProfile,treeSize,root}. Its encoding is RFC8785 JCS UTF-8 over those four JSON members; values and exact bytes are emitted. Its SHA256 is evidence bookkeeping, NOT a new interoperable anchor identity/profile. Comparing to authenticated, independently configured selected bytes rejects the size-4 restatement. Authenticity of those selected bytes is an explicit lab precondition: no production signature, public publication or consensus claim.

ReceiptOS's separate domain-separated binary Merkle algorithm and count-bound root with uint32be(count) remain untouched. Do not apply slot-log ASCII-hex or RFC9162 hashing to ReceiptOS roots.

References: https://www.rfc-editor.org/rfc/rfc9162.html sections 2.1.3 and 4.10; https://www.rfc-editor.org/rfc/rfc8785.html. The code is independently written for the bounded experiment, not copied RFC code components.
