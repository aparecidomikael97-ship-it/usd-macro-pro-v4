# AION — SQLite staged host lifecycle audit — 2026-10-10

Base: main 5744b2b7b17c84331e6f27c569064993ff587782. Separate draft candidate; no Core V1 changes, no production persistence or Worker activation. First install HARD NO-GO.
Protected #1191/#1192/#1193 branches are not modified. #1193 head inspected: 9086025bba2f05567a562acd0c71ecb0dbbb0019; its preview-harness close-on-run-exit fix is not copied or replaced here.

## Root cause and audit
HIGH availability/resource-lifecycle issue: atlasquant_aion_chat_host_staging.py::get_or_create_staged_store stores a live SQLiteChatStore in Streamlit session_state. aion_chat/store.py::__init__ uses sqlite3.connect with native thread safety enabled. A later script-run thread calls _validate_live_store -> storage_health; SQLite raises ProgrammingError. Reproduced against unmodified main in a separate thread with the same session dictionary: StorageUnavailableError: staged host refused unhealthy local store: DATABASE_ERROR:ProgrammingError.
This is a demonstrated host-level rerun simulation, not an observation of a production deployment or a full Streamlit browser test. #1193's Windows browser observation is separate evidence.
MEDIUM cleanup issue: close_all_staged_host_stores/close_staged_host_store popped a holder before close; get_or_create swallowed replacement close exceptions. A foreign-thread close can fail while losing the only session-managed reference. clear_session in atlasquant_access_panel.py also swallows optional cleanup errors; its behavior is not rewritten here.
Product UI uses an injected scoped store only, not a creator. It must receive fully materialized results and errors; no changes to its identity or approval gates. tools/aion_chat_product_staged_preview.py is a harness, not the real host lifecycle fix; remains untouched.
Raw SQLiteChatStore remains explicitly thread-affine. A direct foreign-thread SELECT still raises ProgrammingError in the regression suite; check_same_thread=False is not introduced.

## Minimal implementation
New aion_chat/staged_store.py::OperationScopedSQLiteChatStore caches only path, RLock and revocation/failure state, never a native connection. Allowlisted materializing APIs open native SQLiteChatStore on the calling thread and close it in finally on that same thread. The original schema, WAL, busy_timeout, foreign keys, transactions, backup and restore remain owned by aion_chat/store.py, which is unchanged.
One facade serializes operations with close. close waits for current operation including native cleanup, then revokes future calls; no worker thread/service is started. Independent facades/processes continue to rely on SQLite's existing transactions and busy timeout, not a new distributed lock.
The host caches/reuses the connection-free facade by existing scope/path/credential binding. Identity/tenant/workspace/fingerprint changes revoke the old facade. Logout can safely revoke it from a new script thread. Bad legacy native connections are retained and rejected until owner-thread cleanup; no cross-thread close bypass or silent deletion.
Native database failure is latched on the facade; constraint rejection and SQLITE_BUSY are propagated without being treated as corruption. A close error after commit raises StorageUnavailableError, not success, and latches failure. This does not undo a successful commit or reconcile an uncertain outcome.
The staging backup helper recognizes the explicit new adapter in addition to native SQLiteChatStore; snapshot verification is unchanged. No generic duck-typed authority is added.

## Tests
16 new offline unittest methods use real SQLite files, bounded ThreadPoolExecutor threads, real concurrent transactions and a fresh Python process. Coverage: native affinity, host rerun in another thread, same-thread connection close tracking including exception, identity/tenant/workspace/fingerprint rotation, logout/relogin, tenant isolation, twelve messages through one facade, eight messages through independent facades, actual SQL trigger rejection/rollback, injected read/database fault with failure latch, injected post-commit close fault, verified backup/restore and quick_check, fresh-process recovery, safe refusal/migration of legacy foreign connection, close waiting for an in-flight read, corrupt file rejection.
Local Windows: 36 tests passed (16 new + existing staging host and runtime resilience), 3.400s on the recorded run. No owner installation, secrets or live provider used. CI matrix prepared for ubuntu/windows, Python 3.12, permissions contents:read, exact PR HEAD checkout, no retained credentials, socket network calls denied during tests. requests installation is CI-only to support an existing host guard test; no dependencies installed on owner's machine.
Publication/CI results must be recorded on the actual PR; this local result alone does not certify Linux or a production host.

## Residual risks / limits
- Per-operation open/startup integrity checks cost more than a cached native connection; there is no performance SLO claim. Local staging workload only.
- RLock is per facade. It does not make a multi-call logical turn transactional across messages, nor serialize different processes. Existing partial-persistence and reconciliation contracts still apply.
- Post-commit close error can leave a committed message. It is an error requiring readback/reconciliation, not an invitation to replay. The failed facade blocks subsequent operations; this in-memory latch is not a durable cross-process UNKNOWN_OUTCOME admission ledger.
- Failure latch is explicit and conservative. Recovery requires verified repair and a new authorized host lifecycle; implicit reopen never clears a failed facade.
- Scope/authentication remain provided and checked by the host/product boundaries. Direct raw store access is not a newly authorized action. Revocation does not cancel an already running SQLite transaction; close waits for its result and cleanup.
- A live legacy connection cached before this patch may require owner-thread cleanup or an approved process restart. The patch fails closed rather than touching security controls or abandoning the holder.
- Full Chromium/Streamlit integration and production durability/physical-host assurance are not certified by these tests. The #1193 history/UI changes remain a sibling branch, not assumed integrated.

## Review acceptance
Dedicated exact-HEAD Windows/Linux suite must pass. Verify diff contains only adapter, host lifecycle, explicit backup compatibility, new tests, dedicated CI, the mandatory quality test registration and this report. Core V1 and #1191–#1193 unchanged. No production flag, provider, Worker, trading, payment, deployment or installation authorization. Review overhead and legacy migration fail-stop before approving any integration. No merge authorized.

CI follow-up: the initial HEAD passed 36 lifecycle tests on each OS, but broad gates exposed an unpinned CI dependency and missing registration of the new root test in quality-tests.yml. The workflow now uses the repository's exact requests version and action SHAs; the new test is added to the mandatory inventory. Existing tests and assertions were not weakened. Final exact-HEAD results are recorded in the PR description.
