# AION Presentation Artifact + Control Contract V1

Status: IMPLEMENTATION SAFE / CONTRACT ONLY  
Date: 2026-10-08  
Stacked base: Teaching + Meeting Orchestrator V1  
PPTX created: NO  
PowerPoint opened: NO  
Presentation started: NO  
Production status: NOT DEPLOYED

## Objective

Define the safe boundary between an evidence-valid AION meeting deck and a
future PPTX generator / Microsoft PowerPoint presenter.

The Teaching + Meeting Orchestrator remains the single source of truth for:

- meeting state;
- current slide;
- return slide after Q&A;
- demo state.

This contract must not create a second presentation state machine that can drift
away from AION.

## Presentation artifact request

A READY artifact request binds:

- meeting deck digest;
- artifact ID;
- output format PPTX;
- target application Microsoft PowerPoint;
- AtlasQuant presentation theme;
- 16:9 aspect ratio;
- ordered slide IDs;
- speaker-notes policy;
- chart source manifests;
- chart data lineage;
- chart validation lineage;
- metric evidence lineage;
- request digest.

The request does not produce a file.

## Chart provenance

For every CHART slide, the request carries a deterministic chart-source digest
binding:

- slide ID/order;
- data references;
- validation references;
- evidence references.

This preserves the requirement that generated charts cannot silently use data
different from the data approved by the meeting deck.

## Unsafe PowerPoint features forbidden in V1

The generation request explicitly forbids:

- macros;
- VBA projects;
- external links;
- external relationships;
- embedded OLE objects;
- remote fetches during presentation;
- credentials;
- real customer data.

These restrictions keep the first presentation artifact path deterministic and
auditable.

## Future generated artifact attestation

A future PPTX generator must return independently verified evidence before AION
may prepare any PowerPoint control intent.

Required evidence includes:

- exact generation-request digest;
- artifact SHA-256 digest;
- logical artifact reference;
- PPTX format;
- exact slide count;
- verified slide order;
- verified chart lineage;
- verified metric evidence;
- speaker-notes policy verification when requested;
- absence of forbidden macros/VBA/links/OLE/remote fetch;
- absence of credentials and real customer data.

A valid attestation proves only that an artifact has passed the expected
verification boundary.

This module itself reports:

- artifact_generated_by_this_module=false
- artifact_opened_by_this_module=false
- powerpoint_started_by_this_module=false
- external_action_executed_by_this_module=false

## Presentation control intents

Supported logical control actions are:

- OPEN_ARTIFACT
- START_PRESENTATION
- SYNC_TO_MEETING_SLIDE
- END_PRESENTATION

A control intent binds:

- artifact digest/reference;
- deck digest;
- meeting-session digest;
- meeting state;
- exact current slide ID/index;
- control-intent digest.

It does not send keyboard or mouse events and does not open PowerPoint.

## Q&A / exact resume behavior

When the meeting enters PAUSED_FOR_QA, the meeting orchestrator keeps the exact
slide binding.

The presentation layer may produce a SYNC_TO_MEETING_SLIDE intent for that same
slide.

After ANSWERED -> RESUME, the meeting orchestrator validates and restores the
same slide.

Only then does the presentation layer produce a new sync intent.

Therefore the PowerPoint layer never guesses where to resume.

## Source-of-truth rule

The presentation adapter must never independently advance or rewind the
business meeting state.

It can only mirror a validated meeting session.

This rule prevents scenarios such as:

- PowerPoint at slide 7 while AION thinks slide 6 is active;
- a question returning to the wrong slide;
- physical slide changes silently changing AION context.

## Future physical adapter

Physical PowerPoint control belongs to the future secure desktop runtime.

That adapter will have to re-verify:

- artifact attestation;
- control-intent digest;
- owner/session security;
- local allowlist;
- exact meeting/session binding.

Only after those checks may it open PowerPoint or change slides.

## Explicitly absent

This block does not:

- create PPT/PPTX;
- write a presentation file;
- render charts;
- open Microsoft PowerPoint;
- start slideshow mode;
- change a physical slide;
- send keyboard events;
- send mouse events;
- call subprocess/shell;
- fetch remote content;
- call AI providers;
- use customer credentials/data;
- activate Worker;
- deploy;
- write the frozen Core checkpoint.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_PRESENTATION_ARTIFACT_CONTROL_V1_CONTRACT_VALIDATED`

That validates artifact/request/attestation/control semantics only. No physical
PowerPoint file or presentation has been produced or opened.
