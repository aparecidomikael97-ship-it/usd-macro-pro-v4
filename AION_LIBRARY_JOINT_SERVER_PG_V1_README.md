# AION Biblioteca — server-bound selection + PostgreSQL joint sandbox V1

**Date:** 2026-10-01. Follow-on to the draft PR #491 under tracking issue #477.

This incremental sandbox block makes one narrow architectural improvement: a
`SandboxServerSelectedRead` object holds a **server-owned, immutable-at-call
selection**, not a tenant/domain/entry ID chosen in the browser. It accepts
only an exact server-injected `SandboxLibraryServerReadAssembly`, validates a
3-tuple of bounded IDs *before and after* the read, verifies the returned
minimal `LibraryPanelPreview`, and converts errors into a uniform denial.
It does **not** expose an API, a Streamlit widget, or document bytes.

## Tests

* `test_atlasquant_aion_library_server_selection.py`: 13 new local selector
  contracts; the standalone local run uses lightweight test doubles for the
  inherited auth, preview, and assembly types. The full GitHub repository CI
  must rerun against the real inherited classes.
* `test_atlasquant_aion_library_server_selection_pg.py`: 8 new tests against
  ephemeral **PostgreSQL 16 only** with the exact fixed `localhost` synthetic
  DSN, `CI=true` and `AION_LIB_JOINT_E2E=1`. The test runs the actual native
  login PBKDF2, server assembly, per-tenant ACL queries, atomic review and
  approval, and read-only audit inspection **together**. Distinct DB roles
  have ACL-only SELECT vs document/audit-only SELECT; privileged fixture
  creation/approval uses the ephemeral CI owner only. Tests deny cross-tenant
  inspection, stale/revoked membership, mismatched state, tampered audit,
  server-side selection changed mid-request and sandbox flag changes.

## Explicit limitations

* Signed approval/license materials in tests are synthetic fixtures. No legal
  rights have been verified and no production data have been accessed.
* The selection provider, login registry, signing keys and SQL connections
  are **injected by a trusted server**. This module does not prove the eventual
  live application's dependency injection protects them from clients.
* A correct database snapshot and ACL check cannot protect against a revocation
  or database update **after the response**. Server-side check per request is
  required; never cache an accepted session, ACL, or result.
* The Streamlit library shell remains static/off by default. The joint test
  exercises the internal backend end to end; it does not combine an interactive
  real-app browser with the SQL test in the same run.
* No main change, migration outside ephemeral CI, merge, deployment, actual
  document ingestion, or publication is authorized by this block. Preserve
  the Business ledger PR #472 and the independent AION English issue #483.

Before any real document preview, require independent security review,
authorized administrative provisioning, restricted database credentials,
rights verification, a real external checkpoint, disaster recovery, and a
separate browser-to-PostgreSQL E2E in isolated staging.
