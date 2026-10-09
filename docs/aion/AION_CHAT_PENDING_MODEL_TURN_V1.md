# AION Chat — Durable Pending User Turn Before Model Consent V1

**Scope:** real (but DISABLED BY DEFAULT) reusable user-message write into an
injected scoped chat store. No external inference is installed, invoked or
authorized by this module. This is the FIRST phase of the later guarded model
handoff, stacked on the provider preflight fixes from PR #1119.

## Existing reuse

- `aion_chat.models.Scope` binds the authenticated owner, tenant and workspace.
- `atlasquant_aion_chat_product_bridge.validate_product_binding` checks
  authenticated ADMIN, session username == scoped owner ID, credential
  fingerprint and permissions.
- `aion_chat.store.SQLiteChatStore` provides actual transactional message
  writes, reopen and scoped lookup in disposable CI fixtures, not a fake record
  dict. Production PostgreSQL is not activated or accessed.
- `atlasquant_aion_model_router.privacy_sensitive` blocks **some known**
  sensitive phrases. It is a limited heuristic: cannot certify privacy.
- No new login, RBAC, owner assertion or provider selector.

## What happens

`stage_pending_model_user_turn(store, scope, access, conversation_id,
request_id, message)`:

1. Validate trusted host's authenticated session/SCOPE; reject forged role,
   missing permissions/fingerprint, wrong owner/tenant/workspace and
   non-existent/archived conversations.
2. Require a well-formed nontrivial request ID and exact, nonempty,
   non-truncated UTF-8 message not exceeding current chat turn limit.
3. Block recognized sensitive prompts from the future external-model queue.
   Truly private messages still require an approved **local-only** policy.
4. Write an actual `Message(role='user')` to the pre-existing scoped store
   **before** any model call, with stable message ID, request digest and
   metadata `approval_state='PENDING'`.
5. Reopen/lookup and verify identical content + metadata; repeat with same
   request ID is idempotent; different text under same request ID is blocked.
   If the underlying append commits then loses its return, query the same
   ID and reconcile with its original record; otherwise fail closed.
6. Return only a digest-based correlation receipt, without the raw prompt,
   `owner_signature_verified` or claim of response generation. ALL external
   capabilities, billing, worker and install flags remain false.

The request digest is NOT a secret, electronic signature, durable protected
antirollback witness, payment authorization or proof of a trusted store.

## Strict limitations

- **Not connected to Streamlit UI:** only call from a future trusted host once
  the owner selects an explicit send and accepts the storage conditions.
- **Not a model execution path:** does not call `execute_openai_answer`,
  retrieve a model, consume a nonce, reserve money or add assistant messages.
- **Not HUMAN_OWNER attestation:** `ADMIN` scope binding is a prerequisite
  for user chat, not permission for paid processing or Windows mutation.
- **Not complete external consent:** signed per-turn approval must bind
  owner/session and trusted identity, request digest, exact *post-sanitization*
  prompt bytes, model, price cap, purpose, nonce and policy generation. The
  signature must be verified against an independently enrolled key.
- **No durable model-call deduplication:** preventing duplicate **user writes**
  alone does not make a future billable external POST idempotent. A separate
  atomic financial reservation, proof of the attempted call, outcome/unknown
  reconciliation and request deduplication protocol are mandatory.
- **No implicit privacy readiness:** the pattern filter cannot detect all
  personal data or secrets. Provider-bound context and attachments need their
  own reviewed privacy budget, redaction and data-residency policy.
- **No claim of distributed exactly-once:** SQLite and external provider
  cannot share a transaction. Lost-response after billed request is UNKNOWN
  until independently reconciled; never blindly retry.
- **No owner key, TPM, network or host access:** each physical gate is still
  in #1117, #1049, #1087, #1114 and #1116.
- **No production data:** CI uses `tempfile.TemporaryDirectory` and
  `SQLiteChatStore` only. No real client data, PC or Postgres secrets.

### Required next step

Review this write path, scope isolation and lifecycle first. After that,
a separate scoped owner-authorization ceremony plus amount/nonce reserve can
be implemented, and only THEN a provider call/recorded output could be
considered with separate approval and irreversible billing evidence.

**State:** `provider_called=false`, `billing_executed=false`,
`owner_signature_verified=false`, `model_invocation_authorized=false`,
`external_model_path_activated=false`, `installer_authorized=false`,
`safe_to_resume=false`.

Draft CI-only. NO MERGE, DEPLOY, provider, production store or owner PC.
