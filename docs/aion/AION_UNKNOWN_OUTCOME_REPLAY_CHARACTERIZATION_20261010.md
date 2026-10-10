# AION — Adversarial unknown-outcome / request replay characterization, 2026-10-10

**NOT A FIX. NOT A SAFETY OR INSTALLATION CERTIFICATE.**

This branch starts at integrated Draft #1196 HEAD `6088380f043ef546b0eb74d69c79b6f5d89d778f`. It changes only offline test/diagnostic workflow and this report. No Core V1, main, #1192–#1196 or product code modified.

## Why it matters
- `submit_product_turn` checks `request_id` in a Streamlit session-local set. This is not a durable scoped request ledger and does not reach the stable `turn_id`.
- The underlying `persist_verified_read_result` does **properly** deduplicate by derived `turn_id`. That ID includes the current index and changes when a previously committed request is replayed after loss of session state.
- The operation-scoped facade from #1195 intentionally surfaces `CONNECTION_CLOSE_FAILED` after a real commit. This is an **uncertain outcome** that must never be assumed uncommitted.
- The product submit/continuation path is currently unable to correlate the prior browser request with its committed pair after lost session state. Its exception handling does not specifically convert `StorageUnavailableError` into durable reconciliation.

## Tests deliberately demonstrate the unsafe current behavior

1. Same authorized owner, tenant, workspace, conversation, browser `request_id`, and payload, **new Streamlit session**: existing request is executed again, two additional messages are appended (2→4). New stable IDs differ despite identical logical browser request.
2. Inject a failure *only after* the real assistant message was committed, as native SQLite is closed on the calling thread: original submit raises `StorageUnavailableError`, session has no request acknowledgment, independent readback finds two committed messages. Replaying the same browser `request_id` from a recovered session creates two more messages (2→4).

These tests perform only local SQLite file I/O, synthetic credentials, existing local READ/SEARCH, and temporary directories. Socket connects are blocked. No real provider, production data, Worker or external side effects.

**IMPORTANT: Green test workflow means the vulnerability was reproduced, NOT that the system satisfies desired replay invariants.** It must never be wired to release/readiness as a positive proof of safety. Codex should convert these diagnostics into negative regression tests, requiring 2 messages and no duplicate after stable binding + readback correction.

## Required future fix / NO-GO
- Bind `request_id` durably to owner/tenant/workspace/credential, conversation, full canonical payload digest and a stable operation/turn ID **before execution** in the existing scoped SQLite store. Validate id conflict and isolate tenants.
- Durable `PREPARED/IN_PROGRESS/UNCERTAIN/RECOVERED` status must be fail-closed, not an approval or execution receipt; never invent success. Unknown state blocks silent resend/replay until independent readback.
- Read back by scope+operation ID and verify both persisted messages/content/roles before reporting terminal persistence; partial/unavailable remains UNKNOWN.
- Preserve #1193 truthful historic result presentation as `UNKNOWN`; do not promote message truth from receipt claims.
- Preserve #1195 native thread affinity and real close error reporting; do not blindly integrate external action outbox into chat.
- Await Codex isolated minimum correction with real Win/Linux tests. No merge/deploy/Worker/installer/TPM/witness or paid provider.

**First installation remains HARD NO-GO.**
