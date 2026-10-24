# A190 G12 — Exact CI evidence, tested SHA and regressions (2026-10-23 local / 2026-10-24 UTC)

## Final tested code + LAB fixtures + workflow

- Head code/test/workflow commit: **56ed41b0362c729ea0d2cf5c5abc2069b328d381**.
- GitHub Actions **G12** [run #40051819613](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051819613) — **completed success**:
  - Ubuntu job **120745936228**: **153 tests, OK**, G12 witness/default/no-adapter checks present in job log.
  - Windows job **120745935985**: **153 tests, success**.
  - Total **306 test executions** across the two OS jobs. These are mirrored test cases, not 306 distinct cases.
  - Both jobs used actions/checkout pinned to the exact HEAD SHA above. No provider effects.
- Other success statuses at tested HEAD:
  - A176 no-retry LAB: [#40051819576](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051819576)
  - A177 receipt gate LAB: [#40051819621](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051819621)
  - A178 signed synthetic receipt LAB: [#40051819574](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051819574)
  - A179 synthetic witness LAB: [#40051819579](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051819579)
  - A180 first-attempt preflight LAB: [#40051819608](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051819608)
  - A181 separate-host-custody *simulation* LAB: [#40051819587](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051819587)
  - G6 original caller-controlled-true RED repro with deliberate LAB-only unsafe opt-in: [#40051819595](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051819595)

## Honest first-run history

Initial G12 head **88d86891b644d4446acf32ad3a845e14511c6cb4**, [run #40051684574](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051684574) passed the first narrower G12 job with **73 tests per OS**. **However, related A178/A179/A180/A181 workflows FAILED** because legacy synthetic test fixtures were still relying on implicitly enabled callbacks; G12 correctly quarantined them.

The migration commits explicitly opted those test-only callers into unsafe_allow_synthetic_lab_callbacks=True, updated the G12 matrix to include their cases, and re-ran the suites. The G6 reproducible LAB RED was not deleted or reinterpreted as authorization.

## Outstanding

- The much broader A184 six-P0/canonical workflow **#40051819580** was still in progress while this evidence was written. Its old [#40051684468](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051684468) included baseline/adversarial expected REDs and historical Quality/Security failures. **Do not claim full canonical green.**
- G12's unsafe LAB opt-in **is bypassable by any in-process Python host**. There is no trusted external authority, antirollback storage, OS-independent principal, supplier-side uniqueness, or authenticated real receipt.
- Six P0 remain **0/6 homologados**, including both SQLite compatibility conditions and owner/receipt/first attempt/restart.
- **HARD NO-GO, UNCERTAIN, ZERO_AUTO_RESEND.** No merge/main, provider, Worker, deploy, customer, account, credential, real effect or expenditure.

Evidence is an account of targeted tests, not independent certification or operational readiness.
