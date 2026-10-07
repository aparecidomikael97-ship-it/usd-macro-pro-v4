# AION Chat — Postgres Driver Binding V1 (No Production Credentials)

## Purpose

Install and verify the real Psycopg driver while keeping the entire binding
incapable of opening a database connection.

This is an implementation step beyond the design contract in #987, but it is
still non-production and non-network.

## Dependency

Pinned dependency:

`psycopg[binary]==3.3.6`

The repository Security Gate installs `requirements.txt`, runs `pip check`,
audits dependencies with `pip-audit`, and generates a CycloneDX SBOM.

## Safety boundary

The binding:

- accepts only LOCAL / TEST / CI environments;
- rejects PRODUCTION;
- accepts only a secret **reference**, never DSN/password material;
- requires INTERNAL_PRIVATE endpoint class;
- requires TLS mode REQUIRE;
- keeps autocommit disabled;
- bounds connect and statement timeouts;
- exposes only secret-free connection kwargs;
- has no environment-variable reader;
- has no DATABASE_URL usage;
- has no psycopg.connect call;
- deliberately raises NetworkDisabledError from connect().

## Why import the real driver now

This proves:

- dependency resolution;
- Python compatibility;
- security audit compatibility;
- package importability;
- deterministic version pinning.

It does not prove network connectivity and does not authorize it.

## Next allowed step

`DESIGN_NONPRODUCTION_POSTGRES_INTEGRATION_TEST_CONTRACT`

That future design may define an ephemeral/local integration test, but it must
still exclude production credentials, production databases, deploy and Worker.
