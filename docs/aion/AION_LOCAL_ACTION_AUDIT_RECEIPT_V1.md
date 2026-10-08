# AION Local Action Audit Receipt V1

Status: IMPLEMENTATION SAFE / CONTRACT-ONLY  
Date: 2026-10-08  
Stacked base: AION Secure Local Agent V1  
Production status: NOT INSTALLED / NOT DEPLOYED

## Objective

Define the immutable, fail-closed evidence receipt that a future signed Windows
local adapter must produce after exactly one local action attempt.

This block answers a critical question:

> After AION was allowed to try a desktop action, what can we truthfully prove
> happened?

The receipt contract does not launch applications. It only validates and binds
evidence supplied by a future trusted desktop adapter.

## Outcome model

The overall command outcome can only be one of:

- `CONFIRMED_SUCCESS`
- `CONFIRMED_PARTIAL`
- `CONFIRMED_TERMINAL_FAILURE`
- `OUTCOME_UNKNOWN`

The state is derived from the individual requested actions. A caller cannot
simply label the whole command as successful.

### Why CONFIRMED_PARTIAL exists

The Spotify owner command may contain two logical actions:

1. OPEN_APP
2. MEDIA_PLAYBACK

If Spotify opens but playback is terminally rejected, the truthful result is
`CONFIRMED_PARTIAL`, not full success and not full failure.

This prevents AION from overstating what happened.

## Per-action outcomes

Each requested action can only be:

- `CONFIRMED_SUCCESS`
- `CONFIRMED_TERMINAL_FAILURE`
- `OUTCOME_UNKNOWN`

Every per-action result must bind:

- action name;
- logical app ID;
- exact parameters digest;
- outcome state;
- evidence kind;
- evidence digest;
- positive postcondition flag;
- terminal-failure evidence flag;
- ambiguity trigger when applicable.

The exact parameters digest prevents evidence for one media request from being
reused for another. For example, `sertanejo` and `rock` produce different
bindings.

## Success

Success requires positive postcondition evidence.

Examples of future acceptable evidence categories include:

- OS application activation confirmation;
- media-session confirmation;
- signed adapter observation.

Absence of an error is not success.

## Terminal failure

Terminal failure requires authoritative failure evidence.

Examples include:

- OS launch terminal error;
- media-session terminal error.

Absence of a response is not terminal failure.

## OUTCOME_UNKNOWN

Ambiguity always becomes `OUTCOME_UNKNOWN`.

Supported ambiguity triggers include:

- adapter crash after dispatch;
- IPC loss after dispatch;
- missing OS acknowledgement;
- postcondition not observed;
- observation timeout;
- machine sleep/shutdown;
- conflicting OS observations;
- ambiguous media-session state;
- incomplete evidence.

An `OUTCOME_UNKNOWN` receipt:

- cannot claim physical success;
- cannot claim terminal failure;
- cannot automatically retry;
- cannot automatically reconcile;
- requires a separate reconciliation record;
- requires a fresh owner command and a new nonce for any new attempt.

This protects against duplicate effects. If an app may already have opened,
AION must not silently open it again just because the acknowledgement was lost.

## Adapter identity

A valid future observation must come from:

`SIGNED_LOCAL_ADAPTER`

and must bind:

- verified observation;
- verified adapter signature;
- adapter instance ID;
- adapter binary SHA-256 digest;
- request digest;
- dispatch-readiness digest;
- logical action-set digest;
- attempt ID;
- attempt start time;
- optional completion time;
- evidence-bundle SHA-256 digest.

The receipt builder does not perform the adapter signature verification itself.
The future trusted local runtime must provide the verified attestation.

## Exact dispatch binding

The adapter observation must bind the exact non-executing
`DISPATCH_READY` decision from Secure Local Agent V1.

Changing the request, target, actions or media parameters changes the digest and
invalidates the observation.

## Time rules

The physical attempt must start while the original local action request is
still current.

A terminal success/failure/partial outcome requires an attempt completion time.

An unknown outcome may have no completion time, which correctly models adapter
crash or lost IPC after dispatch.

## Audit receipt

A valid receipt contains a deterministic SHA-256 digest and receipt ID.

The digest binds:

- request digest;
- dispatch-readiness digest;
- action-set digest;
- attempt identity;
- adapter identity/binary digest;
- evidence-bundle digest;
- timestamps;
- per-action outcomes;
- ambiguity triggers;
- safety flags.

Changing bound evidence changes the receipt digest.

## Forbidden receipt material

The receipt and adapter observation reject raw or executable material such as:

- executable paths;
- binaries;
- command lines;
- argv/args;
- shell/PowerShell material;
- environment variables;
- stdout/stderr/raw process output;
- URLs/URIs;
- credentials, tokens, cookies or API keys;
- private keys;
- database credentials.

Only bounded logical identifiers and evidence digests belong in the audit
receipt.

## Important semantic distinction

A receipt may confirm that the **future adapter** produced an observable
physical effect.

That does not mean this Python contract executed the action.

The receipt always keeps:

- `receipt_builder_executed_action=false`
- `external_action_executed_by_this_module=false`
- `executes_action=false`

## Persistence and signatures

V1 does not:

- persist the receipt;
- sign the receipt;
- write the Checkpoint Mestre;
- write a database;
- call a network service.

A future desktop implementation may persist and sign receipts only through a
separately reviewed contract.

## Relationship to Secure Local Agent V1

Secure Local Agent V1 answers:

> Is this owner request structurally ready to be considered by the physical
> desktop adapter?

Local Action Audit Receipt V1 answers:

> After one physical attempt, what outcome is supported by evidence?

Neither contract physically launches an application.

## Explicitly absent

This version does not:

- install a Windows service;
- resolve application executable paths;
- spawn a process;
- open ChatGPT, WhatsApp or Spotify;
- control Spotify;
- retry unknown actions;
- reconcile unknown outcomes;
- persist receipts;
- sign receipts;
- start microphone capture;
- run a hotword listener;
- arm the Global Worker;
- deploy to Render;
- modify frozen Core V1.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_LOCAL_ACTION_AUDIT_RECEIPT_V1_CONTRACT_VALIDATED`

That state validates the outcome/audit semantics only. It does not mean a
desktop adapter is installed or any physical application launch has occurred.
