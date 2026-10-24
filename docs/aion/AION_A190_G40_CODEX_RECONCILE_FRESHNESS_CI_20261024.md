# AtlasQuant / AION — G40 scoped reconciliation and freshness LAB + parallel Codex review

**Date:** 2026-10-24. Branch `lab/aion-a190-g40-reconcile-fresh-clock-contract-20261024` stacked on G39 Draft #1526; G40 Draft #1527. No main merge, no deploy, provider, Worker, secrets, customers or spending.

## Actual independent Codex execution

Read-only Codex CLI v0.163.0-alpha.11.2, model `gpt-6.1-sol`, completed in 91.78s, exit code 0, session `01a16fa3-38d5-7513-93fe-b301c10273c9`. Authorized desktop `am12`; checkout `C:\Users\apare\AtlasQuant-G18-Windows-LAB-20261024` (older **G18**, not G39/G40). Codex read code and proposed contracts only; it did **not** edit files, run tests, call providers, execute Worker or deploy. Its line numbers are specific to G18.

Eight independent findings/proposals:
1. Require purpose-scoped `RECONCILE_LOOKUP` permission before adapter property lookup; SEND permission is insufficient.
2. Denying reconciliation must never rewrite `SENT/UNCERTAIN`, release retries, or hide old effects; expired SEND authorization is not itself a denial of legitimate reconciliation.
3. Old caller-supplied `now` is not fresh time. Recheck UTC/monotonic timing after callbacks and immediately before any send. An in-process fake clock remains untrusted.
4. Check claim lease/owner/generation and protect post-callback state using conditional updates. True fencing requires new persistently monotonic generation.
5. Callback/getter may update SQLite behind the verifier; test reentrant state changes and avoid rewriting later `CONFIRMED` with older status.
6. Derive commercial event IDs from authenticated source claims, not caller strings or caller-picked Ed25519 pins.
7. Define trusted source namespace and tenant/owner/workspace semantics; current local SQLite cannot dedup across different DB hosts.
8. Keep business-event identity independent of redacted payload fingerprint and version any migration. A signature proves key control and data binding, not commercial event existence.

These are proposals, **not certified fixes**.

## Current G40 code candidate

- Optional `strict_reconciliation_auth_lab=True`: `_reconciliation_authority_lab` requires `allowed=True`, `purpose='RECONCILE_LOOKUP'`, exact strings `actor_id,tenant_id,workspace_id`, with fail-closed callback/mutation behavior; **before getattr(adapter, 'reconcile')**. Denial returns `RECONCILE_AUTH_DENIED_NO_LOOKUP` retaining previous Outbox record unchanged; it does not call `_set_blocked`. Historical SEND expiry does not prohibit a separately scoped LOOKUP.
- Optional `fresh_dispatch_clock_lab=callable`: after state changes to `UNCERTAIN` for first-attempt reservation and a synthetic witness returns true, recheck a fresh UTC sample, expiry, lease, worker ownership and state **before** adapter getter; per Codex additional concern, **recheck a second time after the `adapter.send` property getter, before the callable**. On clock rollback, expired authority, expired lease or claim mutation, retain `UNCERTAIN`, drop lease and refuse adapter SEND. No external first-send effects in default config.
- Synthetic adapters/test verifiers are explicitly opted in to reproduce counterexamples. Neither callback nor clock nor a locally signed event constitutes a trustworthy independent root. A fake clock can authorize a synthetic stub despite real-time expiry; that remains an intentional RED.
- No changes to legacy defaults, no operational integration or trusted provider. An adversarial host can still replace code, files, keys, clock or identifiers; the interval between the second freshness check and an eventual external send remains unclosed.

## CI runs and status

Initial focused CI [#40131071775](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40131071775) **SUCCESS** at first tested code SHA `7eeac24efeabcb2930d9efd96caf63b569b769ca`: Ubuntu **259/259** and Windows **259/259** (34 new G40 + 225 inherited G30–G39 tests on each OS).

Codex feedback prompted second adapter-property freshness check and two new adversarial tests:
- `G40_GETTER_DELAY_GREEN=EXPIRED_AFTER_PROPERTY_NO_SEND`
- `G40_GETTER_REENTRY_GREEN=CLAIM_CHANGED_AFTER_PROPERTY_NO_SEND`

Second/latest focused CI [#40131245219](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40131245219) at exact code/workflow SHA `afb2d51d68efb18e4a12d0c470cd7f5a69babce3`: **36 G40 + 225 inherited = 261 distinct tests per OS (522 executions)**. Its final status must be checked before claiming second version passes. This document is a follow-up commit and is not included in that tested SHA.

## Remaining independent hard gates

G39 semantic reservation still opt-in and caller-controlled ID, not authenticated origin. The new reconciling permission and clock are also opt-in LAB checks, not independent identity, unforgeable receipts, signed provider results, global monotonic antirollback or physical time. There is no new `fencing_generation`, true end-to-end atomic external first-send, safe schema migration/backfill, complete hostile-host replay qualification or operational go-ahead.

A184 canonical security/Quality and dependency audit remain separate. Most recently verified security scan reported 48 known vulnerabilities in `pypdf 6.19.0` and `Pillow 12.3.0`; G40 test success cannot waive this.

**0/6 P0 homologados — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.** No Worker, provider, main, merge, deploy, real keys, customer data or new spend.
