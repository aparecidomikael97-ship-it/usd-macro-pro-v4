# AION Windows Atomic Installation Start + File Transaction Journal V1

Status: IMPLEMENTATION SAFE / DESIGN-ONLY INSTALLATION MUTATION BOUNDARY  
Date: 2026-10-08  
Install commitment written: NO  
Owner install authorization consumed: NO  
Install token consumed: NO  
Journal persisted: NO  
Installation started: NO  
Files copied: NO  
Rollback performed: NO  
Package installed: NO

## Objective

Define the exact durable boundary between a future trusted #1057 install token
and the first Windows installation mutation.

This layer is stacked on #1057.

It does not mutate the filesystem.

## No fictional filesystem/database atomicity

Durable state and Windows filesystem/ACL/startup mutations are different
physical systems.

This design therefore does NOT claim they can be one ACID transaction.

Future flow:

1. final pre-copy revalidation;
2. CAS-consume HUMAN_OWNER install authorization + install token;
3. persist INSTALL_COMMITTED;
4. persist an append-only transaction-journal plan;
5. execute exactly one planned mutation at a time;
6. capture/read back after every mutation;
7. append the mutation observation;
8. only then consider the next mutation.

## Write-ahead install commitment

The future durable CAS transition is:

Owner installation authorization:

`UNCONSUMED -> CONSUMED_FOR_INSTALL`

Install token:

`UNCONSUMED -> CONSUMED_FOR_INSTALL`

Installation:

`NONE -> INSTALL_COMMITTED`

All three durable state changes must occur together before first mutation.

This V1 only defines the candidate.

It does not write it.

## Commitment persistence evidence

Future persistence evidence requires:

- install-commitment record digest;
- writer manifest;
- write receipt;
- CAS observation;
- read-after-write observation;
- reopen observation;
- owner-authorization consumption observation;
- token-consumption observation.

Shape validation may reach only:

`INSTALL_COMMITMENT_PERSISTENCE_SHAPE_VALID_BUT_UNTRUSTED`

No journal or filesystem mutation becomes authorized merely by the presence of
those fields.

## Transaction journal

The journal is:

- append-only;
- strictly sequenced;
- non-reorderable;
- non-deletable;
- non-replaceable.

Each operation binds:

- canonical sequence;
- operation ID;
- operation kind;
- target digest;
- before-state digest;
- intended after-state digest;
- rollback-action digest;
- source-artifact digest.

Every mutation must have rollback material before it can enter the plan.

## Supported V1 operation kinds

The design recognizes only:

- COPY_NEW_FILE
- REPLACE_EXISTING_FILE
- SET_OWNER_ACL
- CREATE_STARTUP_ENTRY

This does not execute any of them.

Scheduled Tasks/services remain outside this mutation V1.

## Journal-chain integrity

The first journal entry must bind the deterministic journal genesis digest.

Every later entry must bind the exact preceding entry:

- same installation ID;
- same journal-plan digest;
- sequence exactly previous + 1;
- exact preceding journal-entry digest.

A forged predecessor, skipped sequence or plan mismatch blocks.

## One mutation at a time

Forward progress is allowed only after the previous mutation is classified as:

`INSTALL_OPERATION_APPLIED_CONFIRMED`

A mutation cannot be considered applied from intent alone.

Positive confirmation requires:

- operation attempted;
- before-state observation;
- mutation-write observation;
- after-state observation;
- rollback material present;
- observed before state equals bound before state;
- observed after state equals intended after state.

## Terminal failure

`INSTALL_OPERATION_CONFIRMED_TERMINAL_FAILURE`

requires:

- operation attempted;
- authoritative terminal-failure evidence;
- no evidence that a write occurred.

If write evidence exists while failure is claimed, the result becomes
ambiguous.

## Ambiguity

Any missing/conflicting evidence causes:

`INSTALL_OPERATION_OUTCOME_UNKNOWN`

Examples:

- write may have occurred but after-state cannot be read;
- filesystem flush is uncertain;
- process/observer crashed;
- after-state digest differs;
- conflicting observations exist.

For OUTCOME_UNKNOWN:

- forward progress is blocked;
- automatic retry is forbidden;
- automatic continue is forbidden;
- reconciliation is required;
- rollback review is required.

## Recovery contract

Unknown or terminal-failure states create a separate recovery contract.

Recovery requires:

- reopening the journal;
- filesystem readback;
- rollback executor identity;
- reverse-order rollback plan.

If ambiguity occurs at sequence N, rollback order is:

`N, N-1, ... 1`

The recovery contract itself does NOT authorize or perform rollback.

It does not authorize a new installation.

## Why automatic retry is forbidden

Repeating a file/ACL/startup operation after an ambiguous crash may:

- overwrite an already-applied file;
- destroy before-state evidence;
- apply ACL twice against a changed target;
- create duplicate startup state.

Therefore unknown outcome is fail-closed.

## Generic chat remains non-authoritative

This layer preserves:

`generic_chat_is_install_mutation_authority=false`

The chat instruction "Vamos lá" authorizes only safe design/PR progression.

It cannot consume the owner authorization/token or mutate Windows.

## Maximum current state

`READY_FOR_WINDOWS_ATOMIC_INSTALL_CONSUMER_IMPLEMENTATION`

The next Windows phase may implement first against a synthetic/non-production
target directory:

- durable install-commit writer;
- append-only journal writer;
- one-operation-at-a-time mutation executor;
- before/after state observer;
- recovery/reconciliation reader.

## Explicitly absent

This V1 does not:

- persist INSTALL_COMMITTED;
- consume HUMAN_OWNER install authorization;
- consume an install token;
- persist a journal;
- copy/replace a file;
- change ACLs;
- create startup entries;
- modify Registry;
- create Scheduled Tasks/services;
- execute rollback;
- install a package;
- spawn processes;
- call GitHub/network;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_ATOMIC_INSTALL_START_FILE_TRANSACTION_JOURNAL_V1_VALIDATED`

No physical Windows installation mutation is implied.
