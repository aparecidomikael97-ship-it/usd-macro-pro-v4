# AION Biblioteca — trusted host composition sandbox V1

This module combines the *existing local AtlasQuant session*, **fresh persisted PostgreSQL tenant/domain ACL** from Draft #489 and **authoritative PostgreSQL integrity reader** from Draft #487. It does not create or mount an application or public route, enable uploads, index PDFs or grant/revoke users. It is a trusted-host-only assembly contract for later integration.

`SandboxLibraryServerReadAssembly` requires explicitly injected dynamic (live) providers: `environment_provider`, `enabled_provider`, `access_provider`, `users_provider`, SELECT-only `acl_connect` and SELECT-only `document_connect`, plus an external trusted `AttestationVerifier`, independent identity and checkpoint signing keys, and issuer/audience names. There are **no built-in passwords, network targets, keys, memberships, grants or fallbacks**.

The assembly fails closed unless the current host environment is **exactly** `SANDBOX` and an opt-in provider returns boolean `True`. It checks both at assembly, immediately before each read, and immediately after the read, so that a flag/environment switch during PostgreSQL inspection discards the response. On every read the #487 facade checks session and tenant ACL both before and after the #484 PostgreSQL integrity check. The ACL #489 opens a fresh read-only transaction per membership lookup.

This remains a sandbox **contract**, NOT the production login/IdP, not a public endpoint, and does not cryptographically distinguish a falsely supplied host callback. Actual Streamlit integration must inject callbacks exclusively from trusted server state, use a primary PostgreSQL database with restricted roles and no replica lag, rotate and segregate secrets, log access and revocation to durable audit, confirm licensing and prove full app + DB browser E2E. No real data is exercised here.

Testing: `test_atlasquant_aion_library_server_assembly.py` runs 20 adversarial tests with mocked database interfaces, while the actual PostgreSQL ACL and document tests remain covered by the earlier Drafts #482–#489. The complete suite must pass on the GitHub branch before the new PR is considered validated. Neither this module nor the static shell should be used to expose document content.

No user approval of merge/deploy/data ingestion is assumed by continuation work; keep the entire stack Draft and issue #477 open.
