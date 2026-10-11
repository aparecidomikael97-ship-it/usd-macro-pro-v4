# AION P0 — Handoff identifier/data boundary hardening (2026-10-10)

**Status:** reviewable isolated code candidate, not enrollment/synchronization, not installer-ready.

## Exact history

- Base: Draft #1201 `5e69a31ce8e1bb1a4c58917d801947833271672e` (13/13 CI successes).
- Frozen `main`: `5744b2b7b17c84331e6f27c569064993ff587782`.
- Existing staged SQLite, tested Chromium chat and HTTP/Worker/source interfaces untouched; core V1 frozen.
- Separate source/witness security chain #1191 remains **Draft/unmerged** with intentionally BLOCKED operational source readiness; no real owner enrollment.

## Audited remaining boundary

#1201 correctly removed arbitrary `context` fields, but `continuity_handoff` still passed `owner_subject`, `conversation_id`, `last_turn_id` through generic `_clean(value)`. That path coerced arbitrary objects into strings and copied freeform text into a purportedly secret-free cross-device handoff, e.g. `last_turn_id='Bearer synthetic-secret'`; it also emitted `state=HANDOFF_READY` plus a SHA-256 digest without verifying the source owner or target device/tenant. No actual cross-device network delivery currently exists, so this is a **contract privacy/trust confusion risk**, not evidence of exfiltrated customer data.

## Minimal independent fix

- Owner reference: login username grammar `[a-z0-9][a-z0-9._-]{2,63}`, matching existing normalized access usernames.
- Conversation reference: the actual chat-store 32-character lowercase uuid4 hex **or** generated surface `AION-CONV-` + 24 uppercase hex.
- Optional turn reference: empty, real message uuid4 hex, or `AION-TURN-` + 24 uppercase hex.
- Input must be a literal string of the correct shape; no coercion, HTML/JSON/URL, truncation or arbitrary nested/secret text in these fields. Source/target devices must be literal enum strings.
- Response explicitly says `HANDOFF_PREPARED_UNVERIFIED`, plus false fields for source owner verification, target owner verification, target-device authentication, tenant membership, authorization grant and permission to resume. Digest explicitly not a signature.
- Source #1015 and #1201 tests adjusted to real identifier formats; new negative cases cover alternative secret-bearing fields, objects, CRLF/header injection, excessive length and malformed deterministic IDs. Positive tests use chat `Conversation` and `Message` actual uuid4 IDs plus surface IDs.

**Explicit limitation:** a correctly formatted conversation/turn ID is only a reference — not proof of ownership, unforgeability or absence of secrets. `HANDOFF_PREPARED_UNVERIFIED` is **not** transfer-ready or execution authority. The future target MUST reauthenticate the user/device and check independent tenant/workspace membership before consulting the scoped durable store; this PR does not implement a receiver, remote transport, real trust provider, hotword/desktop actions or bypass.

## CI acceptability

- Original Owner Experience contract suite and new Windows/Linux cross-stack negative tests on exact source head;
- Previously green browser history/SQLite, turn notice, global Quality, Core Security/Certification/Release Readiness must continue to pass on combined head;
- Any failure blocks the candidate. Never recode a failing test to report `READY` or alter the witness manifest `20/20 BLOCKED`.

No merge, deploy, Worker, physical Windows installation, real credential enrollment, sandbox exceptions, paid service or production data. **FIRST INSTALL HARD NO-GO.**
