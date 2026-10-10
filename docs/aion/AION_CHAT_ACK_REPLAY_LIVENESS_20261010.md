# AION staged chat — replay ACK liveness and stale response fence (2026-10-10)

## Scope and immutable source

- Draft comparison branch starts from #1199 exact failing browser-validation HEAD `2627bfc4e60f55f8286581f0fa058c82a300d119`.
- #1199 is itself based on Codex #1198 fixed durable request correlation `d0f368a3c5d9fbf678e8cc36c5b0e463bb0ac06a`, stacked onto #1196 source. Original #1192–#1199, `main`, and frozen Core V1 are unchanged.
- This isolated patch modifies only **UI response correlation** and corresponding tests, **not** durable request IDs, SQLite permissions, external effects, execution/safety policy, witness or production readiness.

## Observed failure before patch

- Real Chromium Windows+Linux on #1199: same `request_id` + same input, staged SQLite remounted between submissions; underlying request remains **2 stored messages** and response notice says `Histórico local reconciliado`.
- The UI fails `expect(.aq-chat-send).to_be_enabled()`: `aion_chat/web/command-chat.js` rejects a *current* response with `data.ack === state.pending` when `data.ack === state.lastAck`, even though a new UI send occurred.
- 155-test focused P0 suite passed independently, so this is an additional **frontend liveness** failure, not proof of persistence duplication.

## Minimal design

The wire event now contains **two separate identifiers**:

- `request_id`: stable browser operation key for #1198's durable SQLite binding/deduplication. It must NOT change on a replay of the same intent.
- `attempt_id`: fresh random UUID for **each client-side send attempt**, no matter if the request ID is reused. It is ephemeral presentation correlation only; it grants zero authority, is not persisted as an action receipt and does not alter the SQLite turn identity.

Staged product and session-only host adapters echo `ack_attempt_id` for a handled request or handled validation error. The component completes the busy submission only when `data.ack === state.pending` **AND** `data.ack_attempt_id === state.pendingAttempt`, not on `lastAck` uniqueness. A stale unsolicited response with an old attempt ID therefore cannot prematurely complete a newer submission, even for the same request ID.

A duplicate session-only request is still never appended twice; it receives a fresh UI attempt acknowledgment with a notice that no new action was executed.

## Strict acceptance on this combined PR HEAD

- Real staged Streamlit+Chromium+SQLite browser regression Windows/Linux from #1199: identical request sent after staged host remount yields `LOCAL_PAIR_RECONCILED`, **2→2** message count, historical assistant state `UNKNOWN`, verified independent local SQLite correlation, normal enabled composer (no 15s timeout).
- Real session-only UI/turn notice/navigation browser Windows/Linux.
- #1198's 155-test dedicated reconciliation suite Windows/Linux, historical truth and SQLite host lifetime suites.
- General Quality and Core safety/certification/release-readiness on exact combined revision. Any CI failure is still a blocker; do not weaken the assertions.
- No unverified `CONFIRMED_SUCCESS`, no auto retry, no external effects, no new approved action or memory promotion.

**Not an install certificate.** Legacy/partial uncertain chat requests, independent antirollback witness/host identity, physical Windows/trust and first install remain **HARD NO-GO**. No merge, deploy, Worker/Render, owner installation, secret enrollment, paid service or persistence activation was authorized.
