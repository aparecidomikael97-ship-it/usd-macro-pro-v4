# AION — Full Resolved Provider Request Binding (pre-consent, NOT authority)

Date: 2026-10-09. Draft stacked on #1123 → #1122 → #1121 → #1120 → #1119.
Applies to the **existing** `atlasquant_aion_provider.py`; not a new LLM runtime.

## What changed in the real adapter

Previously the mathematical #1121 signed-turn V1 bound `final_prompt_sha256`,
`provider_id`, `model_id`, `lane`, policy and maximum cost, but did not
fix the runtime-resolved provider HTTP options. A changed configuration
could send a different model or output token limit after review.

`preview_openai_request_binding(...)` now locally derives a domain-separated
SHA-256 from the **same builder** used immediately before mock HTTP dispatch.
The closed canonical UTF-8 JSON material contains:

- provider = `openai`, POST method and fixed endpoint;
- content type, explicitly selected external lane, resolved model;
- the **entire exact** Unicode final prompt, max output token count;
- effective timeout.

`execute_openai_answer` now requires `expected_request_sha256` to match
that freshly resolved material before `session.post`. Missing, malformed,
noncanonical or stale digest gives `BLOCKED_REQUEST_BINDING`, `called=False`,
no HTTP transport. The body, URL and timeout sent to a fake session are
taken from that same material. The preview output deliberately **does not**
return the prompt or API key, does not make network requests and always marks
itself `BOUND_REQUEST_PREVIEW_UNTRUSTED`.

This binds the logical request parameters, **not** the literal byte-for-byte
wire serialization produced by the HTTP library. Authorization header/API
key, transport TLS stack and other outgoing headers are **not** covered.
The allowlisted endpoint must also be independently restricted in deployment.

## Important: this is not signed owner approval

A hash *supplied by the caller* is not trusted authorization: a hostile
caller can recalculate it. `request_approved=True` remains a legacy boolean,
not consent. This PR deliberately does **not** wire #1121's V1 signature,
#1122's restoreable SQLite hold, Chat UI, budgets or any genuine owner
identity into the provider. Synthetic fake-session tests drive the dormant
adapter in isolation only.

The next required signed schema must bind this **full request digest** and
scope, stored USER turn, signed cost cap, independent trusted policy
generation, nonce and authenticated owner-key registry. Any V2 migration must
be explicit; do **not** silently reinterpret V1 signatures as V2 approvals.
A verified signature alone also cannot authorize a paid POST: durable hold,
one-shot external dispatch, unknown-outcome recovery and trustworthy
independent antirollback must be implemented and reviewed separately.

## HUMAN_OWNER key enrollment — decision criteria, NO provision

1. Use separate `HUMAN_OWNER_ED25519` and `COLLECTOR_ED25519` keys, and
   never accept an unverified public key sent with the same request as
   identity proof. Do not create, reveal, import, copy or rotate any owner's
   secret key in CI/GitHub.
2. A trusted enrollment ceremony must independently verify owner presence,
   key possession and human-readable fingerprint through a second channel.
   Record owner/scope, key id, algorithm, public key fingerprint, role,
   generation, immutable status, source of verification and witness position.
3. The enrolled **public registry** must have independently authenticated
   origin and a rollback-resistant active generation. Rotation, loss,
   revocation and recovery require separate explicit owner decisions and
   cannot rewrite old ledger records to appear valid.
4. For genuine antirollback, pick a remote protected monotonic witness or
   proved hardware mechanism independent of restorable host state; reject
   restored local SQLite state if it is not equal to the protected head.
   Witness unavailable, key unregistered, mismatched generation or untrusted
   clock: **NO DISPATCH**. #1116's RAM witness is not this service.
5. Windows physical key capability, TPM/non-exportability, FIDO/biometrics,
   cost of optional witness services, separate collector and recovery
   evidence require their own authorized gates before any real installation.

## Test boundary and preserved NO-GO

Offline CI exercises: missing/fake digest, post-review model change,
max_output_tokens change, timeout change, text change, lane change and
endpoint substitution; deterministic UTF-8 canonicalization; unchanged
mock POST and `MODEL_OUTPUT_UNVERIFIED`. Neither a real API key nor network
billing is used in tests.

No merge, deploy, API activation, genuine signing key, owner enrollment,
protected witness, actual quota/billing, local installer, change to `am12`,
or machine action. Keep #1117 as master checkpoint.

`trusted_human_owner_consent=false`; `owner_identity_verified=false`;
`independent_witness_protected=false`; `real_budget_reserved=false`;
`provider_called=false` (outside synthetic fake-session tests);
`installer_authorized=false`; `safe_to_resume=false`.
