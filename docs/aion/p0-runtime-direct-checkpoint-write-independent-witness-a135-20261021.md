# AION P0 — A135 direct Checkpoint Mestre write requires independent witness

**2026-10-21 | Draft LAB only | base PR #1418 | no production merge/deploy,
runtime PUT, Global Worker, external supplier, or paid service activated.**

## Security finding

A134 placed a deny-only independent monotonic witness gate before the
historical restore's call to save_runtime_checkpoint. However the shared
checkpoint writer save_runtime_checkpoint in atlasquant_aion_memory.py could
still be called DIRECTLY by any caller with approved=True and a configured
write credential. It validated integrity and made a conditional GitHub PUT
without consulting the A134 witness gate. Therefore the historical restore
entrypoint's refusal was NOT an end-to-end write boundary. An old checkpoint
could be submitted through the ordinary writer, subject to GitHub CAS; this
was a possible bypass of the restoration-specific safeguard, not proof of
unauthorized real GitHub writes.

A135 adversarial tests exercise the genuine entrypoint with requests.put
MOCKED. Prior to the fix, 10 of 11 scenarios failed because an attempted
PUT reached the mock even without independent custody; 1 pre-existing case
approved=False passed. The RED-first workflow is
https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39675300287

## Narrow mitigation in the actual transport

The shared runtime writer now calls
_require_independent_runtime_write_witness(config, expected_sha,
expected_digest) AFTER ordinary integrity/size/preflight checks but BEFORE
any GitHub PUT. No external trust root exists yet, so that helper is
deliberately deny-only. A failed admission returns BLOCKED, saved=False,
verified=False, write_outcome=NOT_ATTEMPTED,
reconciliation_required=False, automatic_retry_allowed=False,
independent_witness_enrolled=False. It does not emit a write, attempt
retry or claim reconciliation as completed.

The function does NOT grant authority based on caller-controlled fields,
environment flags, an OAuth/GitHub token, approved=True, self-declared
owner/witness signatures, or Global Worker arming override. Any future
positive path requires a separately reviewed independent enrollment and
authenticated, durable, monotonic witness integration.

The four legacy happy-path/transport-conflict tests that intentionally
exercise GitHub PUT and readback use an EXPLICIT unit-test-only patched
helper returning allowed=True/synthetic_test_only=True. They test only
internal transport behavior, not real production authority or enrollment.

## Observable effects and precise limits

- Both historical recovery and the generic runtime checkpoint PUT now deny
  when using actual unmocked product gates. Normal mutable checkpoint
  syncing would also be disabled if this LAB patch were deployed unchanged.
  This is intentional temporary safety and requires future product policy
  for read-only mode and independently witnessed state writes.
- Existing checkpoint READ and read-only reconciliation remain possible;
  a write authorization gate does not prove whether an earlier uncertain
  network call completed or whether an external supplier executed.
- Authenticated HUMAN_OWNER, independent witness identity/custody/revocation,
  and supplier effect/no-effect receipts remain entirely unproven.
- The check is not sufficient to prove there are NO other direct write
  transports elsewhere in the repository. A complete call-graph and endpoint
  audit is separately required before homologation.
- Passing mocked tests does not prove an external witness has been enrolled
  or a monotonic last-HEAD established.

## Evidence and release rule

The A135 focused workflow runs 11 new tests, 11 A134 tests, A133/A132
regressions, the original memory/recovery tests and the A127-A131/A126/H0
sets on Ubuntu and Windows. The canonical original 588-module Quality and
Security A74 selections are reexecuted unchanged, not waived. Compare
failure identifiers to docs/aion/evidence/aion_p0_quality_85_red_baseline_20261021.json.

**HARD NO-GO | 0 of 6 P0 homologated | Worker OFF |
ZERO_AUTO_RESEND | no merge, deployment, real restore, external spend.**
