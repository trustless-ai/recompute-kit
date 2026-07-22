"""Independent reimplementation of the 0G Storage flow-merkle root.

Ported verbatim from the 0G protocol reference (0gfoundation/0g-ts-sdk:
constant.ts, MerkleTree.ts, AbstractFile.ts, utils.ts) — this does NOT call the
JS SDK, so a candidate MCP that computes its root via the SDK is checked against
a genuinely second implementation (byte-identity is meaningful, not tautological).

Validated two ways:
  1. reproduces the SDK's own published unit-test golden roots
     (tests/MerkleTree.test.js: build(3..7,35,36) + fromLeftAndRight(0,1));
  2. reproduces the live 0G MCP's rootHash on real content (1/2/multi-chunk).

Rule: content is zero-padded to whole 256-byte chunks (flow-padding), each chunk
is a keccak256 leaf, combined by the 0G flow-merkle (odd-node carry), grouped
into 256 KiB segments. Deterministic, reproducible by any party from public rules.
"""

from Crypto.Hash import keccak

CHUNK = 256
SEGMENT_MAX_CHUNKS = 1024
SEGMENT_SIZE = CHUNK * SEGMENT_MAX_CHUNKS  # 262144


def _k256(b: bytes) -> bytes:
    h = keccak.new(digest_bits=256)
    h.update(b)
    return h.digest()


def _num_splits(total: int, unit: int) -> int:
    return (total - 1) // unit + 1


def _next_pow2(x: int) -> int:
    if x <= 1:
        return 1
    p = 1
    while p < x:
        p <<= 1
    return p


def _compute_padded_size(chunks: int):
    c2 = _next_pow2(chunks)
    if c2 == chunks:
        return chunks, c2
    min_chunk = c2 // 16 if c2 >= 16 else 1
    return _num_splits(chunks, min_chunk) * min_chunk, c2


def _build(leaves):
    """Port of MerkleTree.build() — bottom-up with odd-node carry (NOT pad-to-pow2)."""
    n = len(leaves)
    if n == 0:
        return None
    queue = []
    i = 0
    while i < n:
        if i == n - 1:
            queue.append(leaves[i])
        else:
            queue.append(_k256(leaves[i] + leaves[i + 1]))
        i += 2
    while len(queue) > 1:
        num = len(queue)
        for _ in range(num // 2):
            left = queue.pop(0)
            right = queue.pop(0)
            queue.append(_k256(left + right))
        if num % 2 == 1:
            queue.append(queue.pop(0))
    return queue[0]


def _segment_root(seg: bytes) -> bytes:
    leaves = [_k256(seg[o:o + CHUNK]) for o in range(0, len(seg), CHUNK)]
    return _build(leaves)


def file_root(content: bytes) -> str:
    """0G Storage flow-merkle rootHash of arbitrary content bytes, as a 0x-hex string."""
    n = len(content)
    chunks = _num_splits(n, CHUNK) if n > 0 else 1
    padded_chunks, _ = _compute_padded_size(chunks)
    padded_size = padded_chunks * CHUNK
    data = content + b"\x00" * (padded_size - n)
    seg_roots = [_segment_root(data[o:o + SEGMENT_SIZE])
                 for o in range(0, padded_size, SEGMENT_SIZE)]
    return "0x" + _build(seg_roots).hex()


def file_root_str(text: str) -> str:
    return file_root(text.encode("utf-8"))
