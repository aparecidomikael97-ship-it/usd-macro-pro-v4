# AION #1198 — Full UI + Quality integration validation

**Purpose: validation only; not a fix or permission to merge/install.**

## Baseline and isolation

- Branch created from exact Codex #1198 HEAD `d0f368a3c5d9fbf678e8cc36c5b0e463bb0ac06a`.
- Parent stack: #1196 `6088380f043ef546b0eb74d69c79b6f5d89d778f` with #1192 turn notices, #1193 historical UNKNOWN, #1195 operation-scoped SQLite host, Codex #1198 durable request-id binding.
- A separate Draft PR targets `main` **solely to trigger existing full Quality, browser UI and Core safety workflows**, which are generally scoped to pull requests against main.
- Core V1, main, #1191–#1198 branches and all runtime/production controls remain untouched.
- No changes to product code. The only additional test changes are in `test_atlasquant_aion_chat_product_ui_browser_staged.py`.

## New real-browser acceptance regression

`test_browser_duplicate_request_after_store_remount_stays_two` drives a real Chromium page and staged Streamlit host backed by temporary SQLite:

1. Submit `status geral` with a QA-fixed `request_id` (the browser's original UUID generator is restored immediately after submission).
2. Wait for exactly one user/assistant pair and the truthful `UNKNOWN` historical assistant state.
3. Click the existing QA button to remount the SQLite host; keep the same explicitly bound conversation.
4. Resend **the identical** `request_id` and payload through the real JS composer (the test patches the UUID generator only for the two submission events).
5. Require the local reconciliation notice, normal enabled composer, no Streamlit exception, **still exactly 2 chat messages** and 1 historical `UNKNOWN` assistant.
6. Independently open the QA SQLite database read-only for verification: one scoped request-binding row points to the expected conversation and only two message rows exist. No remote/persistent receipt, external provider or answer truth is thereby proven.

This test does not simulate a distinct browser session with automatic conversation recovery, an involuntary crash mid-frame or a live production identity. Those remain separate validation gates; Codex #1198's dedicated SQLite tests cover the lost session/postcommit fault independently.

## Full CI acceptance on the new combined exact HEAD

- Existing AION History Truth Regression Windows/Linux (including new browser test).
- Existing AION UI Turn Notice Windows/Linux Chromium.
- Existing AION SQLite lifecycle Windows/Linux.
- Existing AION Browser Request Reconciliation Windows/Linux.
- Main-targeted Quality suite with real browser tests, and core security, certification and release-readiness workflows.
- Check every workflow result and logs **for this PR's exact HEAD** before review.
- Any failure remains a hard blocker; do not drop or weaken assertions to obtain green.

## Non-goals and stop conditions

This comparison PR is **Draft only**. Its underlying #1198 is also Draft. No merge, deploy, Worker/Render, production persistence, use of owner identity/credentials or physical installation is authorized. Local SQLite readback is not an antirollback/witness certificate. Partial requests and legacy history remain BLOCKED without sufficient evidence.

**First installation HARD NO-GO.**
