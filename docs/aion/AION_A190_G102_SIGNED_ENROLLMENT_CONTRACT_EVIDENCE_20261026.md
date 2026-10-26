# AION G102 — Signed synthetic enrollment admission

Date 2026-10-26. Parent G101 Draft #1592. Tested code SHA 2862b9076a95efc225f915e243917fa00bb9e769. LAB ONLY. Six P0: 0/6 homologated; HARD NO-GO.

## Contract

A182 admitted caller-redefined original decisions, self-repinned signing keys/fingerprints and wiped/restored synthetic custody when all locally controlled evidence was replaced. Its prior A182 tests explicitly preserve these known-bypass demonstrations.

The new opt-in aion_chat/pinned_external_enrollment_g102_lab.py wrapper freezes an enrolled semantic original SHA256 and a witness trust-root SHA256. Before an existing A182 signed reservation, it requires a challenge-fresh Ed25519 signed attestation with exact issuer, original digest, witness-root digest, high-water sequence/count, status and schema. Absent/malformed/stale/wrong-key evidence, inconsistent sequence or changed identity returns False, preventing reservation and a simulated send.

The attestor is an in-process Python fixture with synthetic signer keys, not a separate service or a hardware-backed root. An actor who can replace all constructor pins and the signer can still bypass. This code is opt-in, not production Worker enforcement or third-party attestation; no P0 closure.

## GitHub CI objective evidence

[G102 run 40341020275](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40341020275) — Windows 28/28 PASS and Ubuntu 28/28 PASS. Ten new tests plus inherited A182 protection tests and remaining-risk tests. New checks: one in-memory fake dispatch, unavailable attestor zero send, wrong signer denied, stale challenge denied, replaced original denied, repinned local root denied against synthetic retained authority, local custody rebootstrap denied against retained test counter, inconsistent signed high-water denied, malformed attestation denied, and six concurrent requests yielding one synthetic reservation.

The inherited negative-risk checks still emit A182_RISK_REPLACE_ORIGINAL_ENROLLMENT=ACCEPTED, A182_RISK_REPIN_ROOT_AND_FINGERPRINT=FAKE_AUTHORITY and A182_RISK_ROLLBACK_CUSTODY_AND_CHECKPOINT=REPLAY. Those passing tests document dangerous risks in untrusted re-enrollment, NOT real protections.

## External acceptance explicitly unresolved

[A184 run 40341019980](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40341019980): five genuine external-red tests still FAIL on both systems: externally monotonic custody/checkpoint, authenticated immutable original business identity, externally pinned root authority, authenticated native SQLite VFS live snapshot, and rollback-proof native write admission after same-inode restore. No skip or xfail.

A184 canonical jobs on this same commit failed BEFORE test execution due to a separate orchestration defect: the runner was copied to RUNNER_TEMP, without G100's sibling Python socket guard module. This is an import failure, not an executed Quality/Security suite result. Stacked G103 Draft #1594 corrects copied-runner resolution, retaining genuine external RED.

NO MERGE / NO DEPLOY / NO WORKER / NO PROVIDER SEND / NO REAL FUNDS. 0/6 P0 HOMOLOGATED; HARD NO-GO.
