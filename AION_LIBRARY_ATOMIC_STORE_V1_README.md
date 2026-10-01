# AION Biblioteca — atomic document / approval / audit store (sandbox V1)

**STATUS: EXPERIMENTAL, DRAFT ONLY.** Stack: #473 → #476 → #478 → #479 → #480 → #481 → new atomic PR. No merge, deploy, migration, real PDF ingestion, external client access or modification to the Business ledger (#472).

## Why this new isolated component

The previous PostgreSQL `SharedApprovalBurnPort` can reserve an approval ID transactionally, but the real document state lives in the old in-memory catalog and the audit log is separate. A crash between these steps strands approval and state. This package adds a new **independent** PostgreSQL DB-API *port*: `AtomicLibraryStore`. It does **not** replace or silently connect to the existing gateway. It imports previously reviewed records only from the trusted host, then executes approval-nonce burn, conditional document-state update and linked audit append in **one database transaction**, committing only if all operations succeed.

- Server-owned fresh DB-API PostgreSQL connection factory, `autocommit=False`; runtime never runs DDL. Sample privileged migration `MIGRATION_POSTGRESQL` declares three Library-exclusive tables.
- Per-document `SELECT ... FOR UPDATE`, signed identity, signed human approval and independent signed rights attestation matching tenant/domain/document/version/full content digest/license/usage/reviewer; reject missing evidence, expired proofs, incorrect role, cross-tenant requests and `ALL_RIGHTS_RESERVED`.
- Re-verifies all attestations **after acquiring the DB row lock** in case they expired or were revoked while awaiting a lock.
- Missing genesis, mismatched/tampered audit genesis, duplicate nonce or any DB error: **ROLLBACK everything and deny**. Opaque SHA-256 approval identity stored instead of raw tokens. Audit links `prev_hash` → `event_hash` across genesis and approval.
- Approval returns only a receipt of the committed new state; no indexing of document contents, no privileged tool execution, no HTTP routes.

## Evidence

- Offline local: 233 existing tests + **30 new** SQLite-backed DB-API simulation tests = **263 / 263**. Python compilation passed. `PYTHONWARNINGS=error::ResourceWarning`.
- Separate `test_aion_core_library_atomic_pg.py` defines **five real PostgreSQL integration tests** (atomic commit, concurrent workers, fail-after-state-update rollback, wrong tenant, duplicate after fresh connection). They **skip** unless `AION_LIB_TEST_PG_DSN` is set and `psycopg` installed.
- New read-only GitHub Actions workflow provisions an **ephemeral local PostgreSQL 16 service** and installs pinned `psycopg[binary]==3.2.10` only inside isolated CI. It runs these tests against the real PostgreSQL wire protocol. An ephemeral, plainly named *synthetic CI-only* password is never production authentication.

## Critical prerequisites before production

1. This is a trusted-server-only storage contract; the existing `AuthenticatedLibraryService` in #480 still uses **SQLite**. The new atomic port is deliberately **not connected** to app routes, raw catalogs or indexers. Integration, migration and cutover require dedicated approval and E2E tests.
2. `ExternalIdentityBridge` has an abstract host callback, not a real cryptographic OIDC/JWKS/FIDO2 integration. Production IdP, roles, signed decisions and source-of-authority for rights must be separately configured and audited. HMAC signatures show at best that a configured **issuer** signed data; they cannot establish lawful document usage or non-repudiable personal consent.
3. `import_reviewed` is a *host-only migration interface* and trusts the source catalog; never expose it to an external caller. Persist and validate the pre-import editorial review/consent lifecycle and use DB-side principal separation.
4. SHA-256 audit chaining **is not independent tamper proof** if a DB administrator can edit and recompute the entire chain. Deploy a restricted append-only audit writer and externally signed checkpoints/verifiable offsite storage before claiming tamper evidence. Migrate/revoke keys and rights.
5. Real sandbox PostgreSQL CI is not an end-to-end test of high availability, primary failover, multi-region replicas, DDL migration safety, retention/LGPD deletion, load, disaster recovery or database permissions. Explicit review by security and legal owners remains required.
6. Avoid turning any optional environment variable or debug pathway into an authentication bypass. Do not use actual customer documents or live credentials in tests.