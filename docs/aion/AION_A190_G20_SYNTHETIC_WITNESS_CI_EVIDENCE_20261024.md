# A190 G20 — Synthetic external witness recovery contract evidence

Date: 2026-10-24. Exact tested SHA: `0b14fb8ee85e963ada0ee8acfdbef0fa2227e69e`.

## Executed CI
- [GitHub Actions #40119482610](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40119482610): completed / SUCCESS.
- Ubuntu job `120947689421`: 16/16 passed.
- Windows job `120947689622`: 16/16 passed.
- Total: **32 executions of 16 distinct synthetic contract tests**.
- Contract and tests: `labs/a190/g20_independent_witness_recovery_contract_lab.py` and `labs/a190/test_g20_independent_witness_recovery_contract_lab.py`.

## Boundary behavior
- Missing/mismatched pinned root, unavailable witness, invalid signature, missing journal, changed digest, stale sequence, mismatched phase and wrong semantic key deny.
- A matching **synthetic** witness can return only `UNCERTAIN_ZERO_AUTO_RESEND`; no `SEND`, `RETRY`, or provider-confirmation path exists.
- First-attempt admission always denies because an atomic independent external reservation is not implemented.

## Unresolved critical issues
The witness test double is in-process, its `verify` returns a controlled Boolean, and `signed_statement` is not cryptographically checked. The root string is a test constant, **not** externally provisioned trust. No real AION runtime integration or real external witness, no durable first-attempt witness, no owner/provider identity root, no WAL/SHM or H0 antirollback attestation. Full canonical Quality/Security suites not rerun. A green CI is NOT P0 homologation.

No merge/main, deploy, Worker, provider, customer, credentials, costs or production effects.

**0/6 P0 HOMOLOGATED · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
