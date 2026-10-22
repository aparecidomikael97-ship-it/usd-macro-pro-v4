# AION P0 A157 — GitHub workflow YAML job/credential containment

**22 October 2026. LAB Draft. 0/6 P0 homologated. HARD NO-GO.**

## Finding: legacy A137 missed executable sibling jobs

A137 scanned four known workflows and looked for one named job's `if: ${{ false }}` guard using text patterns. It did **not** require that the workflow contained only that job. A rogue, executable second job could therefore be added while the A137 check still reported `target_p0_fence_ok=true`. A137 also accepted ambiguous duplicate job-level `if` clauses with a later enabling condition. These are vulnerabilities in **static review coverage**, not evidence of a real unauthorized GitHub job execution.

**RED-first evidence:** commit `6b6e1c0a7d5e53e0e6bd95e107f94705a7224e05`, [Actions #39781328738](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39781328738), **26 FAIL and 1 ERROR in 67 tests on Ubuntu**. The existing A137 auditor explicitly passed the altered string fixtures with a new active job or duplicate `if`. Backup coverage was also absent. All inputs were synthetic YAML strings.

## Fix: strict source-only YAML review of exactly six workflows

- `tools/aion_p0_a157_workflow_yaml_policy_lab.py` parses YAML with **PyYAML BaseLoader** (the `on` trigger remains a string), rejects **all nested duplicate mapping keys**, aliases/anchors/tags, syntax errors and invalid/non-string sources.
- Four **critical blocked** workflows are pinned to their single known job names, exact trigger/permission sets, and an actual YAML job-level `if: ${{ false }}`, not a comment, step guard, env expression, or duplicated condition. Their known writer command must appear in a parsed `run` step, not merely commented text.
- Two **artifact-only source backups** must have exactly one job, `permissions: contents: read`, three steps, pinned checkout and upload-artifact, and `checkout.with.persist-credentials: false`. Obvious `git push`, GitHub API mutator, `requests.put`/similar or HTTP mutation patterns are rejected in the steps.
- The backups have been amended in this LAB branch to set `persist-credentials: false` explicitly; no real backup job was run by this work.
- The remaining A137 auditor still runs but is **not** itself sufficient. The new gate is independently enforced in CI.
- Scope: exact four critical + two source-artifact workflows. **No claim of inspection of all workflows** or real GitHub IAM credentials, branch rules, external PAT/app tokens, `workflow_call` transitively launched jobs, native extensions or shell obfuscation. YAML validation is not a formal execution proof.

## GREEN evidence and regression

- FIX commit `c57f04c044a6ac5f4434a785ba1bbff4b1e760e6`.
- [Actions push #39781930744](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39781930744) **SUCCESS on Windows and Ubuntu**; logs inspected: **67/67 A157-specific cases** per OS = 50 new mutations +16 old A137 +1 backup test.
- In the same run all A145–A156 regressions passed, with 259+16+55+48+73+78+90 = 619 previous tests per OS; **686/686 per OS and 1,372 individual executions combined**. Historical 32 provider-proof errors were preserved as unclosed.
- New source-only decision always returns `HARD_NO_GO_WORKFLOW_CUSTODY_NOT_VERIFIED` and zero real-effect authority even if six policies are consistent.

## CRITICAL: main branch differs from the LAB branch

A read-only fetch of `main` on 2026-10-22 (observed HEAD `5744b2b7b17c84331e6f27c569064993ff587782`) showed:
- **autopilot-v107.yml**: GitHub `contents: write`; **no unconditional job-level hard-stop**.
- **coleta_automatica.yml**: GitHub `contents: write`; **no unconditional job-level hard-stop**.
- **aion-runtime-checkpoint-bootstrap.yml**: GitHub `contents: write`; **no unconditional job-level hard-stop**.
- **aion-runtime-checkpoint-migrate.yml**: GitHub `contents: write`; **no unconditional job-level hard-stop**.
- Both source-backup workflows on `main` also lacked checkout `persist-credentials: false`.

The source findings alone **DO NOT prove workflow activation, scheduled run success, real token scope or a real write**: repository settings and Actions operational states must be checked separately. However, A137/A154–A157 green **only on unmerged branches** cannot be presented as protection already applied to main. An explicit, separately reviewed emergency fail-closed PR against main is warranted; it must not be merged without the owner approving the interruption of benign data collection.

## Unresolved H0 and production decisions

No independently enrolled D1/D2 witness, no owner FIDO2/Windows Hello proof, no verified producer `COMMITTED_EFFECT`/`NO_EFFECT_FENCED` receipts, no latest canonical Security/Quality clean, and no 6/6 P0 acceptance. A job-level false or readonly GitHub token is NOT a verified GitHub-enforced checkpoint-path policy. The 32 historical provider proof errors remain open.

**No merge, deploy, new credentials, paid services, Worker, real restore, supplier effect or authorized auto-resend. HARD NO-GO 0/6 P0.**
