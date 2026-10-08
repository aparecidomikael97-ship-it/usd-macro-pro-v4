# AION Windows Package Attestation Persistence + Installation Authorization Gate V1

Status: IMPLEMENTATION SAFE / DESIGN-ONLY INSTALLATION BARRIER  
Date: 2026-10-08  
Package attestation persisted: NO  
Package attestation reopen verified: NO  
Owner installation authorization persisted: NO  
Installation authorized: NO  
Installation started: NO  
Package installed: NO

## Objective

Define the boundary between an already attested offline package and any future
physical Windows installation.

This layer is stacked on #1055.

It does not duplicate package attestation.

It consumes the existing positive supply-chain state:

`PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED`

and adds:

1. immutable persistence/reopen requirements for the package attestation;
2. a separate HUMAN_OWNER installation authorization ceremony;
3. durable nonce/replay/single-use requirements for that authorization;
4. exact rollback/uninstall/install-plan bindings.

## Package-attestation prerequisite

The package must already satisfy the existing package-attestation contract:

- valid package-attestation schema;
- state PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED;
- release signature verified;
- Authenticode signature verified;
- trusted Authenticode chain verified;
- Authenticode timestamp verified;
- expected publisher match verified;
- package-attestation digest;
- installation-manifest digest;
- archive/SBOM/provenance/dependency-lock digests;
- Authenticode binary/evidence digests;
- release-review digest.

A partial or blocked package attestation cannot enter this gate.

## Persistence contract

The package-attestation persistence contract is:

- append-only;
- compare-and-set;
- exactly-once;
- read-after-write;
- reopen consistent;
- no replace;
- no delete.

It binds the exact:

- package attestation;
- installation manifest;
- archive;
- SBOM;
- build provenance;
- dependency lock;
- Authenticode binary/evidence;
- release review;
- package signer fingerprint;
- package family/version/build identity;
- persistence writer;
- store design.

## Persistence shape is not persistence proof

The future physical writer must provide:

- record key;
- record digest;
- writer manifest;
- write receipt;
- CAS observation;
- read-after-write observation;
- reopen observation;
- persistence timestamp.

A structurally complete record may reach only:

`PACKAGE_ATTESTATION_PERSISTENCE_SHAPE_VALID_BUT_UNTRUSTED`

It still reports:

- persistence_trusted=false
- cas_verified=false
- read_after_write_verified=false
- reopen_verified=false
- installation_authorized=false

Caller self-attestation is rejected.

## Installation gate

The installation gate binds the persisted package identity to one exact future
installation plan:

- package-attestation digest;
- installation-manifest digest;
- archive digest;
- package version/build identity;
- installation target digest;
- owner ACL policy;
- startup policy;
- rollback archive;
- rollback manifest;
- uninstall manifest;
- installation-plan digest;
- owner binding.

A later authorization therefore cannot be reused for another package, target,
ACL/startup policy or rollback plan.

## Rollback and uninstall are mandatory

The owner must not authorize a one-way installation.

The signed install scope requires:

- rollback archive;
- rollback manifest;
- uninstall manifest.

Those are identity/digest bindings in this V1.

No rollback or uninstall is executed here.

## Generic chat is not installation authority

The policy explicitly keeps:

`generic_chat_is_install_authorization=false`

A normal message such as:

`Vamos lá`

continues to authorize only the safe design/PR work already in progress.

It does NOT authorize Windows installation.

## HUMAN_OWNER ceremony

Purpose:

`HUMAN_OWNER_EXPLICIT_WINDOWS_LOCAL_AGENT_INSTALLATION`

Mechanism:

`ED25519_EXTERNAL_OWNER_EXECUTION_KEY`

Allowed decisions:

- AUTHORIZE_WINDOWS_LOCAL_AGENT_INSTALLATION
- DENY_WINDOWS_LOCAL_AGENT_INSTALLATION

Maximum authorization window:

`120 seconds`

## Exact signed installation request

The owner signature binds:

- installation-gate digest;
- exact package-attestation digest;
- package-persistence attestation digest;
- installation-manifest digest;
- archive digest;
- installation target;
- owner ACL policy;
- startup policy;
- rollback archive;
- rollback manifest;
- uninstall manifest;
- install plan;
- owner binding;
- owner public-key fingerprint;
- nonce;
- issued/expires timestamps;
- exact decision.

Any post-signature change breaks verification.

## Real Ed25519 verification

CI uses temporary synthetic owner keys to verify the cryptographic contract.

A valid authorize signature reaches only:

`OWNER_INSTALL_AUTH_SIGNATURE_VERIFIED_PENDING_PERSISTENCE`

It still reports:

- nonce_claimed=false
- authorization_persisted=false
- authorization_consumed=false
- installation_authorized=false
- install_token_issued=false
- installation_started=false
- package_installed=false

A valid signed denial reaches:

`OWNER_INSTALL_DENIAL_SIGNATURE_VERIFIED`

and never becomes installation authority.

## Owner-authorization persistence

A future owner authorization must also prove:

- persistent nonce registry;
- nonce replay guard;
- single-use nonce;
- durable authorization record;
- CAS;
- read-after-write;
- reopen consistency;
- authorization still unconsumed.

Its current maximum shape-only state is:

`INSTALL_AUTH_PERSISTENCE_SHAPE_VALID_BUT_UNTRUSTED`

It still grants no installation authority.

## No self-attestation

These claims are not authority:

- caller package-persistence trust;
- caller install-authorization persistence trust;
- generic chat acknowledgment.

All are fail-closed.

## Maximum current state

The maximum design state is:

`READY_FOR_WINDOWS_INSTALLATION_AUTHORIZATION_IMPLEMENTATION`

The next Windows phase may implement using synthetic/non-production package
records first:

- package-attestation writer;
- package reopen verifier;
- install nonce registry;
- install authorization writer;
- installation preflight.

## Explicitly absent

This V1 does not:

- persist the package attestation;
- claim/reuse an owner nonce;
- persist owner install authorization;
- issue an install token;
- authorize installation;
- copy/delete package files;
- create directories;
- modify Windows Registry;
- modify ACLs;
- create startup entries;
- install a Scheduled Task/service;
- spawn an installer/process;
- execute rollback/uninstall;
- call GitHub/network;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_PACKAGE_ATTESTATION_PERSISTENCE_INSTALL_AUTH_GATE_V1_VALIDATED`

No physical Windows installation is implied.
