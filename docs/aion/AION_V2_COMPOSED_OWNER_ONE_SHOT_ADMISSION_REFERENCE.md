# AION V2 — composed owner-signed preclaim and one-shot local burn (REFERENCE / NO-GO)

**2026-10-09. Draft stacked on #1142 → #1141 → #1140 → #1139 → earlier V2 protection chain.** Frozen Core V1 and `main` preserved. No merge, deploy, external provider API, Windows PC/TPM interaction, genuine HUMAN_OWNER signing, credential enrollment, cloud service or paid inference.

## Why this must follow TLS validation

TLS and a zero-retry Requests adapter protect one class of transport failures. They do not authenticate an owner or ensure a durable server-side once-only dispatch. Earlier reference layers included V2 Ed25519 owner request math (#1125), local SQLite one-shot claim (#1133), two signed dispatch journal heads (#1134), and hardened full OpenAI request preview (#1140). Without **a composed gate binding the same exact request and nonce**, individually green mathematical references can accidentally be misinterpreted as independent production authorization.

This Draft adds an **inert composite** to make all mathematical dependencies agree, with no positive provider execution permission.

## Exact checks and ordering

`atlasquant_aion_v2_owner_signed_one_shot_admission_reference.py`:

1. `review_owner_signed_preclaim_reference` receives strict caller-supplied V2 Ed25519 owner approval envelope and public key pin, original pending message/request SHA256 *assertions*, an exact previously prepared #1133 local journal intent, two signed #1134 witness READs, quoted micro-USD and the values to reconstruct the **actual current #1140 hardened OpenAI provider request preview**.
2. The full V2 approval is reserialized via the existing `canonical_full_request_approval_v2` domain separator and canonical bytes; validates signature *math*, exact schema, purpose, owner key ID, owner/tenant/workspace/conversation/message, nonce, policy generation and cost ceiling. The hash of these exact V2 signed bytes must match the synthetic #1133 journal's persisted `signed_v2_intent_sha256`.
3. The full POST digest is **recomputed using** `atlasquant_aion_provider.preview_openai_request_binding` (the same provider module used for sending, including `allow_redirects=False`, TLS verification, non-proxy and zero-retry transport policy). The signed endpoint must be the exact `https://api.openai.com/v1/responses` origin, with matching lane, model, resolved tokens, timeout and prompt hash. The journal's full request SHA256 and signature payload must be identical to this newly computed digest.
4. Both synthetic #1134 `PRIMARY_WITNESS` and `SECONDARY_ANCHOR` signed HEAD READs must mathematically match the **same local journal** in `PREPARED` state with `claim_sequence=0`. Old head, different nonce, wrong key, signed fork, previously claimed, unknown, or cancelled states BLOCK.
5. Only after every check, `consume_one_local_reference_claim_only` calls the local #1133 SQLite `claim_reference_only`, an atomic `BEGIN IMMEDIATE` transition `PREPARED → DISPATCH_CLAIMED`. This **burns the nonce in the local reference** (if not already consumed), and invalidates the PREPARED witness read. Concurrent attempts yield exactly one successful **reference-only burn**, the rest BLOCK. There is never an HTTP client, callback or `request_approved=True` conversion.

**Every result, including mathematically valid or the local burn, explicitly exposes all execution/trust booleans FALSE:** `paid_dispatch_authorized`, `real_post_authorized`, `network_called`, `owner_enrollment_verified`, `owner_presence_verified`, `original_user_message_persisted_verified`, `remote_journal_head_freshness_verified`, `external_dispatch_cas_performed`, `trusted_budget_hold_verified`, `global_one_shot_guaranteed`, `safe_to_resume`, `billing_settlement_verified`; the same nonce is never permitted for another local claim and automatic paid retry is forbidden.

## Deliberate negative controls

- An attacker replacing the alleged HUMAN_OWNER public pin with their own while signing the exact same payload can pass **Ed25519 mathematics**, but no genuine ownership, enrollment, possession ceremony or authorization is established.
- An attacker replacing a witness pin and corresponding signature can pass the two-head math, but the two allegedly independent services may be under one administrator's control. No genuine noncollusion or remote freshness is proven.
- Replacing both historical signed heads **and** an older journal file permits local mathematics to pass again: **remote monotonic antirollback not present**.
- The original persisted USER message and access/SAML session are **not independently re-read** by this composite, only untrusted hashes supplied by caller. Existing V2 chat-store reviewer remains a separate prerequisite, not a proof this component can substitute.
- A local write that burns a nonce, even after correctly matched signatures, is not a globally atomic remote dispatch/charge reservation. Crash between local and independent cloud witnesses is unsolved. After any possible real HTTP send, timeout remains **UNKNOWN_OUTCOME** and never an authorization for automatic repeat.

## Adversarial tests

New Windows/Linux tests cover successful math but zero network, one reference nonce burn, concurrent independent journal connections, same-nonce replay after crash, UNKNOWN state, wrong owner signature vs forged owner key + pin, altered signed nonce/scope/model/lane/endpoint/timeout/tokens/request full SHA, changed provider preview settings/transport, excessive/boolean cost quote, missing or replayed witness challenges, forged anchor public pin, extra schema authority field, and trap mocks for `requests.Session.send`, module-level `requests.post` and actual model execution.

Full inherited TLS, real Requests loopback, transport hardening, vendor recovery, one-shot SQLite/witness, V2/V1/provider regressions run on GitHub Actions Windows and Linux. Disposable synthetic keys only and no actual external network from this module.

## External admission prerequisites (NOT satisfied)

- Owner FIDO2/Windows Hello ceremony with audited enrollment and key custody, genuine signed intent from the real pending chat turn.
- Independent dual-domain trustworthy monotonic witness/CAS with separately protected public pin registry, replay-proof nonce challenge consumption and remote read-after-write, **not** forged caller values.
- Durable globally fenced one-shot dispatch claim linked to provider-side idempotency where available, aggregate authenticated budget reserve and vendor invoice/usage reconciliation.
- Explicit per-deployment owner approval for cloud services, real keys, paid provider API, merges and deploy; no commitment beyond the R$200/month target.

**Security conclusion: NO-GO.** This is integration of *reference validations* and an inert local nonce burn, not a paid request approval system.
