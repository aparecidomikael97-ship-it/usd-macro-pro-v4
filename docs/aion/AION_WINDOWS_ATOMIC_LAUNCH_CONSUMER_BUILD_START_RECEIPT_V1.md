# AION Windows Atomic Launch Consumer + Build Start Receipt V1

Status: IMPLEMENTATION SAFE / DESIGN-ONLY LAUNCH BOUNDARY  
Date: 2026-10-08  
Launch commitment written: NO  
Owner authorization consumed: NO  
Build token consumed: NO  
Spawn attempted: NO  
Build started: NO

## Objective

Define the exact durable boundary between a future trusted #1053 build token
and the birth of the one allowed Windows build process.

This layer is stacked on #1053.

It does not spawn a process.

## No fictional cross-system atomicity

A database transaction and Windows process creation are different physical
systems.

This design therefore does NOT claim that durable persistence and CreateProcess
can be one ACID transaction.

Instead the future flow is:

1. final pre-spawn revalidation;
2. one durable write-ahead launch commitment;
3. atomically consume HUMAN_OWNER authorization + build token in that same CAS;
4. persist LAUNCH_COMMITTED;
5. allow exactly one spawn attempt;
6. record the physical observation;
7. persist a build-start receipt.

## Write-ahead launch commitment

The launch commitment binds:

- launch ID;
- #1053 prelaunch contract;
- exact owner authorization record;
- exact build token record;
- exact final pre-spawn revalidation;
- expected owner-authorization state UNCONSUMED;
- expected token state UNCONSUMED;
- pre-launch store revision.

The future CAS transition is:

Owner authorization:
`UNCONSUMED -> CONSUMED_FOR_LAUNCH`

Build token:
`UNCONSUMED -> CONSUMED_FOR_LAUNCH`

Launch:
`NONE -> LAUNCH_COMMITTED`

These changes must be committed together in the durable store.

## Commitment persistence

Future persistence evidence must include:

- launch-commitment record digest;
- writer manifest;
- write receipt;
- CAS observation;
- read-after-write observation;
- reopen observation;
- owner-authorization consumption observation;
- token-consumption observation.

Shape validation is not trusted persistence.

The maximum current state is:

`LAUNCH_COMMITMENT_PERSISTENCE_SHAPE_VALID_BUT_UNTRUSTED`

## One spawn attempt only

After a trusted future LAUNCH_COMMITTED record, exactly one spawn attempt may
occur.

The spawn boundary binds:

- launch commitment;
- persistence attestation;
- launch lease;
- exact command digest;
- exact environment digest;
- Job Object policy;
- launch binary digest;
- build script digest.

Maximum commit-to-spawn window:

`5 seconds`

Maximum process count:

`1`

Maximum child process count:

`0`

No PATH lookup, shell or automatic retry is allowed.

## Why automatic retry is forbidden

After LAUNCH_COMMITTED, a crash may happen:

- before the process is spawned;
- during process creation;
- immediately after process creation;
- after the process started but before the observer persisted proof.

A blind retry could therefore create a second build process.

So:

- post-commit crash -> BUILD_START_OUTCOME_UNKNOWN;
- post-commit timeout -> BUILD_START_OUTCOME_UNKNOWN;
- ambiguous spawn observation -> BUILD_START_OUTCOME_UNKNOWN;
- automatic retry -> forbidden.

## Build-start receipt

The receipt begins:

`BUILD_START_RECEIPT_TEMPLATE_READY_UNISSUED`

with:

- outcome=NOT_OBSERVED
- spawn_attempted=false
- process_spawned=false
- receipt_issued=false
- receipt_persisted=false
- build_started=false

## Confirmed success

`BUILD_START_CONFIRMED`

requires all positive physical evidence:

- spawn attempt occurred;
- process was observed as spawned;
- process identity digest;
- process-handle observation digest;
- Job Object membership observation digest;
- executable-image hash observation;
- command observation digest.

Missing any required positive evidence turns requested success into:

`BUILD_START_OUTCOME_UNKNOWN`

## Confirmed terminal failure

`BUILD_START_CONFIRMED_TERMINAL_FAILURE`

requires:

- a spawn attempt;
- no process spawned;
- authoritative terminal-failure evidence.

Silence or incomplete evidence is not terminal failure.

It becomes:

`BUILD_START_OUTCOME_UNKNOWN`

## Ambiguity wins

If ambiguity evidence exists, it overrides a requested success result.

No caller may convert an uncertain start into success.

## Reconciliation

BUILD_START_OUTCOME_UNKNOWN requires a separate reconciliation contract.

The future reconciliation may inspect:

- durable launch state;
- Windows process-table/readback evidence;
- launch-specific process identity;
- Job Object membership;
- start-observer evidence.

It does NOT authorize another spawn attempt.

A new spawn requires a separately designed and explicitly authorized recovery
path.

## Current truth boundary

This V1 does not trust a future observation as physical truth merely because its
fields are present.

It never writes a commitment and never starts a process.

## Maximum current state

`READY_FOR_WINDOWS_ATOMIC_LAUNCH_CONSUMER_IMPLEMENTATION`

The next Windows phase may implement, using a synthetic/non-production build
first:

- durable launch writer;
- CAS consumer;
- one-shot process launcher;
- build-start observer;
- durable start receipt;
- unknown-outcome reconciler.

## Explicitly absent

This V1 does not:

- persist LAUNCH_COMMITTED;
- consume owner authorization;
- consume a build token;
- acquire a real launch lease;
- spawn python.exe;
- create/query a Job Object;
- observe a real process;
- issue/persist a start receipt;
- reconcile a live launch;
- retry a launch;
- build/install a package;
- call GitHub/network;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_ATOMIC_LAUNCH_CONSUMER_BUILD_START_RECEIPT_V1_VALIDATED`

No physical process launch is implied.
