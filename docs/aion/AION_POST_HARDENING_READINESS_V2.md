# AION Post-Hardening Readiness Gate V2 — Crypto-Complete

Status: **staging / Draft-only**.

V2 extends the independently verified V1 gate by making the reconciled tenant
cryptography contract a mandatory stage.

## Required stages

1. tenant crypto;
2. durable-task physical CAS;
3. FinOps admission;
4. behavioral model/prompt evaluation;
5. incident-control authority;
6. operational resilience / DR readiness.

## Tenant crypto invariant

The exact verified snapshot must prove:

- AES-256-GCM;
- 32-byte key and 12-byte nonce contract;
- key material is never serialized;
- key resolver is injected;
- AAD binds tenant/workspace;
- production encryption is required;
- homegrown crypto is false;
- production KMS connected is false until real evidence exists;
- automatic key deletion is false;
- executes_action is false.

Like every other stage, the exact snapshot digest must have an independent
VERIFIED entry in the append-only verification ledger bound to the same
owner/tenant/workspace.

## Strongest result

`READY_FOR_HUMAN_OWNER_REVIEW` remains the maximum result. It does not authorize
merge, deploy, Core Freeze, worker arming, provider activation, restore,
production persistence, payment or real trading.

V2 deliberately distinguishes **cryptographic contract readiness** from a real
production KMS or key-deletion ceremony. Missing operational proof remains
UNKNOWN/BLOCKED rather than being inferred.
