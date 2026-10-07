# AION Chat — Ephemeral Postgres CI Integration Contract V1

## Purpose

Define an isolated PostgreSQL integration-test boundary that can validate the
real Psycopg binding without touching Render Postgres or any production
credential.

This contract is design/CI-only and opens no database connection.

## Allowed environment

Only CI is allowed.

Future implementation may use a GitHub Actions PostgreSQL service container or
another job-local ephemeral database with:

- no persistent volume;
- database recreated per job;
- loopback or CI-service networking only;
- test-only credentials scoped to the job;
- no platform production secret;
- no production DSN;
- no Render endpoint.

## Evidence that CI may prove

- Psycopg connection behavior;
- transaction commit/rollback;
- schema compatibility mechanics;
- scope isolation;
- idempotency/unique constraints;
- unknown-commit/reconciliation handling where simulatable.

## Evidence that CI must never claim

- production network readiness;
- Render private-network readiness;
- production TLS attestation;
- backup/PITR restore readiness;
- production credential readiness;
- production storage attestation.

CI evidence is always labeled non-production.

## Maximum state

`READY_FOR_EPHEMERAL_POSTGRES_CI_IMPLEMENTATION_REVIEW`

## Next allowed step

`IMPLEMENT_EPHEMERAL_POSTGRES_CI_HARNESS`

That implementation may start an ephemeral PostgreSQL service inside CI only.
It must not use production credentials, persistent volumes, Render endpoints,
deploy, Worker, provider/model calls or Core writes.
