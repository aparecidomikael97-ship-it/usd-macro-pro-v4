# AION Biblioteca — actual app browser + PostgreSQL in one synthetic CI cycle

Scope: issue #495, stacked on Draft PR #494. **Not a production UI or endpoint.**
Three new files under scripts/ provide a CI-only sandbox exercise. The existing
AtlasQuant application source, Streamlit admin source, normal Library shell,
business ledger, main branch, and production workflows are unchanged.

The special **test runner** provisions a *fixed localhost, synthetic* PostgreSQL
16 service using its own owner credential. It creates a fictitious metadata-only
entry (no PDF bytes), an ADMIN tenant/domain grant, and two independent SELECT-only
roles for ACL vs document/audit inspection. It then launches the actual unmodified
AtlasQuant app via a separate **test-only Streamlit wrapper** bound to 127.0.0.1.
That wrapper patches one imported Library render function **in memory**, only
after explicit CI/SANDBOX flags and actual AtlasQuant login are enforced. There
is no deployable route, no changes to business logic, and no database owner DSN
in the child app's allowlisted environment.

The UI overlay is intentionally limited to state, version, and boolean integrity.
The ID, content digest, document bytes, raw audit, database messages, and signing
material are NEVER intentionally displayed. A fixed host-only selector is
injected in the child environment; browser URL/query state or UI does not select
tenant, document or role. The role/ACL and signed synthetic approval are checked
by inherited backend code on each request.

## Browser proof (CI workflow)
- Android 390: genuine ADMIN login and review-only metadata display before approval.
- Android 390: ordinary USER login gets no admin Library area.
- Desktop 1440: genuine ADMIN login and review metadata.
- Runner-only approval writes a fictitious signed decision. The **same desktop
  authenticated browser session** navigates away and back; PostgreSQL returns
  APPROVED_FOR_INDEXING metadata.
- Runner revokes that ADMIN's PostgreSQL membership. The same browser session
  navigates back: the test overlay now returns a uniform denial with no metadata.
- Separate app restart with feature flag OFF proves the Library option is hidden.
- Reader roles independently fail an SQL UPDATE check.
- The same workflow job also executes the existing 10 full-chain and 8 server
  selection PostgreSQL adversarial cases (mid-inspection revocation/tampered audit,
  cross-tenant, flag change, host selector mutation, and denied writes). Those
  negatives are backend tests, **not** browser-driven scenarios; do not conflate.

This wrapper is an **instrumented browser test**, not evidence that the unmodified
production Streamlit route has been connected to PostgreSQL. Only the synthetic
CI child process performs test overlay reads. Before real enablement: independent
security review of future live host binding, explicit external rights/license
verification, external key custody, administration of production ACL/migrations,
offsite disaster recovery/PITR, validated complete CI on an authorized main-based
candidate and Mikael's separate explicit approval. No automated merge or deploy.
