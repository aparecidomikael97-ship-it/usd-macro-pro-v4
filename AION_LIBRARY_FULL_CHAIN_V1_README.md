# AION Biblioteca — host-selection + full-chain PostgreSQL16 sandbox V1

**Status:** sandbox, draft only. No Streamlit/API route, no production database or customer data, no new approvals, no migrations outside CI, no merge/deploy authorization. Stacks on PR #491; checkpoint belongs to issue #477.

## Goal
Create one **host-owned selection boundary** that calls PR #491's server assembly, with a server-held selector resolving aliases to tenant/domain/entry and no browser-supplied scope. For every request the existing assembly revalidates the real AtlasQuant login, the separate PostgreSQL ACL (fresh transaction) and the canonical PostgreSQL document audit; the new boundary checks that the selected target remains unchanged during the call. It returns only `selection`, `state`, `version`, `integrity_checked`, never document bytes, rights metadata, audit hashes or identity material.

## Source / evidence
- `atlasquant_aion_library_internal_entry.py`: private `TrustedLibraryAppSelection` and immutable allowlisted DTO; no remote endpoint, no widget, no new keys/connections.
- `test_atlasquant_aion_library_internal_entry.py`: 10 synthetic offline tests including disallowed/changed/removed selections, invalid backend response, non-leaking failures and no cache.
- `test_atlasquant_aion_library_fullchain_pg.py`: **10 opt-in real ephemeral PostgreSQL16 tests** using exactly the expected local CI DSN and explicit `CI=true`, `AION_LIB_FULL_CHAIN_TEST=1`. These integrate the actual `atlasquant_access_control` password hash/session, host composition, reader-only PG ACL, restricted document PG connection, trusted synthetic metadata import/approval and full audit verification. Cases include review-state restriction, explicit scoped reviewer, approved reader, cross-tenant with otherwise valid ACL, grant/revoke across two service instances, credential rotation, audit tamper, flag switched off during DB access, and actual SELECT-only DB role write denial. All users/documents/keys/passwords are synthetic and ephemeral.
- Modified in **new PR only**: isolated AION Library tests, Quality suite, and ephemeral PG workflow. The PG workflow runs new integration tests **after** prior atomic/recovery, native preview, ACL and logical-restore suites.

## Hard restrictions
1. `TrustedLibraryAppSelection` must be created **only by privileged host startup** with the exact `SandboxLibraryServerReadAssembly` and a protected server-owned `resolve_selection()` callback. It is NOT allowed to pass browser/session-state maps or user-supplied tenant/domain IDs directly into it; NEVER expose the object or its constructor to prompt-controlled code, endpoints or clients.
2. Neither this package nor PR #491 mounts any real route or enables the shell: the UI stays static/hidden by default. A real application route requires separately reviewed server-owned dependency injection, DB secrets from managed storage, SEL-only grants in a controlled environment, external authorizations and browser+PG E2E in one test.
3. CI-only DDL/truncation and fixed synthetic PostgreSQL reader credentials MUST NEVER be copied to runtime. Local run of new PG test **skips** unless the three exact CI guards are present. The dedicated reader role only has `SELECT` over 4 specific tables and no mutation rights.
4. This test asserts integration under synthetic conditions. It does not prove production DB migrations, independently verified legal licenses/rights, backup PITR/DR, security review, external identity/SSO or ongoing authorization after response delivery.

**Governance:** all Library PRs remain Draft; do not modify Business ledger #472, `main` or production. AION English issue #483 remains a separate approved roadmap entry.
