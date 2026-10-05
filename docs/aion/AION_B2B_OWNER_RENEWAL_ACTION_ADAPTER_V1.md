# Controlled recurring-action adapter — offline V1

Base: Draft #870, exact head `ca4d0dd8d735f16d0acacbdb06c5bb403ab2fd9b`.
Branch: `business/aion-b2b-controlled-adapter-dry-run-20261005`.

The abstract command plan remains unchanged and non-executable. This addition
implements an adapter **planning contract**, synthetic simulation, reversal
requirements and a future receipt schema. There is no executor or production
wiring. Draft only. DO NOT MERGE / DO NOT DEPLOY.

## Chain and trust boundary

Trusted host scope + existing persistence/writer verifier results + execution
preflight → rebuild the existing command plan → exact command-plan comparison →
fresh, bound synthetic environment → adapter plan → offline synthetic snapshots
and capability coverage → dry-run → synthetic receipt validation.

`build_owner_renewal_action_adapter_plan` additionally requires
`execution_preflight`: rebuilding the existing producer is stronger than trusting
a supplied READY state or a rehashed command-plan digest. No existing producer is
changed or duplicated.

The binding contains owner/tenant/workspace scope, customer, pilot, package,
review type, requested choice, action family, operation kind, command-plan,
action-parameters, execution-preflight and execution-record digests. The writer
request binding uses the existing name
`execution_intent_writer_request_digest` (from `writer_request_digest` in the
upstream writer result). The existing writer result has no independent scope or
package field: its exact receipt/checkpoint/record bindings connect it to the
scoped persistence attestation through the unchanged command-plan producer.

All upstream attestation results are **trusted host inputs**, not customer/UI
claims. This offline layer structurally consumes verified results; it cannot
authenticate an arbitrary caller-created dictionary. It does not rerun signatures,
claim nonces, load keys or write attestation stores. A synthetic ready result is
not proof that a provider exists, that rollback is possible in production, or that
real owner authority has been independently verified here. A digest is binding,
not a signature. There is no API endpoint or integration accepting client claims.

## Public contracts

| Module/API | Maximum state | Meaning |
| --- | --- | --- |
| `build_owner_renewal_action_adapter_plan` | `READY_FOR_CONTROLLED_ACTION_ADAPTER_DRY_RUN` | Eligible for synthetic analysis only |
| `validate_adapter_plan` | canonical plan / exception | Structural rebuilding; no authentication |
| `build_owner_renewal_action_adapter_dry_run` | `DRY_RUN_READY` | Detached in-memory simulation only |
| `validate_dry_run` | rebuilt simulation / exception | Rebuilds rather than accepting a caller digest |
| `owner_renewal_action_receipt_contract` | `FUTURE_RECEIPT_SCHEMA_ONLY` | Expected schema, no actual execution receipt |
| `validate_synthetic_owner_renewal_action_receipt` | `SYNTHETIC_RECEIPT_VALIDATED` | Synthetic structural consistency, no real execution claim |

Malformed or unsafe inputs return `BLOCKED` / `DRY_RUN_BLOCKED`. Validation
helpers deliberately raise `ValueError`/type errors; the three result-producing
boundary functions catch invalid inputs and return a neutral, non-authorizing
blocked result. They never echo rejected secret/material values.

All input trees must be plain bounded JSON dictionaries/lists/scalars; subclasses,
custom mappings, coercive objects, floats, Decimal/Fraction, bytes, NUL/control
characters, forbidden executable/secret keys, URL/IP/command strings, excessive
depth and cycles are rejected. Limits: 4,096 tree nodes, depth 12, 512 characters
per string. No default `str()` coercion. Identity/reference tokens use a limited
ASCII grammar. Unsafe unknown extra fields are rejected at canonical boundaries.

## Separate family capabilities

| Family | Minimal capabilities |
| --- | --- |
| RENEWAL | Contract/service continuity; billing review and customer notice boundaries |
| RENEWAL_WITH_CHANGES | Contract change; package/scope and capacity review; pricing boundary |
| NON_RENEWAL | Offboarding plan; notice; retention; access lifecycle plan; archive/export boundary |
| REMEDIATION | Remediation plan; health recheck; remediation reversal |
| CAPACITY_RESCOPE | Capacity plan; quota boundary; FinOps validation; health recheck |
| REPRICING | Commercial pricing plan; amendment boundary; owner-only approval boundary |
| INCIDENT_REMEDIATION | Incident containment plan; security/privacy recheck; health recheck |
| SERVICE_PAUSE | Pause sequencing; data safety; impact review; reversal path |
| SERVICE_TERMINATION | Termination plan; retention; archive/export; access-revocation plan; irreversible boundary |

Only adapter kind `OFFLINE_MANAGED_SERVICE_CONTRACT` and provider class
`SYNTHETIC_MANAGED_SERVICE` are supported. The names identify synthetic contracts,
not a selected production provider. Missing capabilities or unknown/unsafe extras
block. No family invokes any capability or emits a commercial request.

## Freshness, conflicts and cost

