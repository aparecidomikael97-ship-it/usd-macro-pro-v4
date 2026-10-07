# AION B2B Diagnostic Intake V1

Status: **staging / evidence-bound / human-scored**.

## Objective

Create the structured diagnostic entrypoint for AION Negócios before the existing
B2B Pilot Readiness score is evaluated.

The diagnostic does not replace Pilot Readiness and does not create a second
acceptance/risk model.

## Diagnostic areas

The dossier requires evidence for:

- sales;
- customer service;
- billing;
- team;
- systems;
- bottlenecks.

Each area records:

- current process;
- pain points;
- systems involved;
- evidence references;
- baseline metrics when applicable.

Sales, customer service and billing require at least one evidenced baseline metric.

## Global diagnostic fields

The dossier also binds:

- owner / tenant / workspace;
- candidate ID;
- lead ID;
- company key and label;
- assessor-context reference;
- objectives;
- constraints;
- quick-win candidates;
- candidate integrations;
- global evidence references.

## Completeness

The module computes diagnostic completeness only.

`READY_FOR_HUMAN_SCORING` requires all mandatory evidence to be present.

Incomplete evidence produces `INCOMPLETE` and explicit blockers.

Completeness is **not** an acceptance score.

## Human scoring boundary

The bridge to Pilot Readiness requires:

- `human_assessed=true` exactly;
- an assessor reference;
- explicit scores for all seven existing Pilot Readiness dimensions;
- explicit privacy and operational risk scores;
- planned monthly infrastructure;
- pilot duration;
- assessment evidence refs.

The seven score dimensions remain:

- problem fit;
- process repeatability;
- data readiness;
- owner sponsorship;
- integration feasibility;
- expected value;
- scope clarity.

No score is inferred from text, pain points, baselines or quick wins.

Invalid scores are blocked rather than clamped or guessed.

## Existing gate reuse

`build_pilot_scoring_input` prepares the candidate payload expected by the existing
`assess_b2b_pilot_candidate` gate.

It does not call that gate itself and does not create a parallel scoring engine.

The existing Pilot Readiness layer remains responsible for:

- acceptance score;
- privacy/operational risk handling;
- infrastructure cap;
- managed-operations reference evidence;
- hardening evidence;
- final PILOT_REVIEW_CANDIDATE / REVIEW / DECLINE / BLOCKED decision.

Even a positive result remains owner-review only.

## Safety boundary

The diagnostic never:

- generates scores automatically;
- accepts or rejects a real customer with external effect;
- sends outreach;
- writes CRM data;
- generates a proposal automatically;
- commits pricing;
- signs or changes a contract;
- provisions an account;
- deploys;
- bills or charges;
- calls a provider;
- mutates production.

All automatic-action flags remain false.
