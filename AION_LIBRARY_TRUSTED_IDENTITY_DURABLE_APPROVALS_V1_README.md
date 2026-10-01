# AION Biblioteca — Trusted Identity Bridge + Durable Approval Burn (sandbox V1)

**State:** independent offline security contract, stacked on the Library authorization sandbox PR #479. NOT a production IdP, application authentication, consent/rights verification, or a distributed authorization ledger. No service is enabled, no customer data is ingested and the Business ledger is untouched.

## Added files

- `aion_core/library_security_runtime.py`: three scoped server-side components:
  1. `ExternalIdentityBridge`: accepts only a **host-owned trusted** token verification callable and server-owned tenant/domain membership lookup. Generates short-lived HMAC identity attestations compatible with the existing `AttestationVerifier` only after both callables succeed. Token-submitted roles are never trusted.
  2. `SqliteApprovalBurnLedger`: a single-host SQLite record for at-most-once approval IDs. Signed approvals are burned in an ACID SQLite transaction **before** changing the in-memory catalog, so a crash cannot permit use of that ID after restart on the same database. Duplicates are rejected concurrently using a primary key and `BEGIN IMMEDIATE`. Stores a one-way identifier key and digest, not tokens, signatures or source contents. Distinct from all AION Business ledgers.
  3. `AuthenticatedLibraryService` + `DurableLibraryApprovalGateway`: compose identity, signed human approval, signed rights, tenant/domain/role validation and the durable approval burn. `READ` also goes through server-side membership checks.
- `test_aion_core_library_security_runtime.py`: 39 additional offline tests including identity verification/expiry/issuer/audience, roles from trusted membership, scope mismatch, bad signatures, rights mismatch, at-most-once use after reopen, concurrency, inaccessible/corrupt ledger, crash-before-transition, and facade routing.

## Local evidence

- Existing 166 tests + 39 new tests = **205/205 passed** via `python -m unittest -q ...` using Python stdlib.
- `compileall` passed. `ResourceWarning` configured as errors during the complete suite run.
- Only synthetic signing keys and fake trusted external callbacks used in tests. No API/provider access or paid dependencies.

## Crucial production blocks (fail closed)

1. `verify_token` is an **adapter contract**, not an actual implementation of signed OIDC/JWKS/nonce/PKCE/session validation. A trusted host MUST implement that correctly against a selected IdP; only an authenticated host may construct the bridge and own its HMAC signing keys.
2. `lookup_roles` must read permissions from a trusted server-side RBAC source; never accept a role list from the requesting client. A token may map to more than one tenant only as explicitly granted by the RBAC source.
3. `SecuredLibraryBoundary` and `LibraryCatalog` remain directly callable in Python; before any real routes exist the host must make them inaccessible to external clients and use only the authenticated facade.
4. This SQLite ledger protects **one local host sharing one trustworthy DB file** only. It does not cover multiple servers, network filesystems, independent backups or a distributed rollout. Use shared transactional storage and authorization design before production.
5. Approval burn is committed **before** in-memory document transition. A crash or downstream error after burn may strand an approval and require fresh human review. That intentionally favors no replay over availability. Catalog state, rights revocation and audit events are NOT transactionally persisted by this module.
6. Legal rights grants in upstream signed attestations depend on independent verification of the granting authority, licensed usage, expiry and revocation. HMAC authenticity of a claimed grant cannot establish legality by itself.
7. Implement hardening of files and database ownership, tamper-evident audit, admin-visible recovery and backup procedures, key rotation/revocation, secure IdP integration, real E2E tests and security review before requesting merge or deployment.
8. No Windows Hello/FIDO2, biometric approval, cryptographic non-repudiation or silent automatic approval is implemented. Actual critical actions will continue to require explicit Mikael authorization.

## Local test command

```bash
python -m unittest -q \
  test_aion_core_domain_registry test_aion_core_evidence_pack \
  test_aion_core_memory_architecture test_aion_core_provenance \
  test_aion_core_security_audit test_aion_core_trust_engine \
  test_aion_core_library_foundation test_aion_core_library_guard_contract \
  test_aion_core_library_authorization test_aion_core_library_security_runtime
```

**Dependency order:** #473 (AION Core) → #476 (Library catalog) → #478 (scope guards) → #479 (signed attestation contract) → this draft PR. The separate Business ledger #472 is unaffected.
