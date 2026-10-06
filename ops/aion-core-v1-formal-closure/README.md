# AION Core V1 — Formal Closure OPS Packet

This directory is **operations-only** support for Issue #953. It must not be interpreted as a Core code change or as authority to freeze, merge, deploy, arm the Global Worker, or execute external actions.

## Immutable formal target

- Technical candidate PR: **#951**
- Formal target commit: `662eab4dc4f5bb009fa1ca89f87530df74d30ddf`
- Technical state: `TECHNICAL_CLOSURE_CANDIDATE`
- Current runtime CAS SHA observed read-only: `020facc9991c5d2d4ce457e0840b04c875f8cfae`

The OPS branch is not the freeze target. Any commits in this directory are operational preparation only.

## What is already prepared

`unsigned_v220_evidence_packet.json` contains 17 **unsigned claims** for the real V2.20 certification contract.

The claims were derived from exact-head GitHub evidence:

- AION Core Certification run `37495769399`
  - V2.20 certification/synthetic stress: 67 passed
  - V2.13–V2.19 structural red-team: 320 passed
  - E2E + bounded load: 7 passed
  - chaos/recovery/traceability: 52 passed
  - durable persistence/tenant isolation/audit replay: 132 passed + 9 subtests
  - resource bounds/concurrency: 24 passed + 6 subtests
- PR #951 exact-head matrix: 91/91 workflows green
- Global Worker readiness run `37495769278`
  - PASS / READY_FOR_ADMIN_ARMING
  - 5 successful pulses observed
  - runtime unmodified
  - worker unarmed

Contract test-count sum in the unsigned packet: **2729**.
Required minimum: **1000**.

This count is the V2.20 per-row contract sum. Some multi-domain suites legitimately support more than one certification dimension; the signer must still independently confirm that each signed claim is supported by its referenced evidence.

## Important: this is not a certificate

The packet deliberately has no:

- production `key_id`
- production `key_version`
- signing window
- Ed25519 signature

Therefore it is not eligible evidence and must not be fed into the real certification as if it were signed.

The external signer must independently verify every claim before signing it.

## Authority bootstrap

The real V2.20 chain requires a production certification trust root with this public shape:

```json
{
  "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
  "roots": [
    {
      "key_id": "<production-certification-key-id>",
      "key_version": 1,
      "algorithm": "Ed25519",
      "public_key_b64": "<base64url-raw-32-byte-public-key>",
      "status": "ACTIVE",
      "not_before": "<RFC3339 UTC>",
      "not_after": "<RFC3339 UTC>"
    }
  ],
  "revoked_key_ids": []
}
```

Only the **public key** belongs in a trust-root payload. The private Ed25519 key must remain outside:

- this repository;
- GitHub issue/PR comments;
- ChatGPT/LLM prompts;
- runtime checkpoint JSON;
- CI logs.

The certification key should also remain logically separate from the HUMAN_OWNER V2.24/V2.25 owner-signing key.

## Exact signed V2.20 statement

For each dimension, the external signer must sign the canonical JSON bytes produced by the existing production function:

`atlasquant_aion_core_certification.canonical_evidence_attestation_bytes(dimension, row)`

The signed statement contains:

- schema
- dimension
- state
- source
- run_id
- commit_sha
- evidence_digest
- test_count
- verified
- key_id
- key_version
- issued_at
- expires_at

The existing V2.20 verifier rejects unknown keys, wrong key material, revoked/expired roots, invalid windows, tampering, digest mismatch and missing signatures.

## Real closure chain after signing

1. Attach valid production key metadata + signing window + Ed25519 signature to all 17 claims.
2. Load the public certification trust root with `TrustRootRegistry.from_mapping()`.
3. Run `certify_core(...)` against the immutable target commit.
4. Require exactly `CERTIFICATION_CANDIDATE`.
5. Run V2.21 `build_core_completion_review()`.
6. Require exactly `READY_FOR_OWNER_REVIEW`.
7. Build the V2.21 checkpoint patch with `build_checkpoint_patch_candidate()`.
8. Create the logical Checkpoint Mestre for the formal ceremony and append the exact V2.21 review patch.
9. Generate a fresh V2.22 challenge with:
   - fresh ceremony id;
   - fresh nonce;
   - short validity window;
   - exact target commit;
   - exact V2.20/V2.21/checkpoint binding.
10. Require `READY_FOR_OWNER_DECISION_PREFLIGHT`.
11. Load the current official runtime again and re-check its CAS SHA.
12. Stage the V2.23 runtime candidate with `stage_runtime_persistence_candidate()`.
13. Persist only through the existing official writer:
    `save_runtime_checkpoint(candidate, approved=True, expected_sha=<fresh runtime sha>, allow_global_arming_transition=False)`
14. Require:
    - `status=CONFIRMED`
    - `saved=true`
    - `verified=true`
    - exact write receipt
    - read-after-write SHA equality
    - exact checkpoint digest equality
15. Run V2.23 `verify_external_checkpoint_persistence()`.
16. Only `READY_FOR_OWNER_SIGNATURE_CEREMONY` may proceed to V2.24.
17. V2.24 uses a separate HUMAN_OWNER identity/state signature.
18. V2.25 uses a second signature over only `APPROVE_CORE_FREEZE` or `DENY_CORE_FREEZE`.
19. V2.26 persists/attests that decision record.
20. Even a positively attested APPROVE only yields `core_freeze_ceremony_eligible=true`.
21. Core Freeze execution remains a separate ceremony.
22. Merge, deploy and Global Worker activation remain separate decisions.

## Fail-closed rules

Abort and rebuild the ceremony if any of these occur:

- target commit changes;
- runtime CAS SHA changes before write;
- evidence run no longer supports its claim;
- production trust root is absent, inactive, revoked or expired;
- signing window expires;
- any signature is invalid;
- V2.21 review differs from the V2.20 manifest;
- logical Checkpoint Mestre changes after V2.22;
- write result is ambiguous;
- receipt cannot be uniquely attributed;
- read-after-write differs;
- runtime observation becomes stale;
- any step attempts implicit Core Freeze, merge, deploy or Worker arming.

Never automatically retry an ambiguous runtime write.

## Current blocker

The authorized Windows execution device is offline. Therefore:

- no production private-key operation was performed;
- no production trust root was provisioned;
- no real V2.20 attestation was signed;
- no nonce was consumed;
- no runtime write was attempted;
- no owner signature or decision was created.

This is the correct fail-closed state.
