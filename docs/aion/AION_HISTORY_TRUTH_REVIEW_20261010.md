# AION #1193 — Honest scoped historical result rendering (Draft)

Status: **CANDIDATE / NO MERGE / NO DEPLOY / FIRST INSTALL HARD NO-GO**.

## Proven defect on frozen main baseline

Baseline: `5744b2b7b17c84331e6f27c569064993ff587782`.
`atlasquant_aion_chat_product_bridge.py::read_product_history_page` projected every assistant message stored locally as `CONFIRMED_SUCCESS` and advertised `Receipt verificado` from only a metadata identifier, regardless of fresh independent reverification. This was a presentation trust error, **not proof of unauthorized external execution**.

Córtex prepared the original correction in a local isolated review (original patch and offline XML retained locally). This Draft integrates its conservative historical projection and separately repairs the staged browser consumer of that projection.

## New contract, scoped to history reads

- Page-level `READY`: history page was read from a tenant-scoped store. It is **not** a confirmation that its messages are true.
- Assistant turn `state=UNKNOWN`, `reason=HISTORICAL_RESULT_NOT_REVERIFIED`, `historical_result_reverified=false`.
- `persistence_state=LOCAL_PRESENT`: data is present in this authenticated scoped local store only.
- `receipt_state=NOT_PROVIDED` or `DECLARED_UNVERIFIED` as applicable. Metadata `receipt_id`, `receipt_digest` and `receipt_verified=true` cannot certify evidence or restore trust.
- `verification=NOT_REVERIFIED`, `receipt_verified=false`. Declared verification state is retained as an **untrusted claim**, separate from the result.
- This read path adds no positive reverification procedure. Future positive promotion requires verifiable full receipt content, binding, scope, identity, operation, freshness, and independent evidence.
- No storage mutation, remote retrieval, credential handling, authority grant, provider call, action execution or memory promotion.

## UI alignment

The existing `aion_chat/web/command-chat.js` product label has been changed from `AION · leitura local verificada` to the neutral `AION · histórico local`. `UNKNOWN` is displayed as `Não reverificado · UNKNOWN`, preserving the public turn code and Proof Mode evidence. No new authorization/execution controls were added.

The existing Chromium staging test `test_atlasquant_aion_chat_product_ui_browser_staged.py` was updated to require `UNKNOWN` initially, after SQLite remount, and after navigation; it asserts proof details `NOT_REVERIFIED`, `LOCAL_PRESENT` and no false verified receipt. New SQLite regression tests cover claims of `CONFIRMED_SUCCESS`, missing/malformed receipt, foreign binding, user text, and tenant isolation.

## Existing sibling PR #1192

PR #1192 is an **unmerged Draft** changing the *same* JS file for a separate composer notice; **neither branch is edited by this Draft**. Both independent modifications must be intentionally reconciled before either is considered for merge. In particular, do not revert #1192’s WAITING_APPROVAL/BLOCKED notice or resurrect its old unconditional product heading. #1192 also has an unresolved Linux navigation test failure at its own HEAD, unrelated to this historical-truth patch until a combined integration suite proves otherwise.

## Test truth and open gates

- Córtex local preparation: log of **218 passed, 55 subtests passed** (8.47s), with original **216/50** XML retained; those were executed on its local isolated review, not a hosted GitHub commit.
- This Draft includes its own per-commit GitHub Actions Windows/Linux workflow and full staged Chromium browser regression. Status must be determined from the **exact final HEAD and actual logs**, not assumed.
- Core V1 frozen, #1191, #1192, main, Worker/Render, live provider, production data, enrollment, independent witness and hardware installation are untouched.
- Physical Windows device, full-service real READ/SEARCH with remote verification, offline/online reconciliation, deploy and first install are **not authorized** by this PR. NO-GO remains.

## Review and acceptance

1. No stored assistant message becomes `CONFIRMED_SUCCESS` or claims a verified receipt solely from metadata.
2. UI and browser tests display `UNKNOWN` and a neutral source label across normal sends, remounts and navigation.
3. Wrong tenant cannot read the conversation; no new credential, execution, or memory path.
4. Exact PR-HEAD Windows/Linux tests finish successfully and review finds no regression before separate merge discussion.
5. Any conflict with #1192 is resolved in a separately reviewed integration step. No unattended merge.
