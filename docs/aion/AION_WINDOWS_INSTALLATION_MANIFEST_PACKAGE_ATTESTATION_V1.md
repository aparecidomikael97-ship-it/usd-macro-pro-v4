# AION Windows Installation Manifest + Local Agent Package Attestation V1

Status: IMPLEMENTATION SAFE / NON-INSTALLING SUPPLY-CHAIN BOUNDARY  
Date: 2026-10-08  
Package built: NO  
Package installed: NO  
Windows startup modified: NO  
Real GitHub credentials: ABSENT  
Live GitHub mutation: DISABLED

## Objective

Define the exact future Windows local-agent package before anything is copied or
installed on the owner's PC.

This V1 closes:

- file inventory;
- file hashes;
- package version/build identity;
- archive digest;
- SBOM digest;
- build provenance;
- dependency-lock digest;
- release signature;
- Windows code-signing evidence;
- anti-downgrade rules;
- uninstall/rollback preservation.

It does not build or install the package.

## Closed file inventory

A valid V1 package contains exactly seven logical roles:

1. AGENT_ENTRYPOINT
2. REPOSITORY_MUTATION_RUNTIME
3. RUNTIME_HARDENING
4. PROCESS_ISOLATION
5. HEALTH_IPC_DESCRIPTOR
6. RUNTIME_POLICY
7. UNINSTALL_DESCRIPTOR

Each role is bound to one exact relative path.

No extra file is allowed.

The manifest rejects:

- missing roles;
- duplicate roles;
- duplicate paths;
- role/path swaps;
- absolute paths;
- Windows drive paths;
- backslash paths;
- path traversal;
- forbidden directories;
- unapproved file suffixes.

## Exact destinations

The logical package paths are:

- `agent/aion_repository_mutation_agent.py`
- `lib/atlasquant_aion_repository_mutation_offline_runtime_v1.py`
- `lib/atlasquant_aion_repository_mutation_local_runtime_hardening_v1.py`
- `lib/atlasquant_aion_windows_local_service_crash_isolation_v1.py`
- `config/health-ipc-v1.json`
- `config/runtime-policy-v1.json`
- `config/uninstall-v1.json`

These are package-relative paths.

This PR does not create the physical install directory or copy these files.

## Per-file integrity

Every file requires:

- SHA-256 digest;
- positive bounded size;
- exact role/path binding.

Only AGENT_ENTRYPOINT may carry the package executable flag.

All other package entries must be non-executable data/module entries in this
manifest model.

## Sensitive material forbidden

Every package entry must explicitly prove absence of:

- credential material;
- private-key material;
- secret locator material;
- network endpoint material.

A package that contains any of these is blocked before attestation.

Runtime credentials remain a separate future broker boundary.

## Version/build identity

The installation manifest binds:

- package family;
- offline owner-local channel;
- semantic version;
- build ID;
- exact 40-character build commit SHA;
- Windows platform;
- x86_64 architecture;
- current-user service mode;
- minimum Windows build;
- pinned Python 3.12 patch version;
- creation time;
- exact file list;
- total package size.

## Package-level evidence

Package attestation requires:

- archive SHA-256;
- SBOM SHA-256;
- build-provenance SHA-256;
- dependency-lock SHA-256;
- release-review digest.

The detached release signature covers the exact package release payload,
including manifest, archive, SBOM, provenance, dependency lock, version, build
ID and build commit.

## Detached release signature

V1 performs real Ed25519 public-key verification of the release payload.

The package signer public-key fingerprint must equal the separately expected
signer fingerprint.

The private package-signing key is never loaded by this module.

A wrong signer or wrong signature blocks the package.

## Windows Authenticode boundary

Actual Windows Authenticode verification requires a Windows-produced evidence
attestation.

V1 requires all four facts:

- Authenticode signature verified;
- trusted certificate chain verified;
- trusted timestamp verified;
- expected publisher match verified.

The evidence and binary are bound by SHA-256 digests.

This Linux CI run does not pretend to execute Windows Authenticode verification
itself.

That proof must be collected on Windows before installation.

## Maximum package state

A positive result is only:

`PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED`

It means supply-chain evidence is structurally complete and cryptographically
bound.

It does not authorize or perform installation.

## Anti-downgrade

Upgrade preflight blocks:

- any semantic-version downgrade;
- any boolean attempt to bypass downgrade policy;
- same semantic version with a different manifest.

A future downgrade, if ever needed, must have a separately designed signed
ceremony.

There is no downgrade bypass in V1.

## Rollback prerequisites

Before a future forward upgrade can enter installation review, V1 requires:

- current package-attestation digest;
- rollback archive digest;
- rollback manifest digest.

Upgrade readiness still reports:

- installation_authorized=false
- package_installed=false
- rollback_executed=false

## Uninstall preservation

The uninstall manifest removes only package-owned paths by default.

Before uninstall it requires the kill switch to be forced enabled.

By default it preserves:

- runtime SQLite database;
- audit evidence;
- owner public-key enrollment.

Owner key/data purge requires a separate explicit owner ceremony.

Therefore uninstall does not silently erase forensic history or identity
evidence.

## Why data preservation matters

Deleting the agent package and deleting owner runtime evidence are different
actions.

A normal uninstall should be reversible/auditable.

Destructive purge is a higher-risk owner decision and must remain separate.

## Supply-chain relationship

This package boundary follows the same AION principle already used in the closed
Tool Supply Chain:

- closed inventory;
- pinned hashes;
- drift blocks;
- appearance at runtime never grants approval;
- supply-chain evidence is not execution authority.

This package registry is local-agent-specific and does not replace or modify the
Core Tool Supply Chain registry.

## Explicitly absent

This V1 does not:

- build an EXE/MSI;
- copy files;
- create directories;
- create a startup entry;
- modify Windows Registry;
- modify ACLs;
- install a service or Scheduled Task;
- spawn a process;
- load a private signing key;
- load GitHub credentials;
- open network;
- call GitHub;
- perform repository mutation;
- deploy;
- activate Worker/provider/production persistence.

## PC phase requirements

Before a package is actually installed on Mikael's Windows computer, the PC
phase must verify the real artifact:

- actual file SHA-256 values;
- actual archive SHA-256;
- actual SBOM;
- actual dependency lock;
- actual package provenance;
- actual release signature;
- actual Windows Authenticode signature;
- actual trusted timestamp and publisher;
- actual LOCALAPPDATA target;
- actual owner ACL;
- actual startup mechanism;
- actual rollback archive.

CI cannot substitute for those host-specific facts.

## Next safe phase

After this V1 is green, the next phone-safe block is:

`WINDOWS LOCAL AGENT BUILD RECIPE + REPRODUCIBLE PACKAGE CONTRACT V1`

That can define a deterministic build recipe, locked dependencies and expected
artifact composition without producing or installing a production package.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_INSTALLATION_MANIFEST_PACKAGE_ATTESTATION_V1_VALIDATED`

No installation is implied.
