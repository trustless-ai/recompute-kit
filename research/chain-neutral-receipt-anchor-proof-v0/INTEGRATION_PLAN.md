# Integration plan

1. Independently review the RVR boundary, policy bootstrap, dual-native algorithms and exact finite witnesses. This draft is not ready for production or normative adoption.
2. Review whether a separately versioned RVR anchor-verification profile is warranted. If yes, use existing RVR manifest/closure and native axes; never add a seventh receipt field or reinterpret the generic SHA256_EQUALS claim as execution.
3. Agree on a public policy authority/provisioning model and an actual timestamp-verifier interface before claiming public anchoring. Keep claimed OTS metadata UNVERIFIABLE until that work exists.
4. Implement the browser recipe and embeddable Web Component in recompute-lens only after its licensing/consent question is resolved. The proposed JSON projection is versioned and preserves access to native reports.
5. ReceiptOS Verify may consume this implementation-neutral candidate as an independent Apache-2.0 host, retaining its own license, historical receipt profiles and native results.

The experiment lives in recompute-kit research. A dedicated additive workflow invokes the existing canonical runner API against its suite and executes boundary/mutation controls. Main's original conformance suite remains untouched. PR #78 is an independent open integration dependency; this branch does not edit, merge or assume it landed. No new generic execution or judgment service is planned.
