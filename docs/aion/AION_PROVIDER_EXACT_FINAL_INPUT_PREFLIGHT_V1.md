# AION Model Provider — Exact Final Input Boundary (No activation)

**09/10/2026.** CI-only remediation stacked on Draft #1122. No real model,
owner-PC, store, secrets, billing, merge or deploy is affected.

## Proven bug fixed — signed string vs actual provider input

Prior to this patch:

- The signed-turn math reference #1121 bound
  `sha256(final_prompt.encode("utf-8"))`.
- The actual (currently disconnected from AION Chat) provider executor called
  `clean_prompt = prompt.strip()` and sent that value as JSON `body["input"]`.
  A leading/trailing whitespace character changed the input **after** a
  possible signature review.
- `build_provider_prompt` used `prompt[:MAX_PROMPT_CHARS]`, silently
  discarding trailing evidence, user instructions, or safety content when
  an upstream assembled prompt was too large. Its downstream executor
  cannot notice an already truncated value.

Changes:

1. The builder normalizes its own assembled final framing *before* review,
   refuses to produce a partial prompt if it exceeds MAX_PROMPT_CHARS,
   and returns complete final text to be reviewed/signed.
2. The executor never mutates a provided canonical final prompt. It rejects
   empty input and a noncanonical input that would have changed under
   `strip()`, returning `BLOCKED_PROMPT_MUTATION`, with `called=false`
   and no HTTP request.
3. Once accepted, the exact Unicode string received by the executor becomes
   JSON `body["input"]`. Tests compare UTF-8 bytes in a fake HTTP session.
4. Tests cover whitespace, newlines, Unicode, builder overflow with a low
   fixture bound, and existing provider response/fail-closed regressions.

**The accepted final prompt still needs to be frozen and signed by a trusted
caller before it can ever be sent for real.** This PR does not connect the
Chat or verify an enrolled signer.

## Explicit remaining blockers

- `redact_text` from observability currently truncates individual source
  fields to 4,000 characters. That is a separate pre-builder data handling
  policy; full input provenance/consented context and redaction must be
  established BEFORE creating and signing the final request. A complete
  final prompt does not prove the user input was not previously shortened.
- The detached owner candidate #1121 signs model_id/provider_id/lane/cost,
  but does not bind the *resolved* config values `cfg.model_for_lane(lane)`,
  `max_output_tokens`, endpoint or serialized provider options. Request
  body/options must be canonicalized and bound as an immutable, versioned
  full request with the same bytes/options validated immediately before POST.
- `request_approved=True` remains a boolean accepted from caller; it is
  NOT verification of HUMAN_OWNER, independent public key enrollment,
  protected witness or durable nonce budget consumption. NEVER wire it
  to the browser or to the untrusted SQLite reference #1122.
- Even on the fake successful response, `MODEL_OUTPUT_UNVERIFIED` is
  explanatory content only, not permission to execute tools, Trade, merge,
  deploy, install, sign or send messages.
- Actual provider dispatch needs separately authorized N1 rollout:
  privacy/classification, model/endpoint allowlist, global budget cap and FX,
  real persistent intent/dispatch ledger, one-shot claim, unknown paid outcome
  without blind retry, reliable output storage and identity/witness controls.
- No evidence of a genuine local offline LLM installed or running is created.
  N0 local chat still must not advertise a generated response it did not make.

Existing physical installer gates #1049 12/12, #1087 16/16, trust witness
#1116, and #1117 master state remain independently NO-GO.

**NO MERGE, NO DEPLOY, NO BILLING, NO LIVE API, NO `am12`, NO NEW KEYS.**
