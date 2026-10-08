# AION Chat — TLS Direct App Role CI V1

Status: IMPLEMENTATION SAFE / CI-ONLY  
Date: 2026-10-07  
Depends on: #1004 direct application-role PostgreSQL login  
Runtime target: disposable PostgreSQL 17 only

## Purpose

Strengthen the production-like PostgreSQL path by proving that the application
identity connects directly over a verified TLS session.

The earlier direct-role stage proved least-privilege authentication. This stage
adds transport requirements:

- TCP only;
- TLS required;
- client policy must be `sslmode=verify-full`;
- a CA root must be explicitly provided;
- hostname verification must pass;
- live PostgreSQL transport must report SSL enabled with a non-empty TLS version
  and cipher;
- plaintext TCP must be rejected by the PostgreSQL host authentication policy.

## Disposable TLS setup

GitHub Actions generates a one-day CI root CA and a one-day server certificate
for `localhost`.

The PostgreSQL 17 service is reconfigured inside the disposable job to:

- enable SSL;
- use the generated server certificate/key;
- accept TCP database authentication only through `hostssl`;
- reject matching plaintext TCP before any broader default host rules.

The CA and private keys exist only inside the disposable Actions job. They are
not production credentials and are never committed to the repository.

## Runtime boundary

The TLS backend still accepts only an injected connection factory.

It does not read:

- DATABASE_URL;
- environment variables;
- Render configuration;
- Streamlit secrets;
- provider secret stores;
- passwords.

Before returning a connection to the store, it verifies:

1. the direct application identity is still proven;
2. libpq/psycopg reports client `sslmode=verify-full`;
3. an explicit `sslrootcert` is present in the effective connection
   parameters;
4. `pg_stat_ssl` reports `ssl = true`;
5. TLS version is non-empty;
6. cipher is non-empty;
7. the session is TCP, not a Unix socket.

Failure in any check closes the connection and fails the storage health gate.

## Negative evidence

The dedicated tests prove:

- `sslmode=disable` is rejected by the PostgreSQL server;
- `sslmode=require` is rejected by the AION Chat backend even though the
  transport may still be encrypted, because certificate/hostname verification
  is not proven;
- `verify-full` with a hostname mismatch is rejected;
- the frozen migration/schema candidate remains unchanged;
- direct least-privilege identity, RLS, audit receipts, scope isolation and
  normal store writes remain functional over the verified TLS connection.

## Important production distinction

This CI stage does **not** claim that Render's real private connection or real
certificate chain has been tested.

It proves the client/store behavior that future production composition must
satisfy.

Production still requires fresh provider evidence for:

- private/internal endpoint;
- provider certificate chain and hostname;
- exact TLS connection configuration;
- least-privilege production application identity;
- separate migration/admin identity;
- secret injection outside repository/store code.

## Explicitly absent

This stage does not:

- log into Render;
- provision a database;
- resolve a production DSN/password;
- create a paid resource;
- apply a production migration;
- test provider PITR;
- deploy AtlasQuant;
- activate Global Worker;
- execute external actions;
- mutate Core V1.

## Frozen schema candidate

The candidate remains:

- migration version: 1;
- SHA-256:
  `7dd72d75365862f54c81110027430011f8ac8f81ce629f500cbbd9aa0c00c50c`.

This stage must not modify migration 0001.

## Maximum truthful state

After dedicated TLS CI and main-target repository gates are green:

`TLS_DIRECT_APP_ROLE_POSTGRES_BINDING_VALIDATED_IN_CI`

This is not production persistence readiness.

## Remaining external boundary

When the HUMAN_OWNER returns to the computer:

1. authenticate to Render;
2. verify current plan, price and app region;
3. pass the production preflight;
4. provision within the approved cost ceiling;
5. require private networking;
6. configure verified provider TLS;
7. create separate least-privilege application and migration identities;
8. inject credentials through an approved secret boundary;
9. apply the frozen migration;
10. attest the real connection, scope, RLS, audit, backup and recovery evidence;
11. keep deploy as a separate authorization.
