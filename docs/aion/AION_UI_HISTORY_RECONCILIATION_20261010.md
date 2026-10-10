# AION UI / historical truth reconciliation — Draft candidate 2026-10-10

## Scope and provenance
- Read-only baseline: main `5744b2b7b17c84331e6f27c569064993ff587782`.
- #1192 original HEAD `b7dac475c09ab29f741d2237b164d72d7923d421`: previous-turn `WAITING_APPROVAL`/`BLOCKED` notices, approval proof text, CSS, and real Chromium UI tests.
- #1193 validated HEAD `9086025bba2f05567a562acd0c71ecb0dbbb0019`: scoped historical `UNKNOWN`, receipt `DECLARED_UNVERIFIED`, SQLite QA thread-lifecycle fix, Windows/Linux browser tests, main Quality gate green.
- Integration branch starts at **#1193's exact validated HEAD**, imports #1192's web/CI/test changes, and combines the two narrowly overlapping strings in the same UI JS.
- Both source PRs and Core V1 stay untouched. No merge, deploy, Worker, external data, enrollment or first install.

## Distinct, compatible semantics

**Historical turns (staged product mode):** `UNKNOWN` means the stored assistant result is not independently reverified. Header is `AION · histórico local`. The turn shows `Não reverificado · UNKNOWN`, and Proof Mode distinguishes `LOCAL_PRESENT` from declared receipts and authentic success. No approval notice or composer lock may be emitted for a historical `UNKNOWN` turn.

**Previous-turn approval or block (UI demo mode):** the most recent `WAITING_APPROVAL` turn displays a contextual message only when approval is required and not granted. `BLOCKED` displays a different message. These notices never authorize or prevent a subsequent chat turn. Positive approval metadata alone cannot be shown as verified granted authority.

## Acceptance tests on *this* integration HEAD

- Run the existing #1192 workflow on Windows/Linux with real Playwright Chromium at desktop and mobile widths. Preserve existing navigation, focus, and Proof Mode assertions. Previous #1192 Linux run `38083011027` had an unresolved roles→chat navigation regression, and cannot be considered green based on #1193's independent success.
- Run the existing #1193 workflow on Windows/Linux, with real SQLite staged chat, Chromium, remount and navigation. On this combined branch, assert historical `UNKNOWN` produces **no** approval notice and composer stays enabled.
- Require the global Quality suite plus core security/certification workflows to pass at **this** exact HEAD.
- Investigate and document any failure before signoff. Do not weaken requirements or conflate earlier CI results with current.
- Do not misstate the QA-only SQLite thread lifecycle repair as production hardening. Codex audits the real host independently.

## Gate
**INTEGRATION CANDIDATE ONLY** until exact-HEAD test results are independently checked. Original PRs #1192 and #1193 remain Draft and unmerged; this combined Draft is a comparison/review vehicle, not permission to merge either.
