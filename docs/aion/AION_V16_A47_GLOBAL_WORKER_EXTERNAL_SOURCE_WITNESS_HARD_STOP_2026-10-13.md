# AION V16-A.47 — Global Worker cannot run without an independent external source/witness

**Parent:** V16-A.46 Draft #1259 final HEAD `a43362eed58f9a9d2a3c144add05cb4034ac49f3`. This is a draft, unmerged child of A.46 only. No Core V1/main/AM12 or external service modifications.

## RED reproduced on real Worker path

The A.46 fix rechecked **internal component digests**, but allowed `run_global_worker_once(feature_enabled=True)` to continue to GitHub runtime checkpoint retrieval even though:
- Repo/branch/path/token configuration was caller supplied, without owner↔tenant↔resource authenticity proof pinned by an independent trust root.
- Local GitHub SHA and digest checks do not establish an independently custodied current monotonic head or detect coherent old restore.
- No owner-enrolled signed approval, source trust authority, witness freshness/revocation or independent administration domain existed.

The first A47 test-only HEAD `e3b3c5fa061fef09997e77f0d0fef9108e576106` failed [Security Gate run 38463970460](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38463970460): **3/3 intentional RED** on three direct real-code negative contracts. Explicit feature flag and mocked environment activation both reached `load_runtime_checkpoint` before any independent witness proof. An adversarial configuration descriptor's `write_ready` property was read before source trust verification. All remote/DB/executor methods were mocked inert in these tests; no network or real effect executed; no claim that production was exploited.

## Fail-closed interim correction

At the actual Worker entrypoint, immediately after the preexisting `FEATURE_DISABLED` return, an **unconditional** `BLOCKED/INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED` return is enforced **before config resolution, property evaluation, network access, runtime read/write/CAS, or local executor**. It records zero processed, no execution, no retry, all trust flags false. It cannot be bypassed by `feature_enabled=True`, the environment flag, a local checkpoint, a fake `verified` field or test fixture. Original feature-disabled result preserved. The legacy tick implementation below this barrier is deliberately unreachable and must never be considered enabled.

**This is containment, not completed source integration.** A separately approved future implementation with a real independent trust root, owner/tenant/repo binding, monotonically witnessed current head and recovery/failure domain separation is necessary before any positive path is reviewed. A local key, checksum, mocked CAS, CI green, GitHub token or role ADMIN is not adequate.

## Explicit cost: existing legacy positive tests turn red

Existing historical Global Worker tests intentionally simulate successful tick, lease CAS, local receipt and synthetic work. Once the actual Worker is made fail-closed, those liveness assertions will no longer pass. **Do not xfail, skip, delete, modify or call them "historical successes".** Root Quality already has 23 Outbox + 8 Saga ERROR; A47 will additionally surface obsolete/unsafe Global Worker positive assumptions. Report exact count and categories. Keep negative safety tests passing; leave Quality correctly RED. Future recovery should split non-executing pure simulation from the productive entrypoint under separate review without a bypass.

## Original test artifacts and physical blockers

A.12 `AION_V16_A12_MOBILE_SIX_SOURCE_GATE_20261013.zip` SHA256 `9aef4242ffb096410113460bf68f5b0e5f05d23b4d4f237e7eb59de5a7b04609` (37) and A.16 `AION_V16_A16_MOBILE_REAL_MODULE_REGRESSIONS_PREP_20261013.zip` SHA256 `8c3cb6147845bd4a47996c9aa05191b082783fa72ad8d06f5292e92b4b844205` (8) were created only as sandbox artifacts in another chat, not available at present in container, GitHub, Google Drive, Library or Gmail. Do not replace them or claim execution.

Still **0/6 P0 homologated; 20/20 first-install gates HARD NO-GO**. Source witness, producer committed effect and terminal no-effect guarantee, signed HUMAN_OWNER/host attestation, physical network/sandbox and cost/availability approval are absent. No merge/deploy/Worker/Render/TPM/signer/keys/accounts/spend/AM12/real send.
