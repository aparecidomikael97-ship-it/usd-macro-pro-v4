# AtlasQuant / AION — A190 G32 Chat Store transaction quarantine LAB

**Date:** 2026-10-24. **Exact tested code/workflow SHA:** `0236c065d1fb78a888ba412a6c46a46f9792a936`. Branch `lab/aion-a190-g32-chat-store-transaction-quarantine-20261024` stacked on G31 Draft #1518. **No merge or deploy.**

## Code change

A candidate modification to `aion_chat/store.py` (NOT operationally integrated):
- Adds `_rollback_or_quarantine(primary_error)` that preserves the original error, chains a failed SQLite rollback exception as the cause, detaches and closes the unsafe DB, and prevents the same store from being reused after rollback uncertainty.
- Adds `_managed_write_transaction()` using explicit `BEGIN IMMEDIATE`, commit and exception-directed rollback, with the same fail-closed behavior for create conversation, archive conversation, attachment metadata, save checkpoint and save context summary.
- Refactors `append_message` to use the shared rollback/quarantine handler instead of ignoring a rollback exception.
- Adds isolated `labs/a190/test_g32_chat_store_rollback_quarantine_lab.py` (20 tests) and cross-platform CI that also runs inherited G31 (18) and G30 (23) suites.

## Verified focused CI

- [G32 GitHub Actions **#40124687403**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40124687403): completed **SUCCESS**.
- Ubuntu job `120963490899`: **20/20 G32 + 18/18 G31 + 23/23 G30 = 61/61**.
- Windows job `120963491159`: **20/20 G32 + 18/18 G31 + 23/23 G30 = 61/61**.
- **122 executions of 61 distinct tests**, all synthetic SQLite fault cases and regression selectors.
- Positive markers:
  - `G32_CHAT_QUARANTINE_GREEN=PRIMARY_PRESERVED_CONNECTION_DETACHED`
  - `G32_APPEND_MESSAGE_GREEN=NO_SILENT_ROLLBACK_FAILURE`
  - `G32_NO_RETRY_GREEN=STICKY_FAIL_CLOSED_AFTER_ROLLBACK_ERROR`
  - `G32_REOPEN_LIMIT=LOCAL_SQLITE_IS_NOT_EXTERNAL_FRESHNESS`
  - G31 and G30 retained their existing fail-closed regression markers.

## Broader CI status at the same exact SHA — **6/7 workflow runs success, 1 RED**

- G32 #40124687403 **SUCCESS**.
- G31 inherited #40124687242 **SUCCESS**.
- SQLite staged lifecycle #40124687330 **SUCCESS**.
- A186 SQLite connection factory #40124687322 **SUCCESS**.
- A187 stricter connection admission #40124687289 **SUCCESS**.
- G14 native SQLite marker ABA #40124687252 **SUCCESS**.
- [A184 six-P0 matrix **#40124687249**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40124687249): **FAILURE / RED**. The candidate **canonical quality selector passed 6,449 tests** (job `120963490852`); candidate security-unittest and security-pytest jobs passed. The BASE canonical Quality selector ran 6,322 tests and failed four (job `120963490664`). The candidate security-audit job `120963490676` **FAILED**: `pip-audit -r requirements.txt` reported **48 known vulnerabilities across pypdf 6.19.0 and pillow 12.3.0** (also reported for base). A184 intentional adversarial BASE/external RED jobs failed as expected or due unmet requirements. **No P0 closure**.

## Limitations and next gates

- The write-path tests inject wrapper exceptions over real local SQLite handles, **not** real OS/file-system failure, power loss, disk corruption or trusted monotonic custody.
- A failed `commit()` with an ambiguous durable outcome is not separately certified; a connection may also be held through raw aliases. Requires a fail-closed crash/commit uncertainty contract and tests against live power-fault/storage scenarios.
- Creating a fresh SQLite store after quarantine can show a healthy local database but **does not prove global freshness or no previous external effect**.
- External first-send reservations, independent signer/owner authentication, provider receipts, semantic identity collision gaps (G29), actual restart antirollback and full six-P0 homologation remain outstanding.
- Security audit dependency vulnerabilities remain open and should not be hidden by passing Quality selectors.
- No real provider, Worker, external effect, spending, customer secrets, main/merge/deploy.

**P0 homologados: 0/6. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND.**
