# AION Sealed Provider Call + Outcome Receipt + Reconciliation V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING  
Date: 2026-10-08  
Stacked base: Outbound Execution Authorization + Durable Dispatch V1  
Provider called: NO  
Network opened: NO  
Message sent: NO  
Production status: NOT DEPLOYED

## Objective

Close the last outbound safety boundary before any future real provider call.

This V1 defines:

1. proof that DISPATCH_RECORDED was durably committed;
2. proof that fresh execution authorization was consumed atomically with that write;
3. provider-runtime attestation;
4. exact sealed single-call boundary;
5. immutable outcome receipt;
6. separate OUTCOME_UNKNOWN reconciliation.

No external effect is performed by this PR.

## Durable dispatch write attestation

A future durable writer must prove:

- exact durable-dispatch candidate digest;
- durable dispatch record digest;
- writer-attestation digest;
- persisted state is DISPATCH_RECORDED;
- lease ownership verified;
- lease still valid;
- idempotency reservation verified;
- effect-key reservation verified;
- fresh execution authorization consumed atomically with the dispatch write;
- read-after-write verified;
- writer identity verified.

Without all of these, no call boundary can become ready.

This module does not perform the durable write.

## Provider runtime attestation

Before a future call, the trusted adapter/runtime must prove:

- provider identity reference;
- signed runtime/build digest;
- exact adapter-manifest digest;
- exact endpoint-reference digest;
- exact credential-reference digest;
- endpoint allowlist;
- minimum credential scope;
- credential freshness;
- redirect policy;
- timeout policy;
- transport policy;
- freshness of the runtime attestation.

Only digests/references enter this control plane.

No raw endpoint, secret, credential or authorization header is included.

## Sealed single-call boundary

The call boundary binds the exact:

- call-attempt ID;
- execution ID;
- observability trace;
- durable dispatch record;
- dispatch-write attestation;
- provider runtime attestation;
- provider identity;
- runtime build;
- adapter manifest;
- approved subject;
- action;
- payload;
- resolved-recipient digest;
- endpoint reference;
- credential reference;
- headers/transport/timeout policies;
- idempotency key;
- effect key;
- provider request correlation.

A READY boundary allows exactly one future sealed call attempt.

After DISPATCH_RECORDED, the future executor may not switch:

- provider;
- endpoint;
- credential;
- payload;
- capability;
- scope.

This module still reports provider_called=false and network_called=false.

## Outcome classification

The only primary outcome states are:

- CONFIRMED_SUCCESS
- CONFIRMED_TERMINAL_FAILURE
- OUTCOME_UNKNOWN

There is no generic "probably succeeded" state.

### Confirmed success

CONFIRMED_SUCCESS requires complete positive evidence including:

- provider identity match;
- runtime build match;
- execution ID match;
- trace match;
- provider request correlation;
- idempotency/effect-key match;
- valid response schema;
- response authenticity;
- provider success semantics;
- complete effect confirmation;
- expected postcondition match;
- provider response evidence digest.

If any required success evidence is incomplete, the result becomes
OUTCOME_UNKNOWN.

### Confirmed terminal failure

CONFIRMED_TERMINAL_FAILURE requires authoritative terminal evidence including:

- identity/correlation match;
- valid authenticated response;
- attested provider terminal-failure semantics;
- complete no-effect or terminal-rejection evidence.

Silence is not terminal failure.

## Ambiguity always becomes OUTCOME_UNKNOWN

Examples:

- timeout after dispatch;
- connection reset;
- process crash;
- missing ACK;
- malformed ACK;
- ambiguous ACK;
- correlation mismatch;
- provider identity mismatch;
- unauthenticated response;
- duplicate conflicting responses;
- incomplete effect confirmation.

Even if some code path requests CONFIRMED_SUCCESS, an ambiguity trigger wins and
the receipt records OUTCOME_UNKNOWN.

## Receipt immutability

A primary outcome receipt is append-only and immutable.

It cannot later be rewritten from:

OUTCOME_UNKNOWN -> SUCCESS

or:

OUTCOME_UNKNOWN -> FAILURE.

Any later resolution is a separate reconciliation record.

## No automatic retry

OUTCOME_UNKNOWN explicitly means:

- automatic retry forbidden;
- original receipt immutable;
- separate reconciliation required;
- a new attempt requires fresh authorization and a new durable dispatch.

## Separate reconciliation authorization

Reconciliation itself requires a fresh HUMAN_OWNER authorization with a
different purpose:

`HUMAN_OWNER_EXPLICIT_OUTCOME_RECONCILIATION`

It binds:

- original unknown-receipt digest;
- owner identity/binding;
- key fingerprint;
- signed request digest;
- fresh nonce;
- active trust root;
- persistent replay protection;
- single-use nonce;
- max 120-second authorization window.

That authorization permits reconciliation review only.

It does not permit retry or replay.

## Authoritative reconciliation evidence

Accepted evidence classes are limited to:

- PROVIDER_AUTHORITATIVE_OPERATION_STATUS
- PROVIDER_AUTHORITATIVE_REQUEST_LOOKUP
- PROVIDER_SIGNED_EVENT_OR_RECEIPT
- EFFECT_SIDE_AUTHORITATIVE_READBACK
- IMMUTABLE_DOWNSTREAM_AUDIT_RECORD

Evidence must match:

- provider identity;
- execution ID;
- trace;
- provider request correlation;
- idempotency key;
- effect key.

It must also be:

- source-attested;
- schema-valid;
- authenticated;
- fresh;
- sequence/version monotonic.

## Reconciliation result

A separate reconciliation record may classify the original unknown as:

- RECONCILED_CONFIRMED_SUCCESS
- RECONCILED_CONFIRMED_TERMINAL_FAILURE
- STILL_OUTCOME_UNKNOWN

Conflicting, stale, incomplete or weakly correlated evidence preserves:

`STILL_OUTCOME_UNKNOWN`

Unknown can never be coerced to success or failure.

## New attempt after unknown

A new outbound attempt remains separate.

It requires:

- confirmed no-effect evidence when policy permits retry;
- fresh HUMAN_OWNER execution authorization;
- new idempotency/effect identity as required by policy;
- new durable dispatch;
- new sealed call boundary.

This reconciliation module never authorizes that new attempt itself.

## Full outbound chain

The safe outbound path now reads:

1. Contract/email/WhatsApp draft
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
13. Future one-call provider attempt
14. Immutable outcome receipt
15. Separate reconciliation if OUTCOME_UNKNOWN
16. Future terminal finalization/audit certificate only after outcome is known

## Explicitly absent

This block does not:

- write DISPATCH_RECORDED;
- consume authorization itself;
- resolve raw secrets;
- open sockets;
- call SMTP/Gmail/WhatsApp;
- send email/WhatsApp;
- export/sign a contract;
- query a provider during reconciliation;
- retry;
- replay an external effect;
- write CRM;
- start Worker;
- deploy;
- modify frozen Core V1.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_SEALED_PROVIDER_OUTCOME_RECONCILIATION_V1_CONTRACT_VALIDATED`

This validates final outbound trust-boundary semantics only.

It does not mean a provider call or any external effect has occurred.
