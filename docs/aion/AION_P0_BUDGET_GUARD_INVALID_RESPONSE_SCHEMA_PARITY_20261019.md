# AION P0 LAB — Budget.guard invalid-path response schema disparity

**Date:** 2026-10-19 (America/Cuiaba)  
**Scope:** read-only diagnosis and test-only assertions, branch `lab/aion-p0-quality-governance-20261019`.  
**Status:** **OPEN / NO-GO / not a product fix**.

## Independently observed in LAB CI

The `CumulativeAuthorityBudget.guard` method in `atlasquant_aion_cumulative_authority_budget.py` responds to a valid candidate with `allowed`, `reason`, `grants_authority=False`, `execution_allowed_by_this_component=False`, and `executes_action=False`.

Its `_validate_decision` exception path (invalid owner, tenant, workspace, budget reference, or policy version) returns `allowed=False`, `reason=AUTHORITY_BUDGET_BINDING_INVALID:<type>`, `grants_authority=False`, and `executes_action=False`, **but omits** `execution_allowed_by_this_component` entirely.

This was detected by the newly added LAB `test_05_wrong_scope_budget_reference_policy_denied_even_if_under_budget`: each of its five subtests threw `KeyError` when checking the field, **not because execution was allowed**. This finding is about **inconsistent response schema** and potential consumer contract ambiguity; it is *not* evidence of privilege escalation or a real external send.

## Protective interpretation

- The invalid-path `allowed=False` and `grants_authority=False` remain fail-closed.
- The revised LAB test explicitly checks the actual denial and documents the missing field; no fallback of the form `allowed=True`, positive trusted receipt, or runtime authorization has been introduced.
- This behavior remains an **OPEN product contract parity gap** requiring a separately reviewed change if the consumer contract mandates that field on all outcomes.
- Source of truth for external authority remains an independent producer, real durable receipts, HUMAN_OWNER verification, and fail-closed controls. Local budget ledger rows / invented authorization references are *not* that proof.
- No `atlasquant_aion_cumulative_authority_budget.py`, Saga, Outbox, Quality workflow, or existing historical test was modified in this round.

## Follow-up / exit criteria

1. Agree on the normalized contract for *all* budget responses, including failures.
2. Implement an independently reviewed product fix in a separate authorized engineering branch, preserving all denial semantics and checking all call sites.
3. Add consumer-side contract tests including wrong scope/policy/budget and hostile missing fields; validate on Ubuntu and Windows.
4. Do **not** close any of the canonical 32 Outbox/Saga historical Quality errors or any P0 merely because this LAB test passes.

**Operational status:** HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND; no merge or deploy.
