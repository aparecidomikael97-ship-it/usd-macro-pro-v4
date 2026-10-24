# A190 G34 — Explicit Outbox implicit transaction replacement + atomic schema DDL

**Date:** 2026-10-24. **Exact tested code and workflow SHA:** `33e5a8a9755bc2be7d62b5004a1ba7dec14b78bb`. Branch: `lab/aion-a190-g34-implicit-transactions-schema-atomic-20261024` stacked on G33 Draft PR #1520. **Draft/LAB candidate only. No merge, deploy, provider or Worker activation.**

## Technical change

- In `atlasquant_aion_execution_outbox.py`, the seven remaining state-transition blocks using implicit `with self.db:` now use a shared `_managed_write_transaction()`. It explicitly starts `BEGIN IMMEDIATE`, calls `_commit_or_quarantine()` only after the write body has completed, and rolls back body exceptions through the G31 primary-exception-preserving handler.
- Any COMMIT exception **before OR after the SQLite connection has actually committed** detaches and quarantines both shared Store and Outbox handles. The exception is preserved; the code does **not** retry automatically or treat a rollback as proof that the commit never happened.
- Outbox `_ensure_schema()` no longer uses `executescript()`, which implicitly commits an active connection before executing the script. Instead, its static DDL (no triggers or semicolons inside bodies) runs statement-by-statement inside a single explicit transaction. A mid-schema DDL error rolls back all newly created Outbox tables in the isolated test. A successful schema commit with lost acknowledgement **still** raises an error and quarantines the handle.
- These edits are candidates: no operational transition is authorized.

## Deterministic RED and GREEN (synthetic fault injection around *real SQLite*)

- `G34_BLOCK_PRECOMMIT_GREEN=DENIAL_NOT_PERSISTED_STORE_QUARANTINED`: authority-revocation write not persisted when physical COMMIT never occurred.
- `G34_BLOCK_POSTCOMMIT_RED=REVOKED_PERSISTED_DESPITE_EXCEPTION`: same API error **after real COMMIT** leaves REVOKED durably stored.
- `G34_PRE_WITNESS_POSTCOMMIT_RED=UNCERTAIN_PERSISTED_ACK_UNKNOWN`: pre-first-send UNCERTAIN state was committed despite the acknowledgement exception.
- `G34_NO_SEND_POSTCOMMIT_RED=FINAL_UNCERTAIN_PERSISTED_ACK_UNKNOWN`: second no-witness transition committed despite the exception.
- `G34_POSTCOMMIT_REOPEN_GREEN=UNCERTAIN_NOT_RECLAIMED`: after opening a fresh store, an UNCERTAIN intent is not automatically reclaimed.
- `G34_ATOMIC_DDL_GREEN=NO_PARTIAL_ACTION_SCHEMA_AFTER_ERROR`: mid-DDL failure leaves **no** action tables from a previously empty Outbox schema.
- `G34_SCHEMA_POSTCOMMIT_RED=TABLES_EXIST_ACK_UNKNOWN`: all three Outbox tables exist after successful DDL COMMIT followed by synthetic lost acknowledgement.
- No provider adapter was used in the test; send-lookup trap remains untouched.

## Cross-platform CI proof

[**G34 GitHub Actions #40126044443**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40126044443): **SUCCESS**, at the exact tested SHA above.
- Ubuntu job `120967554300`: **16 new G34 + 24 G33 + 20 G32 + 18 G31 + 23 G30 = 101/101**.
- Windows job `120967554580`: **101/101**.
- **202 test executions of 101 distinct tests**; positive and intentionally RED findings were checked by mandatory log markers.

## Wider CI, same tested SHA

**10 of 11 workflow runs SUCCESS**, including G12, G31, G33, G34, A176, A177, A178, A179, A180 and A181.

[**A184 six-P0 evidence #40126044375**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40126044375) **FAILURE / RED**:
- Candidate canonical Quality job `120967554239`: **6,449 tests passed**.
- BASE canonical Quality job `120967554271`: 6,322 tests, **four failures**, historical.
- Candidate security-unittest and security-pytest jobs passed.
- Candidate security-audit job `120967554210` **FAILED**: `pip-audit -r requirements.txt` reports **48 known vulnerabilities in two packages** (installed `pypdf 6.19.0` and `Pillow 12.3.0`). BASE security-audit also fails. Adversarial BASE and unmet-external-requirements RED cases persist.
- Passing Quality does **not** waive dependencies, security audit or the six P0.

## Limits and follow-up

- Python wrapper fault injection is **not** physical power-cut, fsync/disk failure, WAL tampering, adversarial rollback, trusted first-send reservation or external provider reconciliation.
- Seven formerly implicit Outbox state-transition writes are now explicit; schema initialization uses a narrowly scoped static DDL splitter. Other modules and `SQLiteChatStore` startup/schema paths are not claimed to be universally atomic.
- A new local SQLite connection being healthy does **not** prove external global history freshness or provider-effect absence. `UNCERTAIN` must never be automatically resubmitted.
- Next candidates: real-process termination/crash fault scenarios in disposable LAB files, transaction-start/BEGIN failure containment, outbox after-crash reconciliation requiring an independently held monotonic witness; independently review and remediate dependency audit without unauthorized merge/deploy or spending.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. No main/merge/deploy, Worker, real provider, customer data, external keys or spending.**
