# A190 G13 — Signed semantic origin bridged to the REAL AION Outbox (LAB, 2026-10-23 Manaus)

## Why G13 exists

G6 found that the real ExecutionOutbox used caller-controlled intent_ref in its idempotency key. The same business operation staged with another request identifier became a different local Outbox intent and (in the old deliberately unsafe LAB mode) another simulated adapter send.

G11 showed an offline construction of a **stable native reservation key**, using a signed issuer event's tenant + semantic digest, independent of caller request_id or original_event_ref. G12 changed the real Outbox to **deny callback trust by default**; no actual send is enabled.

G13 joins these in a new **LAB-only bridge**. It uses real ExecutionOutbox.enqueue and its SQLite storage while deriving its canonical intent_ref from the signed semantic digest. No changes to production runtime modules or any provider.

## Protocol

1. A signed event is checked using the caller-provided synthetic Ed25519 issuer pin and G11 verifier, including tenant, time interval, schema and signature.
2. A local canonical payload binds tenant, business_event_id, action, aggregate_key and REDACTED payload. A domain-separated SHA-256 must equal the issuer-signed semantic_digest. This prevents accidental reusing one signed event to stage different local payload/action.
3. The real Outbox's intent_ref becomes semantic-<digest> and its existing SQLite transactionally enforced idempotency is reused. Request aliases and issuer event_ref changes do not change the local decision key.
4. The corresponding G11 documentary DynamoDB/Firestore envelopes map the same signed semantic digest to the same native key, regardless of their own request ID.
5. The bridge rejects G12's explicit unsafe synthetic-callback Outbox mode. The returned record always reports external_root_verified=false, execution_allowed=false, permits_send=false.
6. Even when synthetic true callbacks are injected into a **default** G12 Outbox, dispatch remains UNCERTAIN and never touches adapter.send. No real provider is called.

## Adversarial tests that MUST stay RED

- A caller can replace BOTH signer and trusted public pin and invent another business_event_id to obtain a different digest; local staging is possible twice. **There is no independently pinned issuer**.
- A signed tenant identity covers the tenant, **not every owner/workspace**. Two local scopes under one tenant produce different Outbox idempotency keys despite the same G11 native key. Only an actual independent external reservation can coordinate them.
- Deleting/replacing the local SQLite file, then rebootstrap, allows staging the same signed intent again. **No antirollback custody exists**.
- Digesting a *redacted* payload can conflate private values, and business_event_id authenticity is not established. This is a non-authoritative mapping contract, not proof of unique human/business intent.
- Signed event verification by itself is never evidence of external provider execution, recovery of unknown effects, authorization, or legitimate HUMAN_OWNER control.

## Useful bounded outcomes

| Question | Expected LAB outcome |
| --- | --- |
| Caller changes only request_ref | Existing real Outbox row, IDEMPOTENT |
| Issuer re-signs another event_ref with the same signed semantic digest | Existing real Outbox row |
| Same source event used for changed action or payload | DENY before enqueue |
| Signed tenant differs from real outbox scope | DENY |
| Different signed business_event_id | Separate stage (not permission to send) |
| Untrusted/self-pinned signer, workspace split, or local rollback | RED still reproduced |
| Default Outbox with signed local origin and a fake true guard | UNCERTAIN; ZERO SEND |
| G11 DynamoDB/Firestore request-shapes | Same native key; no actual cloud request |

## What G13 does NOT do

- No IAM, OS principal, key provisioning, FIDO2/Windows Hello, HUMAN_OWNER ceremony.
- No external append-only reservation, cloud API read/write, signed real receipt, provider effect or reliable absence declaration.
- No merge to main, deploy, Worker, credential, customer, account, or budget increase.
- No claim about closing any of the six P0. G12 canonical Quality/Security unit-test green belongs to that tested SHA; G13 must preserve but does not independently rerun the entire canonical suite.

**HARD NO-GO · 0/6 P0 homologados · UNCERTAIN · ZERO_AUTO_RESEND.**

## Evidence

Cross-platform G13/G11/G12 CI must be linked here after running, with exact tested SHA, job IDs, count of tests and any first-run failure preserved. A passing RED reproduction is NOT a passing security gate.
