# AION Owner Experience V1

Status: IMPLEMENTATION SAFE / CONTRACT-ONLY  
Date: 2026-10-08  
Base: main after AION Chat PostgreSQL Persistence V1  
Production status: NOT DEPLOYED

## Objective

Define the owner-facing behavior that sits above the frozen AION Core without
changing Core V1 or granting new execution authority.

The target experience is:

- HUMAN_OWNER is already authenticated by the trusted AtlasQuant host;
- AION can prepare the contextual greeting immediately after login;
- desktop and mobile can share conversation context without transferring login
  credentials;
- commands such as opening Trader, AtlasQuant, ChatGPT, WhatsApp and Spotify
  are classified and planned;
- physical application launch remains delegated to a future secure local agent;
- microphone/hotword readiness is explicit and permission-bound;
- Teaching Mode and Meeting Mode have explicit state contracts;
- Meeting Mode can pause for questions and resume the prior slide.

## Trust boundary

The owner identity is never inferred by this module.

A trusted host must inject an owner assertion containing:

- verified=true;
- principal=HUMAN_OWNER;
- subject matching the authenticated ADMIN username;
- issuer identifying the trusted assertion source.

The authenticated session must already contain:

- ADMIN role;
- app:read;
- aion:admin;
- credential fingerprint.

Failure of any requirement blocks the owner binding.

## Greeting

Once owner binding is valid, AION may prepare:

> Mikael, bom dia/tarde/noite. AION ativo. Bem-vindo ao AtlasQuant.
> O que você gostaria de saber ou fazer?

The contract only prepares the utterance. It does not invoke TTS by itself.

## Voice and hotword

The contract models the hotword "AION" but never opens the microphone.

Hotword readiness requires:

- microphone permission;
- continuous-recognition capability;
- hotword runtime capability;
- app active;
- supported device.

A real listener must be added later in a dedicated device adapter.

## Owner commands

Internal AtlasQuant commands map to trusted host navigation:

- AION, abre Trader;
- AION, abre Negócios;
- AION, abre Investimentos;
- AION, abre AION;
- AION, entra no AtlasQuant.

External application commands map to a future secure local agent:

- AION, abre o ChatGPT;
- AION, abre WhatsApp;
- AION, abre Spotify e toca sertanejo.

This contract never launches applications.

External-app plans require explicit approval and report whether the current
device is supported by the planned desktop adapter.

## Teaching Mode

Teaching Mode declares:

- calm and patient voice style;
- slides;
- drawings;
- exercises;
- adaptive depth.

It does not call a model/provider or create media by itself.

## Meeting Mode

Meeting Mode declares:

- slides;
- sector adaptation;
- live-demo capability contract;
- pause for questions;
- resume to the prior slide.

State machine:

IDLE -> PRESENTING -> PAUSED_FOR_QA -> RESUME_PENDING -> PRESENTING

STOP may safely return active states to IDLE.

Invalid transitions fail closed.

## PC/mobile continuity

Cross-device handoff carries only safe conversation context:

- owner subject;
- conversation id;
- last turn id;
- interaction mode;
- bounded non-secret context.

It explicitly does not transfer authentication or session credentials.

The target device must authenticate independently before consuming the handoff.

## Explicitly absent

This version does not:

- change the frozen Core V1;
- deploy anything;
- activate AION Chat production persistence;
- arm the Global Worker;
- start microphone capture;
- run a hotword listener;
- launch desktop applications;
- navigate a browser;
- call external providers;
- transfer authentication between devices;
- grant HUMAN_OWNER authority from an untrusted input.

Maximum truthful state after green CI:

AION_OWNER_EXPERIENCE_V1_CONTRACT_VALIDATED
