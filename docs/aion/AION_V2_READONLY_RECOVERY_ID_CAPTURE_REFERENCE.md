# AION V2 — immutable local response-ID capture and GET-only recovery planner

**09 October 2026.** Parent Draft #1136, preceding #1135–#1125/V1. **NO-GO for real provider calls, key enrollment, cloud, merge and deploy.** Entire implementation is an inert SQLite/reference planner with simulated event inputs and zero HTTP capability.

## Why this exists

Provider recovery by GET is viable only when **the actual response ID or batch ID was already delivered and durably recorded before the crash**. If initial POST response was lost before ID capture, neither an OpenAI response retrieval endpoint nor an Anthropic batch endpoint can recover from an ID that was never captured. A diagnostic HTTP request ID is not a substitute for provider response/batch ID. GET returning 404/expired/failed does NOT prove no original processing or billing; never automatically repeat the paid POST.

#1136 documented specific supported read modes. This follow-up adds the reference shape for immutably recording a known ID and constructing **fixed, relative, allowlisted GET route plans only**, while continuing the full strict NO-GO authority model.

## Delivered

`atlasquant_aion_v2_readonly_recovery_id_capture_reference.py`:

1. Takes an explicit **`CI_SYNTHETIC_PROVIDER_ID_ALREADY_RECEIVED`** input. It is deliberately NOT an actual provider receipt or independently authenticated server observation. Capture is allowed only if the #1133 reference journal already contains a specific exact signed V2 intent in `DISPATCH_CLAIMED` or `UNKNOWN_OUTCOME` with a persisted claim sequence. Exact owner/tenant/workspace/nonce/signed-intent SHA256/full resolved provider-request SHA256/four-key-roster hash and claim sequence must match; any rebound BLOCKS.
2. For **OpenAI Responses background** and **stored foreground**: requires known `resp_...`; stored foreground also requires an explicit retention opt-in assertion (not independent verification). Does not support unstored, expired, absent or guessed ID. For **Anthropic batch**: requires existing `msgbatch_...` + `custom_id`. No equivalent synchronous Anthropic Messages or Gemini generateContent read-by-responseId assumed.
3. For those valid modes, captures exact ID bytes in a separate local SQLite WAL/`synchronous=FULL` database with strict immutable config, one record per nonce AND one per signed intent digest, canonical content SHA-256 and gap-free monotonic sequence. Duplicate same inputs produce only `EXACT_LOCAL_CAPTURE_ALREADY_STORED_UNTRUSTED`; conflicting IDs, modified model, scope/nonce/digest or forged source are BLOCKED.
4. `plan_recovery_get_reference_only` reloads and rechecks the exact local record against current local journal claim and #1136 static provider recovery matrix. It returns **data only**: e.g. `{"method":"GET","relative_path":"/v1/responses/resp_..."}` or two Anthropic batch paths. No provider origin/domain/URL, authorization header, SDK adapter, transport session, redirect, TLS, clock, key, HTTP request or side effect is supplied.
5. Strict path segment allowlist (ASCII alphanumerics, underscore, hyphen) blocks `../`, `%2f`, query strings, fragments, backslash, arbitrary host, relative traversal, arbitrary POST route or SSRF by constructed path. Signed scope/digest ID binding is reference-only: **host inputs are not authenticated provider IDs**.
6. `local_snapshot_reference_only` computes SHA256 of entire local capture file state. A privileged operator can restore the whole file or journal: this digest is **not an external independently protected antirollback proof**. A snapshot restored from before response ID capture will simply make GET impossible, not authorize a retry.
7. No local capture can ever create a new dispatch claim, call a model, issue GET, refund, attest an invoice or promote an UNTRUSTED candidate to safe-to-resume. **Even successful future GET is separate from provider billing settlement and does not prove duplicate POST safety.**

## Supported relative route examples (NOT sent)

| Mode | Simulated known IDs | Relative GET plan |
|---|---|---|
| OpenAI Responses stored/background | `resp_...` | `GET /v1/responses/{response_id}` |
| Anthropic Message Batches | `msgbatch_...`, `custom_id` | `GET /v1/messages/batches/{batch_id}`, then `GET /v1/messages/batches/{batch_id}/results` and select matching `custom_id` |
| OpenAI unstored / Anthropic synchronous / Gemini synchronous | Not documented as retrievable by an existing single request ID | BLOCK, no GET plan, **never POST retry** |

Provider official references carried from #1136:
- https://developers.openai.com/api/docs/guides/background
- https://developers.openai.com/api/reference/resources/responses/methods/retrieve
- https://platform.claude.com/docs/en/api/messages/batches/retrieve
- https://platform.claude.com/docs/en/api/messages/batches/results
- https://ai.google.dev/api/generate-content

## Adversarial checks and unresolved security

Tests run on Linux and Windows with inherited #1136–#1125/V1 regressions. Cases include lost ID before create reply, immutable exact receipt duplicate vs rebound, forged claimed source, prepared-only rejection, UNKNOWN state, mode swap, path traversal, query injection, altered owner/tenant/nonce/request/roster/cap ID, parallel independently opened SQLite connections, SQL fault rollback, local database corruption, changing policy and original journal/capture restore.

**Important negative controls:** attacker may submit a syntactically plausible fake `resp_...` as a simulated received ID, and local database can retain it. This does not establish its true origin. Even a successfully persisted ID has `real_response_id_captured=False`, `real_response_id_provenance_verified=False`. Independent provider-signature provenance, owner presence, remote monotonic protected dispatch/capture high-watermark, live SDK retry controls, actual TLS authenticated GET and data-correlated billing receipts remain missing. Only an authorized future production implementation could consider an authenticated GET, still never a duplicate POST from this artifact.

**All real flags FALSE:** owner presence, witness freshness, protected journal antirollback, real captured response, network GET or POST, paid authorization, billing, exact-once processing, installer, safe-to-resume. **No real provider API / secret / paid usage / cloud / owner Windows PC / TPM / merge / deploy.**
