# AION G104 — Two-phase first-attempt attestation: RED → GREEN (LAB)

**Date:** 2026-10-26. **Base:** G103 Draft #1594, checked-out stack SHA 6e5f51b56f41f65a7144b50a30b416539630831e. **Tested G104 code SHA:** eb374d3521a4043159ecc2ba0ccb54de94c7c995. PR Draft #1595. **No merge/deploy; 0/6 P0 homologated; HARD NO-GO.**

## Genuine RED, observed before touching the guard

G102 checked a challenge-fresh signed external-looking enrollment before reserving, but never checked that the **reservation itself** was recorded by that same external-looking authority. A correct locally signed A181 reservation could be accepted even when a separately modeled observer's sequence and ledger remained unchanged at zero. A real provider send would be unsafe under such a split view.

G104 added a test that configures G102 with the real synthetic A181 signing/custody callback but deliberately bypasses update of the simulated remote ledger; it requires denial if the remote has not attested the committed effect.

[Original pre-fix G104 CI 40344188528](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40344188528):
- Windows: 21 executed, **1 FAIL**. The guard returned True; expected False.
- Ubuntu: 21 executed, **1 FAIL**. Identical bypass.
- 21 includes inherited G102 cases discovered twice by unittest (imported fixture and subclass); this is not 21 unique controls.
- Actual error text: G104_UNMET: signed preflight alone does not authenticate that the subsequent reservation reached the external ledger.

## Minimal two-phase opt-in correction

File aion_chat/pinned_external_enrollment_g102_lab.py now REQUIRES an explicit post_attestation probe; missing/unusable probe refuses enrollment.

Protocol:
1. Validate original semantic SHA256, enrolled signer fingerprint, local ordinal/count, and fresh signed G102 **preflight** with challenge A.
2. Existing A182 guard authenticates and commits the synthetic signed A180 first-attempt reservation. Capture its actual verified receipt, not caller-reconstructed assertions.
3. Check local ordinal/count advanced by **exactly one**, and the A180 signed reservation sequence matches the new count/ordinal.
4. Generate a fresh distinct challenge B. Ask the separately modeled post-commit witness to confirm the exact reserved effect digest, decision SHA256, technical idempotency key and reservation sequence.
5. Verify the **G104 domain-separated Ed25519 signature** under the previously pinned synthetic anchor root, exact schema/issuer/challenge/original SHA/trust SHA/sequence/ordinal/count and exact receipt identifiers.
6. Only after all checks return True to the in-memory Outbox dispatch. Wrong/missing/stale/mismatched post-commit evidence returns False; if a local reservation was already committed, it is SPENT/UNCERTAIN and must **never be automatically retried as if rolled back**.

The G102 in-memory attestor fixture now records the simulated external reservation entry separately from the caller's postflight request; it does not blindly sign the caller-requested effect. No production Worker protocol, real provider or native SQLite VFS path was modified.

## Corrected cross-OS CI

[Corrected G104 run 40344894057](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40344894057): both Ubuntu and Windows G104 jobs SUCCESS, **29 executed / 0 failures / 0 errors** on each. The test discovery includes the original ten G102 cases twice, plus nine new G104 cases, so there are 19 distinct test methods, not 29 unique contracts.

All nine G104 adversarial markers:
- G104_UNATTESTED_POST_RESERVATION=DENIED_NO_SEND — local signed receipt not found remotely cannot authorize.
- G104_LOST_POST_ACK=SPENT_UNCERTAIN_ZERO_SEND — post attestor unavailable after local commit; Outbox UNCERTAIN and fake adapter called zero times.
- G104_OTHER_EFFECT_POST_PROOF=DENIED — unrelated effect cannot be substituted.
- G104_UNPINNED_POST_SIGNER=DENIED — wrong Ed25519 post signer.
- G104_POST_PROOF_REPLAY=DENIED — stale post challenge.
- G104_DIFFERENT_POST_ORDINAL=DENIED — signed but divergent new sequence.
- G104_OTHER_REQUEST_POST_PROOF=DENIED — another technical request ID.
- G104_NO_POST_ATTESTOR=ENROLLMENT_DENIED — missing post service.
- G104_OTHER_DECISION_POST_PROOF=DENIED — changed decision digest.

Old G102 positive synthetic reservation/custody concurrency cases remain green.

## Critical external restrictions, NOT certified

This work demonstrates a two-phase **contract with test doubles**. The attestor signing key, state, original enrollment and its root are still under test-process control. It is not a physically/administratively independent service, hardware-protected root, monotonic externally attested write log, deployed Worker gate, native SQLite VFS fd/inode proof, provider first-SEND receipt or H0 restart certification. A malicious actor who can replace the complete locally pinned configuration and both synthetic signers can still bypass it. The postflight remote proof is not an atomic distributed transaction with the provider.

The A184 genuine external RED tests must stay RED until verified independent infrastructure exists: (1) externally monotonic custody/checkpoint, (2) immutable authenticated original business identity, (3) externally pinned root, (4) live native SQLite VFS snapshot/version, and (5) rollback-proof same-inode native write boundary.

**0/6 P0 HOMOLOGATED · HARD NO-GO · NO MERGE · NO DEPLOY · NO WORKER · NO REAL SEND · NO FUNDS.**
