# AION P0 — Live destination binding before restoring Checkpoint Mestre

**2026-10-21 — A129 LAB Draft, based on A128 / PR #1411.**
There is NO real GitHub runtime restore, merge, deploy, external credential enrollment, Worker operation, provider effect, or new spend.

## Code observation

At the time of the A128 baseline, restore_checkpoint_revision accepted a caller-provided current_runtime record as long as its local recovery_preflight passed. Its SHA, checkpoint body, status and optional source could have been copied from a different read, become stale, or have been injected into the call. No **fresh GET of the configured target runtime** happened before historical checkpoint readback. The final conditional GitHub write still compared an expected blob SHA, but that alone is not a proof of fresh, complete destination context; equal blob contents can share SHA across origins.

This was a **local restore-gating weakness** shown by control flow analysis. There is no claim that an actual unauthorized write or externally visible effect occurred.

## Narrow code change

An explicitly approved restore now:
1. Runs the existing strict recovery preflight (including A127/A128).
2. Before historical revision readback, calls load_runtime_checkpoint with the exact RuntimeConfig (repo, branch and path), read-only, with bounded timeout.
3. Requires status CONFIRMED; the expected source label for branch:path; the exact validated 40-hex current content SHA; and a present current checkpoint identical to the caller-supplied checkpoint including volatile fields.
4. If the caller supplies a source label, denies if it conflicts with the configured target source.
5. Denies on missing live result, changed SHA, changed bytes, status not confirmed, bad source, timeout or exceptions. No history GET, no PUT, no retry in those paths.
6. Preserves the historical revision revalidation, digest rebinding and GitHub conditional CAS + read-after-write verification after this gate.

An observed current checkpoint with MISMATCH is still eligible for explicit, supervised review; missing current checkpoint is not.

## New synthetic tests (NOT YET EXECUTED)

- 18 checks in tests/test_aion_p0_recovery_live_destination_binding_lab.py, including positive mocked path, stale SHA, same SHA with divergent body, wrong/missing branch/path label, missing checkpoint, non-object envelope, live failure, no explicit approval, MISMATCH repair and exception fail-closed.
- Updated the five approved legacy restore tests in test_atlasquant_aion_recovery.py to mock the newly required read-only destination GET. Other legacy recovery functionality remains unchanged.
- A128 / PR #1411 was amended so a forged historical candidate still reports the recalculated candidate integrity before current-context denial; test fixture behavior documented.
- No tests have been actually run; no GREEN result or passed Security/Quality result is claimed for A128/A129.

## Suggested offline regression commands (not executed)

    python -B -m unittest discover -s tests -p test_aion_p0_recovery_live_destination_binding_lab.py -v
    python -B -m unittest discover -s tests -p test_aion_p0_recovery_current_envelope_completeness_lab.py -v
    python -B -m unittest discover -s tests -p test_aion_p0_recovery_preflight_strict_git_sha_lab.py -v
    python -B -m unittest -v test_atlasquant_aion_recovery
    python -B -m unittest -v test_atlasquant_aion_recovery_traceability_gate

All network calls inside the new tests are mocks; these commands are *not authorization to restore a real runtime*.

## Boundaries NOT solved

- This GitHub GET is from the configured repo, branch and path, but DOES NOT establish an independently enrolled trust root for the repository, account or administrators; a maliciously supplied RuntimeConfig is still outside the protection of this local guard.
- The source string from the existing runtime loader records only branch:path. The effective repo is bound by the GET request config, not independently signed provenance. A missing caller source is accepted for legacy compatibility; live target readback is still required.
- SHA is a Git blob content identifier, not proof of branch ancestry, non-forking history, independent monotonic head, current owner consent, nonrevoked credentials, vendor no-effect or correct historical commit lineage.
- A 409/422 or unknown write result continues to demand reconciliation; zero automatic resend.
- Before any GO, independent root enrollment, live test environment, human owner authorization and full Security/Quality are required.

**HARD NO-GO · 0/6 P0 homologated · Worker OFF · ZERO_AUTO_RESEND.**
Inherited historical rebaseline from #1410 only: canonical Quality 6,810 PASS, 51 FAIL, 34 ERROR of 6,895; Security A74 365 PASS. No updated CI for this Draft.
