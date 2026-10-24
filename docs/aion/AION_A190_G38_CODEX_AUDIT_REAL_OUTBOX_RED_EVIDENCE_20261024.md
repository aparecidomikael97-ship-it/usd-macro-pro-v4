# A190 G38 — Codex read-only audit and real Outbox RED evidence

**Date:** 2026-10-24. **LAB Draft**, stacked on G37 #1524. Initial tested code SHA `78cd59c68ee478b376a13593502adb63e54da0d1`. No merge/deploy, live customer/provider or Worker.

## Parallel Codex audit actually executed

Codex CLI `v0.163.0-alpha.11.2`, model `gpt-6.1-sol`, ran in **read-only sandbox** on connected Windows machine `am12`; cwd `C:\Users\apare\AtlasQuant-G18-Windows-LAB-20261024`, task session `01a16f88-0ae0-7bf1-8a54-3c6be8701f7e`, **process exit code 0** after 122.71 seconds. It **read code and tests only**; did not execute tests, modify files, send, call provider, merge, deploy or query network. Its line numbers refer to **older G18 checkout**, not G37 HEAD; no claim of G37 source verification by Codex.

Eight static candidate observations:
1. **P0:** `intent_ref` controls local idempotency; two caller request aliases for a single obligation create distinct rows.
2. **P0:** valid signatures authenticate claims and signer key, not real commercial event truth; issuer may sign fabricated events.
3. **P0:** self-chosen pin and same-host signer/witness DB do not resist host administrator rollback.
4. **P0:** G13 signed semantic digest and local Outbox scope keys have differing owner/workspace boundaries; same event may be staged in two workspaces.
5. **P1:** redaction before authoritative projection may collapse two raw credential-bearing payloads; this is *projection loss*, not SHA-256 collision.
6. **P1:** authorization callback can omit tenant/workspace without gate rejecting, and cumulative budget guard is conditional on an explicitly budget-bound decision.
7. **P1:** dispatch checks an injected time value once before callbacks; LAB-only synthetic callback path may reach a stub after validity in real time.
8. **P1:** reconciliation takes an `authorize` parameter but does not call it in its body. Production default still rejects external reconciliation; explicit unsafe LAB callbacks demonstrate the interface gap but not a real provider effect.

## G38 actual-code reproduction in synthetic LAB

Created `labs/a190/test_g38_codex_semantic_scope_red_lab.py` (12 cases) and `labs/a190/test_g38_codex_auth_reconcile_red_lab.py` (12 cases) on current G37 stack; run with real `SQLiteChatStore` and real `ExecutionOutbox`, synthetic actors, local SQLite and adapter stubs only. Key RED markers:
- `G38_REQUEST_ALIAS_RED` — same business event staged twice using distinct request IDs.
- `G38_WORKSPACE_ALIAS_RED` and `G38_SCOPE_MISMATCH_RED` — G13 digest shared across two scoped Outbox keys.
- `G38_REDACTED_DIGEST_RED` — different raw sensitive fields collapse under redacted projected identity.
- `G38_AUTH_SCOPE_OMISSION_RED` — missing tenant/workspace callback fields do not cause rejection; **default first-send witness still blocks SEND**.
- `G38_BUDGET_OPTIONAL_RED` — no cumulative guard without budget reference, **but still no SEND in production default**.
- `G38_RECONCILE_AUTH_UNUSED_RED` — with explicit unsafe synthetic LAB switch, reconciliation reads stub even when auth callback would deny.
- `G38_SYNTHETIC_RECONCILE_RED` — a locally injected true-returning synthetic evidence verifier can confirm a locally fabricated result without consulting `authorize`. This is not authenticated provider receipt or deployed behavior.
- `G38_STALE_CLOCK_RED` — explicitly unsafe test-only first-attempt callback plus artificially old `now` argument allows only a **synthetic stub send**; no real provider.
- Positive controls: modified non-redacted business amount denies same request id; explicit wrong tenant/workspace rejected; budget-bound decisions require a guard; default witness disallows provider access; synthetic absence indication never becomes auto-retry.

## CI and disposition

[**G38 run #40128960373**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40128960373): **completed SUCCESS on Ubuntu and Windows**. New 24 tests + inherited G37–G30 173 tests = **197/197 each OS; 394 executions of 197 distinct tests**. Ubuntu job `120976361104`; Windows job `120976360963`. Exact tested SHA remains `78cd59c68ee478b376a13593502adb63e54da0d1`; documentation was committed afterward and is not part of the tested code SHA.

This is diagnostic RED coverage, NOT a remediation. **0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.** Keep G37 same-host issuer/custody rollback, A184 and independent receipt/identity gaps open. No main/merge/deploy/Worker/provider/customer secrets/spend.
