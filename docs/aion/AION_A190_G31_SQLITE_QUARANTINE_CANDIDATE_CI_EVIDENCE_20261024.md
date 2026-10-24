# AION A190 G31 — SQLite transaction rollback quarantine candidate

Date: **2026-10-24**. Branch: `lab/aion-a190-g31-outbox-rollback-quarantine-candidate-20261024` (stacked on G30 #1517). Exact code/workflow SHA fully tested: **`b261bf9d21ef682878361331dd69cb35f9ba1ef0`**. This is a **Draft/LAB candidate**, **not operationally deployed or merged**.

## Change under review

- `aion_chat/store.py`: new `SQLiteChatStore.quarantine_failed_transaction()`. Detaches `store.db` **before** attempting to close the connection, marks failed with reason `TRANSACTION_ROLLBACK_UNCERTAIN`, and ignores any *secondary* close error. A detached store fails health checks and requires explicit recovery; it is not automatically reopened.
- `atlasquant_aion_execution_outbox.py`: new `_rollback_preserving_original(original_error)`. In four transaction exception handlers (enqueue, lease release, claim and effect confirmation), a successful rollback preserves the original exception. A failing rollback quarantines the store, detaches `outbox.db`, raises the **original exception** with the failed rollback as its chained cause and adds a diagnostic note. The stale-claim rowcount branch similarly quarantines a failed rollback and raises `StorageUnavailableError`.
- `labs/a190/test_g30_sqlite_rollback_fault_lab.py`: old intentional G30 RED was rebaselined **in this stacked branch only** to assert the candidate's corrected behavior. The original G30 branch keeps its historical RED evidence.
- `.github/workflows/aion-a190-g30-dispatch-sqlite-fault-lab.yml` expects the updated regression marker. **First inherited G30 workflow #40123892207 failed** because it still required the old RED string; fixed that assertion and revalidated. Never treat a historical RED grep failure as a new security exploit.

## Verified focused Windows + Ubuntu

- [G31 candidate CI **#40123965109**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40123965109): **SUCCESS**. Windows job `120961299803` and Ubuntu job `120961299980` each passed **18 G31 tests + 23 G30 regression tests**, for **82 executions of 41 distinct tests**.
- [Inherited G30 CI **#40123965039**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40123965039): **SUCCESS** on both OSes after assertion update.

Evidence markers in cross-platform logs:
- `G31_PRIMARY_EXCEPTION_GREEN=ORIGINAL_RETAINED_ROLLBACK_AS_CAUSE`.
- `G31_QUARANTINE_GREEN=NO_NEW_STAGING_AFTER_FAILED_ROLLBACK`.
- `G31_CONFIRM_PATH_GREEN=PRIMARY_ERROR_QUARANTINED`.
- `G31_STALE_CLAIM_GREEN=FAILED_ROLLBACK_NO_RETRY`.
- `G31_G30_REGRESSION_GREEN=ORIGINAL_ERROR_RETAINED_STORE_DETACHED`.

## Broader CI truth (do not misreport as all green)

At exact SHA `b261bf9d...`, **13/14 invoked workflow runs finished SUCCESS** (including G12, G14, G30, G31, A176–A181, A186–A187 and SQLite staged lifecycle).

**A184 workflow #40123965046 is FAILURE.** It includes intentional BASE RED and external-requirement RED jobs, and failed security-audit jobs. Candidate canonical security-unittest, security-pytest and **canonical quality selector (6,449 tests run)** finished SUCCESS, but **canonical security-audit (candidate) failed**. Its `pip-audit -r requirements.txt` reported **48 known vulnerabilities in two packages** (pypdf 6.19.0 and pillow 12.3.0); the BASE security-audit also failed. These dependency findings have **not** been fixed in G31. A184's overall RED status **remains a block**; do not re-label it as pass.

## Strict evidentiary limits

All injected failures were **synthetic wrapper faults around a real local SQLite connection**; there was no genuine power-loss, filesystem error, hostile host, external witness, provider dispatch, signed provider receipt or revalidation after a physical crash. Closing/detaching the connection is an *in-process local fail-closed mechanism*, not an external antirollback guarantee or proof that a real effect was not performed. A new SQLite connection may read the prior committed rows but cannot certify absence of missing effects. Callers holding other raw SQLite references, and `SQLiteChatStore` methods outside the Outbox transaction paths (e.g. message append), are **not comprehensively proven** by this targeted patch.

G29 idempotent staging metadata conflicts, caller-defined business semantic identifiers, redacted-payload collisions, independent first-send custody and full A184 security weaknesses remain unresolved.

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. No main/merge/deploy/Worker/provider/customer secrets/spending.**
