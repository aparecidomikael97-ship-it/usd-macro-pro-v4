# AION Secure Local Agent V1

Status: IMPLEMENTATION SAFE / CONTRACT-ONLY  
Date: 2026-10-08  
Stacked base: AION Cognitive Memory + Continuity V1  
Production status: NOT INSTALLED / NOT DEPLOYED

## Objective

Define the security boundary for the future Windows desktop service that will
physically carry out owner commands such as:

- AION, abre o ChatGPT;
- AION, abre WhatsApp;
- AION, abre Spotify;
- AION, abre Spotify e toca sertanejo.

This V1 does **not** open applications. It prepares and validates the logical
request that a separately installed, signed local adapter may consume later.

## UX decision

A fresh owner voice/text command is itself the explicit action intent.

That avoids forcing a second confirmation for ordinary low-risk commands like
opening an allowlisted application. The command still cannot reach the future
physical adapter unless the trusted desktop host also attests the owner,
request binding and freshness.

Therefore:

1. the owner issues one explicit command;
2. Owner Experience classifies it;
3. Secure Local Agent V1 creates a bounded logical request;
4. trusted Windows host verification must attest the owner;
5. durable replay guard must claim a fresh single-use nonce;
6. only then can the future adapter consider the request dispatch-ready;
7. the adapter must reverify immediately before physical execution.

## Allowlist

V1 supports only three logical applications:

- ChatGPT;
- WhatsApp;
- Spotify.

The registry contains logical IDs and supported actions only.

It does not contain:

- executable paths;
- command lines;
- shell fragments;
- URLs/URIs;
- environment variables;
- credentials.

## Supported actions

V1 supports only:

- OPEN_APP;
- MEDIA_PLAYBACK, and only for Spotify.

MEDIA_PLAYBACK carries a bounded query such as `sertanejo` as data. It is not
converted into command-line arguments by this contract.

## Explicitly unsupported

V1 does not authorize:

- arbitrary applications;
- arbitrary executable paths;
- shell/PowerShell/CMD;
- file writes or deletes;
- software installation;
- system settings changes;
- credential access;
- sending WhatsApp messages;
- sending email;
- purchases or payments;
- browser autofill;
- trading orders;
- microphone capture;
- hotword listening.

Those capabilities require separate future contracts and risk review if they
are ever introduced.

## Command binding

The logical target selected by Owner Experience must also be explicitly present
in the original owner command.

The local boundary rejects:

- a planned ChatGPT target paired with a WhatsApp command;
- a command that names multiple allowlisted apps;
- shell chaining such as `&&` or `;`;
- PowerShell/CMD markers;
- HTTP/file URLs;
- other executable material.

This prevents the local layer from silently interpreting a broader command than
the owner actually issued.

## Freshness window

A local action request has a maximum validity window of 60 seconds.

The request binds:

- owner subject;
- HUMAN_OWNER binding digest;
- command ID;
- command-text digest;
- single-use nonce digest;
- desktop device ID;
- Windows platform;
- issue time;
- expiry time;
- logical app target;
- logical actions.

The raw command and raw nonce are not stored in the request envelope.

## Trusted host authorization

A positive dispatch-readiness decision requires a trusted host attestation with:

- verified=true;
- source=TRUSTED_OWNER_DESKTOP_HOST;
- an accepted owner verification mechanism;
- fresh_owner_command=true;
- generic_chat_acknowledgement=false;
- exact owner subject binding;
- exact owner binding digest;
- exact request digest;
- exact nonce digest;
- cryptographic_verification_performed=true.

Accepted mechanism labels in the V1 contract are:

- WINDOWS_HELLO;
- FIDO2;
- OWNER_SESSION_SIGNATURE.

The Python contract does not perform those cryptographic checks itself. The
future trusted Windows host is responsible for producing that attestation.

## Replay protection

Dispatch readiness also requires a separate replay-guard attestation proving:

- the request digest matches;
- the nonce digest matches;
- the nonce is fresh;
- the nonce has been claimed as single-use;
- durable replay rejection is active.

The V1 contract does not persist the nonce registry. That responsibility belongs
to the future installed desktop service.

## Meaning of DISPATCH_READY

`DISPATCH_READY` means only that the pure contract found the required evidence
structurally present and current.

It does **not** mean that this module:

- resolved an executable;
- generated a command;
- spawned a process;
- opened an application;
- called the network;
- performed an external action.

The physical adapter must reverify the request before any real OS operation.

## Relationship to previous blocks

Owner Experience V1 remains responsible for classifying the command and
requiring `SECURE_LOCAL_AGENT`.

Cognitive Memory + Continuity V1 remains responsible for safe cross-device
context and does not grant desktop execution authority.

This block adds the missing desktop security boundary without changing either
system.

## Frozen Core boundary

This implementation does not:

- modify the frozen Core V1;
- arm the Global Worker;
- write the Core checkpoint;
- activate AION Chat production persistence;
- deploy to Render;
- install a Windows service.

## Future physical implementation

The later PC-only implementation will need a separately reviewed signed local
service with at least:

- OS installation/package strategy;
- Windows code signing;
- protected local configuration;
- logical-app-to-installed-app resolution;
- durable nonce/replay registry;
- owner verification bridge;
- process-launch adapter;
- audit receipt;
- uninstall/rollback path;
- least-privilege service identity.

Those items are intentionally outside this phone-safe block.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_SECURE_LOCAL_AGENT_V1_CONTRACT_VALIDATED`

That means the security contract is validated. It does not mean a local agent
is installed or that any desktop application can already be opened by AION.
