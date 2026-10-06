# AION Core V1 — Formal Closure OPS Packet

This directory supports Issue #953 and Draft PR #954. It is **operations-only**. It is not Core logic, not the freeze target, and grants no merge/deploy/worker authority.

## Immutable formal target

- Technical candidate PR: **#951**
- Formal/freeze target: `662eab4dc4f5bb009fa1ca89f87530df74d30ddf`
- Technical state: `TECHNICAL_CLOSURE_CANDIDATE`
- Last read-only runtime CAS SHA: `020facc9991c5d2d4ce457e0840b04c875f8cfae`

The #954 OPS HEAD must never replace the formal target above.

## Unsigned V2.20 evidence packet

`unsigned_v220_evidence_packet.json` contains all 17 required dimensions, explicitly labeled and bound to the immutable formal target.

Evidence sources include:

- AION Core Certification run `37495769399`: 67 V2.20/synthetic-stress tests, 320 V2.13–V2.19 structural tests, 7 E2E/load tests, 52 chaos/recovery tests, 132 durable/tenant/audit tests + 9 subtests, and 24 resource/concurrency tests + 6 subtests.
- #951 exact-head matrix: 91/91 workflows green.
- Global Worker readiness run `37495769278`: PASS / READY_FOR_ADMIN_ARMING, five successful pulses, runtime unmodified, worker unarmed.

Contract test-count sum: **2729**. Minimum required: **1000**.

Current reproducible unsigned packet digest:

`sha256:14ca8f5231465136826518d9133092420c9f19f0f0de53e4c27634017419a72d`

Digest rule:

`sha256(canonical-json(packet-without-unsigned_packet_digest))`

## This is not a certificate

The packet intentionally contains no production key id/version, signing window, signature, or private key.

The private V2.20 certification key and the HUMAN_OWNER private key must remain outside the repository, runtime JSON, CI logs, issues/PRs and LLM prompts. Use separate public trust roots for certification authority and HUMAN_OWNER authority.

## OPS tooling

The helpers live in `ops/aion_core_v1_formal_closure/`.

- `validate_unsigned_v220_packet.py`: verifies 17 dimensions, exact target, row digests, packet digest and 2729 test-count sum; no network/sign/write.
- `export_v220_signing_bundle.py`: exports canonical V2.20 bytes for external signing; never loads a private key.
- `apply_v220_signatures.py`: attaches externally returned signatures; real V2.20 later performs cryptographic verification.
- `prepare_v220_v222.py`: verifies V2.20, builds V2.21, logical Checkpoint Mestre and fresh V2.22; no network/runtime mutation.
- `perform_v223_runtime_write.py`: dry-run by default; writes only with `--execute-v223-write`; enforces CAS, `allow_global_arming_transition=False`, read-after-write and no automatic retry.
- `prepare_v224_owner_signature.py`: creates the short-lived HUMAN_OWNER acknowledgement request; no nonce consumption and no signing.
- `verify_v224_prepare_v225.py`: prebuilds V2.25, verifies V2.24, durably claims the V2.24 nonce, and prepares only `APPROVE_CORE_FREEZE` or `DENY_CORE_FREEZE`.
- `perform_v225_v226.py`: dry-run cryptographically prechecks V2.25 without consuming its nonce; only `--execute-v226-write` consumes the decision nonce and attempts the V2.26 CAS write/attestation.

## Durable nonce registry

V2.24/V2.25 replay protection uses `PersistentNonceRegistry` (SQLite/WAL/FULL synchronous). The registry path must be **outside the repository working tree**.

Suggested Windows location:

`$env:LOCALAPPDATA\AtlasQuantAION\formal-closure\nonce_registry.sqlite3`

Do not delete or recreate the registry during an active ceremony.

## Tight timing boundary

V2.24 and V2.25 request windows are at most 180 seconds. Generate them only when the external signer is ready. If a window expires, rebuild with a fresh ceremony id/nonce. Never reuse a consumed nonce.

## Final authority boundary

A positively attested V2.26 APPROVE may only produce `core_freeze_ceremony_eligible=true`.

It still keeps `core_freeze_execution_authorized=false`, `core_frozen=false`, `merge_authorized=false`, `deploy_authorized=false`, and `worker_armed=false`.

Core Freeze, merge, deploy and Global Worker activation remain separate owner-controlled ceremonies.

## Current real state

The authorized Windows device remains offline. No private-key operation, production trust-root provisioning, real V2.20 signature, nonce consumption, runtime write, owner signature, owner decision or freeze has been performed.
