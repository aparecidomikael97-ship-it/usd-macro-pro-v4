# AION Chat — Render Production PostgreSQL Composition V1

Status: IMPLEMENTATION SAFE / ACTIVATION OFF BY DEFAULT  
Date: 2026-10-07  
Depends on: PostgreSQL schema candidate + direct app-role + TLS + migration identity lifecycle evidence  
Deployment status: NOT DEPLOYED by this change

## Purpose

Bind the reviewed AION Chat PostgreSQL store to host-injected Render
configuration without giving the storage layer authority to discover secrets,
run migrations, deploy AtlasQuant, arm Workers, or mutate Core V1.

Production persistence remains disabled unless the explicit activation flag is
set to true by the trusted host configuration.

## Required host-injected values

The composition accepts only the following approved values:

- `AION_CHAT_PG_HOST`
- `AION_CHAT_PG_PORT`
- `AION_CHAT_PG_DATABASE`
- `AION_CHAT_PG_USER`
- `AION_CHAT_PG_PASSWORD`
- `AION_CHAT_PG_SSLMODE`
- `AION_CHAT_CURSOR_SIGNING_KEY`
- `AION_CHAT_PRODUCTION_PERSISTENCE_ENABLED`

The backend itself does not read environment variables, Streamlit secrets,
provider secret stores, or DATABASE_URL.

## Fixed production identity contract

The only accepted runtime database identity is:

`aion_chat_app`

The only accepted production database is:

`atlasquant_aion_chat_prod`

The expected port is:

`5432`

TLS modes accepted by the composition are:

- `require`
- `verify-ca`
- `verify-full`

The current Render private-network production configuration uses `require`.
The backend additionally verifies that the live PostgreSQL session reports SSL
enabled, a non-empty TLS version, a non-empty cipher, and TCP transport.

## Activation gate

`AION_CHAT_PRODUCTION_PERSISTENCE_ENABLED` is false by default.

Even when all connection values exist, no production store may be constructed
while the activation flag is false.

This allows configuration and code to be prepared and reviewed before a
separate activation/deploy decision.

## Cursor signing key

The HMAC cursor signing key is independent from the PostgreSQL password.

It must:

- be injected by the trusted host;
- contain at least 32 bytes;
- remain stable across process restarts;
- never be derived from the database password;
- never be persisted in chat rows;
- never be emitted in health evidence.

## Runtime health gate

Before the production store is considered usable, health must prove:

- direct session/current identity is `aion_chat_app`;
- no SUPERUSER;
- no CREATEDB;
- no CREATEROLE;
- no REPLICATION;
- no BYPASSRLS;
- TLS is active;
- schema version is compatible;
- required constraints exist;
- forced RLS is present;
- required RLS policies exist;
- schema CREATE is denied;
- database CREATE is denied;
- migration-history SELECT is denied;
- `schema_meta` is read-only;
- conversations have SELECT/INSERT/UPDATE but no DELETE;
- messages/idempotency/attachments/checkpoints/summaries/audit are append-only
  under the normal application identity.

Any failure returns a failed health state and prevents store activation.

## Audit

Production mutations preserve the reviewed content-free atomic audit receipts.

Audit evidence never includes:

- message body;
- conversation title;
- attachment name;
- password;
- token;
- DSN;
- provider secret.

## Migration boundary

This module cannot:

- use `aion_chat_migrator`;
- create or alter roles;
- grant database CREATE;
- execute schema migrations;
- reactivate a sealed migration identity.

Migration administration remains a separate protected boundary.

## Current operator boundary

The Render Environment values may be stored before deployment using
configuration-only save behavior.

Saving those variables does not, by itself, activate the production store.

Before any deployment/activation, the remaining configuration item is a stable
cursor-signing key. The activation flag must remain false until the complete
host binding and main-target CI gates are green and the HUMAN_OWNER separately
authorizes deployment/activation.

## Maximum truthful state

After dedicated CI is green, this branch may claim only:

`RENDER_PRODUCTION_POSTGRES_COMPOSITION_VALIDATED_IN_CI`

It must not claim:

- production application is using PostgreSQL;
- environment variables were deployed;
- production persistence is active;
- Worker is active;
- public deploy happened;
- Core V1 changed.
