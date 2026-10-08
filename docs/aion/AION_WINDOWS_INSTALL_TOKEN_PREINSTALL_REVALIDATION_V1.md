# AION Windows Install Token + Preinstall Revalidation Contract V1

Status: IMPLEMENTATION SAFE / DESIGN-ONLY FINAL PRE-COPY BARRIER  
Date: 2026-10-08  
Preinstall verifier implemented: NO  
Install token implemented: NO  
Install token issued: NO  
Installation authorized: NO  
Installation started: NO  
Files copied: NO  
Package installed: NO

## Objective

Define the final logical barrier immediately before any future Windows
installation may copy its first file.

This layer is stacked on #1056.

It defines:

1. a fresh preinstall revalidation snapshot;
2. an unissued single-use install-token template;
3. the future token issuance/persistence evidence shape.

It does not install anything.

## Fresh preinstall revalidation

Immediately before installation start, the Windows implementation must recheck:

- exact package attestation;
- package-attestation persistence;
- package-attestation reopen;
- HUMAN_OWNER install signature;
- owner install-authorization persistence;
- owner install-authorization reopen;
- owner authorization freshness;
- owner authorization still unconsumed;
- persistent nonce replay guard;
- nonce single-use;
- exact installation target;
- target safety state;
- available disk space;
- minimum Windows version;
- exact owner ACL policy;
- exact startup policy;
- exact rollback archive;
- exact rollback manifest;
- exact uninstall manifest;
- exact install plan;
- absence of unexpected existing files;
- safety-stop state;
- circuit-breaker state;
- absence of new safety blockers.

## Freshness

The preinstall snapshot may be at most:

`10 seconds`

old.

A stale snapshot blocks installation-token issuance.

## Exact binding

The snapshot must match #1056 exactly for:

- installation gate;
- persistence contract;
- package attestation;
- installation manifest;
- archive;
- installation target;
- ACL policy;
- startup policy;
- rollback archive;
- rollback manifest;
- uninstall manifest;
- install plan;
- owner binding;
- safety-stop policy;
- circuit-breaker policy;
- preinstall safety policy.

Any drift blocks.

## Existing-file protection

Before first copy, the future verifier must prove:

- target state reverified;
- target safe;
- no unexpected existing files;
- unexpected_existing_file_count=0.

An unknown file in the installation target is a blocker, not an overwrite
candidate.

## Rollback and uninstall are mandatory

Installation cannot proceed if any of these fail revalidation:

- rollback archive;
- rollback manifest;
- uninstall manifest.

This protects against a one-way installation.

## Safety stop and circuit breaker

Immediately before token issuance:

- safety stop must be armed;
- safety stop must not be engaged;
- circuit breaker must be armed;
- circuit breaker must be healthy;
- no new safety blocker may exist.

This V1 validates only the future snapshot shape.

It does not trust physical state.

## Truth boundary

A structurally complete preinstall snapshot may reach only:

`PREINSTALL_SNAPSHOT_SHAPE_VALID_BUT_EXTERNAL_TRUST_REQUIRED`

It still reports:

- external_trust_verified_by_this_module=false
- package_persistence_trusted=false
- install_authorization_persistence_trusted=false
- nonce_state_trusted=false
- target_state_trusted=false
- rollback_state_trusted=false
- safety_stop_state_trusted=false
- circuit_breaker_state_trusted=false
- install_token_issuance_allowed=false
- installation_authorized=false

## Install token

The future install token is:

- single-use;
- bound to one package;
- bound to one installation target;
- bound to one owner authorization;
- bound to one target-state snapshot;
- bound to one ACL/startup policy;
- bound to rollback/uninstall material;
- bound to one install plan.

Maximum lifetime:

`15 seconds`

Maximum uses:

`1`

Maximum installation sessions:

`1`

Maximum installation targets:

`1`

## Token template is not authority

The positive design state is only:

`INSTALL_TOKEN_TEMPLATE_READY_UNISSUED`

It still reports:

- token_implemented=false
- token_issued=false
- token_signed=false
- token_persisted=false
- token_consumed=false
- owner_install_authorization_consumed=false
- installation_authorized=false
- installation_started=false
- files_copied=false
- package_installed=false

## Atomic consumption requirement

The future physical installer must atomically consume both:

1. persisted HUMAN_OWNER installation authorization;
2. persisted single-use install token;

with the durable installation-start transition.

If that atomic state transition cannot be proven, first file copy is forbidden.

## Final pre-copy revalidation

Even after future token issuance, the installer must perform a final
pre-copy revalidation.

Copy must not begin if any of these changed:

- token expired;
- package attestation changed;
- package persistence/reopen changed;
- owner authorization expired/consumed;
- nonce state changed;
- target changed;
- unexpected files appeared;
- ACL/startup policy changed;
- rollback/uninstall material changed;
- install plan changed;
- safety stop became engaged;
- circuit breaker became unhealthy;
- a new safety blocker appeared.

## Future token persistence

The future issuance evidence must include:

- token digest;
- token signature digest;
- token-signer manifest digest;
- token record digest;
- token nonce record digest;
- write receipt;
- CAS observation;
- read-after-write observation;
- reopen observation.

The maximum shape-only state is:

`INSTALL_TOKEN_ISSUANCE_ATTESTATION_SHAPE_VALID_BUT_UNTRUSTED`

It still grants no installation authority.

## No self-attestation

`caller_claims_token_trusted=true`

is explicitly blocked.

Likewise, a complete preinstall snapshot does not become trusted physical truth
just because a caller says it is.

## Generic chat remains non-authoritative

This layer preserves:

`generic_chat_is_install_start_authority=false`

The current chat instruction "Vamos lá" continues to authorize only safe
design/PR work.

It cannot issue or consume an install token.

## Maximum current state

`READY_FOR_WINDOWS_INSTALL_TOKEN_PREINSTALL_IMPLEMENTATION`

The next Windows phase may implement first with synthetic/non-production
package records:

- preinstall verifier;
- token signer;
- token persistence writer;
- atomic install-start consumer;
- final pre-copy verifier.

## Explicitly absent

This V1 does not:

- trust a physical preinstall snapshot;
- issue/sign/persist/consume an install token;
- consume owner install authorization;
- authorize installation;
- start installation;
- copy/delete files;
- create directories;
- modify ACL/Registry/startup;
- install a Scheduled Task/service;
- spawn installer/process;
- execute rollback/uninstall;
- call GitHub/network;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_INSTALL_TOKEN_PREINSTALL_REVALIDATION_V1_VALIDATED`

No physical Windows installation is implied.
