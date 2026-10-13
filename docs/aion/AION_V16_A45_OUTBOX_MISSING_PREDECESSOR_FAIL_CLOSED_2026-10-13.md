# AION V16-A.45 — deleted Outbox predecessor must never release aggregate FIFO (LAB / NO-GO)

**Exact parent:** A.44 Draft PR #1257, tested HEAD `bb8fc0a72e63327e4950af7885b1aa064e318fa8`. This A.45 Draft is an isolated child branch. The Core V1 frozen tree, main, AM12, external providers and first installation are **untouched**.

## Source-level vulnerability in A.44

The `ExecutionOutbox.claim_next` anti-overtake subquery located earlier same-aggregate intents with an **INNER JOIN** from `action_decisions earlier` to `action_outbox eo`. Its A.44 fix refused *all* surviving earlier Outbox terminal labels, which is necessary but insufficient: directly **deleting the predecessor `action_outbox` row** could remove its decision from the join, letting the next `PENDING` row be locally claimed as if no earlier intent existed. Deleting both preceding local rows created the same gap. This is claim/staging, **not external sending**, which the A.31/A.33 producer gates already forbid.

## Scoped fix

Since there is no independently enrolled producer COMMITTED_EFFECT / terminal NO_EFFECT_FENCED receipt to advance an aggregate, **only `d.aggregate_seq = 1`** may be claimed in the current staging-only Outbox. This rejects later locally persisted sequence numbers even if their earlier Outbox row and decision record are missing, including after a process-style restart. An unrelated aggregate or a different tenant retains its own first claim opportunity. No adapter access, effect ledger insertion, remote call, owner proof, retry permission or terminal release is granted.

This is deliberately stronger than a correlated `NOT EXISTS` over mutable predecessors and is temporary fail-closed behavior pending a fully authenticated future release policy. It may hold subsequent local intents even if a previous local action was legitimately canceled or blocked; that operational liveness trade-off is intentional while proof is absent.

## Real SQLite adversarial tests

Five new tests demonstrate (1) missing preceding Outbox row with decision surviving; (2) deletion of both preceding Outbox and decision rows while later sequence stays 2; (3) gap persists after SQLite reopen; (4) independent aggregate remains claimable; (5) same aggregate key in another tenant remains independently claimable. All assert no effect ledger addition, no attempts by the blocked later intent. Tests are included in root Quality **and** a dedicated required Security Gate step. Every previous 23 Outbox + 8 real Saga historic red test remains present and unwaived.

## Honest security limitations

The ordinal is **also local SQLite data**. A privileged local writer that can rewrite `aggregate_seq`, substitute `action_decisions`, alter local code, restore a coherent old DB, or control the runtime is not stopped by this test. This is **not independent latest-head antirollback** or a signed external producer/owner receipt, and does not certify producer identity, idempotency, terminal late-effect fencing, hardware identity or positive Saga liveness. A future independently custodied witness and producer-enforced proofs are essential. Existing 45 original A12/A16 ZIP tests remain unrecovered/unexecuted.

**0/6 P0 homologated; 20/20 first-install HARD NO-GO**. No main merge, deploy, Worker, Render, credential, key, producer, network send, test on AM12, spending, or execution.
