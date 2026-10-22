# AION P0 A160 — Close inherited A149 CAS mutator bypass in A150 witness

**2026-10-22 — LAB-only Draft. No production migration, no merge/deploy,
no independent witness or provider, 0/6 P0 homologated, HARD NO-GO.**

## Threat: inherited public mutator may bypass stricter subclass

In the LAB, `LeasedPinnedWitnessLAB` (A150) subclasses
`AuthenticatedWitnessLAB` (A149). The A150 override has operator-pinned
key/epoch and a 30-second challenge lease with a synthetic clock floor. The
older A149 methods `issue_challenge` and `publish` do not enforce
that lease or A150's synthetic time validation.

**Critical Python dispatch fact:** even when `engine.publish(...)`
uses A150's override, code can explicitly invoke
`AuthenticatedWitnessLAB.publish(engine, envelope=...)`,
`super(LeasedPinnedWitnessLAB, engine).publish(...)`, or a method
descriptor. Such calls execute A149's older method body with the A150
instance as `self`. A150's overridden `_state` still validates the
extended SQLite schema, so inherited dispatch is a plausible direct
path to bypass the stricter publication policy.

Likewise, `AuthenticatedWitnessLAB.issue_challenge(engine)` can
write an A149 challenge with no corresponding A150 lease row. The
next strict A150 read then detects an inconsistent orphaned challenge,
but the syntactic base-level method still attempted and committed the
undesirable state before that detection. This should be refused
**before any SQLite access**.

The preexisting A150 test #48 attempted to instantiate a fresh A149
engine on A150's schema and observed a rejection. That does **not**
cover invoking A149's unbound methods on the already constructed
A150 object. A160 fills this gap with direct dynamic invocation tests.

## Minimal fail-closed fix

The only product-source change in this LAB branch is to
`aion_p0_a149_authenticated_cas_lab.py`:

- `AuthenticatedWitnessLAB.issue_challenge(self)` now begins with
  `if type(self) is not AuthenticatedWitnessLAB: raise A149Denied(...)`.
- `AuthenticatedWitnessLAB.publish(self, *, envelope, ...)` begins
  with that identical exact-type fence, **before parsing signed
  envelope, querying SQLite, signing or checking fault injection**.
- A149's own synthetic standalone engine remains a direct A149 instance
  and continues to use its old methods for backward compatibility
  within its *insecure* LAB contract.
- A150 still overrides both methods; ordinary `a150.issue_challenge`
  and `a150.publish` continue to use the extended lease and policy
  verification. Read-only A149 base methods on A150 are not blocked.

The `type(self)` fence is intentionally stronger than `isinstance`,
which would incorrectly admit an A150 subclass. It prevents this
particular **inherited-method dispatch** bypass, NOT arbitrary Python
reflection/monkeypatch, compromised host control or alternate provider
endpoint. A149 standalone remains a test-only mutable witness that is
not a production service.

## Objective, falsifiable tests

- **30 new dynamic synthetic tests** exercise direct base calls,
  descriptors and `super`, valid signed requests and expired leases,
  malformed envelopes, idempotency after a successful A150 publication,
  clocks and reopen, no orphan challenge, no bypass of lease expiry,
  and preservation of legitimate A149/A150 isolated behavior.
- All tests use freshly generated disposable Ed25519 keys and
  `TemporaryDirectory` synthetic SQLite databases; no network,
  cloud credential, Worker, provider API or real effect.
- Historical regression expected: A145–A150 **259**, A151 **16**,
  A152 **55**, A153 **48**, A154 **73**, A155 **78**,
  A156 **90**, A157 **67** = **686 previous checks**.
- Total requirement: **716 counted tests per OS**, **1,432 total**
  test executions on Windows + Ubuntu, plus standalone documentary
  and 32-provider-error NO-GO gates. **This is a target until
  GitHub Actions independently concludes green.**
- Initial RED-first commit `e656b31cf7468d82b1c6cb83f959fad51d2a0abe`
  has tests but deliberately lacks the guard; it is submitted for
  independently observable failure. Patch commit
  `d3ab865f1cbeab5ffdf9589ee49daa4bc7a366c6`.
  Never present expected red tests as proven until CI log evidence is
  actually available.

## Important residual security risk

Even after this fix, A149 and A150 remain LOCAL SYNTHETIC implementations:
- A150's lease floor and database are jointly snapshot-restorable by
  the same administrator. A valid signature or replay check is NOT an
  independently nonrollbackable external authority.
- A149's standalone legacy engine remains usable as a separate toy,
  not a supported real deployment.
- This patch does NOT establish independent signer/key custody,
  trusted H0 epoch, external anchor current HEAD, HUMAN_OWNER/FIDO2,
  real provider COMMITTED_EFFECT or terminal NO_EFFECT_FENCED,
  automatic resend, or the 32 historical provider proof blockers.
- A160 is stacked on A157 Draft #1441 and therefore is not merged to
  `main`. A159 security-package PR #1448 is separately based on
  `main`, with its own approved Security/Quality gates; merging neither
  this branch nor that branch has been authorized.
- GitHub `contents:write` and existing main scheduled jobs are
  separately handled in unmerged main containment Draft #1442; this
  change is not a substitute for provider-side IAM enforcement.

**HARD NO-GO / ZERO_AUTO_RESEND / 0 OF 6 P0 / WORKER OFF.**
