# AION Vision, Presence & Presentation Contract V1

Status: DESIGN-ONLY / FAIL-CLOSED / NO CAMERA ACTIVATION

## Objective

Prepare AtlasQuant/AION for a future authorized webcam without changing the AION Core closure path.

The future experience must support:
- owner presence recognition on authorized devices;
- explicit visual understanding on request (for example, "AION, o que eu estou segurando?");
- an owner-controlled presentation mode for meetings and client demonstrations;
- privacy-preserving behavior with visible camera state and no hidden capture.

## Non-goals

This contract does NOT:
- activate any webcam;
- start background recording;
- enable facial recognition as a sole authentication factor;
- authorize login, financial actions, signatures, core freeze, or other sensitive actions from face or voice alone;
- upload frames to any provider;
- persist biometric templates;
- expose owner/customer/private data in demo mode.

## Capability states

A future implementation must expose explicit states only:
- CAMERA_UNAVAILABLE
- CAMERA_AVAILABLE_OFF
- CAMERA_ACTIVE_EXPLICIT
- OWNER_PRESENCE_UNVERIFIED
- OWNER_PRESENCE_MATCH_CANDIDATE
- VISION_REQUEST_READY
- PRESENTATION_MODE_READY
- PRESENTATION_MODE_ACTIVE
- BLOCKED

Ambiguous camera, identity, or model outcomes fail closed.

## Owner presence

1. Facial recognition is optional and must be enrolled explicitly by HUMAN_OWNER.
2. Face match is a convenience/presence signal, never sufficient by itself for sensitive authorization.
3. Sensitive operations continue to require the existing strong owner confirmation path.
4. Biometric material must remain local by default and must never be logged as raw images.
5. Device binding is required before owner-presence results can affect UX.

## Visual questions

A visual request is allowed only when:
- the camera is available;
- the user has explicitly enabled camera use for the current session or request;
- a visible camera-active indicator is shown;
- the request is scoped to the current visual task.

Example:
"AION, o que eu estou segurando?"

Expected behavior:
- capture/analyze the minimum necessary frame(s);
- answer with confidence calibrated to the evidence;
- say when the object cannot be identified reliably;
- do not infer sensitive identity attributes from appearance;
- do not continue recording after the request unless the user deliberately enables a continuous visual session.

## Presentation Mode

Presentation Mode is a distinct, owner-started state for meetings.

When active, AION may:
- introduce itself as an AI from Mikael's AtlasQuant/AION ecosystem;
- explain Trader, Negócios, Investimentos and AION;
- demonstrate approved synthetic scenarios;
- respond to questions from people present;
- use webcam/microphone only under the active session permissions.

Presentation Mode must:
- use the existing B2B Demo/Sandbox boundary;
- default to synthetic data;
- hide owner-private memory, credentials, production integrations and customer information;
- never claim to be human;
- display a clear visual state that demo mode is active;
- provide immediate owner stop/pause controls;
- never auto-contact, bill, write CRM, deploy, trade, sign, or execute sensitive actions.


## PowerPoint / live presentation orchestration

Presentation Mode must support a professional deck-driven meeting flow, including Microsoft PowerPoint-compatible presentations or an equivalent slide surface.

AION should be able to:
- open the approved presentation deck;
- advance, return to, or jump to a requested slide;
- narrate the presentation in natural language rather than merely reading slide text;
- show charts, images, dashboards, screenshots, reports and validation evidence;
- highlight the current metric, chart area, finding or validation being discussed;
- pause the deck when a participant asks a question;
- answer the question within the approved demo scope and then resume the presentation;
- switch between slides and approved live AtlasQuant demo screens when useful;
- present a short executive version or a detailed technical/commercial version depending on the meeting context;
- close with the approved next step, such as diagnostic, pilot or follow-up, without committing pricing, contracts, billing or sensitive actions on its own.

Deck content must be sourced only from an owner-approved presentation package. AION must not invent metrics, customer results, certifications, validations or live operational status. Any uncertain or unavailable data must be stated as unavailable rather than fabricated.

Presentation control is a low-risk navigation capability. Editing the deck, replacing approved evidence, changing commercial commitments, publishing externally, sending files or executing actions outside the meeting remains separately authorized.

This capability is intended to let HUMAN_OWNER participate naturally in the meeting while AION conducts the structured product/project presentation as the primary presenter.

## Voice + camera interaction

The future resident AION agent should support:
- wake-word / explicit invocation where the operating system permits;
- push-to-talk microphone button as a permanent fallback in the chat UI;
- camera button/state control as a separate permission surface;
- commands such as "abre o AtlasQuant", "abre a aba Trader", and presentation-mode navigation;
- voice/face presence only as low-risk UX signals, not authority escalation.

## Mobile/Desktop continuity

Desktop and mobile may share authenticated session/context, but each device keeps its own permission state for:
- microphone;
- camera;
- background presence;
- biometric enrollment.

No device may inherit camera/microphone permission merely because another device granted it.

## Security invariants

- no passive hidden surveillance;
- no face-only or voice-only privileged authorization;
- no implicit consent;
- no persistent recording by default;
- no production data in client demo mode;
- no authority granted by this contract;
- all sensitive actions remain fail-closed.

## Integration points

Future implementation should compose with:
- authenticated HUMAN_OWNER/session binding;
- AION resident desktop agent;
- AION chat UI microphone fallback;
- AtlasQuant navigation/deep links;
- B2B Demo/Sandbox;
- durable audit receipts for camera/presentation state transitions;
- strong owner confirmation for critical actions.

## Delivery sequence

1. UI microphone fallback and explicit camera controls.
2. Resident desktop agent and AtlasQuant open/navigation commands.
3. Webcam device adapter with explicit activation indicator.
4. Local owner-presence enrollment and verification candidate.
5. On-demand visual question pipeline.
6. Presentation Mode over synthetic Demo/Sandbox.
7. Mobile parity where Android/iOS permissions allow.

This sequence remains subordinate to completion of the official AION Core V1 closure.
