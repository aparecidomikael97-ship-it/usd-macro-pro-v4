# A190 G19 — Evidence of synthetic recovery denial oracle

Date: 2026-10-24.

- Exact tested SHA: `c0e62e64f44db79445715fef444e5a21ee6abab4`.
- GitHub Actions run [#40119114243](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40119114243): **completed / success**.
- Ubuntu job `120946582004`: **14/14 synthetic unittest tests passed**.
- Windows job `120946582195`: **14/14 synthetic unittest tests passed**.
- Total: **28 executions across two operating systems**. These are 14 test scenarios repeated on both systems, not 28 distinct scenarios.
- Code under test: `labs/a190/test_g19_recovery_denial_oracle_lab.py`. A **reference oracle only**, not the real AION recovery subsystem.
- SyntheticWitness is an in-process test double and can be rewritten by its own host; it is **not** independently signed, remotely held, durable across adversarial rollback, or a provider-authenticated receipt.
- Tests demonstrate a *proposed fail-closed behavior* under synthetic fault injection. They do not establish first-send crash atomicity, real provider effect reconciliation, true host-independent antirollback, authentic owner/provider roots, WAL/SHM integrity, or H0 restart availability.
- No real network/provider/Worker/customer transaction, production merge, deploy, credentials or cost. No canonical Quality/Security full suite rerun.

**0/6 P0 homologated. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND.**
