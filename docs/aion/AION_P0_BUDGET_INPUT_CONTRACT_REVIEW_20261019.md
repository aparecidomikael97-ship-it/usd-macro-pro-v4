# AION P0 LAB — budget guard input-type contract review

**Date:** 2026-10-19 (America/Cuiaba).  
**Scope:** independent review of the **non-Mapping** input behavior of `CumulativeAuthorityBudget.guard` and its immediate Outbox/Saga consumers.  
**Status:** *OPEN CONTRACT GAP — NOT A P0 HOMOLOGATION OR EXTERNAL EFFECT*.  
**Parent:** Issue #1330 / PR Draft #1331.  
**Isolation:** `lab/aion-p0-budget-input-contract-20261019`, based on prior independent review; **no product code modification**.

## Static findings / hypotheses to verify in offline CI

1. `guard(decision: Mapping[str, Any])` is type-annotated but calls `_validate_decision(decision)` without runtime `isinstance(decision, Mapping)`. That helper executes `row = dict(decision or {})`. A truthy `list` or `tuple` of valid pairs can therefore be reconstructed as a valid decision and yield `allowed=True` **for budget preflight only**. No `grants_authority` or `executes_action` flag is raised by this outcome.
2. For malformed truthy non-Mapping input not convertible to a valid bound dict, the `except` return tries `(decision or {}).get("transaction_id")`. Integers, strings and lists lack `.get`; this path may raise `AttributeError` rather than produce the stable negative response promised to callers.
3. Falsy non-Mapping inputs are expected to return `allowed=False` with explicitly false security flags because `decision or {}` is an empty dict.
4. `Saga.authority_guard` forwards its input directly to `Budget.guard`, so callers bypassing Python type annotations can observe the same preflight behavior, **not a producer receipt**.
5. `Outbox.dispatch_claimed` calls the supplied budget guard in a `try/except Exception`; exceptions fail as `BLOCKED_REAPPROVAL` before any adapter access. Even a valid preflight remains blocked later by `INDEPENDENT_PRODUCER_NOT_ENROLLED`. No real producer is enrolled.
6. A callback supplying `allowed=True` is *not* an independent verifier. The current producer hard stop prevents external execution; a future rollout must require a separately rooted, scoped authority chain and never rely solely on callback assertions.

## Test philosophy: DO NOT MISREAD GREEN

`tests/test_aion_p0_budget_input_contract_observation_lab.py` is an **observation** suite, with tests intentionally asserting the current, undesirable non-Mapping acceptance so it remains reproducible. **A green test proves the gap is observable; it does NOT certify the contract as compliant.**

- Typed valid preflight: `allowed=True`, but **all effect flags false**.
- Non-Mapping pair-list / tuple: diagnostic positive preflight, all effect flags false; acceptance is **unwanted**.
- Malformed truthy input: diagnostic exception, no committed authority/effect.
- Falsy input / invalid scope: denied with false flags.
- Real Saga facade: cannot equate pair-list preflight with producer proof.
- Real Outbox callback: catches erroneous guard input, persists `BLOCKED_REAPPROVAL` and does not read adapter descriptor.
- No `record_confirmed` call, trusted external receipt, Worker, network provider, billing or deployment.

## Exit criteria (separate follow-up, not part of PR #1331)

1. Define the runtime input contract: non-Mapping inputs must be **rejected predictably** before the preflight or given a structured denial, even if `dict(nonmapping)` could be made.
2. Restore a stable, explicit-negative failure contract without trusting `.get` on unvalidated input types. Reject unexpected nested representations and side-effectful Mapping implementations through independent validation.
3. Preserve all existing `allowed=False`/false-effect flags; preserve wrong-thread protection and `Outbox` provider hard stop.
4. Change diagnostic observation tests to **normative negative** assertions when an independently reviewed fix is prepared; run targeted canonical tests on both SO and full Quality where authorized.
5. Do not merge PR #1331 automatically or close #1330 merely because a different input contract is characterized.

**Overall state:** HARD NO-GO; 0/6 P0 homologated; historical Outbox+Saga 32 ERROR OPEN_NOT_WAIVED; Worker OFF / ZERO_AUTO_RESEND.
