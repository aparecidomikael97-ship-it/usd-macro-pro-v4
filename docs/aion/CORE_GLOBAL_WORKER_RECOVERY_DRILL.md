# AION Global Worker Recovery / Incident Drill V1

## Purpose

This block rehearses operator recovery for Global Worker incidents **without
performing recovery**.

It consumes the read-only Operational Supervision snapshot and can prepare a
simulation for:

- live evidence timeout;
- stale lease;
- unsafe GLOBAL_WORKER receipt;
- generic verification-blocked state.

The drill is an exercise. It is not authority to change production state.

## Non-negotiable truth rule

**Simulation is not containment, recovery, reactivation, or proof of LIVE.**

Even when the drill reaches `DRILL_COMPLETED_SIMULATION_ONLY`, it reports:

- `real_incident_contained=false`;
- `real_recovery_confirmed=false`;
- `reactivation_authorized=false`;
- `feature_flag_modified=false`;
- `runtime_modified=false`;
- `executes_action=false`;
- `real_trading_enabled=false`.

## Confirmation boundary

Executing the in-memory exercise requires the exact phrase:

`SIMULAR RECUPERACAO WORKER GLOBAL`

This phrase authorizes only the simulation. It must never be interpreted as
authorization for the real safety-stop ceremony, arming, persistence,
activation, workflow dispatch or worker execution.

## Supported scenarios

### LIVE_TIMEOUT

The drill rehearses:

1. preserve activation/live evidence;
2. freeze permission expansion;
3. identify that a manual safety-stop ceremony may be required;
4. review schedule and shared heartbeat path;
5. require fresh authoritative evidence;
6. keep reactivation unauthorized.

No artificial heartbeat is generated.

### STALE_LEASE

The drill rehearses review of:

- lease owner;
- expiry;
- heartbeat;
- fencing token;
- future claim safety.

It never clears or overwrites a real lease.

### UNSAFE_RECEIPT

The drill preserves the unsafe receipt conceptually and rehearses tracing the
path that reported provider, external-action or real-trading effects.

It never deletes receipts and never modifies executor history.

### VERIFICATION_BLOCKED

The drill requires the verifier reason to be resolved with authoritative
evidence before any LIVE claim can return.

## Stages

Every stage is emitted with:

- `mode=SIMULATION`;
- `executes_action=false`.

Typical stages are:

- PRESERVE_EVIDENCE;
- FREEZE_AUTHORITY_EXPANSION;
- MANUAL_SAFETY_STOP or CONFIRM_SAFE_FLAG_POSTURE;
- DIAGNOSE_ROOT_CAUSE;
- REVALIDATE_SHARED_EVIDENCE;
- REACTIVATION_GATE.

The final gate always states:

`REACTIVATION_NOT_AUTHORIZED_BY_DRILL`

## Safety-stop boundary

When Operational Supervision recommends safety-stop, the drill shows that the
existing ADMIN deactivation ceremony would be required.

It does **not** call that ceremony.

The recovery drill contains no API for repository-variable mutation and no
automatic containment path.

## Central AION

The Central exposes an expander:

`🧪 Drill de recuperação do Worker Global`

The interface states **SIMULAÇÃO SOMENTE** and requires the exact simulation
confirmation phrase before running the in-memory exercise.

After completion, the UI explicitly shows:

- recuperação real: NÃO;
- reativação autorizada: NÃO;
- flag alterada: NÃO;
- runtime alterado: NÃO;
- execução real por estágio: NÃO.

## No new authority

The drill module contains no:

- PUT/POST/PATCH/DELETE;
- runtime Checkpoint write;
- repository feature-flag mutation;
- worker tick;
- workflow dispatch;
- subprocess/shell;
- provider call;
- payment;
- publication;
- deploy;
- merge;
- market order.

## Scope

This block is designed to be implemented and audited while the real Global
Worker remains unarmed/unactivated. It must stay Draft until the surrounding
stack is reviewed.

No merge, deploy, arming, persistence, activation or real containment is part
of this implementation.
