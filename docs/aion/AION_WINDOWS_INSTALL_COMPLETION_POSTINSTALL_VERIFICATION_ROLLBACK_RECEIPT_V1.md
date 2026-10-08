# AION Windows Installation Completion + Postinstall Verification + Rollback Receipt V1

**Status:** IMPLEMENTATION SAFE / DESIGN-ONLY / NOT INSTALLED  
**Date:** 2026-10-08  
**Stack parent:** #1058, Atomic Install Start + File Transaction Journal V1  
**Purpose:** define a fail-closed terminal boundary, not execute one.

## What this stage does not mean

A complete operation journal proves neither installation nor health. A row labeled
APPLIED is not sufficient unless a future independent verifier validates its
persisted provenance and independently reopens the physical Windows target.

This change **does not** implement that verifier or trust attestor. All positive
outcomes in this V1 are `*_CANDIDATE_UNTRUSTED`. Even when the synthetic test
fixture supplies matching digests, `physically_installed_trusted=false` and
`aion_healthy_trusted=false`.

**No GitHub merge, install authorization consumption, token consumption, CAS
write, journal persistence, file copy, ACL/Registry/startup mutation, process
launch, rollback execution, deploy, Worker or provider activation.**

## Four separate boundaries

1. **Completion journal gate.** Read the entire journal plan, canonical genesis,
   chained entries and all per-operation observations. Require every operation
   in the immutable plan exactly once, in order, with exact previous-entry
   digest and operation ID/plan/installation bindings. Recompute content
   digests and reject forgeries. Every operation must be positively classified
   `INSTALL_OPERATION_APPLIED_CONFIRMED`; any `UNKNOWN`, terminal failure,
   gap or mismatch blocks the gate. No operation may be silently skipped.
2. **Postinstall verification plan.** After a complete journal **candidate**,
   enumerate the final target state for every distinct file/ACL/startup target
   (the last operation touching a target owns its expected final state).
   Independently reopen and verify: commitment/CAS, full journal chain,
   signed package manifest, target files, owner ACL, startup entry, and AION
   runtime identity, version and health. The planned checks are exhaustive.
3. **Evidence envelope shape.** Match every planned check against an exact,
   ordered, independently observed readback receipt. Reject any omitted,
   duplicated, mismatched, ambiguous, non-reopened or non-independent result.
   This is **syntax/shape validation only**; a future trusted Windows consumer
   must validate physical receipts, signed provenance, actual file/ACL/startup
   state, runtime health and the independent verifier's authority.
4. **Terminal receipt candidate.** Bind a mutually exclusive SUCCESS,
   TERMINAL_FAILURE, or ROLLBACK_TERMINAL candidate to the installation and
   associated evidence. Shape-valid terminal receipts do not write any
   terminal state and do not prove physical installation or recovery.

## Exact state boundary

| Condition | Shape result | Real-world truth in V1 |
| --- | --- | --- |
| All chained operations matched | JOURNAL_COMPLETION_SHAPE_READY_UNTRUSTED | NOT installed |
| All checks enumerated | POSTINSTALL_VERIFICATION_PLAN_READY_UNTRUSTED | NOT verified |
| Every check envelope matches | POSTINSTALL_EVIDENCE_SHAPE_READY_UNTRUSTED | NOT independently verified |
| Completion candidate + reopened health envelope | INSTALL_SUCCESS_CANDIDATE_UNTRUSTED | NOT success attested |
| Clean authoritative failure before first mutation | INSTALL_TERMINAL_FAILURE_CANDIDATE_UNTRUSTED | NOT failure attested |
| Reverse rollback + full clean-reopen envelope | INSTALL_ROLLBACK_TERMINAL_CANDIDATE_UNTRUSTED | NOT rollback attested |
| Any missing, conflicting or ambiguous evidence | BLOCKED / INSTALL_OUTCOME_UNKNOWN (or ROLLBACK_OUTCOME_UNKNOWN) | No inferred result |

## Coverage details

