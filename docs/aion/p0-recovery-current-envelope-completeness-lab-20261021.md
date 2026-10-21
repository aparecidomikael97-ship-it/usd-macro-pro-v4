# AION P0 — Current runtime checkpoint completeness before recovery

2026-10-21 — LAB only, stacked on PR #1410. No real restoration, merge, deploy, Worker, outside vendor, or new expense.

## Confirmed static gap in base branch

Previously, recovery_preflight verified current_runtime.status and the shape of current_runtime.sha, but did not require the current runtime checkpoint body to exist. When the checkpoint was absent, the current-content comparison silently used an empty digest. Thus, an otherwise clean and distinct candidate could be marked eligible for human review with no observed current checkpoint in the envelope. The approved restore path could then reach the historical readback. This finding does NOT demonstrate an actual GitHub write or provider effect.

## Narrow correction

The current checkpoint must now be a nonempty Mapping before considering the selected revision. Missing, null, scalar, list and empty-mapping payloads return allowed=False and executes_action=False. A present checkpoint with MISMATCH remains eligible for explicit review of a sound historical candidate; prior strict 40-hex SHA and digest checks remain unchanged.

## New regression tests — not yet executed

File: tests/test_aion_p0_recovery_current_envelope_completeness_lab.py

10 checks: valid current envelope, missing/null/empty/list/string/integer current payload, observed MISMATCH repair eligibility, and denial before mocked historical readback and write for absent/empty current.

Proposed offline LAB commands:

    python -B -m unittest discover -s tests -p test_aion_p0_recovery_current_envelope_completeness_lab.py -v
    python -B -m unittest discover -s tests -p test_aion_p0_recovery_preflight_strict_git_sha_lab.py -v
    python -B -m unittest -v test_atlasquant_aion_recovery
    python -B -m unittest -v test_atlasquant_aion_recovery_traceability_gate

No GREEN or RED test-run result for this change is claimed. No workflow was added or dispatched.

## Still OPEN — provenance and cross-origin ambiguity

This fix does not prove that the current runtime envelope belongs to the destination RuntimeConfig repo, branch and path. The current source field identifies branch/path but omits the repository. A Git blob SHA can be identical across repositories when file contents are identical; a conditional contents write alone is not a trust-root or rollback witness.

Next read-only characterization: synthesize different repo/branch/path origins with identical blob SHA, verify eligibility classification, and specify a source binding with exact commit ancestry plus live readback. Keep all network writes mocked. Any real monotonic-head authority, owner identity enrollment, revocation, and provider effect/no-effect remain BLOCKED until independent out-of-band proof exists.

HARD NO-GO — 0/6 P0 homologated — Worker OFF — ZERO_AUTO_RESEND.
Inherited from PR #1410: canonical Quality 6,810 PASS / 51 FAIL / 34 ERROR of 6,895; Security A74 365 PASS. This new LAB change has no verified CI results.
