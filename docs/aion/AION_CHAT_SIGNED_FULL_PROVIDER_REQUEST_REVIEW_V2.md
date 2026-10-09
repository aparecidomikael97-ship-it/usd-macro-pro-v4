# AION Chat — Per-turn signed FULL provider request, V2 mathematical review

**Date:** 2026-10-09. **Draft stacked on #1124**, itself on
#1123 → #1122 → #1121 → #1120 → #1119. Frozen core and main unchanged.

## Threat addressed

The #1121 V1 signature binds a staged USER turn and a final prompt, but
does not bind all runtime-resolved HTTP parameters. #1124 introduced a full
logical request digest checked in the existing provider executor; that digest
alone can be computed or replaced by any caller. V2 now binds it inside a
**different Ed25519 transcript**, with an explicit new schema/domain/purpose.
There is **no V1 signature fallback and no V1→V2 automatic conversion**.

## Read-only verifier inputs and comparisons

`review_signed_full_provider_request_v2` verifies, with a detached synthetic
public pin supplied by the test host:

- Confirmed authenticated access/scope and **stored pending USER** message
  (`request_digest`, original message SHA-256 and message ID).
- Complete canonical final prompt SHA-256. Noncanonical leading/trailing
  whitespace, sensitive markers and oversize input are blocked.
- Closed V2 signed fields including owner/tenant/workspace, conversation,
  message, full-provider-request SHA-256, explicit external lane,
  **resolved** provider/model, full endpoint, output-token cap and timeout
  representation.
- Positive `max_cost_micro_usd` signed cap; independently provided
  synthetic quote must not exceed it; exact policy generation and nonce.
- Mathematically valid Ed25519 signature over canonical UTF-8 JSON,
  domain-separated by V2. Unknown fields, wrong purpose/role,
  cross-scope content, altered parameters and old schema are rejected.

The provider preview and detached verifier use the **same existing adapter**
`preview_openai_request_binding` from #1124. This V2 verifier is not wired
to that adapter's `request_approved` boolean. No production code is allowed
to convert a `FULL_REQUEST_SIGNATURE_MATH_VALID_UNTRUSTED` result to
execution authority.

The output never includes the prompt, private key or provider API key.
It always sets operational booleans FALSE. A repeated signature remains a
valid math candidate, **not** a consumed single-use nonce.

## Exact security limits / NO-GO

**Public key provided as host input is NOT enrolled owner identity.** A
malicious host can inject an attacker pin and generate an equally
mathematically valid signature. The proof says nothing about a human signing
ceremony, owner/collector key custody, signer presence, hardware trust, or
whether the client displayed the entire submitted prompt and costs.

Similarly, `provider_values` are inputs to the reference verifier and
`host_quote_micro_usd` is a synthetic test quote, not independently
attested config or current model pricing. The digest binds **logical JSON
options**, not exact HTTP library wire bytes or TLS routing. Changes to
API-key identity, authentication headers, transport settings, or rate table
are not covered by the signed digest. No production release may treat these
as comprehensively approved without a reviewed production-specific contract.

The #1122 SQLite hold **accepts the #1121 V1 signature**, not this V2
signature; **DO NOT** bridge them by inventing a V1 envelope or passing a
boolean. That ledger can be rolled back or rewritten with a restored disk
snapshot. #1116's transient witness is not a durable independent one.

The only next progression is a separately reviewed genuine trust boundary:
owner and collector enrollment, independent protected witness and monotonic
generation, trusted live price/FX/budget account, V2-native nonce hold,
one-shot dispatch/outcome persistence and human authorization before
any paid provider call.

## Enrollment policy — design only, no keys on GitHub/CI

The future ceremony must require explicit permission and document:

1. Two distinct principals (`HUMAN_OWNER_ED25519` and
   `COLLECTOR_ED25519`) with separate credentials, custody,
   non-exportability evidence **where supported**, scope and RBAC.
2. Owner presence and proof-of-possession signed challenge bound to
   enrollment ID and replay-resistant nonce, verified via a separate
   trusted display/channel; cross-check full fingerprint independently.
3. Independent immutable registry entry with algorithm/key ID/public pin,
   owner identity/scope, generation, role, issuer, enrollment evidence
   digest, revoked/active state and witness sequence. **A key included in
   its own request cannot enroll itself.**
4. Revocation/rotation/lost-device/recovery as new independently recorded
   decisions; never reuse previous nonces, silently relax protections,
   restore old public-key versions or accept rollback of witness head.
5. No credential, secret, private key, fingerprint claimed as validated,
   real TPM evidence or physical installer evidence in this Draft.
   Future hardware/Windows inquiries need explicit owner authorization.

**All real authority flags remain false:** human owner unverified, provider
not called, real budget not reserved, witness not protected, installer blocked,
safe-to-resume false. NO MERGE / NO DEPLOY / NO BILLING / NO PHYSICAL ACTION.
