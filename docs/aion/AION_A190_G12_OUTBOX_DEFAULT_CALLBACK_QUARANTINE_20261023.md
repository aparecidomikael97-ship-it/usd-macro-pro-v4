# A190 G12 — ExecutionOutbox callback quarantine by default (LAB, 2026-10-23)

## Objective and exact scope

Follow-up to the **G6 real Outbox callback trust-boundary RED** and G11 offline conditional-cloud request-shapes. This change deliberately touches the **real** atlasquant_aion_execution_outbox.py, not only a simulator, but is restricted to an isolated Draft PR. No merge, deploy, Worker, account, cloud provider, key provisioning, payment, real adapter or external effect.

The original constructor accepted first_attempt_guard and evidence_verifier supplied by the caller. A caller-provided true-returning function could trigger an adapter send and promote a self-reported effect to CONFIRMED. G6 proved this with a **fake in-memory adapter only**. G11 does not fix this on its own.

## Change

1. **Default quarantine:** unsafe_allow_synthetic_lab_callbacks=False now disables **both** the first-attempt reservation callback and the evidence-verifier callback even when provided by the caller.
2. A claimed action can reach UNCERTAIN (reservation outcome unknown) but **cannot** reach adapter.send through default callbacks. There is no automatic resend from UNCERTAIN.
3. adapter.send attribute lookup occurs only after a positive witness in the explicit LAB opt-in. This prevents untrusted property getters from being evaluated on the default no-send path.
4. reconcile() with the default configuration returns EXTERNAL_TRUST_NOT_CONFIGURED without inspecting the caller's adapter or recording a CONFIRMED effect, including after reopening the SQLite database.
5. The explicit boolean unsafe_allow_synthetic_lab_callbacks=True exists **solely** to preserve preexisting synthetic state-machine tests, Saga, A176/A177, and G6 RED reproductions. Non-booleans are rejected. A missing adapter.send **after** a synthetic witness has accepted the first-attempt reservation stays UNCERTAIN instead of silently reopening a retry.
6. New G12 negative tests exercise forged true callbacks, malicious adapter attribute getters, restart, strict flag typing, semantic relabeling, no blind resend, and the deliberate LAB-unsafe mode. Existing Outbox/Saga and G6 tests are migrated to the explicit synthetic option; G6 RED remains observable inside LAB.

## Proven and unproven

| Property | In G12 default code | Operational consequence |
| --- | --- | --- |
| True callback alone authorizes adapter.send | **NO** | Default caller wiring cannot accidentally lift the no-send gate |
| True receipt callback alone makes CONFIRMED | **NO** | No local unverified effect ledger confirmation by default |
| Automatic retry after uncertain reservation | **NO** | Remains UNCERTAIN / ZERO_AUTO_RESEND |
| Explicit synthetic LAB opt-in can still call fake adapter | **YES** | A malicious in-process host can opt in; this remains a **security weakness**, not a trust solution |
| External HUMAN_OWNER, independent issuer/root or hardware-backed identity | **ABSENT** | P0 not homologated |
| Independently durable, non-rollback reservation witness | **ABSENT** | P0 not homologated |
| Native SQLite file identity with atomic guard, plus compat protections | **UNPROVEN** | P0 not homologated |
| Real provider-side idempotency and signed receipt | **ABSENT** | P0 not homologated |
| Independent process administration controlling opt-in/config | **ABSENT** | P0 not homologated |

**Important limit:** the boolean opt-in is a convenience for unit tests, *not* a secure authorization switch. Python callers who control code can enable it, monkeypatch the process, or inject an adapter. No local option or callback replaces an independent trust root, signed receipts, filesystem rollback resistance, or provider idempotency. This PR must not be merged as production-ready authority.

## Exit gates

A real operational implementation must obtain independently authenticated identity/approval, externally durable one-time semantic first-attempt reservation and trusted recovery after ambiguous responses, provider-verifiable receipts, SQLite identity/compatibility proofs, OS-independent rollback protection and independent negative validation **without** granting unsafe synthetic opt-in. Validate the entire canonical Security/Quality suites separately: this targeted CI is not a substitute.

**Status: 0/6 P0 homologados. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND.**

## Evidence

The accompanying G12 workflow runs G12 + existing Outbox/Saga/A176/A177/G6/G5/G4/G3 on Ubuntu and Windows from the pinned head SHA; linked run, job IDs, test counts and exact tested commit must be inserted after the CI result. Existing historical external RED and advisories remain open; this PR does not claim they are resolved.
