# AION V2 — UNKNOWN_OUTCOME provider observation and HUMAN_OWNER review reference

**2026-10-09.** New Draft stacked on #1134 → #1133 → #1132 → #1131 → #1130 etc. No merge, no deploy, no live model or cloud service. Core/`main` preserved.

## Exact blocking problem

A client may persist `DISPATCH_CLAIMED`, send a paid HTTP request, lose the reply, and recover `UNKNOWN_OUTCOME`. Neither a socket timeout nor a missing response in local logs proves the remote provider did not process or bill it. #1133 covers local no-retry and #1134 models two signed dispatch-journal heads; neither authenticates an actual provider billing record or gives exact-once provider processing.

We cannot silently set **NOT_PROCESSED**, **REFUNDED**, **PROCESSED_WITH_CHARGE**, safe-to-retry or approved. A provider-neutral simulated receipt **is not authoritative** for any of those assertions.

## Code and evidence contract

`atlasquant_aion_v2_unknown_outcome_reconciliation_reference.py` accepts:

1. Existing #1133 reference journal with exact synthetic V2 intent and #1134 **matching** signed primary/secondary witness journal READs in a CLAIMED or UNKNOWN state.
2. A **PROVIDER_EVIDENCE_FIXTURE_ED25519** closed, domain-separated simulated observation, over exact owner/tenant/workspace, month, policy, nonce, signed V2 intent, full provider request digest, key registry digest, full journal snapshot+sequence, original claim sequence, claimed provider/request IDs, observed status, hypothetical response digest and reported micro-USD. Status is one of `PROCESSED`, `NOT_FOUND`, `UNCERTAIN`.
3. Optional **HUMAN_OWNER_REVIEW_FIXTURE_ED25519** closed, separately domain-separated manual acknowledgment, binding exact observation envelope hash, exact journal head/request, a fresh expected review challenge and one typed decision.

`NOT_FOUND` is **INCONCLUSIVE**, not evidence that provider never processed. `UNCERTAIN` is likewise inconclusive. `PROCESSED` must bind a response digest but remains a *signed simulation*; neither billing nor response provenance is independently authenticated. A non-PROCESSED status may not assert a billed amount or response. Contradictory manual decision vs observation blocks. Reviewing one observation cannot be replayed against a different signed observation hash or different nonce/request/head/challenge.

### Safety invariants

All outputs — including `PROVIDER_OBSERVATION_SIGNATURE_MATH_ONLY_UNTRUSTED` and `OWNER_REVIEW_SIGNATURE_MATH_ONLY_UNTRUSTED` — always state:

- `must_not_automatically_retry=True`; `same_nonce_reusable=False`; `needs_human_reconciliation=True`.
- `real_owner_identity_verified=False`, `owner_presence_verified=False`, `provider_public_key_enrolled=False`, `true_provider_provenance_verified=False`.
- `billing_settlement_verified=False`, `real_charge_verified=False`, `real_refund_authorized=False`.
- `paid_dispatch_authorized=False`, `paid_dispatch_performed=False`, `paid_provider_called=False`, `network_called=False`.

This code verifies mathematical signatures against **caller-supplied** fake public pins; it NEVER signs, writes to external witness, reads cloud billing, creates a receipt, mutates journal, sends provider requests, refunds, enables restart or authorizes payment.

## Explicit negative cases in CI

- An attacker substitutes the caller-supplied provider public pin and signs matching fake provider evidence: cryptographic math passes, yet true provenance remains false.
- An attacker substitutes the owner review pin and signs with fake owner key: math passes, but genuine owner presence remains unproven.
- Two contradictory, independently signed **synthetic** provider observations (`PROCESSED` and `NOT_FOUND`) can both verify; only a real provider-controlled authenticated audit record plus billable request ID can resolve the conflict. No actual settlement inferred.
- Reusing exactly the same signed review challenge can make the old math pass again. A real **independently protected challenge/nonce consumption log and enrolled key root** is needed.
- An older witness head after local journal evidence was appended fails under #1134. A complete rollback of journal **and both** heads can still pass if the caller supplies all stale inputs.
- A forged status, swapped full-provider-request hash, altered reported charge, changed claim sequence, changed tenant/nonce, invalid role/domain, stale challenge or substituted signature blocks.

## Practical production admission plan, not executed

1. Evaluate each provider's **actual** request ID, signed/verified API response capability, billing reconciliation or idempotency guarantees, retention horizon and legal terms; do not invent these capabilities. If unavailable, keep UNKNOWN and escalate manual support.
2. Connect real #1131–#1132 owner and witness/anchor keys via separately approved owner-presence ceremony and enrolled protected trust roots, with real nonce/epoch and revocation.
3. Build protected external head for **the dispatch journal itself**, remote atomic one-shot dispatch claim, and explicit disambiguation of crash windows/unknown outcome. Dual cloud states cannot be atomically committed without separate protocol.
4. Manually reconcile provider invoice/reported usage against idempotent journal and independent external receipts. Billing observation and reconciliation approval must be separate. Even if provider says NOT_FOUND, a **new** request requires new owner authorization, nonce, budget evaluation and full request binding; NEVER replay old request.
5. Quote all deployment cost/FX/taxes together within total temporary R$200/month and obtain explicit authorization before enrollment, cloud provisioning, live API, PR merge or deploy.

**NO-GO:** All simulated keys are disposable CI fixtures. No cloud accounts, DNS, secrets, billing or owner device touched. No fake paid API call. No model answer created. No real provider evidence was checked.