A complete journal must bind all four current upstream operation kinds:
`COPY_NEW_FILE`, `REPLACE_EXISTING_FILE`, `SET_OWNER_ACL` and
`CREATE_STARTUP_ENTRY`. The current plan is not extended with Task Scheduler
or Windows-service mutations. The completion verifier must check what the
upstream plan actually contains; it cannot silently expand mutation authority.

Mandatory fresh-reopen scope:

- `INSTALL_COMMITMENT_CAS_REOPEN`: durable install ID, consumed owner
  authorization and consumed token on the **same** write-ahead commitment.
- `JOURNAL_CHAIN_REOPEN`: sequence, genesis and operation/observation integrity
  after a fresh persistence read, not a still-open in-memory object.
- `PACKAGE_MANIFEST_REOPEN`: exact signed/attested package digest and version.
- `TARGET_FILES_REOPEN`: expected copied/replaced files and missing extras;
  reject stale, swapped, symbolic-link/reparse and path traversal surprises.
- `OWNER_ACL_REOPEN`: owner SID and exact effective ACL vs signed policy,
  including inheritance and undesired permissions.
- `STARTUP_ENTRY_REOPEN`: correct Windows owner-scope startup mechanism,
  command, arguments, working directory and intended binary identity.
- `AION_RUNTIME_HEALTH_REOPEN`: independent process identity/version and
  actual health/handshake, with approved local permissions. No simulated health
  or startup-entry existence can be substituted for real health.
- `TARGET_FINAL_STATE_REOPEN`: final before/after-evidence-bound state for
  each unique target after the entire mutation sequence.

Reopened physical receipts must be anchored to the **same installation ID,
package manifest, immutable plan, commitment, Windows owner SID, verifier
policy/version, operation history and terminal receipt**. The future attestor
must independently reject replayed receipts, stale handles, symlink/reparse
redirection, identity changes, observer collusion or missing trust anchors.
These checks are **requirements for future implementation**, not V1 claims.

## Terminal clean failure

A terminal failure is allowed as a **candidate** only when an authoritative,
independent failure receipt proves: failure occurred before the first mutation,
no write occurred, there is no ambiguity, and a fresh readback shows no
residual change. A possible write means `OUTCOME_UNKNOWN`, not a clean
failure. A partial installation cannot be relabeled as a terminal clean
failure to bypass rollback.

## Rollback terminal receipt

On an upstream `UNKNOWN` or `CONFIRMED_TERMINAL_FAILURE`, recovery remains
separate and blocks all automatic forward retry/continuation.

For a failure/ambiguity at sequence N, recovery steps are checked in **exactly**
`[N, N-1, ..., 1]` order. Every rollback step must bind:

- the original operation ID and signed rollback action;
- observed restored state matching the original before-state;
- positive rollback write receipt;
- fresh readback receipt and independent verifier receipt;
- explicit absence of ambiguity.

A final clean-state reopen receipt is mandatory. If a rollback step cannot be
proven, the terminal result is `ROLLBACK_OUTCOME_UNKNOWN`, not success. This
contract **does not execute** reversal, authenticate a real receipt, remove
a start entry, restore ACL, delete a copied file, or allow another install.

## Domain separation and immutability

Use separate schemas/digests for journal completion, postinstall verification
plan, postinstall evidence, rollback receipt and final terminal receipt.
The terminal candidate must bind the verified plan and matching completion
gate; installation ID equality alone is insufficient.

An untrusted caller cannot turn a shape-valid synthetic receipt into a
persistence certificate. The future writer must enforce a durable compare-and-set
terminal transition and read-after-write/reopen attestation; an UNKNOWN outcome
is not equivalent to a clean failed or healthy installed state.

## Non-operational security limits

The pure Python module imports no Windows APIs, subprocesses, network clients,
filesystem write libraries or persistence drivers. It does not read real
Windows state. Synthetic test digests are placeholders, **not evidence**.

The next **computer-dependent** implementation step, after a separate explicit
authorization and security review, is a synthetic-target Windows consumer for
actual independent postinstall readback and terminal receipt attestation.
Production install, deployment and Worker activation remain separate gated
decisions.
