# AION Physical Repository Mutation Runtime V1 — Offline/Local First

Status: IMPLEMENTATION / OFFLINE SYNTHETIC RUNTIME  
Date: 2026-10-08  
Real GitHub API: DISABLED  
Real repository writes: DISABLED  
Production credentials: ABSENT  
Deploy / Worker activation: NO

## Objective

Move from contract-only repository-mutation architecture to a real executable
runtime without exposing the live GitHub repository to writes.

This V1 implements physical local durability and execution only against:

`SYNTHETIC_LOCAL_REPOSITORY_V1`

It performs real SQLite writes and real mutations of an in-memory synthetic
repository model.

It does not perform a GitHub mutation.

## Implemented runtime components

### Local durable SQLite store

A single local SQLite database stores:

- nonce/replay reservations;
- authorization receipts;
- atomic authorization consumption;
- synthetic mutation attempts;
- reconciliation records;
- terminal audit records.

SQLite runs with:

- WAL journal mode;
- synchronous=FULL;
- foreign keys enabled;
- BEGIN IMMEDIATE for write serialization.

On non-Windows hosts the database file is tightened to owner-only permissions on
a best-effort basis.

The database is local runtime evidence, not a Git branch and not a second
production repository truth.

## Fail-closed kill switch

The runtime initializes with:

`kill_switch.enabled=true`

Reason:

`BOOTSTRAP_FAIL_CLOSED`

No attempt or reconciliation may occur until the offline synthetic harness
explicitly opens the switch.

The same kill switch can stop reconciliation after an ambiguous attempt.

This V1 does not define a production ceremony for disabling a live kill switch.

## Durable nonce/replay registry

Nonce reservations are keyed by:

- scope;
- nonce digest.

A second reservation of the same scope+nonce fails with:

`NONCE_REPLAY_REJECTED`

The replay state survives database reopen.

## External HUMAN_OWNER signature verification

The runtime implements actual Ed25519 public-key verification.

It verifies a signature over the exact authorization-receipt digest using a
fixed AtlasQuant/AION domain-separation context.

The runtime contains no private-key generation or owner-signing capability.

It reports:

- private_key_loaded=false
- private_key_generated=false
- signature_generated_by_this_module=false

A real HUMAN_OWNER private signer remains outside this runtime.

## Durable authorization persistence

Before any synthetic attempt, the runtime persists the exact authorization
receipt plus:

- receipt payload digest;
- owner signature attestation digest;
- owner public-key fingerprint;
- PR number;
- mutation;
- main SHA;
- head SHA;
- base branch;
- expiry.

Reopening the same receipt is allowed only when immutable fields match exactly.

Conflicting persistence fails closed.

## Atomic authorization consumption

Authorization consumption uses an immediate SQLite transaction and a conditional
update:

`WHERE consumed_at=''`

Exactly one consumer can transition an authorization from unconsumed to
consumed.

A second consumption fails.

An expired authorization cannot be consumed.

## Synthetic provider

The only provider in this V1 is:

`SYNTHETIC_LOCAL_REPOSITORY_V1`

Supported logical mutations:

- PR_DRAFT_TO_READY
- PR_RETARGET_TO_MAIN
- SQUASH_MERGE_TO_MAIN

The provider mutates only Python synthetic state.

No endpoint, credential, network client or GitHub transport exists in this
module.

## Synthetic success path

The test harness validates:

1. Draft PR becomes Ready;
2. a child PR retargets from its parent branch to main;
3. a synthetic squash merge closes the PR and advances synthetic main;
4. each step requires a new authorization and runtime nonce;
5. the real GitHub repository is never called.

## Fault injection

The synthetic adapter supports four explicit test behaviors:

- SUCCESS
- TERMINAL_FAILURE
- UNKNOWN_AFTER_APPLY
- UNKNOWN_NO_EFFECT

### SUCCESS

The local synthetic mutation occurs and the primary result is:

`CONFIRMED_SUCCESS`

### TERMINAL_FAILURE

No synthetic effect occurs and the primary result is:

`CONFIRMED_TERMINAL_FAILURE`

