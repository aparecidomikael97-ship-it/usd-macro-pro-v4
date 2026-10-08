# AION Windows Offline Build Sandbox + Input Mount Contract V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING SANDBOX CONTRACT  
Date: 2026-10-08  
Physical Windows sandbox created: NO  
Build process spawned: NO  
Production build started: NO  
Network: DENY BY CONTRACT  
Live GitHub mutation: DISABLED

## Objective

Define the exact Windows isolation boundary that must exist before the future
reproducible local-agent build may run.

This layer consumes:

- the reproducible build recipe from #1046;
- the attested offline dependency-cache promotion from #1047.

It does not execute the build.

## Filesystem roots

Five local Windows roots are bound:

- cache root — READ_ONLY;
- source root — READ_ONLY;
- runtime root — READ_ONLY;
- output root — WRITE_ONLY_BUILD_OUTPUT;
- temp root — READ_WRITE_EPHEMERAL.

All roots must be absolute local-drive paths.

UNC/network-share paths are forbidden.

No two roots may overlap, including case-insensitive Windows aliases.

For example, an output directory below the cache root is blocked.

## Write boundary

The future process may write only to:

- output root;
- temp root.

It may not write to:

- dependency cache;
- source tree;
- pinned Python runtime;
- repository;
- another user path;
- a device path;
- a network share.

Output is not trusted as a later input merely because the process created it.

## Filesystem escape rules

The sandbox contract denies:

- path traversal;
- symlink escape;
- NTFS reparse-point escape;
- hardlink escape;
- Alternate Data Streams;
- device path access;
- mount/share escape.

These are contract requirements.

They are not claimed as physically enforced until a future Windows probe proves
them.

## Environment scrub

The build process may not inherit the user's parent environment.

No PATH lookup is allowed.

Sensitive or host-dependent variables such as the following are rejected:

- PATH
- PYTHONPATH
- PYTHONHOME
- HOME
- USERPROFILE
- USERNAME
- COMPUTERNAME
- APPDATA
- LOCALAPPDATA
- TEMP/TMP
- HTTP_PROXY/HTTPS_PROXY/ALL_PROXY
- GITHUB_TOKEN/GH_TOKEN
- GIT_CONFIG_* variables

The contract creates an exact environment containing deterministic build values
and only the five sandbox roots.

## Deterministic environment

The scrubbed environment includes:

- TZ=UTC
- LC_ALL=C.UTF-8
- LANG=C.UTF-8
- PYTHONHASHSEED=0
- PYTHONNOUSERSITE=1
- PYTHONSAFEPATH=1
- PYTHONDONTWRITEBYTECODE=1
- PIP_NO_INDEX=1
- PIP_DISABLE_PIP_VERSION_CHECK=1
- PIP_CONFIG_FILE=NUL
- SOURCE_DATE_EPOCH bound to the #1046 recipe

Caller overrides are forbidden.

## Process allowlist

The future build process policy is:

`SINGLE_PINNED_PYTHON_NO_CHILDREN`

Only one exact absolute `python.exe` under the bound runtime root is allowed.

It must be bound by SHA-256.

The build script must live under the read-only source root and must match the
build-script digest already bound in #1046.

The fixed command shape includes:

- python.exe
- -I
- -S
- pinned build script
- --offline
- --no-network
- exact cache/source/output/temp roots

## Explicit process denials

The contract denies:

- shell;
- cmd.exe;
- PowerShell;
- PATH executable lookup;
- python -c;
- python -m pip;
- arbitrary arguments;
- child process creation;
- detached/background processes.

This V1 does not spawn even the allowed Python process.

## Network boundary

Policy is:

`DENY_ALL`

Denied surfaces include:

- DNS;
- TCP;
- UDP;
- loopback;
- proxies;
- remote named pipes;
- UNC/network shares.

The contract does not create a firewall rule or physically prove the Windows
network boundary.

## Resource limits

The future physical sandbox must enforce at most:

- runtime: 300 seconds;
- memory: 1024 MB;
- output: 128 MiB;
- process count: 1;
- child process count: 0.

The intended Windows mechanism includes a restricted token and Job Object, but
neither is created in this phase.

## Maximum positive state

The maximum positive state is:

`WINDOWS_OFFLINE_BUILD_SANDBOX_READY_FOR_PHYSICAL_PROBE`

It does not mean READY_FOR_EXECUTION.

It still reports:

- physical_windows_sandbox_verified=false
- restricted_token_created=false
- job_object_created=false
- read_only_mounts_created=false
- network_isolation_physically_verified=false
- build_authorized=false
- build_started=false
- package_built=false
- package_installed=false

## Physical proofs still required

Before a real build, the Windows host must independently prove:

1. restricted token;
2. Job Object limits;
3. cache read-only boundary;
4. source read-only boundary;
5. runtime read-only boundary;
6. output/temp-only write boundary;
7. symlink/reparse/hardlink anti-escape;
8. environment scrub;
9. exact pinned Python binary;
10. no child-process escape;
11. network deny;
12. resource-limit enforcement.

Those facts cannot be established by Linux CI.

## Relationship to previous layers

#1045 defines the allowed package composition and release attestation.

#1046 defines deterministic build identity.

#1047 defines trustworthy frozen build inputs.

This V1 defines the execution cage that must contain the future build.

The next physical stage must prove this cage exists on Windows before any
production build starts.

## Explicitly absent

This V1 does not:

- mount folders;
- modify ACLs;
- create a restricted token;
- create a Job Object;
- create firewall rules;
- open or block a real socket;
- spawn python.exe;
- run pip;
- run the build script;
- write output;
- build a package;
- install a package;
- load credentials/private keys;
- call GitHub;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Next safe phase

After this V1 is green, the next phone-safe block is:

`WINDOWS SANDBOX PHYSICAL PROBE PLAN + EVIDENCE SCHEMA V1`

That layer can define exactly how the future Windows PC will measure restricted
token, Job Object, filesystem ACL/mount behavior, process containment and
network isolation without yet authorizing the production build.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_OFFLINE_BUILD_SANDBOX_INPUT_MOUNT_CONTRACT_V1_VALIDATED`

No physical sandbox or production build is implied.
