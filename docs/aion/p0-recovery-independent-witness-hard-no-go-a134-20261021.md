# AION P0 A134 — independent-monotonic-witness restoration HARD NO-GO (LAB)

**Date:** 2026-10-21. **Scope:** stacked Draft on PR #1417. No real
GitHub checkpoint PUT/restore, Worker, commercial supplier operation, paid
account, deployment or merge.

## Objective and boundary

A127–A133 make GitHub current/historical contents, blob identities,
historical ancestry and the runtime branch HEAD more consistent and harder to
race. GitHub itself is still a single rollback and administrative trust domain.
An old but internally consistent HEAD, blob and revision can be replayed after
coordinated rollback, and a caller's approved=True is not authenticated
HUMAN_OWNER consent or externally authenticated witness provenance.

Prior PRs #1115/#1128/#1341/#1362 explicitly demonstrate this limitation with
reference witness state, ephemeral keys, local SQLite and simulations.
These references do **not** constitute independently enrolled custody or
an online, durable, authenticated, split-view-resistant monotonically current
head. No external root of trust is connected to the restore path.

## RED-first defect proof

Before A134, a direct call to restore_checkpoint_revision with approved=True,
a current/candidate checkpoint that passed the existing preflight, mocked live
destination GET, mocked ancestry compare, mocked historical readback and
mocked HEAD-ref GET could reach save_runtime_checkpoint without an independent
witness. In the adversarial suite the synthetic save reported CONFIRMED.
No real GitHub write or unauthorized external action was performed.

RED-first: https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39673628650
Eleven tests: **10 FAIL / 1 PASS** Ubuntu; the sole initial PASS was
approved=False already refusing before any network. Fake environmental claims
and self-declared signed reads offered no independent authority.

## A134 correction: closed until enrollment

The actual historical restore code calls
_require_independent_recovery_head_witness, after all existing read-only
checks but BEFORE checkpoint mutation/audit-event construction and
save_runtime_checkpoint. The helper presently returns only
allowed=False, status=BLOCKED, reason
INDEPENDENT_MONOTONIC_HEAD_WITNESS_NOT_ENROLLED. No caller parameter,
environmental boolean, internally sourced GitHub response or synthetic
signature can enable it. All real (unmocked) historical restore writes are
now fail-closed. In this version there is **no way to enroll a provider**;
allowance needs a separately specified, reviewed and independently verified
production integration, not a config toggle or a JSON claim.

Existing positive unit tests that explore downstream legacy CAS/receipt
behavior explicitly mock only this independent gate as
synthetic_test_only=True; those tests validate internal logic and **never**
claim live enrollment, external authority or GO. The canonical Quality
suite selection is unchanged; historical RED failures are not waived.

## Requirements for a real future trust boundary (NOT implemented)

1. A truly separate administrative domain enrolls a vendor/root/witness
   issuer PIN outside GitHub and outside the AION runtime, with independent
   identity verification, limited roles, audit, security and custody.
2. Signed fresh READ of the exact witness scope, canonical head, epoch,
   sequence, previous checkpoint/commit digest, owner policy generation
   and challenge nonce. The verifier independently owns/records the nonce
   and minimum acceptable sequence; issuer key and revocation anchors cannot
   be supplied by the caller or recovered from rolled-back GitHub history.
3. Durable CAS or append-only head state in that external custodian with
   atomic anti-fork uniqueness, independently read-back witnessed latest
   HEAD, key rotation/revocation and hard-stop on PITR/rollback/split view,
   timeout, stale READ, or unknown durability.
4. Bind the witnessed HEAD to the GitHub repo/branch/path/current blob and
   selected historical revision; check an epoch head after save with a
   supervised uncertainty/reconciliation protocol. Never assume distributed
   atomicity or exactly-once execution across GitHub and witness.
5. Independent HUMAN_OWNER identity/consent and separate supplier effect
   receipts (COMMITTED_EFFECT or NO_EFFECT_FENCED) before any H0 dispatch.
   A signed witness head does not prove whether a supplier executed.
6. Real evidence of costs, IAM isolation, account/credential protection,
   LGPD and release governance before even considering activation.

Until all required evidence is independently verified: **HARD NO-GO,
0/6 P0 homologated, Worker OFF, ZERO_AUTO_RESEND.** No real restore.

## Verification

New A134 adversarial tests use only patched, synthetic GitHub reads and
saves. CI exercises these plus A127–A133, original recovery/memory and
H0 A79 on Ubuntu/Windows. Quality canonical (588 modules) and A74 Security
(365 methods) are rerun with original commands, no waivers or changed
selection. Record exact commit/job and distinguish RED Quality from GREEN
focused suites. A passing denial test is not independent enrollment.
