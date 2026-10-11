# AION V2: offline assertion, causal recovery and private evidence blueprint

FIRST INSTALL = HARD NO-GO. All 20 original evidence gates remain BLOCKED.

## Exact base and preservation

Child of Draft #1217, c79f525cb324d8ffa64c51a4b35a5dd7c4325c4d, itself ahead
of #1216 at 895f3abcd533684ee1eab9b92b6ce9eebf3b74be. Its 17 files and five
commits were inspected. Final #1217 run 38113651019 recorded 246 tests and
380 subtests on both Windows and Linux; original root Quality recorded 6348
tests, 569 root modules. Inherited 213 pytest tests/293 subtests overlap those
regressions and are not added. Those results describe the BASE, not this HEAD.

No Core V1, production dependencies/policies, worker path, original evidence
manifest or previous worktree changed. Existing postcommit UNKNOWN_OUTCOME
CAS fix is untouched. V2 composes the existing CAS and one-shot journal.

## Audit of the six V1 offline modules

- contracts: exact dictionaries, bounded identifiers/permissions, JSON copying;
  protected result fields always override caller details. No trust from hashes.
- ceremony: scope/request/nonce/time, explicit revocation/replay state. A
  simulated assertion is not WebAuthn. V2 adds mathematical verification only.
- windows: local fixture controls cannot establish ACL/TPM/device possession.
- recovery: causal/floor/fork/revocation tests are supplied-claim consistency;
  they do not independently read a store. V2 adds fresh read-only snapshots.
- governance: B2B permission/scope and cost fixtures retain unknown quotes and
  no spending authority. No paid provider was used.
- plan: LOW, reproducible metadata false-positive: boolean baseline_pr,
  textual monthly cap and non-date date yielded REFERENCE_COLLECTION_PLAN_UNTRUSTED.
  Strict positive integer PR, integer budget 0..200 and canonical ISO date now
  refuse them. No readiness bypass existed: every authority flag stayed false.

The prior SQLite commit-then-error regression remains: caller UNKNOWN_OUTCOME,
independent local file contains one append. V2 recovery never calls CAS to
discover an operation; absence cannot accidentally become a new append.

## What is real and what is synthetic

Real: ES256/P-256 signature verification through python-fido2 2.2.1 and
cryptography, SQLite transactions/files, fresh mode=ro connections, subprocess
termination/restart and competing local claims. Public Yubico BSD-2-Clause
COSE vector pinned to commit 018ef972eabbc1408d096941cc1967c83db967fc,
tag 2.2.1. Provenance, vector/wheel digests and license accompany it.
This is a vendor signature vector, not certified WebAuthn conformance. Full
assertions are generated from disposable in-memory keys by tests only.

WebAuthn reference supports canonical ES256 COSE only, a 37-byte authenticator
data profile without extensions, .invalid fixture RP/origin only, UP+UV,
backup flag consistency, increasing nonzero counters and zero-counter explicit
NONE assurance. Duplicate JSON/CBOR, unapproved algorithms/private labels,
oversize inputs, changed scope/challenge/credential and unknown replay state
are refused. Unsupported formats fail closed, never silently downgrade.
The challenge hashes the full prepared intent, including request, operation,
policy generation, nonce and expiration. Signature validity is not enrollment.

Protocol reference: [W3C WebAuthn assertion verification](https://www.w3.org/TR/2026/REC-webauthn-3-20260825/#sctn-verifying-assertion).

Simulated: coordinator, witness and append-only history domains. They are
separate disposable SQLite files, not independent administrative custody or
WORM. Deterministic faults cover before/after commit, lost ACK and fake success.
Existing durable claim occurs before any fake write. No write ACK confirms
success; recovery reads exact operation/query/receipt binding and full existing
append chain, scoped config/genesis and sequence/epoch floors. At most 1024
history records in this reference readback; larger histories remain BLOCKED.
Reconciliation reports REFERENCE_CONFIRMED_UNTRUSTED only for three matching
fixture observations. Same controller/key/domain or contradictory evidence
blocks. No majority fallback, automatic retry or real provider exists.

Unknown and missing observations remain UNKNOWN_OUTCOME or
RECONCILIATION_REQUIRED. Recovered local effects never release durable claims
or confer installation/worker authority. No production entry point imports V2.

## Private dossier rules

New closed JSON schema, synthetic example and runtime validator cover the same
20 requirement IDs, aliases, experiment, source, artifact digest, attestation
reference, time/expiry, negative experiment, unsatisfied dependencies,
institutional verifier, revocation, audit decision and reason. Only fixtures
are accepted here; filling URI/hash/attestation does not verify evidence.
Public projection whitelists requirement IDs and BLOCKED states, omitting all
source references, hashes, aliases and arbitrary input. Exceptions use fixed
reason codes. Never serialize raw inputs to public logs. Future collectors must
store sensitive artifacts privately, minimize personal data and record lawful
access/retention under separately authorized institutional review. No private
evidence was collected. Schema alone is not a sanitizer for arbitrary secrets.

## Residual risks and approval criteria

- HIGH deployment blocker: privileged restoration of every local file can
  bypass local claims/floors. No externally protected monotonic anchor exists.
- HIGH deployment blocker: identity, credential enrollment, physical device,
  independent key custody and administrative domain separation are unverified.
- MEDIUM: revocation/replay/floors supplied by fixture caller; no durable
  WebAuthn challenge-consumption registry or atomic credential-counter update.
- MEDIUM: cross-store atomicity is not established; partial commits require
  read-only reconciliation, no automatic completion or resend.
- LOW: bounded ES256 profile intentionally excludes other algorithms and
  extensions; no browser/authenticator/hardware interoperability validation.
- Local DOS/large-history protection is reference-only; no production SLA.

Approval for this Draft means offline preparatory code only, not install GO.
Acceptance: Windows/Linux green for final HEAD, unchanged regressions present,
no skips, all authority fields false, original 20-gate manifest byte-identical,
postcommit uncertainty preserved and no writing recovery path.

Next safe package: a separate offline durable WebAuthn challenge-consumption
and credential-version ledger with atomic replay/counter tests, still fixture
only and without external enrollment. Physical/third-party evidence remains
owner-dependent and HARD NO-GO.
