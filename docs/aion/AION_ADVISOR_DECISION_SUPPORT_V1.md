# AION Advisor + Decision Support V1

Status: IMPLEMENTATION SAFE / ADVISORY CONTRACT ONLY  
Date: 2026-10-08  
Stacked base: AION Presentation Artifact + Control V1  
Decision authority: HUMAN ONLY  
Execution authority: NONE  
Production status: NOT DEPLOYED

## Objective

Create a rigorous AION "Conselheiro" layer that can:

- compare alternatives;
- surface risks and mitigations;
- identify evidence gaps and conflicts;
- flag risky contract clauses for review;
- provide an evidence-supported recommendation;
- represent calibrated uncertainty without fake precision;
- keep recommendation, approval and execution strictly separated.

The implementation reuses the existing AION Data & Decision Fabric instead of
creating a second decision engine.

## Source of truth

The Data & Decision Fabric already provides:

- CONFIRMED / INFERENCE / HYPOTHESIS / UNKNOWN truth states;
- evidence coverage;
- evidence conflict detection;
- research-required state;
- test-required state;
- risk-review state;
- HUMAN_REVIEW_CANDIDATE;
- no automatic action authority.

The Advisor consumes that evaluation.

It cannot bypass or downgrade a Fabric blocker.

## Advice lifecycle

The safe lifecycle is:

1. Evidence enters the Data & Decision Fabric.
2. A decision case identifies required evidence, tests and risk posture.
3. The Fabric evaluates evidence coverage/conflicts.
4. Advisor structures alternatives, risks, assumptions and dependencies.
5. Advisor may recommend an option only when the Fabric reaches
   HUMAN_REVIEW_CANDIDATE and advisory validation is clean.
6. HUMAN_OWNER reviews the advice.
7. Any approval is handled by a separate approval/authorization contract.
8. Any execution is handled by a separate execution adapter.

Therefore:

`RECOMMENDATION != APPROVAL != EXECUTION`

## Options

A valid advisory assessment requires at least two alternatives.

Each option binds:

- option ID;
- title;
- summary;
- pros;
- cons;
- evidence references;
- assumption references;
- dependency references;
- reversibility;
- rollback reference when applicable;
- broad cost band;
- broad time band.

The Advisor does not invent a ranking score from the number of pros/cons.

## Recommendation gate

A recommendation may only be emitted when:

- the underlying decision state is HUMAN_REVIEW_CANDIDATE;
- required evidence is present;
- no evidence conflict remains;
- required tests are present;
- required rollback review is satisfied;
- advisory options/risks are structurally valid.

A recommendation never sets:

- action_authorized;
- automatic_execution;
- payment_authorized;
- trading_order_authorized;
- contract_signed;
- message_sent.

## Risk register

Supported risk categories include:

- LEGAL_CONTRACT
- FINANCIAL
- SECURITY
- PRIVACY
- OPERATIONS
- TECHNICAL
- REPUTATION
- COMPLIANCE
- MARKET
- EXECUTION
- DEPENDENCY
- OTHER

Supported severity levels:

- LOW
- MEDIUM
- HIGH
- CRITICAL

HIGH or CRITICAL risks require evidence references and a mitigation.

CRITICAL risk forces:

`RISK_REVIEW_REQUIRED`

It cannot be auto-approved.

## Contract-clause advisor

The Advisor can flag a contract clause as a risk review item.

A LEGAL_CONTRACT risk requires a clause reference.

For HIGH/CRITICAL contract risk, the output sets:

`professional_review_recommended=true`

The Advisor explicitly does **not** issue a legal conclusion.

This allows messages such as:

> "This clause may create asymmetric exposure and should be reviewed"

without falsely claiming:

> "This clause is legally invalid."

## Confidence and probability

Confidence is not treated as a probability of success.

The allowed confidence posture is qualitative:

- INSUFFICIENT_EVIDENCE
- CONFLICTED_EVIDENCE
- EVIDENCE_SUPPORTED

The system does not convert evidence coverage into a fake "83% chance of
success."

## Optional probability estimate

Probability is optional.

Default:

`NOT_ESTIMATED`

An estimate may only be accepted as:

`EVIDENCE_SUPPORTED_RANGE`

and requires:

- minimum percentage;
- maximum percentage;
- method reference;
- calibration reference;
- evidence references.

Single-point probabilities are forbidden.

The range must span at least 10 percentage points to prevent false precision in
this V1.

Example of accepted structure:

`55%–75%`

with explicit calibration/evidence lineage.

Example rejected:

`73%`

or an artificially narrow `71%–74%` range.

This contract does not claim that every evidence-backed range is objectively
correct; it only requires the estimate to disclose its method/calibration
lineage and avoid unsupported precision.

## Evidence conflicts

If two current confirmed sources disagree on a required claim, the Data &
Decision Fabric produces EVIDENCE_CONFLICT.

The Advisor then:

- marks confidence as CONFLICTED_EVIDENCE;
- withholds recommendation;
- remains BLOCKED until the conflict is resolved through evidence governance.

It never silently chooses the more convenient source.

## Missing evidence

If required evidence is missing, the assessment becomes:

`RESEARCH_REQUIRED`

The Advisor does not fill evidence gaps with intuition.

## Testing

If the underlying decision case requires a test and no test evidence exists,
the assessment becomes:

`TEST_REQUIRED`

## Memory boundary

Memory may provide context/evidence references, but memory cannot grant
authority.

This V1:

- writes no memory;
- promotes no memory automatically;
- writes no Checkpoint Mestre;
- converts no repeated statement into truth.

## Relationship to the owner stack

The current owner-facing safe stack is now:

1. Owner Experience V1
2. Cognitive Memory + Continuity V1
3. Secure Local Agent V1
4. Local Action Audit Receipt V1
5. Secure Desktop Runtime Blueprint V1
6. Voice + Hotword Runtime V1
7. Teaching + Meeting Orchestrator V1
8. Presentation Artifact + Control V1
9. Advisor + Decision Support V1

## Explicitly absent

This block does not:

- approve a recommendation;
- sign a contract;
- send email/WhatsApp;
- place an order;
- transfer money;
- change a trading position;
- execute a tool;
- call a provider;
- use network;
- write memory;
- activate Worker;
- deploy;
- modify frozen Core V1.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_ADVISOR_DECISION_SUPPORT_V1_CONTRACT_VALIDATED`

That validates advisory/risk/uncertainty semantics only.

It does not mean a recommendation has been approved or executed.