The new synthetic environment contract requires an explicit UTC `as_of`,
`expires_at`, trusted host `now_ts`, and a positive validity window <= 180 seconds.
`as_of <= now < expires_at`; equality at expiry is stale. No system clock read or
inferred TTL. A source reference alone gives no authority.

Evidence refs, exact bindings, synthetic healthy provider/rollback observations,
capacity sufficiency, and explicit absence of billing dispute, security/privacy
incident, contract conflict and irreversible boundaries are required. All three
environment observations must agree; no convenient merge of divergent snapshots.
Snapshot content digests must recompute correctly.

The infrastructure cap is **R$200/month = 20,000 integer cents**. Negative costs,
booleans masquerading as integers, or costs above the cap block. No charge is
performed; no estimate is fetched or asserted to represent real production cost.
Raising this cap requires a separately approved future owner decision.

## Rollback before a future executor

The plan includes a scoped/digested reversal plan, explicit evidence/receipt
requirements, 180-second timeout and owner-confirmation boundary. V1 rollback
mode is `PRE_EXECUTION_STAGING_REVERSAL_ONLY`: discard a synthetic changeset,
restore its synthetic before-state, and review the owner boundary. No rollback
method is called and no real deletion, archive, access revocation or termination
is modeled as reversible.

`NON_RENEWAL` and `SERVICE_TERMINATION` can only simulate reversible **pre-action
staging**, never irreversible business completion. If an irreversible boundary
is observed, rollback is missing/impossible or rollback evidence is degraded,
the result blocks. The current synthetic plan does not prove production rollback
feasibility. Real execution and real reversal require a new, independently reviewed
contract with fresh domain proof, authenticated receipts and explicit authorization.

## Future executor / receipt requirements

The future receipt contract expects command/adapter/dry-run/rollback digests,
owner-execution intent reference, exact customer/pilot/package/family/scope,
idempotency digest, before/after-state digests, timestamp, writer/provider identity
refs and evidence refs. The owner-execution binding digest is a reference to the
existing record/writer chain, never a newly issued authorization or signature.

The validator accepts **synthetic** receipts with `synthetic:` identity refs only.
It rebuilds the simulation, checks all bindings, digest and temporal validity and
rejects rehashed discrepancies. `execution_verified`, `writer_identity_authenticated`,
`provider_identity_authenticated` and `actual_receipt_generated` stay false.
No real receipt producer or real receipt authenticator is implemented.

Any future executor must separately enforce trusted host verifiers, owner
authorization, policy, current capabilities/cost/security checks, true production
idempotency persistence and an actually reversible operation. Neither a synthetic
receipt nor an adapter/dry-run READY state can satisfy that boundary. The current
idempotency key is deterministic and scoped; it is **not** a persisted deduplication
guarantee, replay registry or permission to retry a real action.

## Safety evidence and CI

`test_atlasquant_aion_b2b_owner_renewal_action_adapter.py` runs individual unittest
cases for all families, scope/identity/choice/lineage mismatches, stale evidence,
risk/cost/capability gates, synthetic snapshot conflicts, material injection,
rehash attacks, receipt substitutions, hostile types, bounded work, deterministic
repeated calls, detached outputs and concurrent list isolation.

Runtime instrumentation blocks filesystem read/write/rename/replace/remove,
socket, subprocess, checkpoint append and journal/nonce-store construction across
the entire new chain, then asserts zero attempts. Separate fixture preparation
and the existing writer-verifier compatibility test use test-only keys and a
temporary nonce database; they are outside the offline adapter boundary. Import
AST checks forbid direct provider/executor/HTTP/billing/CRM dependencies. There is
no production runtime, worker, UI, provider, billing, CRM or deployment wiring.

Dedicated CI: `aion-b2b-owner-renewal-action-adapter.yml`, pinned existing action
SHAs, Python 3.12, existing `cryptography==50.0.2`, contents-read only. Aggregate
B2B readiness and quality gates include the new suite. Exact insertion anchors
were checked to occur once before editing; no ambiguous replacements or relaxed
old tests. Final counts/run links belong in the delivery report/PR because run
results cannot be known before creating the exact-head checkpoint.

Local pre-delivery evidence: 244 new cases passed with pytest and unittest;
42 original pure-chain/architecture cases and 36 subtests passed. The broader
Windows run had 922 passes and 67 failures, all in old temporary SQLite cleanup
(`WinError 32`); an isolated unchanged upstream writer suite reproduced the same
failure (2 pass / 5 fail) without importing the new adapter. The nonce registry,
writer verifier and original tests are byte-for-byte unchanged from the base.
No persistence patch or weakened test is included. Linux CI remains the original
execution environment of those gates and must be checked before final delivery.

Every successful and blocked boundary result explicitly retains false flags for
provider/network, secrets/credentials/endpoints/method/headers/executable payload,
shell/command generation/execution, production mutation, customer contact,
billing, deploy, provisioning, CRM write, business authority and action execution.
Repository delivery/CI traffic is authorized tooling; “zero network side effect”
describes the adapter's runtime, not Git push or dependency installation.

**ZERO MERGE / ZERO DEPLOY / ZERO REAL ACTION.**
