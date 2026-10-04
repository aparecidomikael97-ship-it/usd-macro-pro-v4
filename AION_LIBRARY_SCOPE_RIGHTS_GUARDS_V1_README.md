# AION Library Scope & Rights Guardrails V1 — isolated follow-up

This patch is a **sandbox guardrail**, **not** authentication or production-ready licensing.

- `LibraryCatalog.transition` and `find_by_entry_id` now require explicit `tenant_id` and `domain_id` and reject mismatched scope. Tenant/domain identifiers are normalized only within a strict character allowlist; a caller must not treat the scope strings as verified identity.
- `APPROVED_FOR_INDEXING` requires transition `actor` to match the recorded `human_approved_by` identifier. **String equality does not authenticate a human reviewer** or verify their role; a trusted RBAC approval adapter with an exact-decision-bound signature is mandatory before real ingestion or use in production. See issue #477.
- `ALL_RIGHTS_RESERVED` metadata is no longer sufficient for `APPROVED_FOR_INDEXING`, even if a rights-holder name is supplied. Rights grants and licence scope still require independent verification; declaring any other licence in metadata does not automatically grant permission. No ingestion/indexing exists in this package.
- Added 10 negative/positive guardrail tests; updated 32 existing Library V1 tests for the new explicit scoped transition API. Six Nightshift original suites unchanged.

## Verifiable local checks
```
python -m compileall -q aion_core test_aion_core_*.py
python -m unittest -q test_aion_core_domain_registry test_aion_core_evidence_pack test_aion_core_memory_architecture test_aion_core_provenance test_aion_core_security_audit test_aion_core_trust_engine test_aion_core_library_foundation test_aion_core_library_guard_contract
```
Local result: **134/134 passed** (92 Nightshift + 32 Library + 10 guard contracts). GitHub CI and independent review remain required.

This follow-up PR must remain draft and stacked on Library PR #476; it is neither an authorization to merge/deploy nor a substitute for issue #477.
