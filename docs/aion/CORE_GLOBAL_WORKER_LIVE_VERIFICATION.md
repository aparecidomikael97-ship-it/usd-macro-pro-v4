# AION Global Worker Live Activation Verification V1

This block defines the first operational state that may truthfully be called
**live** after the Global Worker feature flag is enabled.

It is entirely read-only.

## Truth model

These states are deliberately separate:

1. `STAGED_ARMED`
2. persisted `ARMED`
3. feature flag `ENABLED`
4. shared heartbeat observed
5. completed shared tick observed
6. optional `GLOBAL_WORKER` work receipt observed

A repository variable becoming ENABLED is never sufficient to claim that the
worker is operational.

## Activation boundary

Post-activation evidence must be newer than a trustworthy activation boundary.

The verifier uses the later timestamp from:

- repository variable `updated_at`;
- the explicit activation result `activated_at`, when still available in the
  current UI session.

At least one trustworthy timestamp is required.

## Heartbeat evidence

The worker state in the shared Checkpoint must remain:

- `ARMED`;
- `kill_switch = false`.

A heartbeat is accepted only when:

- `last_heartbeat_at >= activation boundary`;
- `last_runtime_id` begins with `gha-`.

This binds the observation to the GitHub Actions global runner rather than a
browser/session worker.

## Tick evidence

A fully completed idle tick requires:

- `last_tick_at >= activation boundary`;
- the same `gha-` runtime identity.

A completed tick proves the scheduled runner actually woke even when no work
was due.

Therefore an idle worker can truthfully become:

`LIVE_CONFIRMED_IDLE`

without inventing a work receipt.

## Work receipt evidence

When due work exists, the verifier also looks for executor receipts with:

`authorization_mode = GLOBAL_WORKER`

and `completed_at >= activation boundary`.

If found together with heartbeat/tick evidence, the state is:

`LIVE_CONFIRMED_WITH_WORK`

## Unsafe receipt fail-closed

Any post-activation GLOBAL_WORKER receipt reporting:

- provider call;
- external action;
- real trading;

blocks the live claim.

This verifier never converts such evidence into success.

## Lease protection

A lease that still has an owner after its expiry is considered stale and
returns:

`BLOCKED_STALE_LEASE`

The system must not present a stale lease as healthy operation.

## Timeout

Default maximum wait for the first shared heartbeat/tick:

`4500 seconds` (75 minutes)

This covers more than two nominal 30-minute pulse opportunities plus scheduling
delay.

If no shared heartbeat is observed after that window:

`LIVE_EVIDENCE_TIMEOUT`

The correct operational response is to treat the worker as not confirmed live
and use the existing safety-disable path if activation had occurred.

## Statuses

- `NOT_ENABLED`
- `AWAITING_LIVE_EVIDENCE`
- `LIVE_HEARTBEAT_CONFIRMED_AWAITING_TICK`
- `LIVE_CONFIRMED_IDLE`
- `LIVE_CONFIRMED_WITH_WORK`
- `LIVE_EVIDENCE_TIMEOUT`
- `BLOCKED_STALE_LEASE`
- `BLOCKED_UNSAFE_RECEIPT`
- `BLOCKED`

Only the two `LIVE_CONFIRMED_*` states set `live_confirmed=true`.

## Central AION

The Activation Ceremony panel gains:

`📡 Verificar Worker Global ao vivo`

That action:

- rereads the repository flag;
- rereads the shared runtime Checkpoint;
- performs only read-only verification;
- shows heartbeat, tick and work-receipt status;
- never executes a worker tick itself.

## No mutation authority

The verifier contains no:

- PUT / POST / PATCH / DELETE;
- runtime checkpoint save;
- feature-flag mutation;
- worker tick;
- workflow dispatch;
- subprocess/shell;
- provider call;
- payment;
- publication;
- deployment;
- trading.

## Current repository state

This block is being developed while the real runtime remains unactivated.

Therefore CI can prove the verifier logic with synthetic state, but it cannot
claim a real live heartbeat until the separate arming, persisted arming and
feature-activation ceremonies are explicitly executed in the future.

A green PR means the verification mechanism is ready, not that the worker is
currently live.
