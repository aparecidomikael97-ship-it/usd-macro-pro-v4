# AION V2 — Mandatory durable admission: conservative source gate

**10/10/2026 · Draft, on top of #1161.**

The Autopilot direct Shadow/Flight sink caller used only a per-process
quarantine. A new Python process, separate machine, GitHub Actions job or
rollback could reattempt an unknown write. The existing one-process lock is
not globally authoritative.

## Interim production-code policy

The actual Autopilot callsites retain their existing guard wrapper, but
that wrapper now **always refuses to invoke the Shadow/Flight writers**
until a shared independently verified durable one-shot claim is built,
operated, proved and separately authorized. No toggle/test flag exists
to bypass the refusal. A denial says DURABLE_CLAIM_REQUIRED, no write
attempted by this guard, and never asserts remote durability. Existing
read-only reporting and other unrelated Autopilot sinks remain out of scope.

This is a deliberate **availability trade-off for safety**: the two sinks
will not persist new samples through this guarded Autopilot path. This
does NOT prove any past uncertain write is resolved.

## Required future protocol (not yet implemented)

- Immutable operation identity bound to repo, runtime branch, sink, exact
  serialized payload digest, expected revision, actor identity and expiry.
- Persistent claim stored with independently witnessed monotonic generation
  and compare-and-swap across **different processes/hosts/runners**.
- A claim recorded durably BEFORE any network PUT; crash after a claim must
  result in blocked/UNKNOWN pending state on every subsequent process.
- Explicit outcomes for NOT_ADMITTED, PENDING, VERIFIED_REMOTE_READBACK,
  UNKNOWN, CONFLICT, or operator-signed resolution; none are retry grants.
- Read-only reconciliation comparing the whole payload, generation, scope
  and independent custody evidence; no "record id exists => SAVED" shortcut.
- Rollback/tamper, storage corruption, partition, stale witness, lost ACK,
  concurrent callers and restored checkpoint MUST all fail closed.
- No new authority, spending or physical device operation from this draft.

## Scope and outstanding work

The owner's seven-file local Codex Shadow/Research consumer patch is staged
in a separate worktree and **was not copied or changed by this PR**.
Integration of the #1156 and #1161 source histories is still pending.
GitHub #1117 remains HARD NO-GO. No merge/deploy/Worker/cost increase.

Testing must demonstrate the guard never calls real writers, in-process
parallel calls and a fresh Python process, plus the inherited security CI.
All tests are offline and cannot certify independent durable CAS.
