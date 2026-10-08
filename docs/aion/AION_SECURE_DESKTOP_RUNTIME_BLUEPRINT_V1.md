# AION Secure Desktop Runtime Blueprint V1

Status: IMPLEMENTATION SAFE / BLUEPRINT-ONLY  
Date: 2026-10-08  
Stacked base: AION Local Action Audit Receipt V1  
Production status: NOT INSTALLED / NOT STARTED / NOT DEPLOYED

## Objective

Freeze the architecture of the future Windows companion agent before PC-only
implementation begins.

This block does not create an installer or run software. It defines the
security boundaries, components, threat model, readiness gates and ordered PC
implementation sequence.

## Core architectural choice

V1 uses a:

`PER_USER_DESKTOP_AGENT`

running as:

`CURRENT_USER`

inside the interactive Windows user session.

It is **not** designed as a SYSTEM service.

### Why

The intended owner experience includes:

- opening desktop applications;
- controlling approved local media actions;
- future microphone/hotword capability;
- tying actions to the currently authenticated owner session.

Those behaviors belong naturally in the interactive user session.

Running the V1 process as SYSTEM would add unnecessary privilege and complicate
safe interaction with user-session applications.

Therefore V1 requires:

- current-user identity;
- no SYSTEM runtime;
- no runtime elevation;
- least privilege;
- explicit user-login startup;
- kill switch;
- uninstall path;
- rollback path.

## Runtime components

The blueprint requires:

1. TRUSTED_OWNER_HOST_BRIDGE
2. OWNER_IDENTITY_VERIFIER
3. REPLAY_REGISTRY
4. APP_ALLOWLIST_RESOLVER
5. PROCESS_LAUNCH_ADAPTER
6. MEDIA_SESSION_ADAPTER
7. POSTCONDITION_OBSERVER
8. AUDIT_JOURNAL
9. RECEIPT_PIPELINE
10. KILL_SWITCH
11. UNINSTALL_ROLLBACK

Missing any required component blocks a ready implementation plan.

## PWA/native bridge

The current product path still includes a PWA, so browser-to-agent integration
must be treated as a dedicated security boundary.

Approved design candidates are:

- `LOOPBACK_BRIDGE`
- `CUSTOM_URI_SIGNED_ENVELOPE`
- `NATIVE_SHELL_IPC`

The final physical choice must be validated on the PC.

### LOOPBACK_BRIDGE rules

If loopback is selected, V1 requires:

- local/loopback bind only;
- no LAN/public bind;
- strict origin allowlist;
- request identity/authorization checks;
- exact protocol version;
- no implicit trust because traffic came from localhost.

### CUSTOM_URI_SIGNED_ENVELOPE rules

If custom URI is selected, every action envelope must be signed/verified and
remain subject to nonce/freshness rules.

### NATIVE_SHELL_IPC rules

If a future native AtlasQuant desktop shell is selected, the native channel
must still use strict local access control and exact protocol versioning.

## Internal IPC

The blueprint uses:

`WINDOWS_NAMED_PIPE`

for internal local component boundaries.

The future implementation must restrict the pipe ACL to the current authorized
user and exact expected components.

Named-pipe selection here does not mean a pipe has been created.

## Owner verification

At least one approved owner verification mechanism must be bound:

- WINDOWS_HELLO
- FIDO2
- OWNER_SESSION_SIGNATURE

Fresh owner verification remains separate from memory and from generic chat
acknowledgements.

## Replay protection

The installed agent must include a durable single-use replay registry.

A consumed nonce cannot be accepted again after:

- process restart;
- crash;
- logout/login;
- app restart.

The exact persistence technology is intentionally not fixed in this blueprint.

## Application authority

The local agent remains allowlist-only.

It must not expose:

- arbitrary executable paths;
- shell execution;
- arbitrary command lines;
- remote script execution;
- credential export.

Logical app resolution happens locally and must remain behind the allowlist
boundary defined by Secure Local Agent V1.

## Audit

Every attempted physical action must feed the Local Action Audit Receipt V1
pipeline.

The installed runtime therefore requires:

- postcondition observer;
- append-only audit journal;
- receipt pipeline;
- deterministic evidence digests.

Unknown outcomes remain unknown and cannot be auto-retried.

## Code signing

The future package requires:

- signed binary;
- verified signing chain;
- binary SHA-256 verification;
- signed update verification.

V1 intentionally starts with:

`SIGNED_MANUAL_UPDATE`

rather than a complex automatic updater.

This reduces the initial update attack surface. A secure auto-update system can
be designed later as a separate version.

## Local secret storage

Allowed plan modes are:

- WINDOWS_DPAPI_CURRENT_USER
- NONE_REQUIRED

No repository-embedded secret is allowed.

The preferred choice depends on whether the selected bridge needs local secret
material after the PC integration spike.

## Threat model

The blueprint explicitly covers:

- remote command injection;
- arbitrary executable launch;
- shell injection;
- owner identity spoofing;
- request replay;
- unsigned binary replacement;
- IPC hijacking;
- receipt falsification;
- privilege escalation;
- silent persistence.

Each threat has a required control in the machine-readable blueprint.

## Readiness meanings

### READY_FOR_PC_IMPLEMENTATION

This state means:

- architecture choices are internally consistent;
- all required security controls are declared;
- all required runtime components are planned;
- the design is ready for PC-only implementation work.

It does **not** mean the agent exists or is installed.

### INSTALLED_RUNTIME_ATTESTATION_VALID

This later state can only be evaluated when a real PC supplies verified
installation/runtime evidence, including:

- plan digest binding;
- binary digest;
- signed evidence bundle;
- attestor identity/signature;
- code signature;
- publisher identity;
- current-user runtime;
- absence of SYSTEM/elevation;
- absence of remote/LAN listeners;
- local channel ACL verification;
- bridge-specific security verification;
- owner verification bridge;
- durable replay registry;
- allowlist resolver;
- append-only audit journal;
- receipt pipeline;
- kill switch;
- uninstall and rollback;
- signed-update verification.

The blueprint module never gathers this evidence itself.

## PC implementation sequence

Once we are physically on the Windows PC, the planned order is:

1. PACKAGE_AND_SIGNING_SCAFFOLD
2. LOCAL_BRIDGE_SPIKE
3. OWNER_IDENTITY_BRIDGE
4. DURABLE_REPLAY_REGISTRY
5. ALLOWLIST_RESOLVER
6. PHYSICAL_ADAPTER
7. POSTCONDITION_OBSERVER
8. AUDIT_JOURNAL
9. KILL_SWITCH_UNINSTALL_ROLLBACK
10. RED_TEAM_AND_INTEGRATION

This sequence contains goals only. It generates no shell/PowerShell/install
commands.

## Important boundary

The following remain false in this phone-safe block:

- physical_install_started;
- runtime_process_started;
- startup_entry_created;
- ipc_endpoint_created;
- application_launched;
- network_called;
- worker_armed;
- deploy_executed;
- core_checkpoint_write;
- executes_action.

## Relationship to previous blocks

The sequence now becomes:

1. Owner Experience V1 — understand trusted owner intent.
2. Cognitive Memory + Continuity V1 — preserve safe context.
3. Secure Local Agent V1 — validate a low-risk local action request.
4. Local Action Audit Receipt V1 — truthfully classify the physical result.
5. Secure Desktop Runtime Blueprint V1 — define how the real Windows companion
   is allowed to be built and verified.

The actual PC runtime remains the next physical boundary.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_SECURE_DESKTOP_RUNTIME_BLUEPRINT_V1_VALIDATED`

That means the architecture/readiness contract is validated only. No Windows
agent has been installed or started.
