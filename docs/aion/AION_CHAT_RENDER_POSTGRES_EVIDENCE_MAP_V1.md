# AION Chat — Render Postgres Evidence Map V1

Status: **EVIDENCE_MAPPING_ONLY_NOT_PROVISIONED**

Date: 2026-10-07

## Purpose

Map official Render Postgres platform capabilities against the production
storage requirements defined by:

- #978 — Production Storage Attestation V1;
- #976 — Production Chat Activation Contract V1;
- #980 — Production Storage Candidate Decision V1.

This document is evidence-only. It does not provision a database, create
credentials, enable billing, change `render.yaml`, migrate data, activate a
provider/model, deploy, arm a Worker, or execute an external action.

## Evidence status vocabulary

- **PROVIDER_CONFIRMED** — official Render documentation confirms the platform capability.
- **CONFIG_REQUIRED** — Render supports the control, but AtlasQuant must explicitly configure it.
- **APPLICATION_REQUIRED** — the control belongs in AtlasQuant code/schema/governance.
- **RUNTIME_PROOF_REQUIRED** — can only be attested after a real candidate instance exists.
- **NOT_READY** — prerequisite is intentionally not enabled yet.

## #978 Production Storage Attestation mapping

| Requirement | Status | Evidence / action |
| --- | --- | --- |
| production backend | RUNTIME_PROOF_REQUIRED | A paid Render Postgres instance must exist before this can become true. Free Postgres is not production and expires. |
| non-ephemeral storage | PROVIDER_CONFIRMED + RUNTIME_PROOF_REQUIRED | Managed Render Postgres is persistent storage, but the actual AtlasQuant instance must still be attested. |
| durable storage | PROVIDER_CONFIRMED + RUNTIME_PROOF_REQUIRED | Managed Postgres is durable; actual instance health and persistence must be verified. |
| HUMAN_OWNER / tenant / workspace scope binding | APPLICATION_REQUIRED | Must be enforced by AtlasQuant schema/query boundaries and authenticated session context. Provider tenancy alone is insufficient. |
| default-deny access | CONFIG_REQUIRED + APPLICATION_REQUIRED | Disable unnecessary external DB access; use same-region internal URL. AtlasQuant must also enforce application-level authorization. |
| encryption at rest | PROVIDER_CONFIRMED | Render documents AES-256 encryption for Postgres primary/replicas/backups. |
| encryption in transit | CONFIG_REQUIRED | External DB connections are TLS-encrypted. Internal connections support TLS and AtlasQuant must require it with `sslmode=require`. |
| backup policy | PROVIDER_CONFIRMED + CONFIG_REQUIRED | Paid Render Postgres has continuous PITR and logical exports. AtlasQuant must choose an explicit recovery/retention policy. |
| tested restore | RUNTIME_PROOF_REQUIRED | Capability exists, but an AtlasQuant restore drill must be executed and evidenced after provisioning. |
| schema migration plan | APPLICATION_REQUIRED | AtlasQuant must define forward migration, rollback/compatibility policy, and pre-production validation. |
| health check | APPLICATION_REQUIRED + RUNTIME_PROOF_REQUIRED | Connection/query health must be integrated into the production host and tested. |
| fail closed on unavailability | APPLICATION_REQUIRED | AION chat must refuse durable success when DB health is unknown/unavailable; no silent session-only success. |
| retention policy | APPLICATION_REQUIRED | Retention/deletion policy must be explicitly defined for conversations, attachments metadata and audit evidence. |
| auditability | APPLICATION_REQUIRED | Platform logs help operationally, but AtlasQuant must record scoped data-access/audit events without leaking conversation content into logs. |
| ephemeral runtime filesystem forbidden | PROVIDER_CONFIRMED BY ARCHITECTURE | Production chat history must live in Postgres, not the web service filesystem. |
| production-ready attestation | NOT_READY | Can only become true after all CONFIG/APPLICATION/RUNTIME proof items close. |

## Critical network posture

Recommended production posture:

1. create Postgres in the **same Render region** as the AtlasQuant web service;
2. use the Render **internal database URL**;
3. require TLS on the internal connection with `sslmode=require`;
4. disable external DB access when not operationally required;
5. store connection credentials only in Render-managed environment/secrets;
6. never serialize DB credentials into Core/checkpoint/chat history.

Render documentation notes that external access is configurable and can be
restricted or disabled. Production AtlasQuant should not leave broad external
database access enabled by default.

## Backup and recovery posture

Paid Render Postgres provides point-in-time recovery and logical exports.

Required AtlasQuant proof after provisioning:

- create controlled test data;
- trigger/obtain a recovery point or logical export;
- restore into an isolated recovery instance/environment;
- verify row counts, scope boundaries and integrity;
- prove the production service did not silently switch to the recovered copy;
- record the restore evidence and destroy the test recovery resource when approved.

A backup capability without a tested restore remains **not attested**.

## #976 Production Chat Activation mapping

| Requirement | Current state |
| --- | --- |
| HUMAN_OWNER session binding | READY IN #975, NOT MERGED |
| attested production store | CONTRACT READY IN #978, REAL INSTANCE NOT ATTESTED |
| provider-neutral gateway | EXISTING REPOSITORY CAPABILITY |
| healthy local fallback | EXISTING CAPABILITY; production health proof still required |
| external provider configuration ready | NOT READY / intentionally disabled |
| external-model feature flag | NOT ENABLED |
| provider pricing configured | NOT ACTIVATED |
| valid model budget | NOT ACTIVATED |
| positive remaining budget | NOT APPLICABLE UNTIL PAID MODEL USE IS AUTHORIZED |
| per-turn explicit approval | CONTRACT REQUIRED; production host implementation still pending |
| external actions blocked | CONFIRMED by frozen Core/runtime boundary |

Storage readiness must never imply model/provider readiness.

## Cost posture

Official Render material current in October 2026 lists the smallest paid
Render Postgres compute candidate (`0.1c-256mb`) at approximately USD 6/month.
Render Postgres storage is priced separately, with 1 GB included and additional
storage billed per GB.

This is a sizing reference only. Pricing must be rechecked immediately before
any owner-authorized provisioning.

## Official platform evidence reviewed

- Render Docs — Create and Connect to Render Postgres
- Render Docs — Render Postgres Recovery and Backups
- Render Docs — Private Network
- Render Docs — Deploy for Free
- Render Docs — Compute Plans
- Render Pricing / current Render architecture guidance

Verified on 2026-10-07.

## Remaining blockers before provisioning can even be proposed

1. #975 merge/reconciliation;
2. #976 merge/reconciliation;
3. #978 merge/reconciliation;
4. production schema/scope design;
5. migration contract;
6. health/fail-closed contract;
7. retention/audit policy;
8. exact region and minimum sizing decision;
9. owner review of estimated recurring cost.

## Next allowed step

`DESIGN_PRODUCTION_CHAT_POSTGRES_SCHEMA_AND_SCOPE_CONTRACT`

That next step remains design/CI-only. Provisioning stays separately protected.

## Non-authority statement

This document does not authorize:

- database creation;
- credentials/secrets;
- paid resource creation;
- migration;
- provider/model activation;
- deploy;
- Worker arming/activation;
- trading;
- external actions;
- Core writes.
