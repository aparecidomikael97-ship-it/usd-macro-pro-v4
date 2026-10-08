# AION Windows Probe Collector + Independent Verifier Contract V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING TWO-PARTY VERIFICATION CONTRACT  
Date: 2026-10-08  
Collector implemented: NO  
Collector executed: NO  
Verifier implemented: NO  
Verifier executed: NO  
Physical evidence collected: NO  
Build authorized: NO

## Objective

Define the two independent Windows components required after #1049:

1. a physical-evidence collector;
2. an independent evidence verifier.

The collector measures.

The verifier judges.

They may not collapse into one component.

## Core separation rule

`WHO_COLLECTS DOES NOT DECIDE. WHO DECIDES DOES NOT COLLECT.`

The collector may eventually execute only the exact physical measurement methods
defined by #1049.

It may not:

- verify its own evidence;
- mark evidence as independently verified;
- issue a verification receipt;
- authorize a build;
- start a build;
- install a package;
- mutate a repository;
- merge;
- deploy;
- load GitHub credentials;
- execute an arbitrary command;
- open a shell, PowerShell or cmd.exe.

The verifier may eventually read immutable evidence and evaluate it.

It may not:

- execute Windows probes;
- collect raw evidence;
- modify raw evidence;
- modify collector evidence;
- authorize/start the build;
- install a package;
- mutate a repository;
- merge or deploy;
- execute arbitrary commands.

## Exact measurement contract

The collector manifest inherits all twelve #1049 requirements and their exact:

- canonical sequence;
- measurement method;
- measurement-plan digest;
- expected observation;
- negative test;
- freshness window.

If the set or order differs, the collector manifest blocks.

## Collector identity

A collector manifest binds:

- collector ID;
- probe-plan digest;
- sandbox-preflight digest;
- host-binding digest;
- #1049 collector-design digest;
- collector source SHA-256;
- collector test SHA-256;
- collector binary SHA-256;
- build provenance digest;
- package attestation digest;
- collector Ed25519 public-key fingerprint;
- exact measurement contract;
- forbidden capabilities.

## Collector release signature

The collector release manifest is signed with Ed25519.

The release signature covers:

- component identity;
- collector manifest digest;
- source digest;
- test digest;
- binary digest;
- collector key fingerprint.

A binary change after signing invalidates the release signature.

The collector private key is not loaded by this module.

## Independent verifier identity

A verifier manifest binds:

- verifier ID;
- same probe-plan/preflight/host context;
- collector manifest digest;
- collector key fingerprint;
- verifier source SHA-256;
- verifier test SHA-256;
- verifier binary SHA-256;
- raw-evidence decoder digest;
- verification-policy digest;
- trust-policy digest;
- verifier Ed25519 public-key fingerprint;
- exact required checks.

## Mandatory difference

Collector and verifier must use different:

- logical identities;
- source digests;
- binary digests;
- signing keys.

A shared value in any of those identity-critical dimensions blocks the verifier
or separation contract.

## Verifier required checks

The future verifier must independently recompute at least:

- plan binding;
- sandbox-preflight binding;
- host binding;
- measurement-plan binding;
- collector-manifest binding;
- collector release signature;
- collector binary digest;
- raw evidence digest;
- sequence;
- expected observation;
- negative-test observation;
- freshness;
- collector identity;
- evidence immutability.

The collector is not authoritative for any of those verification results.

## Verifier release signature

The verifier itself has a separate Ed25519 release signature.

Its release identity covers:

- verifier manifest digest;
- verifier source digest;
- verifier test digest;
- verifier binary digest;
- verifier key fingerprint.

A collector key cannot satisfy the verifier key binding.

## Process/state separation

The future physical implementation requires:

- separate process boundary;
- separate writable state;
- verifier access to raw evidence as read-only;
- no shared private key;
- no shared executable binary;
- no shared writable verification state.

This V1 defines those requirements but does not physically prove them.

## Immutable evidence handoff

The intended physical flow is:

`COLLECTOR -> IMMUTABLE EVIDENCE STORE -> VERIFIER`

The verifier must not receive a mutable in-memory object directly from the
collector as authority.

The handoff must be digest-bound and immutable/read-only from the verifier's
point of view.

The exact Windows storage mechanism remains PC-side implementation work.

## Verification receipt template

This V1 defines the future verifier receipt shape.

All twelve requirements start:

`NOT_VERIFIED`

with blockers:

- PHYSICAL_EVIDENCE_NOT_COLLECTED
- INDEPENDENT_VERIFIER_NOT_EXECUTED

Therefore:

- required_total=12
- verified_total=0
- all_requirements_verified=false
- receipt_issued=false
- receipt_signed=false
- physical_proof_verified=false
- windows_sandbox_verified=false
- build_authorized=false

## Why the receipt is unissued

A schema is not evidence.

A signed collector binary is not evidence that the sandbox passed.

A signed verifier binary is not a verification result.

The receipt can be issued only after the future verifier actually evaluates the
future physical evidence.

## Synthetic cryptographic validation

CI generates temporary Ed25519 key pairs solely for tests.

The tests prove:

- valid collector release signature verifies;
- changed collector binary digest invalidates the signature;
- valid verifier release signature verifies;
- wrong verifier key blocks;
- shared collector/verifier key blocks;
- shared source/binary identity blocks.

These are contract tests only.

No production signing key is created or stored.

## Maximum state

After this V1 is green, the maximum state is:

`READY_FOR_WINDOWS_COLLECTOR_VERIFIER_IMPLEMENTATION`

This means the two-party design is ready for future Windows implementation.

It still reports:

- collector_implemented=false
- collector_executed=false
- verifier_implemented=false
- verifier_executed=false
- physical_evidence_collected=false
- verification_receipt_issued=false
- physical_proof_verified=false
- windows_sandbox_verified=false
- build_authorized=false
- build_started=false
- package_built=false
- package_installed=false

## Next PC phase

The next physical phase is:

`IMPLEMENT_WINDOWS_COLLECTOR_AND_INDEPENDENT_VERIFIER_WITH_SYNTHETIC_PROBES`

That work requires the owner's Windows PC.

The first executions must use synthetic/non-production sandbox probes only.

Even a green physical-probe verification must remain separate from production
build authorization.

## Explicitly absent

This V1 does not:

- inspect Windows;
- create a restricted token;
- create/query a Job Object;
- open probe files;
- spawn a probe process;
- attempt child-process creation;
- test real network surfaces;
- collect raw evidence;
- write immutable evidence;
- execute the verifier;
- issue/sign a verification receipt;
- authorize/start a build;
- build/install a package;
- load production private signing keys;
- load GitHub credentials;
- call GitHub;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_PROBE_COLLECTOR_INDEPENDENT_VERIFIER_CONTRACT_V1_VALIDATED`

No physical Windows proof or build authority is implied.
