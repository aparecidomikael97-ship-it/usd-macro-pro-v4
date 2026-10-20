# AION LAB — Candidate for Input Contract issue #1332

**Date:** 2026-10-19. **Status:** CANDIDATE ONLY, no integration, no merge or deploy.

## Precise product change

In `CumulativeAuthorityBudget.guard`:

- Before attempting `dict(decision)`, verify `isinstance(decision, Mapping)`. Reject non-Mapping lists and tuples **even if** they contain valid field pairs and could otherwise yield `allowed=True` preflight.
- On the error-return path, avoid unconditional `(decision or {}).get(...)`. Use a diagnostic transaction hint only for Mapping inputs; if its `get` is hostile/throws, return `transaction_id=""`.
- Preserve `allowed=False`, `grants_authority=False`, `execution_allowed_by_this_component=False`, `executes_action=False` on every validation denial.
- Do not change budget arithmetic, confirmation ledger, Outbox/Saga, producer enrollment, role checks, SQLite persistence or authority caps.

## Regression design

Two prior diagnostic tests intentionally *observed* the old unwanted `allowed=True` on pair lists/tuples. **In this candidate only**, assertions were converted to **normative `allowed=False`**; malformed truthy non-Mapping inputs now must get a structured negative response. A previous independent review test expecting `AttributeError` now requires stable false flags. An extra case tests a hostile `Mapping` object with `__iter__` and `get` that raise: denial must remain non-throwing and non-authorizing.

A green test in the **original diagnostic branch** meant only "gap reproduced". Green tests in this candidate mean the **specific input contract was corrected within LAB**. Neither implies producer enrollment, P0 homologation, a real external receipt or readiness to merge.

## Exit gates

- Cross-platform targeted GitHub Actions matrix, including canonical budget-only tests, schema parity/consumer tests, independent abuse cases and normative input contract tests.
- Separate human/third-party PR review, explicit confirmation of no contract regression for honest Mapping subclasses.
- Full canonical Quality and current Security evidence before any integration. Historical 32 Outbox/Saga errors remain nonwaived.
- HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND, no provider access, merge or deploy.
