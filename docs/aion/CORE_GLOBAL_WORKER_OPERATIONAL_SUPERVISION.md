# AION Global Worker Operational Supervision V1

This layer sits above Live Activation Verification and translates raw evidence
into operator posture, severity, incident state and a recovery checklist.

It is read-only.

## Principle

A recommendation is not an action.

The supervisor can recommend a safety stop, but it never changes the repository
feature flag, runtime Checkpoint, lease, schedule or worker state.

The existing explicit deactivation ceremony remains the only path for changing
the feature flag.

## Inputs

The supervisor consumes:

- a Global Worker Live Verification report;
- authoritative read-only feature-flag evidence.

It does not query external systems by itself.

## Postures

### STANDBY_SAFE

The feature flag is authoritatively UNSET/DISABLED and there is no preserved
incident that must remain visible.

### ACTIVATION_PENDING

Used for:

- AWAITING_LIVE_EVIDENCE;
- LIVE_HEARTBEAT_CONFIRMED_AWAITING_TICK.

This is low severity and does not automatically recommend a stop.

### HEALTHY_LIVE_IDLE

The global runner completed a verified tick after activation and no due work
receipt was required.

### HEALTHY_LIVE_WORK

The global runner completed a verified tick and at least one post-activation
GLOBAL_WORKER receipt exists.

### INCIDENT_LIVE_TIMEOUT

No shared heartbeat was confirmed within the live verification window.

Severity: HIGH.

If the feature flag is still ENABLED, manual safety-stop is recommended.

### INCIDENT_STALE_LEASE

A global lease still has an owner after expiry.

Severity: HIGH.

If the feature flag is still ENABLED, manual safety-stop is recommended.

### INCIDENT_UNSAFE_RECEIPT

A post-activation GLOBAL_WORKER receipt reported provider, external action or
real-trading effect.

Severity: CRITICAL.

If the feature flag is still ENABLED, manual safety-stop is recommended.

### INCIDENT_VERIFICATION_BLOCKED

Live verification was blocked by an evidence, context or integrity failure.

Severity: HIGH.

Human review is required before making any operational claim.

## Incident preservation after disable

Turning the feature flag off prevents future wake-ups, but it does not erase an
already observed incident.

For example, an unsafe receipt remains CRITICAL after a safety disable. The
only change is that another safety-stop is no longer recommended because the
flag is already disabled.

## Recovery checklist

Every report includes recovery steps.

Common rules:

- preserve evidence;
- keep real trading/external actions blocked;
- do not widen permissions during diagnosis.

Incident-specific steps cover:

- timeout;
- stale lease;
- unsafe receipt;
- blocked evidence.

The checklist is guidance only and does not execute a step.

## Incident proposal

`operational_incident` can produce an Incident-Center-compatible proposal with:

- deterministic incident ID;
- severity;
- title/detail;
- evidence source;
- safety-stop recommendation;
- automatic containment=false;
- automatic rollback=false;
- real orders=false.

The proposal is not automatically inserted into the Checkpoint or Incident
Center.

## Central AION

After a live verification snapshot, the Central shows:

- posture;
- severity;
- safety-stop recommended: SIM/NÃO;
- incident-open warning;
- recovery checklist.

The UI explicitly states:

- supervision is read-only;
- automatic containment: NO;
- automatic feature-flag mutation: NO;
- real trading: NO.

## No mutation authority

This module contains no:

- repository-variable write;
- Checkpoint write;
- worker tick;
- workflow dispatch;
- subprocess/shell;
- provider call;
- payment;
- publication;
- deployment;
- merge;
- market order.

Any future automatic containment would require a new explicit architecture and
approval boundary; it is not part of V1.


## Session-local supervision history

The Central keeps a bounded operator-facing history in Streamlit session state.

- evidence-derived event IDs deduplicate identical snapshots;
- the UI keeps at most 50 observations;
- the latest five are displayed;
- incident and critical-incident counts are summarized;
- history is not persisted to the runtime Checkpoint;
- history does not write repository variables or any external observability service.

This history is a convenience for the active ADMIN session. Shared runtime,
feature-flag, lease and receipt evidence remain the source of truth.
