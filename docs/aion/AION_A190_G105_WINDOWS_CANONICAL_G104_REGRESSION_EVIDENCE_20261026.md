# AION G105 — Full Windows canonical verification after G104 post-reservation witness LAB

**Date:** 2026-10-26. Parent G104 Draft #1595 code+evidence head 859f71e6947ef7d476dedb9118197dc44bb335d8. G105 contains a dedicated verification workflow only: no application/test/Worker changes. Draft LAB; 0/6 P0 HOMOLOGATED, HARD NO-GO.

## Purpose

G104 closed a synthetic preflight-only first-attempt reservation confirmation gap, with a second signed challenge after the local A180 reservation. Genuine RED before patch was observed on Windows and Ubuntu: G104 run [40344188528](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40344188528), a locally signed receipt not recorded by the separately modeled attestor was wrongly accepted.

G104 corrected synthetic contract run [40344894057](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40344894057) succeeded with 29 executions on each OS (19 unique test methods due inherited discovery duplication); all nine new post-commit failure scenarios returned DENY/UNCERTAIN and zero synthetic SEND as applicable.

G104's A184 Ubuntu candidate run [40344894049](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40344894049) confirmed unchanged Quality 6449/6449, Security unittest 368/368, pytest 2825/2825, zero currently known pypdf/Pillow advisories. Five true external requirements remained RED on Windows and Ubuntu.

## G105 objective Windows outcomes

[Workflow run 40345778705](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40345778705), tested G105 verification-only source SHA 110b0f70e2e591c1270ab5e344573d0634baf238, **all 3 jobs SUCCESS**:

- Original canonical Quality, Windows: **6449/6449 PASS**, Ran 6449 tests in 158.483s, OK. Job 121652191236. Original Quality selector unchanged.
- Original canonical Security unittest, Windows: **368/368 PASS**, Ran 368 tests in 5.553s, OK. Job 121652191695.
- Original canonical Security pytest, Windows: **2824 PASS + 1 SKIPPED**, zero failed, in 58.40s. Job 121652191695. This one Windows platform skip was present before G104 and must NOT be counted as a pass.
- Original canonical pip-audit -r requirements.txt, Windows: **No known vulnerabilities found**, pip check No broken requirements found, unchanged Bandit high-severity selector SUCCESS. Job 121652191091. No ignored vulnerabilities, scanner exemptions or bypass of signature controls.

All Windows jobs used Python 3.12 and unchanged G90-pinned dependencies, with existing scoped LAB Python socket guard. The guard permits only internal Windows asyncio stdlib self-pipe and denies normal Python network connect; it is NOT an OS firewall or a guarantee for subprocesses.

## Critical no-go remains

A successful synthetic post-commit attestation depends on in-process fixture keys, a mocked 'remote' ledger and an optional LAB callback. No live independent attestor/root, permanent original identity enrollment, monotonic third-party custody, authenticated SQLite VFS native descriptor/snapshot, rollback-proof same-inode write authority, actual external provider first-SEND ACK-loss reconciliation or H0 recovery has been demonstrated.

The five deliberately RED A184 external acceptance tests are not xfailed/skipped/waived; six P0 remain **0/6 HOMOLOGATED, HARD NO-GO**.

NO MERGE, NO DEPLOY, NO WORKER, NO REAL PROVIDER SEND, NO REAL FUNDS.
