# AION Windows — Terminal Receipt Persistence + Post-Reboot Health V1

**Status:** IMPLEMENTATION SAFE / DESIGN ONLY / NO WRITE / NO REBOOT  
**Date:** 2026-10-08  
**Base:** #1059 Installation Completion + Postinstall Verification + Rollback Receipt V1

## Objective

A terminal install receipt is not durably persisted merely because a caller
constructed a valid-looking receipt. Even a durably persisted install-success
receipt is not proof that AION remains healthy after a Windows restart.

All contract classifications are candidate / `UNTRUSTED` and lack the power to
perform or authorize a real installation, state write, reboot or repair.

## Boundary A — single durable terminal receipt

Upstream inputs: the #1059 terminal receipt **shape candidate** and immutable
installation/journal/owner/host/package/target bindings.

Future terminal-record storage requirements:
- One durable **single-assignment** terminal record per installation ID and store
  identity, with a deterministic record key and stable nonce.
- State transition via compare-and-set:
  `terminal_state NONE (revision N) -> receipt_outcome (revision N+1)`.
- Atomic enforcement of compare, write and revision; do not infer success when
  a timeout or transport error occurs.
- An identical replay is **read-only** verification, not a second write.
  A conflicting outcome or changed receipt for the same installation blocks.
- Only a privileged, independently authenticated future consumer may perform
  the write. Caller-created hashes, review documents or chat messages do not.
- A fail-closed write receipt must bind the exact installation ID, terminal
  candidate digest, owner SID, host identity, store identity, record key,
  CAS prior/after state, nonce, writer identity and revision.

This V1 builds **write-intent candidates only**. It never consumes
HUMAN_OWNER authorization or install token, and it does not touch any database.

## Boundary B — durable-write evidence and reopen

A future persistence verifier must require independently validated:
1. exact CAS commit receipt with authoritative writer identity;
2. compare-and-set observation of expected `NONE` and revision;
3. post-CAS state and next revision;
4. read-after-write from the canonical durable store;
5. fresh close/reopen from independent reader;
6. stable record/store/install/owner/host/package/journal bindings;
7. detectable replay or duplicate outcome conflict.

The Python module only checks envelope shapes. Even with all digests present,
`terminal_receipt_persisted_trusted=false` and
`reopen_physically_verified=false`. No result in V1 permits a real trust
promotion.

## Boundary C — post-reboot verification

Post-reboot health revalidation is scoped to a **SUCCESS candidate** only;
a clean failure or rollback receipt cannot be mistaken for a boot-healthy app.

A future trusted device-side verifier must establish **real reboot occurrence**
using an independently corroborated boot epoch distinct from the preboot epoch,
fresh device identity, a one-time postboot challenge tied to the install, and
non-replayable receipts. Boot epoch/challenge digests are only placeholders in
this V1.

After Windows startup, all checks are mandatory:

1. Fresh reopen of the terminal receipt.
2. Exact install commitment and full journal chain.
3. Host and owner SID identity match.
4. Proof the Windows boot epoch changed.
5. Package signature/version and all final target files.
6. Effective owner ACL policy after reboot.
7. Startup entry target, args, intended binary and owner context.
8. AION process/binary identity and expected version.
9. Actual local runtime health and challenge-bound handshake.
10. No unexpected change after startup.
11. Independent response to the fresh reboot challenge.

Each check must have a dedicated after-reboot independent-readback envelope,
bound to the identical installation/terminal receipt/challenge/boot epoch.

## Health classifications

| Candidate classification | Required observation | Operational meaning |
| --- | --- | --- |
| `POSTREBOOT_HEALTHY_CANDIDATE_UNTRUSTED` | Every check positively verified in a complete synthetic evidence envelope | Shape only, **not real health** |
| `POSTREBOOT_UNHEALTHY_CANDIDATE_UNTRUSTED` | All evidence envelopes valid, at least one authoritative, independent negative health/security check | Shape only, requires reconciliation |
| `POSTREBOOT_HEALTH_OUTCOME_UNKNOWN` | Missing readback, unresolved mismatch, ambiguous process/identity, stale epoch/challenge, or conflicting request | Never infer success |

A confirmed unhealthy runtime does not mean a clean install failure or a
verified rollback. No automatic reinstall, retry, repair or uninstallation.

## Safety, replay, and privilege constraints

- Receipt persistence is distinct from physical health.
- Positive digests alone cannot prove a Windows OS readback.
- Reboot-check receipts must be authenticated to actual device owner/session,
  verifier binary and installation ID; enforce nonce freshness and boot-epoch
  authenticity in the **future device consumer**, not in this pure module.
- Same-install retry cannot consume another owner token or authorize new
  mutating actions.
- If the terminal-record store is unavailable, CAS is ambiguous, boot is not
  observable, identity changed, or the health responder cannot be authenticated,
  the outcome remains UNKNOWN.
- Existing terminal success can later become unhealthy; retain immutable
  original terminal receipt and record health separately as new observations.
- Offline mode must use previously established on-device trust anchors, never
  an unverified external answer or an assumed provider success.
- Sensitive identifiers should be represented by policy-approved digests;
  production receipts require independently established authenticity.
- Do not claim a permanent 24h wake-word service without separate permissions,
  user settings and platform service constraints.

## This PR does not do

No Windows device access, no persistent CAS write, no install commitment,
no token/owner approval consumption, no journal or terminal receipt persistence,
no file copy/replacement, no ACL/startup change, no process launch, no reboot,
no health probe, no rollback, no uninstall, no deploy or Worker activation.

The maximum state is
`READY_FOR_TERMINAL_PERSISTENCE_AND_POSTREBOOT_CONSUMER_IMPLEMENTATION`.

The next PC-dependent step is a **synthetic trusted store and device-test
harness**, with explicit security review before any real Windows integration.
Never promote `*_CANDIDATE_UNTRUSTED` to trusted without independent,
privileged physical attestation.
