# AION A156 — historical checkpoint recovery denial and dormant migration workflows

**Date:** 2026-10-22. **Scope:** isolated LAB Draft; no live provider, Worker, deployment or runtime GitHub write. **Status: HARD NO-GO; 0/6 P0 homologated.**

## Scope, actual code and security finding

The real `atlasquant_aion_recovery.py::restore_checkpoint_revision` performs multiple **read-only** GitHub checks before attempting any restore. Crucially, it relies on the following NO-GO boundary:

1. An administrator approval flag is an immediate initial preflight requirement.
2. Real destination, ancestry, candidate history and branch HEAD are checked before a restore.
3. The helper `_require_independent_recovery_head_witness` currently returns an **unconditional blocked** verdict, because no independent monotonic witness has been enrolled.
4. `if witness_admission.get("allowed") is not True` must immediately return a complete blocked result with `saved=False`, `verified=False`, `restore_confirmed=False`, `automatic_retry_allowed=False`, `automatic_restore=False` and no fake owner/head proof.
5. The only subsequent checkpoint save must call the shared `save_runtime_checkpoint` writer with an expected SHA. This writer is separately restricted by A154.

The earlier A154 static gate checks the **direct writer**, but not the semantics of the **historical restore route**. A future change that reverses the restore witness branch, removes its return, replaces the helper, or adds another mutator could invalidate the recovery guarantee without triggering the direct-writer gate.

A156 adds a conservative AST audit of the **actual recovery source**. This is preventative regression coverage, not proof of an existing exploited bypass. It does not alter the operational recovery function.

## Delivered controls

- `tools/aion_p0_a156_recovery_restore_deny_ast_lab.py`: read-only static verification of the helper's unconditional deny-only return, initial admin approval, direct witness invocation with expected metadata, immediate negative admission, no separate network mutation or shadowing, and a single well-bound downstream shared checkpoint save whose CAS expected SHA is exactly derived from the reviewed preflight blob SHA, not a candidate or hardcoded SHA.
- `tests/test_aion_p0_a156_recovery_restore_deny_ast_lab.py`: **60 adversarial AST mutation tests**, e.g. `is not True` → `is True`, `allowed=True`, forged witness authority, alternative save, early PUT, late/missing return, local helper rebinding, unreviewed HTTP mutation, and auto-retry/status changes.
- `tests/run_aion_a156_restore_deny_counted_lab.py` also reuses **11 previous actual restore tests** with GitHub HTTP and save mocked, **13 branch HEAD TOCTOU tests**, and **six A69 hard-stop tests** proving bootstrap/migration jobs retain unconditional job-level `if: ${{ false }}`. Together this is **90 counted A156-specific/restore regression cases**.
- CI Windows+Ubuntu also runs **529 previous A145–A155 cases**, target **619 exact cases per OS**, plus standalone static restore and checkpoint gates, static broad writer inventory, E0–E5 NO-GO decision and historical 32 producer proof errors. The count is a **target until Actions logs prove it**.

## Threats that remain unresolved

| Threat | A156 interpretation |
|---|---|
| Fake `approved=True` or custom environment claims | Existing real recovery tests deny without external witness |
| Restore guard inverted or softened in future | New AST regression rejects tested mutations |
| Extra direct `requests.put` or alternate mutator in restore function | New narrow AST heuristic flags tested expressions |
| Old bootstrap/migration workflow unexpectedly re-enabled | Existing six A69 source-based tests enforce job-level false |
| Valid GitHub HEAD/commit CAS without external authority | Not sufficient: same GitHub trust domain can be rolled back |
| Recovery done through another language, workflow, SDK or dynamic alias | **Not proven safe** by this Python source AST |
| Mutating repo with a `contents:write` token outside the protected functions | **Not prevented** by either static audit |
| Real independent nonrollbackable witness, Owner/FIDO2 and producer effect receipt | **Still missing** |

A clean syntax audit is not formal call-graph/taint proof or effective GitHub path-scoped IAM. It does not prove all possible recovery or write surfaces. In particular the checkpoint bootstrap/migrate workflows stay disabled and **must not be enabled based on a passing LAB run**.

Historical Quality's 51 FAIL + 34 ERROR baseline and the 32 producer-proof errors (23 independent enrollment, eight committed effect receipts, one terminal no-effect fence) have not been dismissed. The whole AION P0 acceptance gate remains **0/6, HARD NO-GO, ZERO_AUTO_RESEND**.

**No merge, deploy, Worker, account provisioning, real restore, token use, supplier effect or new spend authorized by this PR.**
