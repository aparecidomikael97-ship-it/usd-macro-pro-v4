# AION Windows Build Completion + Package Attestation Handoff V1

Status: IMPLEMENTATION SAFE / DESIGN-ONLY TERMINAL BUILD BOUNDARY  
Date: 2026-10-08  
Build executed: NO  
Build completion observed: NO  
Package attested: NO  
Installation authorized: NO  
Package installed: NO

## Objective

Define the terminal semantics after #1054 has already proven that one build
process started.

This layer answers:

- did the build really finish successfully?
- did it fail terminally?
- is the result ambiguous?
- may its outputs enter the existing package-attestation pipeline?

It does not run or install anything.

## Allowed build outcomes

Only three terminal classifications exist:

- BUILD_COMPLETED_SUCCESS
- BUILD_COMPLETED_TERMINAL_FAILURE
- BUILD_COMPLETION_OUTCOME_UNKNOWN

No other state may be treated as terminal truth.

## Success requirements

A requested success becomes BUILD_COMPLETED_SUCCESS only when all required
positive evidence exists:

- process exit observed;
- exit code exactly zero;
- process identity digest;
- exit-observation digest;
- build-log digest;
- exact output-inventory digest;
- archive digest;
- SBOM digest;
- build-provenance digest;
- dependency-lock digest;
- installation-manifest digest;
- package-manifest digest;
- network-deny observation digest;
- sandbox-integrity observation digest;
- zero unexpected outputs.

The dependency lock and both manifest digests must exactly match the build
contract.

Missing or mismatched evidence does not become "partial success".

It becomes:

`BUILD_COMPLETION_OUTCOME_UNKNOWN`

## Terminal failure

BUILD_COMPLETED_TERMINAL_FAILURE requires:

- process exit observed;
- non-zero exit code;
- authoritative terminal-failure evidence.

A non-zero exit code without authoritative failure evidence is not enough.

It becomes OUTCOME_UNKNOWN.

## Ambiguity wins

If ambiguity evidence exists, it overrides requested success.

Examples include:

- process/observer crash;
- output directory incomplete;
- terminal state cannot be reopened;
- artifact inventory does not match;
- uncertain filesystem flush;
- conflicting process observations.

Ambiguity means:

`BUILD_COMPLETION_OUTCOME_UNKNOWN`

and:

`automatic_retry_allowed=false`

## Why retry is forbidden

A repeated build can overwrite or mix artifacts with the first build.

Therefore an ambiguous build completion must be reconciled first.

No second build is automatically authorized.

## Artifact promotion

Only BUILD_COMPLETED_SUCCESS may create:

`BUILD_ARTIFACT_SET_READY_FOR_ATTESTATION_REVIEW`

The artifact set binds:

- completion observation;
- launch/build IDs;
- archive;
- SBOM;
- provenance;
- dependency lock;
- installation manifest;
- package manifest;
- build log;
- output inventory;
- network-deny observation;
- sandbox-integrity observation.

Even this state reports:

`artifact_set_trusted_as_physical_output=false`

because this PR does not physically collect/reopen the Windows files.

## Reuse existing package-attestation boundary

The repository already has:

`atlasquant_aion_windows_installation_manifest_package_attestation_v1.py`

This V1 does not rebuild that supply-chain system.

Instead it creates a handoff candidate whose next expected state is:

`PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED`

from the existing package-attestation contract.

## Successful build is not package attestation

A successful build proves only that the build outcome is terminally successful.

It does NOT prove:

- release signature;
- Authenticode;
- trusted certificate chain;
- trusted timestamp;
- publisher match;
- package installation safety.

Those remain separate supply-chain proofs.

## Package attestation is not install authorization

Even the existing positive package state:

`PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED`

does not authorize installation.

This PR keeps:

- installation_authorized=false
- package_installed=false

## Unknown reconciliation

BUILD_COMPLETION_OUTCOME_UNKNOWN requires a separate reconciliation contract.

The future reconciler may read:

- process terminal state;
- durable build/start records;
- output store;
- artifact directory;
- exact output inventory.

It may not:

- automatically rerun the build;
- promote artifacts;
- authorize a new launch;
- install anything.

## Maximum current state

The maximum design state is:

`READY_FOR_WINDOWS_BUILD_COMPLETION_IMPLEMENTATION`

The next Windows phase may implement against a synthetic/non-production build:

- build-completion observer;
- artifact collector;
- durable completion receipt;
- package-handoff verifier;
- unknown-outcome reconciler.

## Explicitly absent

This V1 does not:

- start or stop a process;
- observe a real Windows build;
- create archive/SBOM/provenance;
- sign a package;
- verify real Authenticode;
- persist a completion receipt;
- install files;
- modify Registry/ACL/startup;
- call GitHub/network;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_BUILD_COMPLETION_PACKAGE_ATTESTATION_HANDOFF_V1_VALIDATED`

No production build completion or package installation is implied.
