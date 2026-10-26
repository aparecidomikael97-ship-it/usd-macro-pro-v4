# AION A190 / G114 — public-key-only client, signer-side test keyfile

**Date:** 2026-10-26. **PR:** #1604, Draft LAB stacked on G113 #1603. **No main merge, deploy, Worker, provider SEND or real funds. Six P0: 0/6 HOMOLOGATED; HARD NO-GO.**

## Verified security interface problem in G113

G113's older `SubprocessWitnessClientLab` stores a 32-byte synthetic Ed25519 signing seed and passes it to the child process as `--synthetic-seed HEX`, making the secret material visible to any actor who can read that process's command arguments on the same machine.

G114 has an objective test that intercepts **actual** child-process argv and confirms this existing G113 behavior, then executes the new code and checks that **neither the raw private key nor its hex representation occurs anywhere in the new subprocess command arguments**. This fixes an unsafe protocol design, not same-host administrative compromise.

## New G114 opt-in LAB components

- `labs/a190/g114_public_key_witness_client_lab.py`: exposes only `pinned_public_key` and `transport` constructor fields. No private seed, private signing key or signing-key path in the public client object. Retains inherited G113 exact Ed25519 signature, event identity, nonce and counter checks. `ALREADY_RESERVED` still DENIES new authorization.
- `labs/a190/g114_witness_subprocess_transport_lab.py`: controls an IPC test process, sends bounded JSON and supplies a TEST FILE PATH (never the signing bytes) in child argv. Missing/invalid response denies; lost ACK after possible COMMIT becomes UNCERTAIN.
- `labs/a190/g114_witness_keyfile_server_lab.py`: reads the synthetic signer seed from a TEST keyfile on the GitHub runner. Rejects missing/symlinked/malformed file. POSIX runner requires group/world permissions disabled; Windows uses OS-native file behavior. Never silently generates a new signer on restart. Signs G113's persisted reservation after COMMIT. **This is not KMS/HSM or remote custody; same-host administrators can read or change the file.**
- `labs/a190/test_g114_public_only_witness_lab.py`: 15 tests, including the former G113 argv exposure, public-only client, lost ACK after COMMIT, same-event different technical request ID denied, signer failure, pin mismatch, replay, tampered payload, wrong enrollment, four concurrent child reservations, unknown event/wire error, absent database, client trust configuration missing and two separately enrolled events sharing an effect.
- Unchanged inherited G113 tests: 13 regressions, including deliberate same-host rollback bypass demonstration.

## Objective cross-OS evidence

[GitHub Actions G114 run 40367418397](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40367418397), tested G114 source SHA `b79f2042c312779a56879cdc61758abaff1ca40f`:

| OS | New G114 | Inherited G113 | CI status |
| --- | ---: | ---: | --- |
| Ubuntu, job 121728785328 | 15/15 PASS | 13/13 PASS | SUCCESS |
| Windows, job 121728784537 | 15/15 PASS | 13/13 PASS | SUCCESS |

Confirmed markers include `G114_LEGACY_SECRET_ARGV=CONFIRMED_NEW_CLIENT_PUBLIC_ONLY`, `G114_LOST_ACK_AND_NEW_PUBLIC_CLIENT=SPENT_NO_RETRY`, `G114_CONCURRENT_PUBLIC_ONLY_CLIENTS=ONE_TEST_COMMIT`, `G114_OTHER_SIGNER_WITH_FIXED_PUBLIC_PIN=DENIED`.

## Explicitly documented remaining vulnerabilities and nonclaims

**G114_SAME_HOST_ROLLBACK=STILL_VULNERABLE_NOT_P0**: restoring the signer-owned *local* witness SQLite database makes the original business event reservable again at sequence 1. This is a **successful attack demonstration**, not proof that the control has been fixed.

The test transport itself knows the *path* to the signing keyfile. A privileged same-host actor can read it, change the pinned public key in local config, bootstrap a new ledger, replace the process, or bypass this purely optional LAB client. Signing keys provisioned by test fixtures and host-controlled original business enrollment cannot establish authenticity or independent monotonicity. The Python subprocess boundary is not administrative separation.

No live H0 gateway, provider first SEND, real externally authenticated owner approval, true monotonic off-host custodian, pinned external root enrollment, native SQLite VFS attestation, or same-inode rollback-proof native write boundary was deployed or proven. The five genuine A184 external RED requirements stay RED and are not waived.

## Next LAB-only integration

A follow-on opt-in test may connect this public-only G114 process client to the **existing in-memory Outbox first-attempt guard** and verify unknown/invalid/duplicated/lost-ACK decisions. This does not authorize adding it to the production Worker or claiming P0 closure. Independently administered service, protected enrollment, key lifecycle, LGPD, quotas and signed H0 evidence remain prerequisites for eventual real acceptance.

**0/6 P0 HOMOLOGATED · HARD NO-GO · NO MERGE/DEPLOY/WORKER/LIVE SEND/REAL FUNDS.**
