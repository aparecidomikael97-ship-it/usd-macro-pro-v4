# AION V16-A.47 — Global Worker cannot run without an independent external source/witness

**Parent:** V16-A.46 Draft #1259 final HEAD `a43362eed58f9a9d2a3c144add05cb4034ac49f3`. This is a draft, unmerged child of A.46 only. No Core V1/main/AM12 or external service modifications.

## RED reproduced on real Worker path

The A.46 fix rechecked **internal component digests**, but allowed `run_global_worker_once(feature_enabled=True)` to continue to GitHub runtime checkpoint retrieval even though:
- Repo/branch/path/token configuration was caller supplied, without owner↔tenant↔resource authenticity proof pinned by an independent trust root.
- Local GitHub SHA and digest checks do not establish an independently custodied current monotonic head or detect coherent old restore.
- No owner-enrolled signed approval, source trust authority, witness freshness/revocation or independent administration domain existed.

The first A47 test-only HEAD `e3b3c5fa061fef09997e77f0d0fef9108e576106` failed [Security Gate run 38463970460](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38463970460): **3/3 intentional RED** on the initially strict no-fetch/no-descriptor negative contracts. Explicit feature flag and mocked environment activation reached `load_runtime_checkpoint` before independently enrolled source trust, and a hostile config's `write_ready` property was accessed. All remote/DB/executor methods were mocked inert; no network or real effect. The strict **no-fetch** requirement was refined after the first A47 hard-stop made **A46 corrupt-checkpoint checks unreachable**, a regression in security coverage. The final gate explicitly permits the existing read-only GET and preserves A46's raw-integrity veto, but forbids ALL lease CAS, runtime writes or executor calls without independent source/witness enrollment. The RED tests remain recorded; final tests assert no productive boundary crossing, not no read.

## Fail-closed interim correction

At the Worker entrypoint, a non-`RuntimeConfig` object is denied **before descriptor access or network calls** (`GLOBAL_RUNTIME_CONFIG_TYPE_INVALID`). For a valid config, the original read-only checkpoint fetch and **A46 raw digest verification** run. If the raw checkpoint is MISMATCH/UNKNOWN, A46 blocks first. Otherwise, a separate **unconditional** `BLOCKED/INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED` return is enforced **before checkpoint normalization, lease CAS, runtime write, retry, local executor or external action**. It reports zero processed, no execution/retry, all independent trust flags false. It cannot be bypassed by `feature_enabled=True`, the environment flag, a local checkpoint, fake `verified` field or fixture. The original feature-disabled result is preserved. The legacy positive tick implementation below this barrier is unreachable until reviewed external witness enrollment.

**This is containment, not completed source integration.** A separately approved future implementation with a real independent trust root, owner/tenant/repo binding, monotonically witnessed current head and recovery/failure domain separation is necessary before any positive path is reviewed. A local key, checksum, mocked CAS, CI green, GitHub token or role ADMIN is not adequate.

## Explicit cost: existing legacy positive tests turn red

Existing historical Global Worker tests intentionally simulate successful tick, lease CAS, local receipt and synthetic work. Once the actual Worker is made fail-closed, those liveness assertions will no longer pass. **Do not xfail, skip, delete, modify or call them "historical successes".** Root Quality already has 23 Outbox + 8 Saga ERROR; A47 will additionally surface obsolete/unsafe Global Worker positive assumptions. Report exact count and categories. Keep negative safety tests passing; leave Quality correctly RED. Future recovery should split non-executing pure simulation from the productive entrypoint under separate review without a bypass.

## Original test artifacts and physical blockers

A.12 `AION_V16_A12_MOBILE_SIX_SOURCE_GATE_20261013.zip` SHA256 `9aef4242ffb096410113460bf68f5b0e5f05d23b4d4f237e7eb59de5a7b04609` (37) and A.16 `AION_V16_A16_MOBILE_REAL_MODULE_REGRESSIONS_PREP_20261013.zip` SHA256 `8c3cb6147845bd4a47996c9aa05191b082783fa72ad8d06f5292e92b4b844205` (8) were created only as sandbox artifacts in another chat, not available at present in container, GitHub, Google Drive, Library or Gmail. Do not replace them or claim execution.

Still **0/6 P0 homologated; 20/20 first-install gates HARD NO-GO**. Source witness, producer committed effect and terminal no-effect guarantee, signed HUMAN_OWNER/host attestation, physical network/sandbox and cost/availability approval are absent. No merge/deploy/Worker/Render/TPM/signer/keys/accounts/spend/AM12/real send.
