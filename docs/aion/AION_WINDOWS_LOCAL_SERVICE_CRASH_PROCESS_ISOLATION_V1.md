# AION Windows Local Service Installation Blueprint + Crash/Process Isolation V1

Status: IMPLEMENTATION SAFE / OFFLINE LOCAL PROCESS ISOLATION  
Date: 2026-10-08  
Windows service installed: NO  
Process spawned by this module: NO  
TCP/HTTP listener: NO  
Real GitHub credentials: ABSENT  
Live GitHub mutation: DISABLED

## Objective

Prepare the hardened repository-mutation runtime for a future Windows owner
installation without installing or starting a Windows service.

This V1 implements process-isolation primitives and a non-installing deployment
blueprint.

## Service model

The selected model is:

`CURRENT_USER_LOGON_AGENT`

The runtime is intended to run under the authorized current Windows user.

It does not require or authorize:

- LocalSystem;
- SYSTEM;
- a machine-wide runtime identity;
- a remote service account;
- runtime administrator elevation.

The planned startup trigger is the current user's Windows logon.

Installation mechanics remain future PC work.

## Installation blueprint

The blueprint binds:

- per-user runtime layout;
- owner-only ACL attestation;
- package digest;
- code-signing evidence digest;
- uninstall-plan digest;
- owner-key enrollment digest;
- current-user process identity;
- owner-only health IPC.

The blueprint never installs anything.

It reports:

- windows_service_installed=false
- scheduled_task_installed=false
- process_spawned=false
- filesystem_modified_by_blueprint=false

## Process singleton

The runtime uses an atomic local lock file.

Acquisition uses create-if-absent semantics.

Exactly one process may acquire the lock.

CI stress launches 32 contenders and requires exactly one winner.

The lock contains immutable owner/process metadata and a digest over that
metadata.

Tampering with PID, instance ID or another bound field invalidates the digest.

## Lock persistence after crash

A lock is never automatically deleted because it appears old.

A stale heartbeat means only:

`PROCESS_LIVENESS_ATTESTATION_REQUIRED`

It does not mean the process is definitely dead.

The lock remains in place.

The runtime also forces the kill switch enabled.

## Crash recovery

Stale-lock recovery requires external evidence proving:

- the previous process is not running;
- the current Windows session matches the authorized owner;
- the lock digest matches the crashed instance;
- the runtime kill switch is enabled.

Only after the recovery record is durably written may the stale lock be removed.

Recovery does not:

- replay a repository mutation;
- release consumed authorization;
- reopen the mutation gate;
- authorize automatic restart.

## Fail-closed startup

Every process start forces:

`kill_switch.enabled=true`

with reason:

`SERVICE_STARTUP_FAIL_CLOSED`

Even if the owner had previously opened the local synthetic mutation gate, a
restart closes it again.

The owner must complete the separate signed kill-switch ceremony from the
previous hardening layer before mutation readiness can become true again.

## Fail-closed shutdown

Clean shutdown also forces the kill switch enabled before releasing the process
lock.

This prevents a future process from inheriting an already-open mutation gate.

## Fail-closed crash handling

When a stale heartbeat is detected, the runtime forces the kill switch enabled
with the crash-recovery reason.

The lock remains present until verified dead-process recovery.

## Heartbeat

The service-instance row records a last heartbeat timestamp.

Maximum accepted heartbeat age in V1:

`30 seconds`

A stale heartbeat degrades health and makes mutation readiness false.

Heartbeat freshness does not grant mutation authority.

## Health vs readiness

Health and mutation readiness are deliberately separate.

A process may be:

- healthy=true;
- mutation_runtime_ready=false.

This is the normal state immediately after startup because the kill switch is
enabled.

Mutation readiness requires:

- process health;
- current singleton lock;
- matching service instance;
- SQLite integrity;
- fresh heartbeat;
- kill switch disabled through the signed owner ceremony.

## Owner-only local health IPC

The logical future health transport is a Windows named pipe:

`\\.\pipe\AtlasQuant.AION.RepositoryMutationRuntime.Health.v1`

Allowed operations:

- GET_HEALTH
- GET_READINESS

The health IPC contract forbids:

- command dispatch;
- repository mutation dispatch;
- credential exchange;
- anonymous access;
- remote pipe access;
- TCP listener;
- HTTP listener.

This V1 defines the IPC contract only.

It does not open the named pipe.

## Same durable runtime truth

Service-instance and crash-recovery metadata are added to the same hardened
SQLite database used by the offline runtime.

No second runtime database is introduced.

## Crash/restart relation to authorization

Process recovery never changes repository-mutation authorization semantics.

In particular:

- consumed authorization remains consumed;
- authorization is never auto-released;
- OUTCOME_UNKNOWN remains non-retryable;
- restart never creates a new attempt authorization.

## Explicitly absent

This V1 does not:

- install a Windows service;
- install a Scheduled Task;
- spawn the local agent;
- change Windows startup settings;
- modify a real ACL;
- create a firewall rule;
- open a named pipe;
- open TCP/HTTP;
- permit LAN/remote control;
- load the HUMAN_OWNER private key;
- load GitHub credentials;
- query or call GitHub;
- perform a live repository mutation;
- deploy;
- activate Worker/provider/production persistence.

## PC phase boundary

Because this work is being prepared without direct access to the owner's
Windows machine, CI validates the process-isolation logic only.

A later PC phase must prove the actual host properties:

- Windows account/SID;
- LOCALAPPDATA path;
- filesystem ACL;
- package/code signature;
- process startup mechanism;
- process identity;
- named-pipe ACL;
- abrupt-kill recovery;
- reboot recovery;
- uninstall path.

Those facts must not be inferred from CI.

## Next safe phase

After this V1 is green, the next safe phone-side block is:

`WINDOWS INSTALLATION MANIFEST + LOCAL AGENT PACKAGE ATTESTATION V1`

That block can define the exact files, hashes, permissions, startup entry and
uninstall/rollback manifest that the PC installation will later verify.

It should still perform zero installation and zero live GitHub write.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_LOCAL_SERVICE_CRASH_PROCESS_ISOLATION_V1_VALIDATED`

This means the local process isolation and crash-recovery logic is validated.

It does not mean anything has been installed on the owner's Windows computer.
