# AION V2 — host-signed session bound to persisted USER chat and signed owner preclaim

**2026-10-09. Reference-only Draft on #1144 → #1143 → #1142 → ... . STRICT PRODUCTION NO-GO.**

## Objective and threat model

#1144 checks the real persisted pending USER turn through the existing `SQLiteChatStore` and `validate_product_binding`, but the purported `access={allowed,mode,role,session}` identity decision is supplied by the application host. A forged `AUTHENTICATED/ADMIN` dictionary can pass mere consistency checks. Without an independently enrolled identity-provider verifier key, authenticated session token / revocation and trusted monotonic time, **there is no genuine owner-session authority**.

This new integration models a separate, domain-separated, Ed25519-signed **HOST_SESSION_AUTHORITY** attestation that binds the exact same owner, tenant, workspace, conversation, message, nonce, V2 signed-intent digest and immutable full provider-request SHA256 as #1144. The host signer key must be distinct from the owner, primary witness and secondary anchor keys. These are **synthetic test keys provided by the caller**, not an IdP connection or independent trust anchor.

## Inert reference protocol

`atlasquant_aion_v2_host_session_attested_preclaim_reference.py`:

1. Canonical strict JSON with `ATLASQUANT_AION_V2_HOST_SESSION_SCOPE_ATTESTATION_V1\0` domain, closed schema/purpose/role/issuer/audience and signer key ID. Verifies Ed25519 using caller-provided public pin.
2. Exact owner/tenant/workspace, `username=owner_id`, `host_role=ADMIN`, fingerprint SHA256, sorted *minimal* `["aion:admin","app:read"]` privileges and host access granted/mode authenticated. No credential fingerprint raw text is returned or logged.
3. Exact conversation/message/nonce, signed V2 intent digest and full provider request digest bound to the #1144 persisted pending turn, dual PREPARED witnesses and local reference-only journal.
4. Distinct session-signing key ID and public bytes from all three other roles. A signed issuer/audience prevents accidental cross-service use.
5. Caller-provided fresh challenge, exact session epoch and caller-provided revocation generation floor, exact integer issued/auth/expires timestamps: maximum 300-second asserted credential lifetime, 600-second asserted prior authentication age, 30-second future skew and expired-session rejection. These **do not establish an independent clock, challenge consumption, or a real revocation lookup**. The challenge and session epoch are math-only caller input.
6. `review_host_attested_persisted_preclaim_reference` performs signed host scope math first, then #1144's full persisted chat/owner V2/witness preclaim math. `consume_host_attested_persisted_local_reference_only` repeats the host math and delegates to #1144's own double-read of chat and one reference-only SQLite `PREPARED → DISPATCH_CLAIMED` local nonce burn. It **never calls a model**, spends, installs, signs, provisions, issues a session token or returns a network-capable authorization.

The existing session access structure is unchanged by this Draft and no real login/SDK integration has been introduced.

## Adversarial coverage

- Incorrect host Ed25519 signature / signer ID or substitution of the host, owner or witness key as session authority.
- Cross-tenant, cross-workspace, cross-user, wrong conversation/message, nonce, V2 signed-intent digest, provider-request SHA, issuer, audience, challenge or permissions.
- Forbidden role/anonymous/disallowed session and edited credential fingerprint.
- Expired, future-dated, excessively long and outdated sessions; revoked or stale epoch/floor in caller-supplied values.
- Additional signed `paid_dispatch_authorized` field rejected under closed schema; no V1 fallback.
- Existing persisted USER row modified, owner signature invalid, missing secondary witness, stale journal claim and owner nonce replay are rejected.
- **Deliberate negative controls:** a malicious caller replacing the host public pin with their own and signing an otherwise exact transcript can still pass math. Replaying an identical session challenge can pass read-only math repeatedly, until local journal nonce burn; no independent challenge-consumption store exists. A malicious caller may supply a fake clock or a manipulated local SQLite store. No actual identity-provider verification, real signer enrollment, remote CAS/high-watermarks, billing reconciliation or cross-store atomicity.
- Tests trap any actual HTTP/model calls.

## Conditions for production acceptance — NOT implemented

- Independent trustworthy IdP signature root enrollment and key-custody ceremony, with tenant/issuer trust pin protected against user input substitution.
- Real trusted session token introspection or signed token verification with documented issuer/audience, revocation, `jti`/nonce consumption, trusted non-rollback clock and durable monotonic session epoch.
- Genuine HUMAN_OWNER key enrollment, trusted FIDO2/Windows Hello presence where required, separately protected independent PRIMARY_WITNESS and SECONDARY_ANCHOR roots.
- Owner-signed exact request bytes, real budget reservation and independently durable globally fenced one-shot dispatch CAS, trusted read-after-write and provider receipt/billing reconciliation. Loss of provider response after possible POST remains UNKNOWN_OUTCOME and can **never** automatically trigger another paid POST.
- Explicit owner permission for any real key registration, cloud service, payment, merger or deployment; temporary total infrastructure ceiling R$200/month.

**All operational booleans including `real_idp_signature_verified`, `session_signing_root_enrolled`, `signed_host_session_freshness_proven`, `paid_dispatch_authorized`, `real_post_authorized`, `network_called`, `global_one_shot_guaranteed`, `billing_settlement_verified` and `safe_to_resume` remain FALSE.** No cloud, real credentials, paid calls, owner's physical Windows computer, merge or deploy; frozen Core V1/`main` untouched.
