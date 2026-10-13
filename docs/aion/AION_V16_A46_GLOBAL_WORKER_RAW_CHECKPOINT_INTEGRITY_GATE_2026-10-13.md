# AION V16-A.46 — Global Worker raw checkpoint integrity gate before CAS and execution

**Parent:** V16-A.45 Draft PR #1258 exact HEAD `66d422919306dc9832cbc46eaf6bcfe763689cbb`. This change is isolated, unmerged, and never enables Worker/Render/provider/installer or production host.

## Confirmed source-level risk

In `atlasquant_aion_memory.load_runtime_checkpoint`, a valid HTTP read and decode can produce `status=CONFIRMED` even when `checkpoint_integrity_report(checkpoint).state=MISMATCH` or `UNKNOWN` (the report is returned as a separate field). In `atlasquant_aion_global_worker.run_global_worker_once`, the original real path previously checked only `loaded.status == CONFIRMED` then called `ensure_operating_checkpoint` **before** considering original persisted digests. Normalization can regenerate component structures and may hide the original mismatch in memory. A caller can also put a made-up `loaded.integrity.state=CONFIRMED` in the read result. The worker could then proceed to process local tasks and persist a new claimed lease despite no integrity proof of the raw bytes.

## Minimum fail-closed repair

- After successful checkpoint fetch and before **any** normalization, Worker independently recomputes `checkpoint_integrity_report(loaded.checkpoint)`. It **does not** trust `loaded.integrity` as authoritative.
- If its local report is not `CONFIRMED` or `MIGRATION_REQUIRED` (the preexisting compatibility states accepted by the checkpoint writer), return `status=BLOCKED`, `reason=GLOBAL_CHECKPOINT_INTEGRITY_MISMATCH/UNKNOWN`, `executor_called=false`, `automatic_runtime_checkpoint_persistence=false`, `external_action_executed=false`, with zero processed.
- An unexpected exception during this check also fails closed as `UNKNOWN`. No lease CAS, local executor, runtime write or claimed effect occurs from this path.
- Three new real Worker mocked-read adversarial tests: corrupted tasks digest with **forged green integrity metadata**, corrupted Global Worker digest, and confirmed read with absent checkpoint. Each proves `_persist_runtime_checkpoint_cas` and `_execute_due_local_work_authorized` not called. Existing root Quality Worker tests retained, and these three are additionally mandatory under the independent Security Gate.

## Assurance explicitly NOT provided

- This is **intra-checkpoint, local cryptographic digest consistency** ONLY. Correct hashes can be recomputed by an attacker controlling the checkpoint content, GitHub repository, admin credentials or whole DB/backup.
- It does **not** verify external resource ownership, tenant/repo/path binding, independently enrolled issuer root, latest monotonic current-head antirollback witness, producer effect/terminal fence, signed HUMAN_OWNER or hardware identity. `MIGRATION_REQUIRED` remains locally write-safe according to prior contract, not independent proof.
- The real Global Worker is still disabled operationally; no flag, credential, deployment, CI synthetic report, or draft is authorization to turn it on.
- 45 original A.12/A.16 ZIP tests remain missing in active files: `AION_V16_A12_MOBILE_SIX_SOURCE_GATE_20261013.zip` (37, SHA-256 `9aef4242ffb096410113460bf68f5b0e5f05d23b4d4f237e7eb59de5a7b04609`) and `AION_V16_A16_MOBILE_REAL_MODULE_REGRESSIONS_PREP_20261013.zip` (8, SHA-256 `8c3cb6147845bd4a47996c9aa05191b082783fa72ad8d06f5292e92b4b844205`). Do not recreate as if these are originals; ask for original bytes, hash-check and execute only when source is available and authorized.
- The 23 historical Outbox and 8 historical Saga Quality ERROR remain real RED pending separately enrolled producer receipts and terminal no-effect fence.
- **0/6 P0 homologated; first-install 20/20 HARD NO-GO**. No merge/main/Core V1, AM12/TPM, provider, Worker/Render, credentials, spend or external effects.
