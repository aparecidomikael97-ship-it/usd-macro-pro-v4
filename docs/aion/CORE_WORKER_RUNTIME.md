# AION Worker Runtime V1

Worker Runtime V1 adds controlled autonomy to the AION scheduler/executor stack.

It is intentionally **session-scoped autonomy**, not a claim of durable 24/7
multi-instance infrastructure.

## Runtime model

The worker can be explicitly armed by an authenticated ADMIN. Once armed, the
Central AION UI uses a Streamlit fragment to call `worker_tick` periodically
while that Streamlit session remains active.

Default interval: 60 seconds.

The worker does not create a daemon, operating-system service, cron job or
external queue consumer.

The runtime truth flags remain:

- `session_autonomy = true`
- `multi_instance_safe = false`
- `continuous_24x7_confirmed = false`
- `external_persistence = EXPLICIT_CHECKPOINT_SAVE`

## State machine

Worker state is persisted under:

`aion_core_worker_v1`

States:

- DISABLED
- ARMED
- PAUSED
- KILLED

A worker becomes ARMED only after an explicit authenticated ADMIN confirmation.

PAUSED releases the current lease and prevents further ticks.

KILLED activates the kill switch, releases the lease and prevents further
ticks until a new explicit arming action creates a new arm digest.

## Lease and heartbeat

Every autonomous tick requires a lease.

The lease records:

- owner/runtime ID
- random lease token
- acquired_at
- heartbeat_at
- expires_at

If another runtime sees a live lease owned by a different runtime, it returns
`LEASE_HELD` and performs no work.

The current owner refreshes the heartbeat and lease expiry on each tick.

When a previous lease has expired, a different runtime can reclaim it. This
increments both:

- `lease_reclaims`
- `crash_recoveries`

Idempotent execution receipts remain the protection against repeating a
terminal occurrence after a crash/reclaim.

## Authorization boundary

The executor now distinguishes:

- `HUMAN_CLICK`
- `ARMED_WORKER`

Manual execution still requires the explicit checkbox/click introduced by the
previous executor block.

Autonomous execution is permitted only after a valid Worker Runtime arming
state and claimed lease. Worker receipts store `authorization_mode=ARMED_WORKER`
and a worker authorization digest. They do not pretend that a human clicked
for every periodic tick.

This does not grant physical authority.

## Capability and Guardian boundary

The Worker Runtime calls the same allowlisted local executor kernel:

- ADMINISTRATION
- MEMORY
- RESEARCH
- VOICE preparation only
- CONTENT draft only
- OBSERVABILITY

The same Guardian, sensitive-intent blocker and safety flags remain active.

The worker cannot automatically:

- call a provider
- generate neural audio
- publish content
- deploy
- merge
- execute subprocesses/shell
- make payments
- move money
- place market orders
- enable real trading

## Retry queue

Retry state is derived from FAILED executor receipts.

Only retryable local exceptions enter the queue.

Queue rows contain:

- occurrence key
- schedule ID
- capability
- attempt
- retry_after
- WAITING_BACKOFF or READY state

The executor's existing maximum attempt and backoff policy remains authoritative.

The Worker Runtime does not spin in a tight retry loop. It retries only on a
later periodic tick after the backoff expires.

## Checkpoint integrity

Worker state carries its own digest.

The master Checkpoint integrity report includes the worker namespace. A tampered
worker state becomes `MISMATCH` and the normal Checkpoint save gate blocks
external persistence.

Worker changes participate in the Checkpoint conflict digest and existing
backup/version history/rollback.

## Session limitations

The lease is stored in the working Checkpoint associated with the active
Streamlit session.

Therefore V1 does **not** claim globally safe coordination across multiple
independent Render instances or multiple disconnected browser sessions.

This limitation is explicit and intentional because all currently autonomous
capabilities are local/read-or-draft and have no physical/external side effects.

A future multi-instance worker requires a genuinely shared atomic lease store.

## UI controls

The Central AION shows:

- worker state
- lease state
- retry queue size
- 24/7 confirmation state
- interval
- Arm Worker
- Pause Worker
- Kill switch
- tick/processed/success/failure/block/crash-recovery statistics

When ARMED, a Streamlit fragment invokes the worker periodically.

Each tick writes only to the working Checkpoint. External durability still
requires the existing explicit master-checkpoint save flow.

## Next infrastructure gate

To claim global/24x7 autonomy, a later block must provide:

- shared atomic lease/compare-and-swap storage
- multi-instance fencing tokens
- durable heartbeat independent of browser sessions
- durable queue/claim semantics
- deployment/runtime supervision
- instance identity attestation
- operator-wide kill switch
- explicit cost/resource budgets

Until that exists, the product must not describe Worker Runtime V1 as globally
multi-instance-safe or continuously available 24/7.
