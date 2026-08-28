# erc8275-win-rate-bps.v0

Prospective ERC-8275 basis-points issuance surface.

Run the hash-pinned conformance leg:

```bash
bin/conformance-suite \
  --vectors conformance/erc8275-win-rate-bps-v0/erc8275-win-rate-bps-v0.vectors.json \
  --vectors-sha256 01d354ec0cf5f1b5de88526fdb22461c72ed296ae5d289efbb26ba4ec7c88c49 \
  --adapter-cmd "python gate.py"
```

The legacy float-4dp `agent-flow.vectors.json` artifact is deliberately not
edited. New artifacts pin `0x0501b75d…68daf`; old artifacts remain resolved
under their historical convention.

The mutation-coverage leg is a second CI check:

```bash
bin/conformance-suite \
  --vectors conformance/erc8275-win-rate-bps-v0/erc8275-win-rate-bps-v0.vectors.json \
  --vectors-sha256 01d354ec0cf5f1b5de88526fdb22461c72ed296ae5d289efbb26ba4ec7c88c49 \
  --adapter-cmd "python gate.py --prove-mutations"
```

It proves that the legacy-float representation is distinguishable and that
both missing and unknown convention pointers resolve to `unverifiable`.
