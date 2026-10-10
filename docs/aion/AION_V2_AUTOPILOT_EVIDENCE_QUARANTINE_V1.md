# AION V2 — Autopilot Shadow/Flight per-process quarantine (Draft)

**Scope:** Blocks one real Autopilot consumer bypass of UNKNOWN_OUTCOME.
This is not a cross-process or physical closure certificate.

The real Autopilot now routes its Shadow and Flight calls independently through
a conservative lock-protected process registry keyed by repository, branch and
sink. Once a writer reports UNKNOWN_OUTCOME, conflict requiring reconciliation,
an exception, malformed or unverified success, another invocation in that
process never calls the sink again. Merely finding ALREADY_PRESENT cannot turn
the uncertain write into confirmed SAVED. Only the existing store's SAME GITHUB
ENDPOINT READ AFTER WRITE verified SAVED can return ordinary adapter success,
which does NOT prove independent witness or remote durability.

No automatic release, replay, paid API calls, installation or deployment.
The guard makes no new network calls; existing writer calls remain guarded by
their earlier URL/status protections.

**Open P0:** Restarting a process, a new GitHub Actions runner, or a second
machine discards this in-memory quarantine and can race. A separate, durable,
independently verified one-shot claim with CAS, recovery and explicit owner
policy is still required. The uncommitted Windows Codex consumer branch
codex/aion-unknown-outcome-consumers is not included; integrate separately
without overwriting local files. Existing additional GitHub writes remain a
separate hardening scope.

Test with tests/test_atlasquant_aion_v2_autopilot_evidence_guard.py plus the
inherited Windows/Linux write status suite. Synthetic tests are not physical
attestation. Issue #1117 remains HARD NO-GO. This Draft PR does not authorize
main merge, deployment, spending or hardware activity.
