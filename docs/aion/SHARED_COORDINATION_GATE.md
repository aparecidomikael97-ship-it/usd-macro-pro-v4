# AION Shared Coordination Gate V1

This block defines the contract required before AtlasQuant may claim globally
coordinated or continuously available autonomous workers.

It intentionally ships **without a production shared backend adapter**.

Repository inspection found no already-connected Redis, PostgreSQL, Supabase,
shared SQLite, CAS/ETag store or distributed lock service suitable for this
claim. Therefore the runtime remains fail-closed.

## Why this gate exists

Worker Runtime V1 can operate autonomously inside one active Streamlit session.

That is not enough for:
- multiple Render instances;
- disconnected browser sessions;
- failover between instances;
- globally unique ownership;
- true continuous 24/7 worker claims.

A shared atomic store is required to prevent two workers from believing they
both own the same job.

## Required backend capabilities

A production adapter must prove:

- shared_across_instances
- atomic_compare_and_swap
- monotonic_versions
- atomic_monotonic_fencing_token
- ttl_expiry
- atomic_delete
- durable_outside_browser
- global_kill_switch_namespace

Self-declared metadata is not enough. The adapter must pass a real bounded
probe.

## Provider-neutral adapter

The `SharedCoordinationAdapter` protocol requires:

- `describe()`
- `read(key)`
- `compare_and_swap(...)`
- `delete(...)`
- `next_fencing_token(...)`

No database or network library is imported by this block.

No endpoint, credential or paid service is configured automatically.

## Real CAS probe

`run_coordination_probe` is available for a future injected adapter.

It requires explicit authenticated ADMIN confirmation because it performs
temporary external mutations.

The probe verifies:

1. absent/read behavior;
2. create CAS;
3. rejection of a stale CAS;
4. live CAS using the current version;
5. read-after-write;
6. monotonic store versions;
7. monotonic fencing tokens from a separate atomic counter;
8. cleanup.

The probe uses a random temporary namespace and a short TTL for the fencing
test.

A successful probe receipt is bound to the exact adapter identity and expires
after 15 minutes.

A stale, future-dated, modified or different-adapter receipt cannot support
activation.

## Custo Zero policy

If an adapter declares `external_paid_service=true`, the probe is blocked
unless paid-service approval is explicitly supplied.

This repository block does not activate any paid service.

## Resource budget

The activation gate requires exact integers for:

- max_workers
- max_claims_per_minute
- max_lease_seconds
- max_probe_writes

Booleans, numeric strings and out-of-range values are rejected.

The observed probe mutation count must fit inside the approved
`max_probe_writes` budget.

## Fencing

The shared lease does not derive fencing tokens from a local counter.

A production adapter must provide an independent atomic monotonic fencing
counter.

Each new ownership generation receives a higher fencing token.

Releasing or deleting a lease does not reset that counter.

A stale worker cannot heartbeat a lease after a newer owner has taken control,
because owner, lease token and fencing token must all match.

## Shared lease manager

`SharedLeaseManager` supports provider-neutral:

- claim
- heartbeat
- release
- global kill switch

An active lease owned by another runtime returns `LEASE_HELD`.

A race lost during CAS returns `CAS_CONFLICT`.

A heartbeat from a stale owner or stale fencing token returns `LOST`.

## Global kill switch

The kill switch is stored in a separate shared namespace.

Its epoch increments whenever active/inactive state changes.

A claim checks the kill switch before attempting ownership.

Leases include the observed kill epoch so a later integration can fence work
across global stop/re-enable cycles.

## Checkpoint Mestre

Successful probe receipts may be staged under:

`aion_shared_coordination_v1`

The bundle has its own digest and participates in the master Checkpoint
integrity gate.

A tampered probe bundle turns the master integrity state into `MISMATCH` and
blocks normal external checkpoint persistence.

Storing a successful probe receipt does not mean a global worker has started.

## Activation gate

`activation_gate` requires all of:

- authenticated ADMIN context;
- configured adapter;
- all required capabilities;
- fresh successful probe bound to that adapter;
- exact resource budget;
- probe mutations within the budget;
- explicit activation confirmation.

Even when all are satisfied, V1 returns:

- `coordination_ready=true`
- `global_worker_started=false`
- `execution_authorized=false`

This block validates infrastructure. It does not start a global worker.

## Central AION

The Central shows **Shared Coordination Gate V1 · autonomia global**.

With the repository's current state it truthfully reports:

- backend: NONE
- coordination: UNAVAILABLE
- multi-instance: NÃO
- 24/7 global: NÃO
- reason: NO_SHARED_ATOMIC_STORE_CONFIGURED

This is deliberate.

## Still required for global worker activation

After a real atomic backend is chosen and explicitly approved, a later block
must connect:

- a production adapter;
- instance identity attestation;
- shared scheduler/checkpoint claim semantics;
- fencing token propagation into every executed occurrence;
- durable shared receipts/idempotency;
- operator-wide kill switch;
- runtime supervisor independent of browser sessions;
- cost/resource enforcement;
- deployment configuration and operational runbook.

Until then AtlasQuant must not claim global multi-instance safety or 24/7
autonomous operation.
