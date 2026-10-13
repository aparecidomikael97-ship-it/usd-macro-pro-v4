# AION V16-A.37 — executable untrusted receipt inspection (DENY-ONLY / LAB)

**Status: NO-GO / reference shape filtering only.** No real provider identity, external witness, committed-effect evidence or terminal no-effect fence is enrolled.

**Exact parent:** Draft #1249 HEAD `b7b0726a0e179f0182d556cbe25e33c29c6b62db`. The current production-facing Outbox still denies before `adapter.send` and `adapter.reconcile`. This change **does not import this precheck into those two methods**, create an adapter, unlock a branch or change the post-send historical tests.

## What was added

- `atlasquant_aion_producer_receipt_untrusted_precheck.py`: independent, network-free, callback-free, read-only **untrusted claim inspection** with exact primitive schemas, bounded identifiers, context matching and strict **separate** `POSITIVE_COMMITTED` / `NEGATIVE_NO_EFFECT_FENCED` alleged domains. The domains are deliberately named `UNTRUSTED`; they are **not production cryptographic receipt domains**.
- `test_atlasquant_aion_producer_receipt_untrusted_precheck.py`: unittest adversarial suite for both perfectly matching and malformed claims; every result MUST deny issuer authentication, signature verification, independent witness, effect admission, retry and Saga progress.
- A standalone mandatory step in the AION Core Security Gate compiles and runs this dedicated suite **independently of the historically failing 23 Outbox Quality tests**, without deleting them or granting test-time authorization.

## Important contract boundaries

**Shape-matched does not mean verified.** The strongest possible output is
`status=BLOCKED_EXTERNAL_PROOF_UNAVAILABLE`,
`reason=INDEPENDENT_PRODUCER_AND_WITNESS_NOT_ENROLLED` and
`shape_matched=true`, while **all permission and evidence booleans are false**.

Inputs labeled `claimed_signature`, `claimed_effect_ref` and
`claimed_terminal_fence_ref` are **mere strings supplied by an untrusted party**.
The precheck deliberately never validates any signature, public key, issuer
chain, nonce uniqueness, revocation, external head freshness, producer commit,
terminal late-effect fence, or receipt replay. Exact matching against the
`expected_local_binding` does not turn that locally supplied binding into
independent evidence: a caller who can control both sides could make them match.

A `POSITIVE_COMMITTED` claim cannot be substituted for a
`NEGATIVE_NO_EFFECT_FENCED` claim. Closed fields prevent smuggling of
`trusted=true`, `provider_enrolled=true`, `confirmed=true`,
`authoritative_absence=true`, `fenced=true` and other flags as authority.
The precheck also excludes user-defined mapping subclasses or dynamic
values/keys before performing equality or field lookups, to avoid property
and comparison callbacks from input objects in this offline scope.

The module **has no runtime grant API** and does not expose a user-controlled
mode that can set `external_action_authorized`, `effect_ledger_authorized`,
`retry_authorized` or `saga_advance_authorized` to true. This still does not
establish immutable code provenance or stop a future caller from ignoring
the decision; it must remain disconnected from productive adapters.

## Security limits / future requirements

This phase proves only syntactic rejection and *non-elevation* of untrusted
claims; it does not prove the existence or correctness of any cryptographic
receipt verifier. Before changing the **hard denial** in the Outbox:
1. Independently enroll the actual producer issuer, account, host/HUMAN_OWNER
   and scoped key/epoch with custody **outside** the host and deployment account.
2. Verify a current signed head from an independent monotonic witness, with
   revocation and joint host+backup rollback detection.
3. For positive receipts, verify **producer-side committed effect** bound to
   exact scope, digest, request, key, attempt and epoch, then CAS to CONFIRMED.
4. For negative receipts, verify **terminal producer-enforced no-effect fence**
   covering delayed and already queued attempts; a signed lack-of-record
   cannot authorize a retry.
5. Exercise original A.12 37 + A.16 8 regressions only if original archives
   and expected hashes are retrieved, and close 20 real first-install gates.

**Not achieved:** 23 legacy Outbox tests, physical Windows/AM12 owner proof,
signed external receipt issuer, producer guarantees, independent witness and
any productive send/reconcile path. **0/6 P0 homologated; 20/20 first-install
HARD NO-GO**. No merge, deployment, Worker/Render, real credentials, purchases,
provider calls or external action.
