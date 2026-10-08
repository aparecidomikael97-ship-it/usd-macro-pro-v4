# AION Windows Build Token + Prelaunch Revalidation Contract V1

Status: IMPLEMENTATION SAFE / DESIGN-ONLY FINAL PRE-SPAWN BARRIER  
Date: 2026-10-08  
Prelaunch verifier implemented: NO  
Build token implemented: NO  
Build token issued: NO  
Build authorized: NO  
Build started: NO

## Objective

Define the final logical objects immediately before a future Windows build
process may exist:

1. a fresh prelaunch revalidation snapshot;
2. an unissued single-use build-token template;
3. the future token issuance/persistence evidence shape.

This layer is stacked on #1052.

It does not issue a usable token and does not spawn python.exe.

## Fresh prelaunch snapshot

Immediately before any future launch, the Windows implementation must recheck
the complete build state rather than relying on an earlier green result.

The prelaunch snapshot may be at most 10 seconds old.

It must revalidate:

- trusted physical certificate;
- all 12 physical sandbox requirements;
- verifier receipt signature;
- verifier receipt persistence;
- receipt reopen;
- evidence-chain reopen;
- HUMAN_OWNER signature;
- owner authorization persistence;
- owner authorization reopen;
- owner authorization freshness;
- owner authorization still unconsumed;
- persistent nonce replay guard;
- nonce single-use;
- same host;
- same package manifest;
- same reproducible build recipe;
- same offline input promotion;
- same sandbox preflight;
- exact pinned Python binary;
- exact build script;
- exact scrubbed environment;
- exact process allowlist;
- network-deny state;
- safety-stop state;
- circuit-breaker state;
- absence of new safety blockers.

## Exact binding

The snapshot must exactly match the #1052 gate for:

- gate contract;
- build recipe;
- offline inputs;
- sandbox preflight;
- package manifest;
- package-attestation policy;
- owner binding;
- evidence-store contract;
- receipt-persistence contract;
- launch binary path digest;
- launch binary SHA-256;
- build-script SHA-256;
- safety-stop policy;
- circuit-breaker policy;
- prelaunch safety policy.

Any drift blocks.

## Safety stop and circuit breaker

The future host must prove:

- safety stop is armed;
- safety stop is not engaged;
- circuit breaker is armed;
- circuit breaker is healthy.

This V1 validates only the shape of those observations.

It does not trust them as physical truth.

## Truth boundary

Even a complete future snapshot can reach only:

`PRELAUNCH_SNAPSHOT_SHAPE_VALID_BUT_EXTERNAL_TRUST_REQUIRED`

It still reports:

- external_trust_verified_by_this_module=false
- physical_revalidation_trusted=false
- authorization_persistence_trusted=false
- nonce_state_trusted=false
- safety_stop_state_trusted=false
- circuit_breaker_state_trusted=false
- build_token_issuance_allowed=false
- build_authorized=false

A caller cannot create launch authority by setting a boolean.

## Build-token template

The build token is intended to be:

- single-use;
- audience-limited to the offline Windows build sandbox;
- tied to one exact prelaunch snapshot;
- tied to one exact owner authorization;
- tied to one exact host;
- tied to one exact recipe/input/package state;
- tied to one exact Python binary and build script.

Maximum lifetime:

`15 seconds`

Maximum uses:

`1`

Maximum process count:

`1`

Maximum child process count:

`0`

## Token template is not a token

The positive design state is:

`BUILD_TOKEN_TEMPLATE_READY_UNISSUED`

It still reports:

- token_implemented=false
- token_issued=false
- token_signed=false
- token_persisted=false
- token_consumed=false
- owner_authorization_consumed=false
- launch_authorized=false
- build_authorized=false
- build_started=false

## Atomic consumption

The future physical launcher must atomically consume both:

1. the persisted HUMAN_OWNER build authorization;
2. the single-use build token;

with the actual process launch.

If the atomic transition cannot be proven, the process must not start.

No authorization/token may remain reusable after a successful launch.

## Final pre-spawn revalidation

Even after future token issuance, the launcher must perform one final
pre-spawn revalidation.

The process may not be spawned if any of the following changed:

- token expired;
- host changed;
- package/recipe/input changed;
- sandbox changed;
- physical certificate/receipt/evidence chain changed;
- owner authorization expired or was consumed;
- nonce state changed;
- pinned Python/build script changed;
- network deny changed;
- safety stop became engaged;
- circuit breaker became unhealthy;
- a new safety blocker appeared.

## Future token persistence

The future token issuance evidence must include:

- token digest;
- token-signature digest;
- token-signer manifest digest;
- token record digest;
- token nonce record digest;
- write receipt;
- CAS observation;
- read-after-write observation;
- reopen observation.

The maximum shape-only state is:

`BUILD_TOKEN_ISSUANCE_ATTESTATION_SHAPE_VALID_BUT_UNTRUSTED`

It still has:

- token_signature_verified=false
- token_persisted_trusted=false
- token_nonce_single_use_verified=false
- cas_verified=false
- read_after_write_verified=false
- reopen_verified=false
- final_pre_spawn_revalidation_verified=false
- launch_authorized=false

## No self-attestation

`caller_claims_token_trusted=true`

is explicitly blocked.

A document containing a signature digest is not itself proof that the signature
was verified.

## Generic chat remains non-authoritative

This layer preserves:

`generic_chat_is_launch_authority=false`

The current conversation instruction "Vamos lá" therefore continues to mean
safe design/PR work only.

It cannot issue or consume a build token.

## Maximum current state

The maximum current state is:

`READY_FOR_WINDOWS_BUILD_TOKEN_PRELAUNCH_IMPLEMENTATION`

The next PC-side phase may implement, using synthetic/non-production data first:

- prelaunch verifier;
- token signer;
- token persistence writer;
- atomic launch consumer;
- final pre-spawn verifier.

## Explicitly absent

This V1 does not:

- trust a physical prelaunch snapshot;
- issue/sign/persist/consume a build token;
- consume owner authorization;
- authorize launch;
- spawn python.exe;
- run the build script;
- build/install a package;
- write SQLite/files;
- modify ACL/Registry;
- call GitHub/network;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_BUILD_TOKEN_PRELAUNCH_REVALIDATION_V1_VALIDATED`

No production build authorization or process launch is implied.
