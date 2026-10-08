# AION Voice + Hotword Runtime V1

Status: IMPLEMENTATION SAFE / RUNTIME CONTRACT ONLY  
Date: 2026-10-08  
Stacked base: AION Secure Desktop Runtime Blueprint V1  
Physical microphone status: NOT OPENED  
Hotword listener status: NOT STARTED  
Production status: NOT DEPLOYED

## Objective

Define the owner voice interaction contract before any real microphone or
wake-word runtime is activated.

The goal is the owner experience:

- say **"AION"** while AtlasQuant is active;
- AION detects the wake word;
- captures one owner command;
- routes that command safely;
- keeps text available as fallback;
- later, when approved runtime support exists, responds with the official AION
  neural voice.

This PR does not turn any of those physical capabilities on.

## Critical security rule

**"AION" is an activation phrase, not authentication.**

Wake-word detection:

- does not prove HUMAN_OWNER identity;
- does not grant privileges;
- does not approve an external application launch;
- does not approve payments, trading, file deletion or software installation;
- does not replace Windows Hello/FIDO2/owner-session verification.

Voice commands remain downstream of the same owner binding and Secure Local
Agent controls defined in the previous blocks.

## Activation modes

V1 defines two activation channels.

### HOTWORD

The phrase must begin with the exact normalized token:

`AION`

Examples:

- `AION, abre o ChatGPT` -> activation detected
- `AION, abre a aba Trader` -> activation detected
- `abre o AION agora` -> ignored as wake activation
- `AIONIC abre o ChatGPT` -> ignored

Fuzzy wake-word activation is intentionally disabled in V1. False-positive
reduction is preferred over aggressive matching.

### PUSH_TO_TALK

The microphone button can activate one command capture without requiring the
wake word.

Push-to-talk still requires:

- active AtlasQuant app/site;
- microphone permission;
- explicit user gesture;
- owner security boundary after speech recognition.

## Runtime states

The machine-readable state model includes:

- DISARMED
- ARMED
- LISTENING_FOR_WAKE_WORD
- CAPTURING_COMMAND
- COMMAND_READY
- RESPONDING
- PAUSED_PRIVACY
- SUSPENDED_APP_INACTIVE
- BLOCKED_PERMISSION
- ERROR

The pure state machine does not open the microphone itself.

## Privacy controls

V1 requires:

- explicit microphone permission;
- visible microphone/privacy indicator;
- one-tap privacy pause;
- app-active requirement for hotword listening;
- no raw audio persistence;
- no raw transcript persistence;
- ephemeral audio processing only;
- text fallback;
- no generic device TTS fallback.

Revoking microphone permission transitions the runtime to:

`BLOCKED_PERMISSION`

Making the app inactive transitions active voice states to:

`SUSPENDED_APP_INACTIVE`

Privacy pause transitions active voice states to:

`PAUSED_PRIVACY`

## Background / "24h" semantics

The desired owner experience is to be able to call AION continuously while the
authorized AtlasQuant experience is active.

V1 deliberately does **not** claim unrestricted OS-level background listening.

The contract exposes:

- `app_active_required_for_hotword_v1=true`
- `background_listening_supported_v1=false`

This avoids pretending that Android/browser/Windows background microphone
restrictions have already been solved.

A later physical host implementation can extend this only after OS-specific
permission, battery, privacy and lifecycle behavior is verified.

## Command routing

Recognized text is routed through the existing Owner Experience V1 command
planner.

Examples:

### Local application

`AION, abre o ChatGPT`

Routes to:

- kind: LOCAL_APPLICATION
- target: chatgpt
- adapter: SECURE_LOCAL_AGENT

The voice layer still reports:

- physical_execution=false
- external_action_executed=false

The Secure Local Agent must independently perform owner verification, replay
protection and local action checks.

### AtlasQuant navigation

`AION, abre a aba Trader`

Routes to:

- kind: ATLASQUANT_NAVIGATION
- target: trader
- adapter: TRUSTED_HOST_NAVIGATION

The voice contract still does not navigate the interface.

### Conversation

`AION, me explique inflação`

Routes to:

- kind: AION_CONVERSATION
- target: aion
- adapter: AION_CHAT_RUNTIME

No external action authority is created.

## Transcript privacy

The runtime consumes recognized text as ephemeral input but does not return or
persist the raw transcript.

Instead, routing output carries a deterministic transcript digest.

The command envelope binds:

- voice session ID;
- activation ID;
- timestamp;
- source device;
- owner binding digest;
- activation mode;
- transcript digest;
- route kind;
- target;
- required adapter.

This allows evidence/audit correlation without requiring raw voice transcript
persistence.

## Sensitive speech

Credential-like speech is blocked from the normal voice command route.

Examples include phrases containing:

- password/senha;
- tokens;
- API keys;
- private keys;
- JWT/cookies;
- card/CVV material.

The purpose is to avoid accidentally treating spoken credentials as ordinary
commands.

## High-risk actions

Voice phrases that appear to request actions such as:

- payments/Pix;
- transfers;
- trading/order execution;
- destructive file operations;
- software install/uninstall

are blocked from this low-risk voice runtime and require a separate,
higher-assurance authorization ceremony.

No such ceremony is implemented by this PR.

## Response output

The runtime preserves a text-first safety fallback.

Neural audio is only **eligible** when:

- a voice session is active;
- the fixed official AION voice profile is ready;
- TTS readiness is true;
- the user has initiated/requested audio interaction.

Even when eligible, this contract reports:

- provider_called=false
- audio_generated=false
- audio_playback_started=false

The host/provider layer must do the real work later.

## Official voice profile

This runtime uses the existing fixed AION/AtlasQuant neural voice profile
identity.

Generic browser/device speech fallback remains forbidden for this owner runtime.

There is older contextual voice-assistant code in the repository that can
render browser speech in a separate legacy/presentation surface. This V1 does
not activate or expand that behavior. A future reconciliation block should
remove ambiguity between that legacy surface and the fixed official voice
policy before full product rollout.

## Cross-device continuity

Voice continuity may transfer only safe metadata:

- session ID;
- source/target device;
- last route digest;
- runtime state;
- handoff digest.

It does not transfer:

- raw audio;
- raw transcript;
- microphone state;
- authentication;
- owner authority.

The target device must:

- reauthenticate;
- request/verify its own microphone permission;
- start its own local listener when physically implemented.

## Relationship to desktop runtime

The intended chain is now:

1. Owner Experience V1
2. Cognitive Memory + Continuity V1
3. Secure Local Agent V1
4. Local Action Audit Receipt V1
5. Secure Desktop Runtime Blueprint V1
6. Voice + Hotword Runtime V1

The physical Windows runtime from step 5 will later host the desktop microphone,
wake-word, local owner verification and application adapter boundaries.

## Explicitly absent

This block does not:

- request microphone permission from the OS/browser;
- open a microphone;
- record audio;
- store audio;
- start continuous recognition;
- run an ASR model;
- call an ASR provider;
- start a wake-word listener;
- invoke Windows Hello/FIDO2;
- generate neural audio;
- call a TTS provider;
- play audio;
- open ChatGPT;
- open WhatsApp;
- open Spotify;
- navigate AtlasQuant;
- execute payments;
- execute trades;
- delete files;
- install software;
- run a background worker;
- deploy;
- write the frozen Core checkpoint.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_VOICE_HOTWORD_RUNTIME_V1_CONTRACT_VALIDATED`

That state validates the voice/hotword state, privacy and routing contract only.

It does **not** mean the microphone or hotword runtime is physically active.
