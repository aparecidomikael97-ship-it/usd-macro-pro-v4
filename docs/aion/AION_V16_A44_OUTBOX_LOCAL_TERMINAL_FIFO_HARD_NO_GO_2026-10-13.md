# AION V16-A.44 — Outbox local terminal state must not release same-aggregate work

**Parent:** A.43 Draft #1256 at `ada3f34874348522d3ea16bcf61219226c6f7300`. This is an isolated Draft laboratory change only. The Core V1 frozen tree, main, AM12 host and production integrations are unchanged.

## Verified source-level gap

Before this change, `ExecutionOutbox.claim_next()` considered any preceding same-aggregate Outbox row in `CONFIRMED`, `FAILED`, `REVOKED` or `BLOCKED_REAPPROVAL` to be terminal. The preceding row and all effect ledger entries reside in locally writable SQLite. At the current AION trust level, none can constitute a separately authenticated producer receipt or producer-enforced terminal no-effect fence. Direct local manipulation of the previous state to `CONFIRMED` or `FAILED` (or of a pre-send denial state) therefore allowed the following Outbox intent to be CLAIMED despite the absence of actual producer proof.

This is an **aggregate ordering/claim staging** flaw; existing `dispatch_claimed` still hard-blocks before examining the adapter's `send` property, and `reconcile` hard-denies before inspecting the adapter. A claim is not proof of a real provider send, and no such send was demonstrated.

## Scoped deny while producer enrollment is absent

`claim_next()` now requires **no previous same-scope, same-aggregate intent** to exist when choosing a `PENDING` or `RETRY` candidate. Local terminal-looking states of any kind cannot grant an exemption. Independent, unrelated aggregates remain eligible for local staging and claim (never sending). The system intentionally prevents *all* subsequent same-aggregate claims until a future separately reviewed design independently verifies either a genuine committed producer effect or an authenticated no-effect fence and grants a precise release.

Why not exempt local `REVOKED` or `BLOCKED_REAPPROVAL`? While produced by local authorization gates before adapter access in ordinary flows, the markers are writable in the same untrusted SQLite failure domain; a direct writer could forge them exactly as `CONFIRMED` and `FAILED`. Conservatively including all four terminal-looking states eliminates this direct FIFO bypass until there is an independently evidenced trust root.

## Evidence added

Five real Outbox SQLite adversarial tests:
1. Manually forge each of the four terminal-looking states; assert next local claim denied, attempts remain 0 and no effect appears.
2. Even forging a matching `action_effects` ledger row together with `CONFIRMED` is not external producer testimony and must not release later claim.
3. A separate aggregate remains claimable; same aggregate blocked.
4. Denial remains after reopening the SQLite database.
5. The first legitimate staged intent remains claimable; second never overtakes it.

Registered both in root Quality suite and as a separately mandatory security workflow step. Do not xfail/skip/remove 23 historical Outbox and 8 historical real Saga errors; those errors arise from absent real producer/source-enrolled positive/liveness semantics, not solved by this patch.

## Limits / no-go

No provider, independent signer, source pin, terminal no-effect guarantee, HUMAN_OWNER host enrollment, independent antirollback current-head witness, deployment or external effect has been demonstrated. Local SQLite cannot authoritatively attest terminal delivery/non-delivery. Future positive admission must guard all release paths with independent producer-origin evidence, per-aggregate causality, antirollback and owner policy. Existing simulator tests must never be promoted into receipt authority.

`20/20` physical first-install gates stay HARD NO-GO; `0/6` P0 homologated. Original 45 A12/A16 ZIP tests remain unrecovered/unexecuted. No merge, deploy, Worker/Render, external send, provider setup, credentials, spending, AM12 operation or key work.
