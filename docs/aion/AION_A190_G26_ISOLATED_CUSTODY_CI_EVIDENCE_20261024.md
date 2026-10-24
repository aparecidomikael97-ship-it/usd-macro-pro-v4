# A190 G26 — In-process isolated custody protocol CI evidence

Date: 2026-10-24. Exact tested SHA `47f3c85d21beb4451c679786b2374c6883cb472f`.

## CI evidence
- [GitHub Actions #40121213255](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40121213255): both jobs completed SUCCESS.
- Ubuntu job `120952935773`: **18/18**.
- Windows job `120952935960`: **18/18**.
- Total: **36 executions of 18 distinct tests**.

## Protocol model
A separate in-process `IsolatedCustodyService` object holds an ephemeral Ed25519 private key, monotonic counter and semantic reservations. Exact replay is idempotent, conflicting semantic reservation denies. Signed challenge-bound attestations and a matching high-water mark allow only `UNCERTAIN_ZERO_AUTO_RESEND`, never SEND/RETRY.

## Explicit RED evidence
- `G26_CUSTODY_RESTART_RED=IN_MEMORY_RESERVATION_LOST`: a new instance cannot recover a previous reservation.
- `G26_MONOTONIC_RESTART_RED=COUNTER_RESET_AFTER_RESTART`: counter restarts at 1.
- `G26_CUSTODY_ROLLBACK_RED=OLD_SERVICE_ACCEPTS_OLD_HISTORY`: replacing custody with an old in-process instance can make old history appear current.

## Limits and follow-up
This is NOT a separate machine, external operator, remote witness, non-rollback storage, externally provisioned key, or actual first-attempt external reservation. An object-private Python field does NOT protect keys from hostile code in the same process. The next implementation must establish actual independence and monotonic durability before any P0 claim. No real AION runtime integration, provider, Worker, main/merge/deploy/customer/credentials/spend, canonical Quality/Security rerun or P0 closure.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
