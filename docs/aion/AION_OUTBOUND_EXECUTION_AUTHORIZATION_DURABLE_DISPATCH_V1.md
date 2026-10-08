# AION Outbound Execution Authorization + Durable Dispatch V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING  
Date: 2026-10-08  
Stacked base: Approval + Outbound Dispatch Bridge V1  
Provider call: NO  
Durable dispatch write: NO  
Production status: NOT DEPLOYED

## Objective

Close the two remaining safety gates before any future external outbound effect:

1. fresh HUMAN_OWNER execution intent;
2. durable dispatch record preparation.

This layer still does not send email, WhatsApp or export/sign a contract.

## Fresh execution authorization

A prior APPROVED draft is not enough.

A new execution ceremony is required and must bind the exact outbound bridge
digest.

V1 requires:

- purpose: HUMAN_OWNER_EXPLICIT_OUTBOUND_EXTERNAL_EFFECT_EXECUTION;
- mechanism: ED25519_EXTERNAL_OWNER_EXECUTION_KEY;
- decision: AUTHORIZE_OUTBOUND_EXECUTION or DENY_OUTBOUND_EXECUTION;
- exact owner binding digest;
- owner key fingerprint;
- signed request digest;
- authorization nonce digest;
- verified owner signature;
- verified active trust root;
- persistent nonce replay guard;
- single-use nonce claim;
- authorization window no longer than 120 seconds.

A valid result means only:

`FRESH_EXECUTION_INTENT_VERIFIED`

It does not produce a command and does not call a provider.

## Separate persistence attestation

The fresh authorization cannot jump directly to payload/dispatch.

A separate persistence attestation must prove:

- authorization digest;
- persisted-record digest;
- writer-attestation digest;
- read-after-write verification;
- atomic write / CAS semantics;
- verified writer identity;
- persistence happened after authorization issue and before authorization expiry.

This contract does not perform the persistence.

It only validates the attestation.

## Why persistence is separate

The execution-intent object itself continues to report:

- authorization_persisted=false
- persistence_attested=false

A separate record proves the write.

This prevents an in-memory "verified" state from being treated as durable
authorization after a crash or restart.

## Sealed payload attestation

After persisted authorization, a future trusted adapter may provide a sealed
payload attestation.

Only digests are carried:

- exact bridge digest;
- authorization digest;
- authorization-persistence attestation digest;
- subject digest;
- adapter manifest digest;
- payload digest;
- payload schema reference;
- recipient-resolution digest;
- endpoint-reference digest;
- credential-reference digest;
- headers-policy digest;
- transport-policy digest;
- timeout-policy digest.

V1 explicitly excludes the raw:

- recipient address/phone;
- provider endpoint;
- credentials;
- payload.

The attestation must be fresh: at most 30 seconds old.

## Durable dispatch record candidate

Only after:

- exact approved bridge;
- fresh owner execution intent;
- separate authorization-persistence attestation;
- fresh sealed payload attestation;

may the system build:

`READY_FOR_DURABLE_DISPATCH_RECORD_WRITE`

This is only a deterministic candidate for a future write.

It binds:

- execution/task/step IDs;
- bridge digest;
- fresh authorization digest;
- persistence attestation digest;
- payload attestation digest;
- exact subject digest;
- approval packet/evidence digests;
- adapter manifest digest;
- requested action;
- idempotency/effect-key digests;
- wire-payload digest;
- recipient/endpoint/credential reference digests;
- transport/header/timeout policy digests;
- lease identity digest;
- observability trace ID;
- candidate dispatch timestamp.

## Mandatory atomic behavior

The future durable writer must:

1. already hold the correct lease;
2. atomically write the durable dispatch marker;
3. atomically consume the single-use execution authorization with that write;
4. persist state as DISPATCH_RECORDED before the external effect.

This V1 does none of those physical writes.

## Ambiguous outcomes

After a future DISPATCH_RECORDED state:

- process crash -> OUTCOME_UNKNOWN;
- timeout -> OUTCOME_UNKNOWN;
- ambiguous provider acknowledgement -> OUTCOME_UNKNOWN.

OUTCOME_UNKNOWN:

- cannot automatically retry;
- requires explicit evidence-based reconciliation;
- requires an outcome receipt.

These semantics mirror the existing durable execution kernel philosophy.

## Important state separation

Even a READY durable candidate reports:

- dispatch_record_written=false;
- authorization_consumed=false;
- provider_call_allowed_after_this_module=false;
- provider_called=false;
- network_called=false;
- message_sent=false;
- contract_exported=false;
- signature_requested=false;
- external_action_executed=false.

## Relationship to previous blocks

The safe outbound chain now becomes:

1. Draft contract/email/WhatsApp
2. Human approval packet
3. Human approval decision evidence
4. Approval + Outbound Dispatch Bridge
5. Fresh owner execution intent
6. Authorization persistence attestation
7. Sealed payload attestation
8. Durable dispatch record candidate
9. **Future** durable dispatch write
10. **Future** sealed single provider call
11. **Future** outcome receipt
12. **Future** reconciliation if outcome is unknown

## Explicitly absent

This block does not:

- verify Ed25519 itself;
- persist nonce;
- persist authorization;
- write durable execution state;
- claim or consume approval;
- resolve raw recipient;
- expose raw endpoint/credentials/payload;
- call Gmail/SMTP/WhatsApp;
- export/sign contract;
- send any message;
- start Worker;
- deploy;
- write frozen Core checkpoint.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_OUTBOUND_EXECUTION_AUTH_DURABLE_DISPATCH_V1_CONTRACT_VALIDATED`

That validates execution-authorization/persistence/payload/dispatch-candidate
semantics only.

No external effect has occurred.
