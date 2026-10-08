# AION Chat — Direct App Role Connection CI V1

Status: IMPLEMENTATION SAFE / CI-ONLY  
Date: 2026-10-07  
Depends on: #1002 schema candidate freeze  
Runtime target: disposable PostgreSQL 17 only

## Purpose

Prove the AION Chat PostgreSQL path while authenticated directly as the
least-privilege application identity.

Earlier CI proved least privilege by opening the disposable database as an
administrator and issuing a role switch. That is useful for schema/RLS
verification, but it is not the intended production composition.

This stage closes that gap without contacting a real provider.

## Direct identity

The disposable CI application login is:

`aion_chat_app_ci_login`

It is created only inside the GitHub Actions PostgreSQL service.

The password used by the test is a disposable CI fixture. It is not a Render
credential, not a production secret and has no authority outside that
ephemeral PostgreSQL service.

Every store connection must prove:

- `session_user = aion_chat_app_ci_login`;
- `current_user = aion_chat_app_ci_login`;
- LOGIN is enabled;
- SUPERUSER is disabled;
- CREATEDB is disabled;
- CREATEROLE is disabled;
- INHERIT is disabled;
- REPLICATION is disabled;
- BYPASSRLS is disabled.

An administrator connection accidentally injected into this backend fails
closed.

## No role switching

The direct-login backend does not execute `SET ROLE`.

This is intentional: the future production process should connect using the
application credential itself, not keep a privileged session alive and reduce
privilege after connection.

## Database privileges

The direct application identity receives only the reviewed runtime profile:

- schema `aion_chat_v1`: USAGE, no CREATE;
- `schema_meta`: SELECT only;
- `schema_migrations`: no SELECT;
- `conversations`: SELECT + INSERT + UPDATE, no DELETE;
- messages: SELECT + INSERT;
- message idempotency: SELECT + INSERT;
- attachments: SELECT + INSERT;
- checkpoints: SELECT + INSERT;
- summaries: SELECT + INSERT;
- access audit: SELECT + INSERT.

The normal application identity cannot perform retention deletion. That remains
behind the separately reviewed retention boundary.

## RLS and scope

Forced RLS remains mandatory.

Every operation also keeps the application-level
owner/tenant/workspace predicates.

The database scope settings are transaction-local:

- `app.owner_id`;
- `app.tenant_id`;
- `app.workspace_id`.

They must clear at transaction end so a future connection pool cannot leak one
scope into another.

## Audit path

The direct-login store keeps the atomic, content-free storage audit receipts
from #998.

The test proves real conversation/message mutations plus their audit receipts
while connected directly as the application role.

## Frozen schema

This stage does not change the frozen candidate migration.

Candidate migration remains:

- version: 1;
- path: `migrations/aion_chat_postgres_v1/0001_initial.sql`;
- SHA-256:
  `7dd72d75365862f54c81110027430011f8ac8f81ce629f500cbbd9aa0c00c50c`.

The direct-role tests re-run the schema candidate attestation and require
`POSTGRES_SCHEMA_CANDIDATE_FROZEN_IN_CI`.

## Fail-closed cases

The dedicated CI covers:

- wrong database password;
- administrator identity injected by mistake;
- BYPASSRLS role drift;
- unexpected DELETE privilege drift;
- attempted privilege escalation to the PostgreSQL administrator role;
- attempted migration-history read;
- attempted ordinary DELETE;
- attempted object creation inside the application schema;
- cross-owner scope reads;
- transaction-local scope clearing.

## Configuration boundary

The runtime module does not read:

- `DATABASE_URL`;
- process environment variables;
- Render configuration;
- Streamlit secrets;
- passwords;
- provider secret managers.

It accepts only an injected connection factory.

Production configuration/secret resolution remains a separate composition
boundary.

## Explicitly absent

This stage does not:

- authenticate to Render;
- create a provider database;
- create a production application user;
- resolve or store a production password;
- prove private Render networking;
- prove TLS;
- apply a production migration;
- run provider backup/PITR;
- deploy AtlasQuant;
- activate Global Worker;
- execute external actions;
- mutate Core V1.

The disposable CI service uses loopback with `sslmode=disable`; this is not
evidence for production TLS.

## Maximum truthful state

After the dedicated workflow and broad main-target gates are green:

`DIRECT_APP_ROLE_POSTGRES_BINDING_VALIDATED_IN_CI`

This does not mean production persistence is ready.

## Remaining external boundary

When the HUMAN_OWNER is at the computer, the production-only sequence remains:

1. authenticate to Render;
2. inspect current workspace/resources;
3. verify exact current plan price and region;
4. pass the production preflight;
5. provision only after the price decision;
6. require private networking and TLS;
7. create a dedicated least-privilege application login and separate migration/admin identity;
8. inject secrets outside the store;
9. apply the frozen migration in isolation;
10. attest direct application login, RLS, health and audit;
11. verify backup/PITR and perform a restore drill;
12. keep deployment as a separate authorization.
