# AtlasQuant / AION — G41 persistent local claim-generation fencing LAB evidence

**Date:** 2026-10-24. **Code/workflow SHA submitted for final G41 CI:** `78e2b9c5f802cfe13eaec09cc7663d36ea1465ab`. Branch `lab/aion-a190-g41-claim-generation-fencing-20261024` stacked on G40 Draft #1527. G41 Draft PR #1528. **LAB candidate, no operational deployment.**

## Parallel Codex audit — actual scope

Codex CLI v0.163.0-alpha.11.2 / model `gpt-6.1-sol` ran with **read-only sandbox** on the connected authorized Windows device `am12` against `C:\Users\apare\AtlasQuant-G18-Windows-LAB-20261024`. Session `01a16fb2-c52b-76a2-9edf-5810a8e89cd6`; **exit 0 after 135.29 seconds**. It **did not edit/run tests, dispatch Worker, access a provider, merge, deploy or read real credentials**. Its file lines refer to **older G18 code, not current G40/G41 GitHub head**. The G41 GitHub CI separately validates our branch; Codex did not independently review that current diff.

Salient Codex recommendations: a durable incrementing claim generation and conditional SQL on each ownership/state change; reject stale callbacks, reused worker IDs, lease change, and reentrant state updates; never overwrite `CONFIRMED` or its effect ledger with delayed `SENT`/`REVOKED`; true fencing must span send boundary and rely on independent antirollback custody. Versioned migration must refuse old writers; adding `triggers` is not free because historical SQLite restore checks reject them. There is no proof of physical machine rollback or external provider from Codex static review.

## G41 candidate implementation — bounded local protection

- **Opt-in** `ExecutionOutbox(..., strict_claim_fencing_lab=True)` enforces a required `dispatch_claimed(..., claim_generation_lab=N)` positive integer equal to the persisted `action_outbox.attempts`, which increments atomically upon `claim_next`. No new production schema or destructive migration required for this LAB. This column is repurposed as a **local** epoch, not independent global high-water.
- The candidate validates state+owner+epoch before and after authorization, before first-witness reservation, after witness, after synthetic adapter getter, and when consuming the result. First-attempt reservation SQL compares current generation and lease owner.
- When strict flag enabled, authority denial uses scoped conditional update from the same `CLAIMED`/generation; callback reentry to `CONFIRMED` does not rewrite it to `REVOKED`. Initial first-witness denial refuses to clear newer state. The synthetic `SENT`, callback rejection/error and local `_confirm` branches employ scoped conditional writes. `_confirm` inserts a local effect ledger entry and updates Outbox state within the SAME SQLite transaction; when fenced state CAS loses, the transaction rolls back its inserted ledger.
- **LAB constraints**: non-strict legacy callers stay unchanged and can bypass the new protection; `attempts` can be copied/rolled back with SQLite; no independent authentic first-send witness, provider-side guarantee, real receipt or remote lock. In-process synthetic callback and clock are controllable by host.

## New adversarial tests

`labs/a190/test_g41_persisted_claim_epoch_lab.py`, **18 test cases**:
- Persists claim attempts, repeat/replay, same-worker expiration and reacquisition with incremented epoch, reopen and old-holder refusal.
- No-generation/wrong-generation denial before user callback or adapter.
- Authority callback, witness callback, getter and send callback reentry; terminal `CONFIRMED` not overwritten with older denial/send/error, effect ledger kept.
- Synthetic only `SENT` is a local stub result, never a genuine provider effect.
- **RED**: `G41_SAME_HOST_ROLLBACK_RED=OLD_GENERATION_RESTORED_WITH_SQLITE`. A controlled copy of an earlier SQLite file restores its old generation when the database is replaced; no host-rollback guarantee.
- Default witness still leaves `UNCERTAIN` unreclaimed; no automatic resend.

## CI and corrections

The first [G41 run #40132512245](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40132512245) failed BEFORE tests due a missing `}` syntax error on a new return expression. The next [run #40132594379](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40132594379) caught another new unclosed return dictionary. Neither counted as pass. A third [run #40132654109](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40132654109) executed the 18 cases and failed 5 reentrancy tests: a local CAS opt-out flag used reversed SQL predicate `?=0` instead of `?=1`, which prevented intended legacy confirmations. Fixed the six predicates and reran.

[**G41 latest focused CI #40132740575**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40132740575) at **code/workflow SHA `78e2b9c5f802cfe13eaec09cc7663d36ea1465ab`**: new 18 + inherited G40 36, G39 28, G38 24, G37 34, G36 20, G35 18, G34 16, G33 24, G32 20, G31 18, G30 23 = **279 distinct tests per OS**. **FINAL G41 focused CI SUCCESS:** Ubuntu job `120987739164` **279/279**; Windows job `120987739393` **279/279**. Total **558 executions of 279 distinct tests** at the exact tested code/workflow SHA. All mandatory positive and intentional-RED markers passed. Following documents-only commits are not the validated code SHA.

## Open P0 and security obligations

- Local attempt epoch protects only against stale holders over **unchanged** durable local history. It is **not independently monotonic**, cannot defeat SQLite+binary co-rollback and does not solve first-send exactly-once across providers.
- No authenticated semantic source event/real HUMAN_OWNER binding, provider-signed receipts, independently provisioned monotonic custodian, H0 adverse restart proof, or qualified native SQLite cross-platform operational readiness.
- Real external effect still requires independent provider reconciliation; default witness = DENY. No automatic requeue of `UNCERTAIN`.
- **Same-code SHA broad CI: 14/15 workflows SUCCESS**, but [A184 #40132740514](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40132740514) **FAILURE/RED**. Candidate Quality job `120987739233` **SUCCESS: 6,449 tests**; BASE Quality job `120987739331`: 6,322 tests, **4 historical failures**. Candidate security-unittest and security-pytest passed; candidate dependency audit job `120987739404` **FAILED** with 48 known vulnerabilities across `pypdf 6.19.0` and `Pillow 12.3.0`; BASE audit also failed. External P0 trust prerequisites remain absent, no global homologation.

**0/6 P0 homologados. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND. No main/merge/deploy, Worker, provider, customer data/secrets or spend.**
