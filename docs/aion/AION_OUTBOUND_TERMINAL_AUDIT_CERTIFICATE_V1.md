# AION Outbound Terminal Finalization + Audit Certificate V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING  
Date: 2026-10-08  
Stacked base: Sealed Provider Outcome + Reconciliation V1  
Final state persisted: NO  
Audit seal persisted: NO  
Certificate persisted: NO  
Production status: NOT DEPLOYED

## Objective

Close the outbound lifecycle after a provider outcome becomes authoritative.

This V1 defines:

1. terminal finalization candidate;
2. external finalization-persistence attestation;
3. deterministic audit-seal manifest;
4. external audit-seal persistence attestation;
5. read-only terminal certificate.

It does not execute, retry, reopen, persist, sign or contact any provider.

## Finalizable outcomes

Only these states may become terminal:

- CONFIRMED_SUCCESS
- CONFIRMED_TERMINAL_FAILURE
- RECONCILED_CONFIRMED_SUCCESS
- RECONCILED_CONFIRMED_TERMINAL_FAILURE

These states are never finalizable:

- OUTCOME_UNKNOWN
- STILL_OUTCOME_UNKNOWN

Unknown must remain open for reconciliation.

## Verified outcome chain required

The terminal layer does not trust a record by shape alone.

Before finalization it calls the #1027 outcome-chain verifier.

Therefore a tampered or structurally invalid outcome/reconciliation record cannot
enter terminal closure.

## Success finalization

FINALIZED_SUCCESS requires:

- authoritative known success outcome;
- execution ID match;
- trace match;
- idempotency-key match;
- effect-key match;
- provider-request correlation match;
- provider identity match;
- authenticated terminal evidence;
- fresh terminal evidence;
- complete effect confirmation;
- expected postcondition match;
- no unresolved evidence conflict;
- no pending reconciliation;
- no pending rollback/compensation;
- FinOps observation within policy.

## Terminal failure finalization

FINALIZED_TERMINAL_FAILURE requires authoritative terminal failure/no-effect
evidence plus the common identity/correlation/evidence gates.

If rollback/compensation is required and still pending, finalization blocks.

## Finalization persistence

A READY finalization still does not mean the final state is stored.

A separate persistence attestation must bind:

- finalization digest;
- finalization-record digest;
- writer-attestation digest;
- read-after-write;
- atomic write/CAS;
- writer identity.

The module itself reports:

`persisted_by_this_module=false`

## Audit seal

After persisted finalization, AION may build a deterministic terminal
chain-of-custody manifest binding:

- execution ID;
- final state;
- terminal revision;
- finalization digest;
- finalization record/persistence attestation;
- durable dispatch record;
- sealed provider call boundary;
- primary outcome receipt;
- reconciliation record when applicable;
- approved subject digest;
- idempotency/effect-key digests;
- provider request correlation;
- terminal evidence set;
- rollback/compensation settlement when applicable;
- FinOps observation;
- observability trace;
- pre-terminal audit-chain digest.

The audit seal is:

- immutable;
- append-only;
- non-authoritative for execution;
- not a retry token;
- not a reopen token;
- not an external-effect authorization;
- not a real signature.

## Audit-seal persistence

The future durable store must separately prove:

- exact seal-manifest digest;
- persistence-record digest;
- writer attestation;
- reopen consistency;
- read-after-write;
- writer identity.

This module does not perform the write.

## Terminal certificate

Only after both finalization and audit seal have persistence attestations may the
certificate become:

`TERMINAL_CERTIFICATE_READY`

The certificate is a deterministic read-only evidence descriptor.

It binds the terminal state and the persisted terminal/audit lineage.

It is explicitly not:

- execution authorization;
- retry authorization;
- reopen authorization;
- external-effect authorization;
- a real/legal/cryptographic signature.

## Tamper detection

The terminal certificate digest is recomputed from its canonical manifest.

Changing a bound field such as terminal revision changes the expected digest and
invalidates verification.

## End-to-end outbound lifecycle

The safe owner-facing outbound path is now architecturally closed:

1. Draft contract/email/WhatsApp
2. Exact human approval packet
3. Human approval decision evidence
4. Approval-to-dispatch bridge
5. Fresh owner execution authorization
6. Authorization persistence attestation
7. Sealed payload attestation
8. Durable dispatch record candidate
9. Future durable DISPATCH_RECORDED write
10. Dispatch-write attestation
11. Provider-runtime attestation
12. Sealed single-call boundary
13. Future provider call
14. Immutable outcome receipt
15. Separate reconciliation when OUTCOME_UNKNOWN
16. Terminal finalization
17. Finalization persistence attestation
18. Audit-seal manifest
19. Audit-seal persistence attestation
20. Read-only terminal certificate

## Explicitly absent

This block does not:

- persist terminal state;
- persist audit seal;
- persist certificate;
- retry/reopen execution;
- query/call provider;
- open network;
- send email/WhatsApp;
- export/sign contract;
- sign with a real key;
- write CRM;
- arm Worker;
- deploy;
- modify frozen Core V1.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_OUTBOUND_TERMINAL_AUDIT_CERTIFICATE_V1_CONTRACT_VALIDATED`

This validates terminal closure and evidence-chain semantics only.
