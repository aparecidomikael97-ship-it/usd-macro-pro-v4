# AION Global Worker Recovery Evidence / Incident Closure V1

## Purpose

This layer prevents the AION from treating a simulated drill, a disabled flag,
or one new heartbeat as proof that a Global Worker incident is resolved.

It binds three things:

1. the original Operational Supervision incident;
2. explicit remediation evidence;
3. newer shared runtime / feature-flag evidence.

The highest state this module can produce is:

`CLOSURE_REVIEW_READY`

That means **evidence is sufficient for a human closure review**. It does not
mean the incident is closed.

## Truth boundary

The module always preserves:

- `incident_closed=false`;
- `automatic_closure=false`;
- `human_closure_required=true`;
- `reactivation_authorized=false`;
- `feature_flag_modified=false`;
- `runtime_modified=false`;
- `executes_action=false`;
- `real_trading_enabled=false`.

Even when recovery evidence is strong enough to support review, real incident
closure remains a separate human/governance action.

## Remediation evidence

Remediation evidence is session-local and is bound to the original incident
evidence digest.

It requires all of the following:

- root cause identified;
- corrective action verified;
- regression check passed;
- original incident evidence preserved;
- reviewer confirmation;
- remediation evidence timestamp after the incident;
- exact phrase:

`CONFIRMAR EVIDENCIA DE REMEDIACAO WORKER GLOBAL`

The phrase authorizes only creation of the in-memory remediation evidence. It
does not authorize a safety stop, reactivation, merge, deploy, worker tick,
Checkpoint write, or feature-flag mutation.

## Fresh current evidence

Closure readiness also requires newer shared evidence after the incident.

A safe current state can be either:

- authoritative flag UNSET/DISABLED + live verifier reports `NOT_ENABLED`; or
- authoritative flag ENABLED + verifier reports `LIVE_CONFIRMED_IDLE` or
  `LIVE_CONFIRMED_WITH_WORK`, with heartbeat and tick confirmed.

A disabled flag alone is not enough if remediation is missing.

## Incident-specific blockers

### Timeout

If the feature flag remains ENABLED, the current live status must be a
confirmed LIVE state. Otherwise:

`LIVE_TIMEOUT_NOT_RECOVERED`

### Stale lease

If current evidence still reports a stale lease:

`STALE_LEASE_STILL_PRESENT`

### Unsafe receipt

If current evidence still reports unsafe GLOBAL_WORKER receipts:

`UNSAFE_RECEIPT_STILL_PRESENT`

### Verification blocked

If current verification is still blocked:

`VERIFICATION_STILL_BLOCKED`

## Binding

Remediation evidence must reference the exact original incident evidence digest.
A mismatch produces:

`REMEDIATION_INCIDENT_BINDING_MISMATCH`

Current evidence must also postdate the incident. Old snapshots cannot close a
newer incident.

## States

- `NO_OPEN_SUPPORTED_INCIDENT`
- `CLOSURE_BLOCKED`
- `CONTAINED_AWAITING_REMEDIATION`
- `CLOSURE_REVIEW_READY`

`CONTAINED_AWAITING_REMEDIATION` means the Worker is currently in a safe
disabled posture, but the case still lacks enough remediation evidence.

## Closure review record

`closure_review_record()` creates only a session-local review record.

Even for a ready case it says:

- `status=READY_FOR_HUMAN_CLOSURE_REVIEW`;
- `incident_closed=false`;
- `persistent=false`;
- `executes_action=false`.

The closure package digest binds the original incident, remediation package and
fresh current evidence for later human review.

## Central AION

The Central exposes:

`🧾 Evidência de recuperação / fechamento`

The operator can confirm remediation facts, enter the exact phrase and then
request a fresh read-only assessment.

The panel explicitly distinguishes:

- “pronto para revisão humana” from “encerrado”;
- recovery evidence from actual closure;
- closure review from reactivation authority.

## No new authority

This module contains no:

- repository-variable write;
- runtime Checkpoint write;
- worker tick;
- workflow dispatch;
- subprocess/shell;
- provider/payment/publication/deploy/merge/trading action.

## CI audit

The Draft PR may be retargeted temporarily to `main` only to run the standard
pull-request workflows. After audit it must return to its stacked base.

No merge, deploy, arming, persistence, activation, reactivation or real incident
closure is authorized by this block.
