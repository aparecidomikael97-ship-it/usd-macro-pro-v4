# AION — Last-turn notice and honest approval display (Issue #1189)

**Status:** proposed integration in an isolated Draft PR; **not released**.

## Audited problem

The JS chat component already renders `WAITING_APPROVAL`, `BLOCKED`, `REJECTED` and a per-card approval notice. Its composer, however, did not explain the distinction between a *blocked/pending earlier turn* and the ability to send a new unrelated message. The prior suggested Claude patch was not runnable: `contractData` / `approvalStatus` are not public fields in this component, and `canSendMessage = !blocked` would incorrectly disable unrelated conversations.

## Small scoped correction

- Add an accessible, concise contextual notice **inside the existing composer**, derived from the most recent assistant turn on the current newest page using `data.turns[turn_id]`.
- `WAITING_APPROVAL` requires public `approval.required === true` and absence of a public verified grant; the message states no action was executed and conversation can continue.
- `BLOCKED` says a prior request was blocked by policy, without claiming that approval alone would unblock it. Hide contextual notice for `PLANNED`, `REJECTED`, `CONFIRMED_SUCCESS`, older pages, errors, or unknown state.
- Never derive authorization from browser messages or toggle the global send control based on a prior action; existing busy-state logic remains unchanged.
- The Proof Mode grant label derives from public `approval.granted === false`; all other values display `NOT_VERIFIED`, **never an unverified positive grant**. In this V1 planning contract, approval is always ungranted. The product bridge's `CONFIRMED_SUCCESS` means verified **read-only** history, not an executed external action.
- No new React component, provider, Worker, Core, authentication or persistence logic; no tenant data is persisted in the browser.

## Audit evidence

- `aion_chat/web/command-chat.js`: original assistant card label + Proof Mode and composer.
- `atlasquant_aion_chat_surface.py`: public turn states `PLANNED`, `WAITING_APPROVAL`, `BLOCKED`, `REJECTED`; `approval.granted=False`, no executor/receipt.
- `atlasquant_aion_chat_workspace_ui.py`: scoped session, public projection, `data.entries`, `data.turns`, page and notice.
- `atlasquant_aion_chat_product_bridge.py`: verified read-only `CONFIRMED_SUCCESS`, with `approval.granted=False`.
- `test_atlasquant_aion_chat_command_browser.py`: existing Streamlit/Chromium integration matrix reused.

## Validation and open gates

- Added Chromium E2E regression at desktop 1440x900 and simulated mobile 390x844: pending → blocked → new read-only turn; ensure input/send remains enabled, notice changes correctly, no fake approval control, no horizontal overflow.
- Scoped GitHub Actions workflow for Windows and Linux against the PR's **exact HEAD**; report actual workflow results in the PR, never claim tests passed before logs prove it.
- Review accessibility/live-region noise and focus at mobile breakpoints.
- No owner Windows device test, no native Android/iOS certification, no provider activation, no real approval, no external execution, no merge/deploy/installation authorized.

**Protected:** Core V1 freeze, #1190 P0 files, #1117 physical install NO-GO, Worker/Render, trusted source/tenant/auth gates.
