# A190 G12 — Final CI evidence, tested SHA and preserved failures (2026-10-23 Manaus / 2026-10-24 UTC)

## Final code and test/workflow SHA

**0f6e042bfb568ef08f431a9cbebb414ce3fd7e06** — before this document-only update.

- [G12 run #40052147405](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40052147405) **completed success**, pinned checkout exactly to SHA above.
  - Ubuntu job **120746939997**: **175 tests, OK**.
  - Windows job **120746940121**: **175 tests, success**.
  - **350 executions across two operating systems**, 175 case selections per OS, including G12, real Outbox, Saga, A176–A181, A184 callback, G6, G5/G4/G3, Chaos campaign and Quality workflow coverage.
  - G12 direct hostile cases assert no adapter property lookup, no send, no false receipt admission, no retry on uncertain restart. Synthetic unsafe option remains explicitly reproducing RED.

## Broad canonical suites at final candidate

[A184 base-vs-candidate 18-job run #40052147390](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40052147390) on this PR head reported:

| Gate | Base selection | Candidate selection at tested SHA |
| --- | --- | --- |
| Canonical Quality unittest selector | **6,322 tests; 4 FAIL** (job 120746940261) | **6,449 tests; 0 FAIL / 0 ERROR / OK** (job **120746940366**) |
| Canonical Security unittest selector | **365 tests; 3 FAIL** (job 120746940230) | **368 tests; 0 FAIL / 0 ERROR / OK** (job **120746940289**) |
| Canonical Security pytest selector | success | success |
| Canonical security audit / dependency checks | **FAIL** | **FAIL** (job 120746940326) |
| A184 specific / regression / SQLite jobs | not treated as P0 authority | **success** Ubuntu and Windows |
| A184 adversarial BASE RED + external-RED | RED | **still RED, purposely not waived** |

**Interpretation:** this is an evidence-backed pass of the Quality and Security **unittest selectors** in this comparison, not a fully green Security audit or production qualification. Base and candidate test selections differ (6,322 vs 6,449 and 365 vs 368); do not attribute all historical improvements exclusively to G12. The security audit reported vulnerable dependencies (including Pillow advisories). The A184 workflow's **overall conclusion remains FAILURE** because its independent negative and audit jobs are still RED. Full release remains HARD NO-GO.

Other independent targeted workflows on final SHA were triggered; targeted G12 and A184 job IDs above are the primary reproducible evidence. Historical 5 external-RED per OS and the reported 43 advisories are not declared closed here.

## Debugging timeline — failed attempts remain visible

1. Initial G12 code head **88d86891b644d4446acf32ad3a845e14511c6cb4**; [G12 #40051684574](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051684574): **73 per OS green**, but A178–A181 workflows **FAILED**, because implicit synthetic callback tests were quarantined. This was a regression in test setup.
2. After migrating A178–A181 and A184 callback fixtures, tested SHA **56ed41b0362c729ea0d2cf5c5abc2069b328d381**; [G12 #40051819613](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051819613) **153/153 per OS success**. Separate A176/A177/A178/A179/A180/A181/G6 runs also passed.
3. Canonical comparison on this intermediate SHA [#40051819580](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40051819580) found **candidate 6 FAIL / 6,413 tests**: five in Chaos fixtures (implicit synthetic mode) and one Quality workflow coverage failure (six root A190 tests absent from canonical explicit selector).
4. Migrated Chaos fixture only when synthetic evidence is supplied; retained default fail-closed test. Added all six A190 root tests to the Quality selector without removing tests. Final SHA above: **175/OS G12 PASS, 6,449/6,449 Quality unittest PASS, 368/368 Security unittest PASS**.

## Outstanding blocking truths

- The optional unsafe_allow_synthetic_lab_callbacks=True deliberately accepts caller-controlled LAB witnesses; a hostile in-process host can enable it or monkeypatch. **This is NOT a security root.**
- Owner identity, external immutable antirollback reservation, provider-effect idempotency, authenticated provider receipt, OS-independent storage/authority and both SQLite P0 compatibility conditions are not independently homologated.
- Security audit remains red; external-RED cases remain visible and not waived; no actual partner or provider has attested anything.
- **0/6 P0 homologados. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND.**
- This Draft PR was not merged or deployed. No Worker, customer, cloud vendor account, credential, external effect or paid action.

All statements here concern the selected GitHub CI jobs and their observable results, not independent certification.
