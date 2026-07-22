"""Independent reimplementation of the ENSIP-7 (EIP-1577) contenthash encoding for
IPFS — the CID -> `0xe301…` byte string an ENS `setContenthash` write commits.

Derived from the public spec (ENSIP-7 / EIP-1577 + the multiformats CID/multibase/
multicodec rules), NOT by calling the @ensdomains/content-hash JS library — so a
candidate MCP that uses that library is checked against a genuinely second
implementation (byte-identity is meaningful, not tautological).

Validated against the content-hash library's own published golden vectors
(CIDv0 + CIDv1 of the same content -> the same contenthash) and the live ENS MCP.

Scope v0: ipfs-ns only (protocol code 0xe3). ipns/swarm/onion are out of scope.
"""

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"  # base58btc: no 0 O I l


def _b58decode(s: str) -> bytes:
    num = 0
    for ch in s:
        num = num * 58 + _B58.index(ch)
    # leading '1's are leading zero bytes
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + body


def _multibase_decode(s: str) -> bytes:
    """Decode a multibase string (leading char = base prefix)."""
    prefix, rest = s[0], s[1:]
    if prefix == "b":  # base32 RFC4648 lower, no padding
        import base64
        up = rest.upper()
        up += "=" * ((-len(up)) % 8)
        return base64.b32decode(up)
    if prefix == "z":  # base58btc
        return _b58decode(rest)
    if prefix == "f":  # base16 lower
        return bytes.fromhex(rest)
    raise ValueError(f"unsupported multibase prefix: {prefix!r}")


def _cid_binary(cid: str) -> bytes:
    """Return the CIDv1 binary form: varint(version=1) ‖ varint(codec) ‖ multihash."""
    if cid.startswith("Qm") and len(cid) == 46:
        # CIDv0: base58btc of a raw multihash (sha2-256). Upgrade to CIDv1 dag-pb.
        mh = _b58decode(cid)
        return b"\x01\x70" + mh  # version 1, codec 0x70 (dag-pb)
    # CIDv1: multibase-decoded bytes already are version ‖ codec ‖ multihash
    b = _multibase_decode(cid)
    if not b or b[0] != 0x01:
        raise ValueError("not a CIDv1 (expected version byte 0x01)")
    return b


def encode_ipfs(cid_or_uri: str) -> str:
    """CID (or ipfs://CID) -> ENSIP-7 contenthash as a 0x-hex string."""
    cid = cid_or_uri.strip()
    for p in ("ipfs://ipfs/", "ipfs://", "/ipfs/"):
        if cid.startswith(p):
            cid = cid[len(p):]
            break
    cid = cid.strip("/")
    return "0x" + b"\xe3\x01".hex() + _cid_binary(cid).hex()
