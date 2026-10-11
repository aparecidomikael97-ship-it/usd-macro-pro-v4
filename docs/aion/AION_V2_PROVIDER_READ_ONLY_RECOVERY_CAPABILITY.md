# AION V2 — provider-specific read-only recovery capability gate

**Checked 09 October 2026.** Stacked Draft on #1135 → #1134 → #1133 → #1132 → #1131 etc. **REFERENCE ONLY / NO-GO.** No keys, provider APIs, billing, cloud provisioning, deploy or merge.

## Executive decision

**Do not retry a paid generation POST when it has an UNKNOWN_OUTCOME.** Different providers offer different retrieval mechanisms. A server-issued ID seen in the successful response does NOT help if the response was lost **before** the ID was captured and durably stored. HTTP 404 / timeout / missing item / expired retention or diagnostic request ID is NOT evidence that the first model request was never processed or billed.

This documentation-backed, static capability matrix must never be mistaken for a certified live vendor feature, provider idempotency, actual billing settlement or owner authorization. Re-check current vendor documentation when activating a model endpoint.

| Provider + precise modality | Publicly documented capability | AION recovery gate | Source |
|---|---|---|---|
| OpenAI Responses, **background** | GET `/v1/responses/{response_id}`, poll queued/in-progress with known response ID; retention has configuration and time-window constraints | Only plan read-only GET **if prior valid `resp_...` ID is already durably captured**; if ID missing or retention expired, UNKNOWN persists | https://developers.openai.com/api/docs/guides/background |
| OpenAI Responses, **stored foreground** | Retrieve response object by known ID when stored/retained | Only plan GET for known persisted `resp_...` with explicit `store=true` retention evidence; do not infer from request debug ID | https://developers.openai.com/api/reference/resources/responses/methods/retrieve |
| OpenAI Responses, **unstored/unretained** | No assumption of a retrievable response after expiry/nonretention | NO SAFE GET; block re-POST | https://developers.openai.com/api/docs/guides/background |
| Anthropic **Message Batches** | GET known batch ID, then read results; match individual result by unique `custom_id`; results only temporarily retained (guide says 29 days) | Only plan read of **known persisted `msgbatch_...` + custom ID**; never infer a single sync Messages API retrieval | https://platform.claude.com/docs/en/api/messages/batches/retrieve and https://platform.claude.com/docs/en/api/messages/batches/results |
| Anthropic **synchronous Messages API** | HTTP `request-id` is diagnostic/support correlation; no general Messages GET documented in cited reference | NO SAFE GET for lost synchronous reply; keep UNKNOWN and use support/billing if applicable | https://platform.claude.com/docs/en/api/errors |
| Google Gemini **synchronous generateContent** | Response fields include `responseId` and `usageMetadata`; API reference shown for `generateContent` | No general GET of a past synchronous generation established by this research. Do not assume recovery via `responseId` | https://ai.google.dev/api/generate-content |

**Do not overclaim idempotency:** A readable response ID and an idempotent **GET** operation do NOT prove the original billable POST can be retried without duplication. No universal provider idempotent POST contract has been verified. SDK automatic POST retries are a separate critical hazard and must be explicitly disabled or otherwise proven safe when a real adapter is approved.

## Code: capability gate, no network

`atlasquant_aion_v2_provider_recovery_capability_reference.py` uses an immutable mode classification:
- `OPENAI_RESPONSES_BACKGROUND`
- `OPENAI_RESPONSES_STORED`
- `OPENAI_RESPONSES_UNSTORED`
- `ANTHROPIC_MESSAGES_BATCH`
- `ANTHROPIC_MESSAGES_SYNC`
- `GEMINI_GENERATE_CONTENT_SYNC`

Only the first two OpenAI modes (with correct known response ID/retention condition) and Anthropic batches (with known batch ID and custom ID) can produce `READ_ONLY_RECOVERY_BY_KNOWN_ID_MATH_ONLY_UNTRUSTED`. This is a **mathematical planning candidate to potentially perform a GET in a separately authorized future implementation**, not a command, provider contact or successful recovery.

All other modalities produce `NO_DOCUMENTED_RECOVERY_BY_KNOWN_ID_NO_RETRY` or BLOCK. The caller supplies the IDs, so this proof neither verifies whether they were actually received before a crash nor that the provider object still exists. Fake recovered statuses `COMPLETED`, `NOT_FOUND`, `EXPIRED`, `PENDING`, `FAILED`, `ERROR` are all **inconclusive** with respect to charges and re-POST permission.

The gate explicitly requires:
- Exact mode ↔ provider classification.
- Exact owner/tenant/workspace, nonce, signed V2 intent and resolved full request SHA-256, reference `DISPATCH_CLAIMED|UNKNOWN_OUTCOME`.
- Exact locator schema; response ID cannot be substituted with `request-id`, a batch `custom_id` cannot substitute for the batch ID, and mixed modes/extra fields are rejected.
- Explicit `transport_auto_retry_enabled=false`. This setting is a caller assertion, NOT a real SDK configuration audit.
- `documented_retention_opt_in=true` for stored foreground OpenAI mode; no assumption of retention for unstored responses.
- All authorization, billing, trust and actual execution gates permanently false.

## Required production integration evidence (NOT delivered)

1. Before any potential POST, a **remote monotonic one-shot claim** must be committed with protected owner/tenant/nonce/model intent and budget. Independent signed fresh witness/anchor roots, enrollment, revocation and antirollback are not live (#1130–#1134).
2. Confirm vendor's current specific endpoint/mode, retention and legal constraints; actual provider HTTP client SDK defaults and backoff/retry settings; whether the provider offers real request-level idempotency and provider-side billing receipts; report unknown capability as unknown, NOT supported.
3. Capture server-provided response ID as soon as legitimately received, persist and anchor it; a crash **before** receiving it is unsolved here and must remain UNKNOWN. For batch capture batch ID + unique custom ID; batch list/support is only a diagnostic fallback, not proof that another batch is safe.
4. A future **GET-only adapter** may poll by a known identifier with scoped authenticated credentials and strict exact response/request match; it must never become a generation POST.
5. Billing settlement is separate and must use genuine authoritative usage/cost evidence. An absent GET object, diagnostic ID or local log does not establish zero charge. Reusing the old nonce after ANY claimed POST is never allowed.
6. Actual aggregate infrastructure budget must fit **R$200/month** and requires explicit owner authorization for any new cloud service or paid inference. No costs or services activated in this Draft.

## Threat/counterexample tests

Missing `resp_...` ID after lost create reply -> BLOCK, not POST. Diagnostic OpenAI request header is not response ID. Unstored mode with nominal ID -> NO SAFE GET. Anthropic sync request ID -> NO SAFE GET. Gemini responseId -> NO SAFE GET by documented evidence available. Batch custom ID without batch ID -> BLOCK. Mismatched owner/nonce/model digest, auto-retry enabled, POST authority injection, provider/mode swap, malformed IDs -> BLOCK. A simulated GET returning COMPLETED or NOT_FOUND still cannot authorize paid retry, prove charge/no-charge, refund or protected identity. All tests run without network or keys, with inherited #1135→V1 regressions on Linux and Windows.

**Core/main untouched. Draft stacked; no merge, deploy, real model usage or physical computer actions.**
