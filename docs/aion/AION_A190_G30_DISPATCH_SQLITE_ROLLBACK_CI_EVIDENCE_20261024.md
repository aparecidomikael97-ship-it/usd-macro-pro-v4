# AION A190 G30 — Real dispatch deny gates and SQLite rollback fault evidence

Date: 2026-10-24. Exact tested code SHA: `e663da11353c407ea8de1021097a908961f9f82f`.

## CI evidence
- [GitHub Actions #40123109704](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40123109704): **completed SUCCESS**.
- Ubuntu job `120958737556`: **23/23**.
- Windows job `120958737740`: **23/23**.
- **46 executions** of **23 distinct tests** in three suites:
  - `labs/a190/test_g30_real_dispatch_gates_lab.py` (15 tests).
  - `labs/a190/test_g30_budget_gates_lab.py` (6 tests).
  - `labs/a190/test_g30_sqlite_rollback_fault_lab.py` (2 tests).

## Actual tested boundaries
Real `ExecutionOutbox` / `SQLiteChatStore` use synthetic staging data and deliberate trap adapter properties. No real send, provider, Worker, callback trust, effect or external receipts.

**GREEN**
- Current policy-version or authorization-reference mismatch prevents adapter lookup: `G30_POLICY_GATE_GREEN=NO_ADAPTER`; `G30_AUTH_GATE_GREEN=NO_ADAPTER`.
- A stale policy from a G29-style `IDEMPOTENT` replay is blocked when the dispatch authorization callback reports the new policy: `G30_REPLAY_DISPATCH_GREEN=STALE_POLICY_BLOCKED`. Does not eliminate inconsistent staging metadata or independently prove callback trust.
- Wrong actor, tenant, workspace, denied/revoked authority, missing/wrong reauth, expired authority, callback failure, mismatched Worker, expired lease and budget-gate errors stop dispatch in tested cases.
- A correct authority and budget without a trusted external first-attempt witness goes to `UNCERTAIN` with **zero adapter lookup**: `G30_NO_WITNESS_GREEN=UNCERTAIN_ZERO_SEND`, `G30_BUDGET_WITNESS_GREEN=NO_SEND`.
- An UNCERTAIN row was not automatically re-claimed; default reconciliation does not access an untrusted adapter.

**RED**
- `G30_SQLITE_ROLLBACK_MASK_RED=ORIGINAL_FAILURE_OBSCURED_TRANSACTION_OPEN`: inject a write exception through a proxy around the *real SQLite connection* during `ExecutionOutbox.enqueue`. If proxy `rollback()` then also fails, its `OSError` masks the original `RuntimeError` and the underlying SQLite transaction remains open. This is a deterministic exception path, **not** evidence of native SQLite rollback failure under a real disk fault.
- Control: when rollback succeeds, original exception remains visible and transaction ends.
- Lab cleanup rolls the real connection back explicitly; no residual transactions shipped.

## Open engineering work
- Guard against rollback exceptions masking primary error; quarantine/close or rebuild a connection after uncertain transaction outcomes and require healthy-store revalidation.
- Build explicit staging conflict/reapproval semantics for G29 changed metadata. Independently prove trusted authority and semantic identity rather than relying on callbacks controlled by the host.
- Independently durable atomic first-attempt reservations and provider receipts remain absent; no automatic resend even if staging is correct.
- Canonical Quality/Security not rerun. No merging, production changes, external providers, Worker, real secrets, customers or budget increase.

**0/6 P0 homologados | HARD NO-GO | UNCERTAIN | ZERO_AUTO_RESEND.**
