# AION P0 — 32 canonical Outbox/Saga ERROR: independent evidence exit gates

**Audit date:** 2026-10-20. **State:** **RED / HARD NO-GO / 0/6 P0 homologados**.  
**Immutable baseline:** GitHub Actions [#39334210568](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39334210568), 6,562 tests, 51 FAIL + 34 ERROR. Of these, **23 Outbox ERROR + 9 Saga ERROR**. This document does **not** rerun full Quality or mark those methods green.

## Exact observed first boundary, not guessed root cause

| First observed exception in canonical Quality | Count | Required external exit evidence |
| --- | ---: | --- |
| `INDEPENDENT_PRODUCER_NOT_ENROLLED` | **23** | Independently rooted enrollment binding producer identity, provider account, tenant/workspace, action scope, policy, issuer keys, lease, and durable enrollment epoch before executing or even inspecting adapter properties |
| `INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED` | **8** | Durable, independently authenticated **COMMITTED_EFFECT** causal receipt bound to exact request/idempotency key, action payload digest, producer account and scope, replay/epoch fence, and evidence of which external effect actually committed |
| `INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED` | **1** | Provider-enforced **terminal NO_EFFECT_FENCED** proof, with protection from any **late effect**, proof binding and independent witness; adapter `found=False` or `authoritative_absence=True` is not sufficient |
| **TOTAL** | **32** | **No such enrollment, receipt, or fence is enrolled here** |

The machine-readable [case-level matrix](AION_P0_32_EXTERNAL_PRODUCER_EVIDENCE_MATRIX_20261020.json) records all 32 canonical class/method/subtest identities, original source line, observed exception, current OPEN_NOT_WAIVED state, and the *missing* external evidence. The inferred behavior family is **only a triage heuristic from the method name**: it must not be represented as proof of a final technical root cause.

## Protocol before considering any external provider

1. **Do not substitute local fixtures for evidence.** SQLite `CONFIRMED`, `FAILED`, fabricated effect rows, `FakeAdapter`, self-described `producer_enrolled=True`, mocked signatures, local hash chains, and any budget `allowed=True` preflight remain insufficient for producer authentication.
2. **Verify enrollment and exact origin independently.** Identity must be pinned to the actual sender/owner, scope and provider account, with a secured root and revocation/rotation strategy independent of action input and callback attributes. Reject unknown or stale roots.
3. **Bind all evidence to a single causal transaction.** Authenticate producer issuer, event kind, request ID/idempotency key, payload/action digest, account, scope, transaction, epoch/sequence, and durable monotonic witness. Reject replay, equivocation, stale lease, cross-tenant substitution and detached effect references.
4. **Split COMMITTED_EFFECT from NO_EFFECT_FENCED.** An eventual delivered/queued status is not necessarily a committed effect receipt, and an empty search result or a callback-reported negative is not proof that the provider cannot effect the action later. NO_EFFECT_FENCED must be a provider-enforced terminal guarantee.
5. **No automatic retry in ambiguity.** After unknown effect state, preserve `SENT`/`UNCERTAIN` + FIFO hold, revalidate independently and follow a provider-specific reconciliation/manual route. **ZERO_AUTO_RESEND** unless a separately verified idempotent/enforced no-effect protocol is present.
6. **Never bypass approval.** Human owner proof, policy, RBAC, budget, scope and security hard stops are separate controls. Valid receipts, if eventually available, must not replace human authorization or permission to execute.
7. **Release protocol must be independently reviewed.** Validate actual provider capability, real issuer proofs, process restart, replay/antirollback, network partitions, uncertain responses, API errors, compensation and cross-platform tests. Run canonical Quality/Security with explicit evidence, then P0-specific homologation. Merely making 32 historical tests green through weakened guards is prohibited.

## Safe local tests in this LAB

`test_aion_p0_quality_32_external_evidence_gates_lab.py` checks:
- **one-to-one exact 32-case inventory** against the canonic registry, original source method lines, and open/error status;
- **23/8/1 gate accounting** without waiving or relabeling historical ERROR;
- **pre-adapter producer denial** even when adapter self-claims trust (property descriptors never touched);
- **no local reconciliation** of `SENT` or `UNCERTAIN`, no callback or resend;
- **local-only CONFIRMED** not sufficient for Saga effect or budget accounting;
- **local-only FAILED / REVOKED / BLOCKED_REAPPROVAL** not sufficient for provider-enforced terminal no-effect;
- **uncertain forward** remains `RECONCILIATION_REQUIRED`.

**This only verifies current fail-closed behavior; it cannot prove that unavailable positive receipts would be valid.** No real provider contacted, Worker still OFF, no merged code, no deploy, no external idempotency mechanism presumed.

## Status and next action

- **Case status:** 32 `OPEN_NOT_WAIVED`. Full Quality remains RED at the recorded baseline until separately reexecuted.
- **H0 security P0:** 0/6 homologated, no authority elevation. HARD NO-GO.
- **Engineering dependency:** independently verified provider capabilities and proof roots must be obtained/validated before designing productive enrollment, COMMITTED_EFFECT or NO_EFFECT_FENCED admission. The correct fallback where capabilities do not exist is **manual reconciliation and non-automatic resend**, not fake proof.
- **FinOps:** no paid provider, Worker activation or additional spend authorized.
