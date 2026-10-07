# AION Operational Resilience / DR Readiness V1

Status: **staging / Draft-only**.

## Objective

Turn recovery claims into an evidence-bound readiness gate without pretending
that a production restore, deploy or failover has happened.

This block evaluates:

- component health;
- availability SLO;
- error-budget burn;
- heartbeat freshness;
- RPO;
- RTO;
- backup integrity;
- backup encryption/key availability;
- recovery-drill freshness;
- exact restored revision/digest;
- boot and health verification after a drill.

## Policy

The gate has no permissive defaults for operational targets. It requires a
`VERIFIED` policy bound to the same owner/tenant/workspace as the evidence.

The policy must explicitly provide:

- availability SLO;
- maximum error-budget burn;
- RPO seconds;
- RTO seconds;
- maximum recovery-drill age;
- maximum heartbeat age;
- minimum successful drill count;
- required component list.

Missing, malformed, cross-scope or unverified policy => BLOCKED.

## RPO

The latest accepted recovery point must be no older than the policy RPO.
Backup evidence must bind:

- backup id;
- source revision;
- full SHA-256 source digest;
- VERIFIED integrity;
- encryption=true;
- key_available=true;
- key_ref;
- evidence refs.

This is a recovery-point readiness check, not a claim that every production
write has already been replicated.

## RTO / recovery drills

A successful drill must:

- reference an accepted backup;
- finish inside the policy RTO;
- recover the exact source revision and digest;
- verify restored integrity;
- prove application boot and health;
- include evidence refs;
- explicitly prove that the drill did not mutate production, call a provider or
  execute an external action.

The minimum number of successful drills and drill freshness are policy-bound.

## Service-level readiness

Every required component needs:

- HEALTHY state;
- availability at or above SLO;
- error-budget burn within policy;
- fresh heartbeat;
- evidence refs.

Missing required components fail closed.

## Output

The strongest state is `READY_FOR_ADMIN_REVIEW`.

It does **not** mean:

- production-ready claim;
- authorized restore;
- automatic failover;
- automatic deploy;
- automatic re-enable.

A separate incident-control/authority gate and explicit HUMAN_OWNER decision are
still required before any real operational mutation.

## Guardrails

- Draft only;
- merge=false;
- deploy=false;
- restore=false;
- failover=false;
- provider/network=false;
- worker arming=false;
- Core Freeze=false;
- production mutation=false;
- `executes_action=false`.
