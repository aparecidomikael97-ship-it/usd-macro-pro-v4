# AION Windows Immutable Evidence Store + Verification Receipt Persistence Contract V1

Status: IMPLEMENTATION SAFE / DESIGN-ONLY PERSISTENCE CONTRACT  
Date: 2026-10-08  
Store opened: NO  
Database opened: NO  
Evidence persisted: NO  
Verification receipt persisted: NO  
Build authorized: NO

## Objective

Define how future Windows physical-probe evidence and the independent-verifier
receipt must be persisted without allowing rewrite, reorder, truncation or
retroactive promotion.

This layer is stacked on #1050.

It does not open a database or write files.

## Persistence model

The persistence mode is:

`APPEND_ONLY_CAS_EXACTLY_ONCE`

Required semantics:

- append-only;
- compare-and-set;
- exactly-once;
- single-writer commit;
- read-after-write;
- reopen consistency.

Delete, replace and truncate are forbidden.

## Canonical store identity

The store contract binds:

- one logical store namespace;
- #1049 probe-plan digest;
- #1048 sandbox-preflight digest;
- host-binding digest;
- collector manifest + key fingerprint;
- verifier manifest + key fingerprint;
- collector/verifier separation digest;
- writer-manifest digest;
- evidence-store design digest;
- receipt-store design digest.

The store also derives a deterministic evidence-chain genesis digest.

## Twelve immutable evidence records

One evidence record is required for every canonical physical requirement.

Each record binds:

- store namespace;
- probe plan;
- host binding;
- requirement;
- canonical sequence;
- record key;
- store contract;
- sandbox preflight;
- measurement-plan digest;
- collector manifest;
- collector binary;
- collector release payload;
- collector signature evidence;
- raw evidence SHA-256;
- evidence-payload SHA-256;
- expected observation;
- negative-test observation;
- collected/valid-until timestamps;
- previous-record digest;
- expected pre-store revision;
- future committed revision.

The record digest is calculated over that complete material.

## Record identity vs record content

The deterministic record key identifies:

`host + plan + requirement + sequence`

The evidence-record digest identifies the complete content.

Therefore:

same record key + same record digest
= idempotent replay

same record key + different record digest
= conflict

A changed raw-evidence digest changes the record digest even though the logical
record identity remains the same.

## Chain order

The evidence chain must contain exactly 12 records in the exact order inherited
from #1049.

Record 1 points to the deterministic genesis digest.

Each later record points to the preceding evidence-record digest.

Reordering or changing one intermediate previous-record digest invalidates the
chain.

## Maximum evidence-chain state

The maximum state in this design phase is:

`TWELVE_RECORD_EVIDENCE_CHAIN_CANDIDATE_READY_UNTRUSTED`

This means the chain is structurally consistent.

It does not mean:

- evidence was physically collected;
- evidence is independently verified;
- records were persisted;
- the chain survived reopen;
- the Windows sandbox passed.

## Verification receipt persistence

The verification receipt is a separate append-only record.

It is bound to:

- store contract;
- complete evidence-chain digest;
- final chain-head digest;
- probe plan;
- host;
- verifier manifest;
- collector/verifier separation;
- receipt-template digest;
- receipt revision 1.

The future receipt must be exactly-once, CAS-protected and immutable.

## No retroactive receipt promotion

This V1 consumes the unissued #1050 receipt template.

It explicitly requires:

- receipt_issued=false
- verified_total=0

A caller cannot turn the template into a final receipt merely by changing those
fields.

The actual future verifier-issued receipt requires a later physical execution
and verifier-signature boundary.

## No evidence mutation after receipt

Once a future verification receipt is committed, its bound evidence chain may
not be changed.

Therefore:

`evidence_chain_mutation_after_receipt_allowed=false`

A later probe must create a new plan/run identity and new evidence chain, not
edit the old one.

## Future persistence attestation

The schema defines the shape expected from a future writer/reopen verifier:

- record kind;
- record key;
- record digest;
- expected pre-store revision;
- committed store revision;
- writer-manifest digest;
- write-receipt digest;
- CAS-observation digest;
- read-after-write observation digest;
- reopen observation digest;
- persistence timestamp.

However, shape validation is not persistence proof.

The maximum state is:

`PERSISTENCE_ATTESTATION_SHAPE_VALID_BUT_UNTRUSTED`

It still reports:

- physical_persistence_verified=false
- cas_verified=false
- read_after_write_verified=false
- reopen_verified=false
- record_persisted_trusted=false

## Self-attestation is rejected

A future caller cannot pass:

`caller_claims_persistence_verified=true`

and create trusted persistence.

That claim is explicitly blocked.

The physical writer and independent reopen verifier must provide externally
validated evidence later.

## Crash semantics

The future implementation must distinguish:

- crash before commit — do not infer persistence;
- crash after commit — reopen exact existing record;
- replay same identity/same digest — idempotent;
- replay same identity/different digest — conflict;
- partial chain — not complete;
- receipt without complete chain — forbidden.

This PR defines the contract only.

## Relationship to #1050

#1050 separates:

`COLLECTOR -> IMMUTABLE EVIDENCE -> VERIFIER`

This V1 defines the persistence boundary represented by
`IMMUTABLE EVIDENCE` and the later verifier receipt.

It does not replace the collector/verifier separation.

## Maximum implementation-review state

`READY_FOR_WINDOWS_EVIDENCE_PERSISTENCE_IMPLEMENTATION`

The next PC-side implementation may build:

- append-only local evidence writer;
- CAS revision control;
- read-after-write observation;
- independent reopen verifier;
- synthetic crash/replay tests.

It must still use synthetic/non-production evidence first.

## Explicitly absent

This V1 does not:

- create/open SQLite;
- create a directory;
- start a transaction;
- attempt CAS;
- write an evidence record;
- write a receipt;
- delete/replace a record;
- execute collector/verifier;
- collect physical evidence;
- verify physical evidence;
- authorize/start a build;
- build/install a package;
- load credentials/private keys;
- call GitHub;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_IMMUTABLE_EVIDENCE_RECEIPT_PERSISTENCE_V1_VALIDATED`

No physical persistence or physical Windows verification is implied.
