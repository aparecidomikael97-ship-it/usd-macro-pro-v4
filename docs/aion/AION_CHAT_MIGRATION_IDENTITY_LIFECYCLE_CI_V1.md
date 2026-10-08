# AION Chat — Migration Identity Lifecycle CI V1

Status: IMPLEMENTATION SAFE / CI-ONLY  
Date: 2026-10-07  
Depends on: #1006 verified TLS direct application-role PostgreSQL binding  
Runtime target: disposable PostgreSQL 17 only

## Purpose

Separate migration authority from normal AION Chat runtime authority.

This stage proves that the reviewed migration can be applied through a
short-lived, directly authenticated PostgreSQL migration identity over verified
TLS, then that identity can be sealed so it is no longer a standing login.

The application identity remains separate and continues to operate after the
migration identity is sealed.

## Migration identity

Disposable CI role:

`aion_chat_migrator_ci_login`

Required cluster posture while active:

- LOGIN;
- NOSUPERUSER;
- NOCREATEDB;
- NOCREATEROLE;
- NOINHERIT;
- NOREPLICATION;
- NOBYPASSRLS.

The role receives temporary database-level CREATE only so it can create the
reviewed application schema during the initial migration.

It does not receive server-superuser authority.

## Transport

The migration connection is attested before it is returned to the migration
runner.

It must prove:

- `session_user = current_user = aion_chat_migrator_ci_login`;
- direct login, not role switching;
- client `sslmode=verify-full`;
- explicit CA root;
- live TCP connection;
- live PostgreSQL TLS with non-empty version and cipher;
- least-privilege cluster role flags.

Failure closes the connection and fails closed.

## Migration

The existing reviewed migration runner is used unchanged.

Candidate migration remains:

- version: 1;
- path: `migrations/aion_chat_postgres_v1/0001_initial.sql`;
- SHA-256:
  `7dd72d75365862f54c81110027430011f8ac8f81ce629f500cbbd9aa0c00c50c`.

The migration role becomes owner of the application schema/tables because it
executes the reviewed DDL directly.

## Post-migration seal

After migration and migration-health attestation:

1. database CREATE is revoked from the migration identity;
2. LOGIN is disabled;
3. the role remains owner of the reviewed schema/tables;
4. new connections using its credential are rejected.

This removes standing migration login authority while preserving ownership
needed for a future separately authorized migration lifecycle.

Reactivation for any future migration is outside normal application runtime and
requires an explicit protected administration step.

## Runtime separation

After the migration identity is sealed, a different application identity is
created with only the reviewed runtime grants.

The CI proves that the application can still:

- connect directly over verify-full TLS;
- pass forced-RLS health;
- create conversations/messages;
- produce atomic content-free audit receipts.

The application identity cannot:

- create schema objects;
- read migration history;
- use migration authority.

## Important production distinction

This stage does not define how Render will create or rotate real credentials.

It proves the identity lifecycle that production provisioning should reproduce:

- separate migration identity;
- short-lived login window;
- verified TLS;
- no superuser;
- application role separate from migration role;
- revoke database CREATE after initial schema creation;
- disable migration LOGIN when migration is complete.

## Explicitly absent

This stage does not:

- log into Render;
- create a production database;
- create production credentials;
- read provider secrets;
- charge money;
- apply a production migration;
- deploy AtlasQuant;
- activate Global Worker;
- execute external actions;
- mutate Core V1.

## Maximum truthful state

After dedicated CI and broad main-target gates are green:

`MIGRATION_IDENTITY_LIFECYCLE_VALIDATED_IN_CI`

This is not production persistence readiness.

## Remaining external boundary

When the HUMAN_OWNER is at the computer:

1. authenticate to Render;
2. verify plan, exact price and app region;
3. pass the production preflight;
4. provision private PostgreSQL;
5. verify provider TLS;
6. reproduce separate application/migration identities;
7. inject secrets outside repository/store code;
8. run the protected migration through the migration identity;
9. seal that identity after successful attestation;
10. verify backups/PITR and restore;
11. keep application deployment as a separate authorization.
