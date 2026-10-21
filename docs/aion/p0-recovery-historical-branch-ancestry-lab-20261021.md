# AION P0 — Historical revision branch ancestry fence (A130, LAB)

2026-10-21. This is an isolated Draft stacked on PR #1412, not on main.
No merge, deployment, real restoration, provider execution, Global Worker, credentials, or new spending.

## RED-first code gap

restore_checkpoint_revision validated the syntax of selected.revision, revalidated candidate content and compared its digest, but a valid 40-hex commit ref could point to an unrelated commit in the same GitHub repository. The GitHub Contents API allows a GET by arbitrary commit ref independently of whether that commit belongs to config.branch. A current-runtime blob SHA is not proof of historical ancestry.

**RED-first run:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39660627100 (branch commit 60987b880db720c8896758b9295cec6b70e3dae7). Ubuntu: 11 FAIL / 1 PASS in 12 synthetic tests. This confirmed missing branch ancestry admission; the mocked restore path reached historical readback and a mocked save for unrelated revisions. No actual GitHub runtime PUT or external side effect happened.

## Narrow fail-closed patch

After existing A127/A128 strict preflight and A129 fresh-target GET, before historical content GET:

- _verify_runtime_revision_ancestry compares the selected historical commit SHA to the configured runtime branch through a read-only GitHub Compare API request.
- Accept only status ahead or identical, with exact base_commit SHA and merge_base_commit SHA matching the selected commit; validate head_commit SHA format. For identical, head_commit must match the revision too.
- Divergence, behind, missing fields, malformed JSON, timeout, rate limit, branch denial or HTTP error return allowed=False.
- The existing historical content revalidation, candidate digest binding and CAS write/read-after-write remain mandatory after this gate.
- No automatic retry, restoration without explicit approval, or external effects are authorized.

## Tests and status

12 new RED-first synthetic cases in tests/test_aion_p0_recovery_historical_revision_ancestry_lab.py:
diverged/behind/unrelated merge-base, mismatched base, invalid JSON, missing merge-base, timeout, unknown compare status, valid ancestor, identical commit, exact repo/branch compare URL, and no-approval denial. All GET, history read and save endpoints are mocked.

Five legacy approved-restore unit tests and the A129 positive test helper mock the *new ancestry API only*; A130 tests cover the actual comparison behavior. The A127/A128/A129 CI that previously passed Ubuntu 165/165 and Windows 165/165 remains separately evidenced by https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39660071542.

**Any new A130 GREEN must be recorded from the exact CI run and HEAD, not inferred from this patch.**

## External proof still absent

GitHub's branch comparison does not prove an independently anchored, monotonic or non-forking latest head. It also cannot establish independent owner identity, credential epoch/revocation, trustworthy repository governance or actual producer effect/no-effect. Branch movement can still occur between GET/compare/PUT; a conditional file SHA write mitigates content conflicts but is not an external monotonic witness.

HARD NO-GO. 0/6 P0 homologated. Worker OFF. ZERO_AUTO_RESEND.
Canonical Quality baseline remains 51 FAIL + 34 ERROR, pending separate rerun.
