# AION Biblioteca — shared approval PostgreSQL port V1 (SANDBOX)

This is an *unconfigured*, offline tested PostgreSQL DB-API **storage port**, stacked on draft PR #480. No PostgreSQL connection was established; no cloud credentials, real identity tokens, customer information, migrations or production services were used. **Do not merge/deploy** without a separate scoped authorization from Mikael and a security review.

## Implemented

- `aion_core/library_shared_approval_port.py` supplies `SharedApprovalBurnPort`. It accepts only a **host-owned, fixed** connection factory returning a new PostgreSQL DB-API connection configured with `autocommit=False`; no dynamic SQL or arbitrary table/schema identifiers are accepted.
- A unique opaque SHA-256 identifier of `(issuer, approval_id)` is inserted with `INSERT ... ON CONFLICT DO NOTHING RETURNING`, then explicitly committed. A duplicate, missing schema, connection failure, absent transaction settings or invalid inputs **deny** the operation.
- The port enforces at-most-once reuse only when all workers use the **same PostgreSQL writable primary**, all callers use this port, migrations are installed and database durability/availability are managed by the host. Merely placing this file in the app does not enforce these assumptions.
- `MIGRATION_POSTGRESQL` is an explicit, separate DDL artifact. The module **does not auto-migrate** or write to AION Business ledgers. Runtime credentials should be restricted to required actions on the separate AION Library table only. Never send or log raw user tokens, keys or document bytes.
- `test_aion_core_library_shared_approval_port.py` contains 28 sandbox tests. The database adapter uses temporary SQLite solely to simulate the SQL and DB-API contract, including concurrency and replay across multiple instances/reinitialization. **This is not equivalent to an integration test against PostgreSQL.**

## Why this is NOT a production integration

1. **No PostgreSQL host / real IdP configured.** No real OIDC JWKS signature validation, token revocation, trusted tenant membership or verified rights-provider adapter has been performed here. The bridge in #480 is only an interface.
2. This port commits only the **approval burn**. The document catalog in the upstream PRs remains in memory; burn and document-state transition are **NOT atomic together**. A crash after burn requires a newly issued, explicitly confirmed approval. A complete shared document + decision + audit transaction is a separate future design.
3. Revoked rights, user membership and signing keys require live trusted lookups/revocation before every action. Token freshness by itself is insufficient.
4. Raw `LibraryCatalog`, `SecuredLibraryBoundary` and the synthetic attestation issuer must remain inaccessible to external clients. All real app routes must enforce trusted middleware, strict RBAC, document/tenant scoping, a real rights authority and an admin-signed decision.
5. Before any real integration, independently review transaction isolation, privilege grants, TLS, connection pooling/rollback, row-level tenancy for persisted document state, backups, audit integrity, disaster recovery and concurrent PostgreSQL test results. Do not treat SQLite tests as evidence of these production properties.

## Developer usage (reference only)

```python
# Server-only composition after establishing the approved Postgres configuration.
# `trusted_postgres_connect` must be an operator-owned, independently validated
# connection factory; it must NOT be derived from a client request.
from aion_core.library_shared_approval_port import SharedApprovalBurnPort

approval_burns = SharedApprovalBurnPort(connect=trusted_postgres_connect)
# Call `burn` only after the existing trusted gateway verifies signed identity,
# signed human approval, legal rights grant, document SHA/version and scope.
# Do not replace the upstream gateway until transactional document state exists.
```

`trusted_postgres_connect` above is a documentation placeholder, not provided code; running this snippet without a trusted server adapter is intentionally impossible.

## Local tests

```bash
PYTHONWARNINGS=error::ResourceWarning python -m unittest -q \
  test_aion_core_domain_registry test_aion_core_evidence_pack \
  test_aion_core_memory_architecture test_aion_core_provenance \
  test_aion_core_security_audit test_aion_core_trust_engine \
  test_aion_core_library_foundation test_aion_core_library_guard_contract \
  test_aion_core_library_authorization test_aion_core_library_security_runtime \
  test_aion_core_library_shared_approval_port
```

Local baseline: **205 upstream + 28 new = 233 passing**. Remote GitHub CI has to verify the pushed commit separately. Existing stack #473 → #476 → #478 → #479 → #480, all draft; Business ledger #472 remains independent.