# AION Teaching + Meeting Orchestrator V1

Status: IMPLEMENTATION SAFE / ORCHESTRATION CONTRACT ONLY  
Date: 2026-10-08  
Stacked base: AION Voice + Hotword Runtime V1  
PowerPoint status: NOT CREATED  
Presentation status: NOT STARTED  
Demo status: NOT EXECUTED  
Production status: NOT DEPLOYED

## Objective

Turn the Owner Experience foundation for TEACHING and MEETING into a deterministic
orchestrator with explicit state, slide position, Q&A pause/resume, exercise
tracking, evidence-bound meeting decks and sandbox-only demo planning.

This block is intentionally non-rendering and non-executing.

It does not generate presentation files, run a slideshow, call a model,
evaluate student answers itself, start a demo, open a browser, or write memory.

## Reuse instead of duplication

Owner Experience V1 already defines:

- TEACHING mode;
- MEETING mode;
- teaching voice style;
- slides/drawings/exercises flags;
- meeting pause-for-question behavior;
- meeting transition semantics.

This orchestrator reuses those contracts rather than creating a competing mode
system.

## Teaching program

A teaching program binds:

- topic;
- learner level;
- learning objectives;
- optional learner-profile reference;
- ordered slide manifest;
- exercise manifest;
- program digest.

Supported levels:

- BEGINNER
- INTERMEDIATE
- ADVANCED

Supported teaching slide kinds:

- TITLE
- OBJECTIVES
- CONCEPT
- DIAGRAM
- EXAMPLE
- WORKED_EXAMPLE
- EXERCISE
- RECAP

The orchestrator stores references/manifests, not rendered slide bodies.

## Teaching session state

Supported states:

- TEACHING
- PAUSED_FOR_QA
- RESUME_PENDING
- EXERCISE
- FEEDBACK
- COMPLETED

### Question handling

When the learner interrupts with a question:

1. current slide ID/index are frozen as the return location;
2. the question is represented by a digest;
3. state becomes PAUSED_FOR_QA;
4. after the answer, state becomes RESUME_PENDING;
5. RESUME verifies the frozen slide binding;
6. the session returns to the exact same slide.

The raw question is not persisted by this contract.

## Exercises

Exercises are explicitly bound to a teaching slide.

A submitted answer is represented by a digest only.

Moving to FEEDBACK requires an externally supplied, verified evaluation record
with:

- matching exercise ID;
- evaluation digest;
- verified=true.

This orchestrator does not grade the answer itself and does not call a model.

## Adaptive teaching

The existing TEACHING mode exposes adaptive depth.

V1 records the selected level and learner-profile reference but does not
silently rewrite long-term memory or promote a learner profile.

Future adaptation can use verified learning evidence while remaining governed
by the existing cognitive-memory layer.

## Meeting deck

A meeting deck binds:

- sector;
- audience;
- objective;
- optional client reference;
- ordered slide manifest;
- deck digest.

Supported meeting slide kinds include:

- TITLE
- AGENDA
- CONTEXT
- PROBLEM
- SOLUTION
- ARCHITECTURE
- CHART
- ROI
- CASE
- DEMO
- ROADMAP
- Q_AND_A
- NEXT_STEPS

## Evidence-bound metrics and charts

The meeting orchestrator does not permit evidence-free metric slides.

CHART, ROI and CASE slides require evidence references.

CHART slides additionally require:

- data references;
- validation references.

This is the contract boundary intended to prevent invented charts or fabricated
business metrics from reaching a client presentation.

V1 does not render the chart. It only verifies that the slide manifest carries
the required evidence lineage.

## Meeting Q&A

The meeting session reuses the Owner Experience meeting state machine.

When a question interrupts a presentation:

1. current slide ID/index are frozen;
2. question is represented by a digest;
3. meeting enters PAUSED_FOR_QA;
4. ANSWERED moves to RESUME_PENDING;
5. RESUME verifies the frozen slide;
6. presentation returns to the exact same slide.

No "approximately where we were" behavior is accepted.

## Live demo boundary

A meeting can include a DEMO slide, but V1 only permits a demo plan for:

`SYNTHETIC_SANDBOX`

The demo gate requires:

- demo script reference;
- sandbox digest;
- verified sandbox attestation;
- no production tenant access;
- no real customer data;
- no credentials;
- no external side effects;
- no payments;
- no trading;
- no publication;
- no message sending.

If any forbidden capability is enabled, the demo plan is BLOCKED.

Even a READY demo plan reports:

- physical_demo_started=false
- network_called=false
- external_action_executed=false
- executes_action=false

The meeting state can move to DEMO_ACTIVE only as an orchestration state.
That must never be interpreted as proof that a physical demo is running.

## PowerPoint boundary

This V1 does not create or present PowerPoint.

The meeting deck deliberately reports:

- powerpoint_created=false
- presentation_started=false
- charts_rendered=false

A future PowerPoint adapter can consume an evidence-valid deck only after its
own generation/rendering/export tests exist.

## Cross-device continuity

The orchestrator exposes a safe handoff context containing only:

- mode;
- session/meeting ID;
- session state;
- program/deck digest;
- session digest;
- current slide ID/index;
- return slide ID/index.

It transfers no:

- raw question;
- raw answer;
- raw slide content;
- authentication;
- owner authority.

Target-device reauthentication remains mandatory.

## Memory boundary

This V1:

- creates no second memory database;
- promotes no memory automatically;
- writes no Checkpoint Mestre;
- persists no raw learning answer;
- persists no raw question.

Later integration with Cognitive Memory + Continuity should carry only governed
digests/state and explicitly approved learning records.

## Relationship to previous owner stack

The mobile-safe chain now becomes:

1. Owner Experience V1
2. Cognitive Memory + Continuity V1
3. Secure Local Agent V1
4. Local Action Audit Receipt V1
5. Secure Desktop Runtime Blueprint V1
6. Voice + Hotword Runtime V1
7. Teaching + Meeting Orchestrator V1

## Explicitly absent

This block does not:

- create PPT/PPTX files;
- render slides;
- render charts;
- start presentation mode;
- open PowerPoint;
- open a browser;
- run a demo;
- connect to production tenants;
- use real customer data;
- send WhatsApp/email;
- make a payment;
- execute a trade;
- record microphone/camera;
- call AI providers;
- write memory;
- activate Worker;
- deploy;
- alter frozen Core V1.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_TEACHING_MEETING_ORCHESTRATOR_V1_CONTRACT_VALIDATED`

That validates orchestration semantics only. It does not mean a lesson,
PowerPoint presentation or live demo has physically run.
