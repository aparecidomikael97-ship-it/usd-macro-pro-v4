# AION Physical Verification -> Build Authorization Gate V1

Status: IMPLEMENTATION SAFE / DESIGN-ONLY FINAL BUILD BARRIER  
Date: 2026-10-08  
Physical certificate trusted: NO  
Owner build authorization persisted: NO  
Build token issued: NO  
Build authorized: NO  
Build started: NO

## Objective

Define the final barrier between a physically verified Windows sandbox and the
first future production build of the AION Windows local agent.

This layer is stacked on #1051.

It deliberately separates:

1. physical sandbox verification;
2. signed verification receipt;
3. receipt persistence/reopen proof;
4. fresh HUMAN_OWNER build intent;
5. owner authorization persistence/non-replay proof;
6. prelaunch revalidation;
7. future launch-token issuance.

This PR does not cross that barrier.

## Generic chat is not build authorization

A normal chat instruction such as:

`Vamos lá`

is not build authorization.

The policy explicitly keeps:

`generic_chat_is_build_authorization=false`

and:

`chat_acknowledgement_is_authorization=false`

The owner build ceremony is a separate cryptographic operation.

## Physical side of the gate

Before an owner signature request can have meaningful authority, the future
physical certificate must bind and prove all of the following:

- 12/12 physical requirements verified;
- independent verifier receipt signed;
- verifier receipt signature verified;
- verification receipt persisted;
- receipt persistence CAS verified;
- receipt read-after-write verified;
- receipt reopen verified;
- evidence-chain reopen verified;
- certificate freshness;
- same host binding;
- same sandbox-preflight binding;
- same reproducible build recipe;
- same offline input promotion;
- same collector manifest;
- same verifier manifest;
- zero unresolved verification blockers.

## Exact build scope

The build gate contract also binds:

- reproducible-build recipe digest;
- offline-input promotion digest;
- sandbox-preflight digest;
- package-manifest digest;
- package-attestation policy digest;
- owner-binding digest;
- #1051 evidence-store contract digest;
- #1051 receipt-persistence contract digest.

A later build authorization is therefore not a generic permission to "build
something".

It is tied to one exact proposed build state.

## Physical certificate freshness

A future physical-verification certificate may be at most 60 seconds old when
used at this gate.

The current module only validates the future certificate's shape.

Therefore the maximum current physical-certificate result is:

`PHYSICAL_CERTIFICATE_SHAPE_VALID_BUT_EXTERNAL_TRUST_REQUIRED`

That is not a physical-proof verdict.

## HUMAN_OWNER ceremony

The owner ceremony purpose is:

`HUMAN_OWNER_EXPLICIT_WINDOWS_LOCAL_AGENT_FIRST_PRODUCTION_BUILD`

Mechanism:

`ED25519_EXTERNAL_OWNER_EXECUTION_KEY`

Allowed decisions:

- AUTHORIZE_WINDOWS_LOCAL_AGENT_BUILD
- DENY_WINDOWS_LOCAL_AGENT_BUILD

The maximum authorization window is 120 seconds.

## Owner request bindings

The signed request binds:

- gate-contract digest;
- physical-certificate digest;
- verification-receipt digest;
- receipt-persistence attestation digest;
- evidence-chain digest;
- reproducible-build recipe;
- offline input promotion;
- sandbox preflight;
- package manifest;
- package-attestation policy;
- owner binding;
- owner public-key fingerprint;
- fresh nonce;
- issued/expires timestamps;
- exact decision.

Changing any bound field after signing breaks the request digest/signature.

## Real Ed25519 verification

This contract performs public-key verification of the owner signature over:

`OWNER_SIGNATURE_CONTEXT + exact_request_digest`

CI uses temporary synthetic owner keys only.

No production HUMAN_OWNER private key is created, stored or loaded.

A valid authorize signature reaches only:

`OWNER_BUILD_AUTH_SIGNATURE_VERIFIED_PENDING_PERSISTENCE`

It still does not authorize the build.

A signed denial reaches:

`OWNER_BUILD_DENIAL_SIGNATURE_VERIFIED`

and never becomes authorization.

## Nonce and single use

A valid owner signature alone is insufficient.

The future system must also prove:

- nonce recorded durably;
- persistent replay guard;
- nonce single-use;
- authorization record persisted;
- authorization CAS;
- read-after-write;
- reopen consistency;
- authorization still unconsumed.

This V1 defines the persistence-attestation shape only.

Its maximum state is:

`BUILD_AUTHORIZATION_PERSISTENCE_SHAPE_VALID_BUT_UNTRUSTED`

It still reports:

- nonce_claimed_trusted=false
- persistent_nonce_replay_guard_verified=false
- nonce_single_use_verified=false
- authorization_persisted_trusted=false
- cas_verified=false
- read_after_write_verified=false
- reopen_verified=false
- build_authorized=false

## No self-attestation

A future caller cannot turn persistence into trusted persistence merely by
passing:

`caller_claims_persistence_verified=true`

That is explicitly rejected.

Likewise, a physical-certificate document does not become trusted physical truth
because it says so.

## Prelaunch revalidation

Immediately before a future launch token can exist, the physical implementation
must recheck:

- certificate freshness;
- same host;
- same recipe;
- same offline inputs;
- same package manifest;
- receipt still present and unchanged;
- evidence chain still present and unchanged;
- owner authorization not expired;
- nonce not replayed;
- authorization still unconsumed;
- no new blocker;
- kill switch / safety state still acceptable.

The contract reserves this as a separate future implementation layer.

## Build token

This V1 defines that a future build token will be required.

It does not define a token as authority merely from the owner signature.

The token may exist only after all physical and persistence proofs are
independently verified at prelaunch time.

Current values remain:

- build_token_implemented=false
- build_token_issued=false
- build_authorized=false
- build_started=false

## Maximum current state

The maximum design state is:

`READY_FOR_BUILD_LAUNCH_GATE_PHYSICAL_IMPLEMENTATION`

It means the final barrier is specified well enough for future Windows
implementation.

It does not mean the build is allowed.

## Next PC phase

The next Windows phase is:

`IMPLEMENT_PHYSICAL_VERIFICATION_AND_FRESH_OWNER_BUILD_AUTHORIZATION_GATE`

That phase requires the owner's Windows computer.

It must first use synthetic/non-production probes and authorization records.

The first production build remains a separately authorized future action.

## Explicitly absent

This V1 does not:

- trust a physical certificate;
- execute a Windows physical probe;
- persist a nonce;
- persist an owner authorization;
- consume an authorization;
- issue a launch/build token;
- authorize a build;
- spawn python.exe;
- run the build script;
- build a package;
- install a package;
- open SQLite;
- modify files/ACLs/Registry;
- call GitHub;
- mutate a repository;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_WINDOWS_PHYSICAL_VERIFICATION_BUILD_AUTHORIZATION_GATE_V1_VALIDATED`

No production-build authorization is implied.
