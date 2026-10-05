# AION Data Drift + Decision Drift V1

Status: **staging / Draft-only**.

## Objective

Monitor whether the input population or AION decision behavior has moved far
enough from a verified reference window to require degradation or a promotion
hold.

## Data Drift

For each bounded feature histogram, the monitor computes Population Stability
Index (PSI) against the reference distribution.

Policy defines separate warning and blocking thresholds.

The monitor requires:

- exact owner/tenant/workspace binding;
- minimum sample size;
- version/window identity;
- evidence refs;
- same feature set;
- finite non-negative normalized distributions.

## Decision Drift

The monitor computes total variation distance (TVD) between reference and
current decision distributions and separately checks:

- safety-violation rate regression;
- current UNKNOWN rate;
- current human/override rate.

These safety rates are hard blocking limits rather than soft drift warnings.

## States

- `STABLE`: no warning/block threshold exceeded;
- `DEGRADED`: warning threshold crossed;
- `BLOCKED`: invalid evidence, scope mismatch, hard drift or safety limit.

Any state other than STABLE produces `HOLD_PROMOTION`.

## Promotion gate

The optional promotion gate can return at most
`HUMAN_REVIEW_CANDIDATE`.

It never authorizes promotion and never:

- retrains;
- changes a model;
- changes a prompt;
- calls a provider;
- mutates production.

## Guardrails

Draft only.
merge=false.
deploy=false.
automatic_retraining=false.
automatic_promotion=false.
automatic_model_switch=false.
provider_called=false.
production_mutation=false.
Core Freeze=false.
worker arming=false.
real trading/payment=false.
