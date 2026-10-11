# AION — Consolidated UI + Staged SQLite host review (Draft, 2026-10-10)

## Provenance (immutable source commitments)

- Base of this candidate: #1194 `bcd87e4794bf7b883f87861f80bad0aac735d415`. #1194 reconciles #1192 (turn-scoped WAITING_APPROVAL/BLOCKED notices) and #1193 (historical UNKNOWN, LOCAL_PRESENT and unverified receipt semantics) with independent Windows/Linux browser and core CI green.
- Additional imported files are exact content snapshots from Codex #1195 HEAD `e0e249db64c1bef32ff47f0048a9900542dd144a`: `aion_chat/staged_store.py`, `atlasquant_aion_chat_host_staging.py`, `atlasquant_aion_chat_storage_resilience.py`, `test_atlasquant_aion_chat_sqlite_lifecycle.py`, its exact-HEAD Windows/Linux CI and audit report.
- `.github/workflows/quality-tests.yml` is **reconciled** to include BOTH independent test files: `test_aion_history_truth_preparation.py` and `test_atlasquant_aion_chat_sqlite_lifecycle.py`. Nothing previously registered was removed.
- Core V1 files, original Draft branches #1192/#1193/#1194/#1195 and `main` were not edited; **this is a separate comparison/review branch**.

## Boundaries and direct acceptance

1. Historical result reads of assistant messages remain `UNKNOWN` and receipts remain declared/unverified until independently checked; never infer `CONFIRMED_SUCCESS` from local presence or metadata alone.
2. Only latest WAITING_APPROVAL/BLOCKED turn produces a last-turn informational notice; a stored UNKNOWN never becomes an approval notice or chat-wide lock. Approval has no new authority.
3. The real staged host caches **connection-free facade** per scope, not a raw SQLite connection. Every allowlisted call opens and closes its native connection on its calling thread. SQLite native thread checks remain enabled, and identity/tenant/credential rotation revokes the old facade. No provider, network, Worker or production persistence is authorized.
4. The staged preview's previously implemented close-on-script-run-exit harness behavior from #1194 remains intact and is exercised with the facade as an integrated combination. It is not counted as an independent production assurance certificate.
5. Real SQLite and Chromium suites on Windows/Linux, plus mandatory Quality, staged lifecycle, security, and core CI must pass on **THIS exact final HEAD**. Source PR standalone green checks do not certify interaction.

## Remaining gates (NO-GO)
- No first install, unattended merge, release/deploy, Worker/Render activation, cloud credential or production provider use.
- Full physical Windows host, independent identity/witness, multi-process admission, unknown outcome reconciliation, performance and long-duration restart/tenant changes remain separately blocked.
- Per-operation database open/integrity checks may introduce latency; a committed write followed by a close error remains an unknown outcome, not idempotency proof.
- No claim that AION Core V1 itself is complete for consumer production use merely because CI suites are green.

**Disposition:** Draft integration evaluation; merge authority remains HUMAN_OWNER only, explicitly per later instruction. Avoid merging older overlapping source PRs separately if this integrated candidate is selected.