### UNKNOWN_AFTER_APPLY

The synthetic effect occurs, but the primary result is intentionally:

`OUTCOME_UNKNOWN`

This models a timeout/reset after the provider may already have applied the
effect.

Automatic retry remains false.

### UNKNOWN_NO_EFFECT

No synthetic effect occurs but the primary result is still:

`OUTCOME_UNKNOWN`

Again, retry remains forbidden.

## Authoritative synthetic readback

An OUTCOME_UNKNOWN may be reconciled only by inspecting the current synthetic
repository state.

The reconciliation does not replay the mutation.

It produces either:

- RECONCILED_CONFIRMED_SUCCESS
- RECONCILED_CONFIRMED_TERMINAL_FAILURE

and always keeps:

- repository_mutation_replayed=false
- automatic_retry_allowed=false
- new_attempt_authorized=false

## Terminal audit persistence

The local runtime can persist one terminal/open audit record per attempt.

Possible outcomes:

- CERTIFIED_FINAL_SUCCESS
- CERTIFIED_FINAL_TERMINAL_FAILURE
- CERTIFIED_OPEN_AMBIGUOUS

An unknown attempt may be persisted as OPEN_AMBIGUOUS before reconciliation.

After a reconciliation, a separate fresh test fixture/attempt is used rather
than rewriting an existing conflicting audit record.

The audit store is append-only per attempt.

## What this V1 resolves from the #1041 gap register

Implemented locally/offline:

- durable nonce/replay registry;
- durable authorization store;
- atomic authorization-consumption store;
- Ed25519 public-key verification;
- emergency kill switch;
- synthetic mutation transport;
- synthetic attempt observation/evidence;
- synthetic authoritative postcondition readback;
- synthetic unknown-outcome reconciliation;
- local terminal audit persistence.

## What remains intentionally unresolved

### Real HUMAN_OWNER private signer

This runtime verifies signatures but cannot sign for the owner.

### Live GitHub state reader

No real PR/main/workflow state is queried.

### Signed live GitHub mutation adapter

No production adapter binary exists.

### Runtime credential broker

No GitHub credential is loaded, resolved or stored.

### Live GitHub transport executor

No provider write request exists.

### Live authoritative postcondition reader

Only synthetic state readback exists.

### Live reconciliation evidence collector

Only synthetic reconciliation exists.

### Production-grade terminal audit binding

Local terminal audit persistence exists, but it is not connected to a live
provider evidence chain.

## Security boundaries

This module contains no imports for:

- requests;
- urllib network calls;
- socket;
- subprocess;
- Git client libraries.

The CI gate also rejects live provider indicators.

The policy must continue to report:

- live_github_state_reader_implemented=false
- live_github_adapter_implemented=false
- runtime_credential_broker_implemented=false
- live_github_transport_executor_implemented=false
- real_github_credentials_loaded=false
- real_github_network_path_enabled=false
- github_api_called=false
- network_called=false
- live_repository_mutation_authorized=false
- live_repository_mutation_performed=false
- production_repository_mutation_performed=false
- automatic_retry_allowed=false

## Runtime truth

A successful test in GitHub Actions proves the Python runtime behavior under an
ephemeral CI host.

It does not mean the runtime has been installed on Mikael's Windows computer.

It does not mean a persistent local service is running on the owner's PC.

Installation, OS hardening, key enrollment and local service lifecycle remain a
future PC phase.

## Next safe phase

After this V1 is green, the next safe runtime stage is:

`LOCAL RUNTIME HARDENING + OWNER KEY ENROLLMENT BLUEPRINT + FILESYSTEM/PROCESS INTEGRATION`

still without production GitHub writes.

That phase should focus on:

- Windows local service/process boundary;
- owner public-key enrollment;
- local database location and ACL;
- kill-switch control surface;
- crash/restart recovery tests;
- concurrent consumption stress;
- backup/reopen integrity;
- synthetic provider adapter isolation.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_REPOSITORY_MUTATION_OFFLINE_RUNTIME_V1_VALIDATED`

This means the offline/synthetic runtime executes locally and durably.

It does not mean live GitHub mutation is ready.
