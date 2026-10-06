# AION Chat — Issue #659 UI/browser delivery

## Base and scope

Exact initial HEAD: `9226ff57633bafcd62c275c0f2d4ba7f843c8ed4`.
Branch: `integration/aion-chat-ui-codex-20261004`.
Draft source base: `integration/aion-chat-command-surface-v1-20261004`.
No rebase to main. No merge, deploy, freeze, worker arm or production operation.

## Actual product entry and flow

`render_reference_workspace` keeps its existing authenticated area gate and routes AION home and Chat to `render_aion_chat_workspace`. All other workspace routes retain existing handlers. The home is now a conversational shell, not a disconnected standalone preview. The old SQLite chat preview and its endpoints remain untouched and separate.

Trusted host access -> scoped session history -> browser text/attachment metadata -> `submit_turn` -> unmodified `build_chat_turn` (#656) -> unmodified `append_chat_history` -> allowlisted presentation -> message/status/Proof Mode. No second Core, planner, memory store or approval system.

Context/role/tenant/workspace/actor come from trusted access, never a browser claim. Session chat state is keyed by that identity and role; conversation_id is server-created and stable. Client request IDs deduplicate delivery without conferring authority. turn_id and turn_index come from #656. Tests prove cross-tenant UI session separation and ignore context/approval/feature claims.

## Interaction and truth

- User/assistant message pairs, multiline composer, Enter sends, Shift+Enter inserts newline; IME composition is excluded from Enter interception.
- Busy/disabled state and immediate status; no spinner. A 15-second UI timeout preserves the draft and explicitly avoids claiming success.
- Stop is VISUAL ONLY in V1. It cannot cancel Core execution or approve anything. The planning result may still be registered; wording says so.
- PLANNED, WAITING_APPROVAL, BLOCKED and REJECTED are derived from the same Chat Turn contract. Assistant text is a deterministic explanation of the planning envelope, not a fabricated model answer or execution receipt.
- Approval is a state/note, with no grant button. Text such as sim, ok or autorizo tudo does not grant authority.
- Proof Mode is optional and builds its DOM on expansion. Public capability, policy, blockers, approval, Golden Path stages and planned/missing evidence/receipt are allowlisted; full core_preflight and private reasoning never reach the browser.
- Provider is not connected. Runtime online/offline/degraded status is not assumed; UI explicitly says it was not observed.

## Attachment boundary

The browser uses File.name/type/size only. No FileReader, body, base64, upload ingestion, file execution or automatic raw prompt insertion. The server whitelists metadata before #656. Client-supplied hashes are omitted: no trusted ingest hash exists in this UI layer. File/image selection and removable chips are available; the composer explains that secure ingestion is not active.

## History, performance and persistence

Logical history has no small message cap. The existing canonical append contract produces each new pair; extending avoids copying the entire logical history on every send. Rendering/transmission is a paginated window of at most 40 messages, with previous/recent navigation. Browser QA seeds 120 real planning turns (240 logical messages) through the same adapter, reaches the earliest turn, then continues to 242 messages. Unit tests also verify windowing/idempotency.

Session history is not durable history. No SQLite/DB/journal/checkpoint/memory persistence is connected by this sprint. Returning through existing AION modules preserves session history and conversation_id. Browser refresh/disconnection/session expiry are not guaranteed durable continuity. The previous standalone durable preview is not silently substituted as a production store.

Shell is a lightweight same-session Streamlit V2 component; Core/chat-contract imports are deferred until a turn is submitted, so opening the shell does not import the planning stack; no large reference artwork in the conversation. History window limits DOM cost, technical Proof Mode DOM is lazy. Smart scrolling follows a submitted turn and otherwise preserves reader position; explicit jump-to-recent control appears away from the bottom. Native details menus and visible focus keep keyboard navigation. Dark navy, cyan and violet follow the existing AtlasQuant visual direction, without claiming pixel fidelity to reference artwork.

## Responsive/accessibility evidence

Chromium validation: 1920x1080, 1440x900, 1280x720, 768x1024, 390x844 and 390x480. The last viewport SIMULATES the reduced area with keyboard open; no claim of native iOS/Android keyboard/device certification. visualViewport resize drives available height; the flex history scrolls above the composer, rather than messages being covered by an overlay.

Labels, role=status/aria-live, keyboard focus, focus-visible, readable contrast, reduced motion and hover/focus geometry are tested. Mobile functions remain reachable through the visible Functions menu. Desktop sidebar keeps existing AION modules, including the eight-roles page.

## Finding on #656 — reconciled by coordinator

The original Codex finding was valid: the initial Chat Turn V1 flattened multiline whitespace. The coordinator chain now separates representations:
- `message` preserves normalized line endings, indentation and multiline content;
- `canonical_message` is whitespace-normalized only for routing/intent;
- raw and canonical digests are separate;
- durable history and resume context preserve the conversational representation.

The reconciled UI still keeps `display_text` as a presentation field for compatibility, but it is no longer required to compensate for data loss in the Core contract.

The broad regression detected a new direct Streamlit import in the adapter. Component registration was moved into the existing atlasquant_reference_ui host and injected into the adapter; the original architectural coupling test was preserved unchanged and passed.

Other initial test issues were harness errors, not Core findings: two Central controls share a route (select the visible breakpoint control); Playwright uses File.arrayBuffer internally to construct synthetic selection; page.evaluate returns a class as callable unless wrapped; Streamlit V2 controls live in Shadow DOM. Instrumentation and locators were corrected without weakening authority/metadata assertions.

## Protected boundaries and CI

atlasquant_aion_chat_surface.py, V2.20–V2.26, certification/freeze/owner decision, worker runtime, trust roots, policy kernel, execution authority, existing shared workflows and deploy workflows remain unchanged.

A new isolated `.github/workflows/aion-chat-command-ui.yml` runs only tests on the requested stacked PR base. Read-only repository permissions, pinned actions, local Chromium and artifact upload; no deployment, runtime command, provider or owner operation. Existing workflows are not rewritten. This dedicated gate addresses #659's requirement to initiate relevant CI despite existing shared gates filtering other base branches.

## Validation and limitations

Final exact local/CI results and SHA are recorded in the delivery report and Draft PR. Mandatory UI browser tests do not silently skip when Playwright is missing. Test runtime dependencies remain pinned to existing requirements; missing local cryptography was installed in an isolated artifact directory for broad Core regression, not the global Python environment.

No paid provider, external action, memory promotion, execution, approval grant, durable history, safe attachment ingestion, real receipt, native mobile certification or streaming model output is claimed. #659 delivers the truthful V1 conversational planning surface; the wider #537 durable/voice/execution vision remains incomplete.

## Final local UI validation

- New session/boundary suite: 9 test functions, 14 executable cases (the final lightweight-import test included).
- New browser suite: 3 test functions, 8 executable cases; 8 passed in 79.49 s.
- Related render/contract block: 87 passed, 4 subtests passed in 6.98 s.
- Architectural boundary + new session tests: 21 passed, 15 subtests passed in 22.18 s; original independence inventory unchanged.
- Measured AION navigation after Central is visible: 265.43–519.89 ms across six dimensions. Selected follow-up sends: 272.84–407.24 ms. These are local observations under concurrent test load, not a production SLA; cold browser/Streamlit/Central startup is recorded separately (3.7–5.4 s).
- Final broad Core regression: 215 files, 5,280 passed, 5 skipped, 743 subtests passed in 237.99 s. Existing browser regression: 9 passed in 463.01 s (all eight reference-browser matrices plus the old standalone chat browser). The five skips are existing Windows symlink limitations: developer intelligence, journal store, journal governance, V2.13 real trust authority, V2.7 durable crash isolation. No remaining failures.

## CI portability check

First Linux run: 87 related tests passed; browser 7 passed/1 failed. The absolute scroll <100 assertion included Playwright bringing a below-fold summary into view (different Linux font metrics). The test now positions the click target first, captures scroll, performs the real click and verifies the opened Proof list plus scroll stability within 1 px. This is a stricter measurement of the actual no-jump contract, not a relaxed threshold. No product/Core patch was required for this CI finding. Final rerun status is in the delivery report/PR.
