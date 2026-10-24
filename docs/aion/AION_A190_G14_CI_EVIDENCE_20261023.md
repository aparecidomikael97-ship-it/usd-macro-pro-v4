# A190 G14 — SHA-pinned SQLite CI evidence (2026-10-23 Manaus / 2026-10-24 UTC)

## Tested code, tests and workflows

**SHA: b4eb186b6c91b82754485fc78d79260cbf7835fa**. Later commits to this branch may change documentation only; do not transfer these test claims to untested code.

### G14 targeted real SQLite cross-platform

[Run #40055856863](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40055856863): **success**, both OS.

- Ubuntu job **120758566215**: new G14 8/8, plus A183, SQLite path/anchor/read/write/lifecycle/recovery, Outbox, Saga and other existing suites 106/106; **114/114** total.
- Windows job **120758566473**: same **8/8 + 106/106 = 114/114**.
- **228 selected test executions across Ubuntu and Windows.**
- Separate A186, A187 and SQLite staged lifecycle workflows triggered by runtime file changes all reported **success** at same tested head.

### G14 independent A184 broad suite

[Run #40055856788](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40055856788):

| Selected test gate | Base | Candidate at tested SHA |
| --- | --- | --- |
| Canonical Quality unittest selector | **6,322 tests; 4 FAIL**, job 120758566005 | **6,449 / 6,449 OK**, job **120758566090** |
| Canonical Security unittest selector | **FAIL** (historical), job 120758566030 | **368 / 368 OK**, job **120758566096** |
| Canonical Security audit/dependency scan | FAIL | **FAIL**, dependency advisories still open |
| A184 external RED / adversarial BASE RED | RED | **RED**, never waived |
| A184 sqlite/specific/regression | n/a as external trust evidence | Targeted candidate suites pass |

The **overall A184 workflow is FAILURE** from expected adverse and dependency-audit jobs. Green unittests do not override that. Test coverage differs across base/candidate; improvement must not be credited exclusively to G14.

## Narrow proven change

- Separate **independently initialized** SQLite databases carry different local markers, stable through ordinary WAL writes and reopen.
- A183 native same-filename ABA to a different local marker is **denied before wrong-file read or write on Ubuntu**. On Windows those particular ABA renames were rejected by OS; that is not a portable identity proof.
- A marker mismatch **after** a committed synthetic write causes UNCERTAIN / latched handle; the persisted effect was independently verified in the temporary database, not replayed.
- Existing backup copy retains marker. This is correct continuity but also defeats marker-only clone detection.

## RED limits reproduced and recorded, NOT silently closed

- Ubuntu G14 cloned-native read: **G14_CLONED_NATIVE_MARKER_READ=WRONG_FILE_ACCEPTED_RED**. Same-marker clone can still fool the marker and pathname checks. This is a critical remaining P0 incompatibility.
- Ubuntu clone write: SQLite native engine returned SQLITE_READONLY_DBMOVED (OS/native denial). This is one observed rejection, NOT a universal proof against same-marker write redirection on other versions/OSes.
- Windows swap attempts: OS denied rename (good for test host, not portable VFS attestation).
- Attacker can edit/copy/delete the local marker, and native SQLite's file handle remains unverified. No external antirollback witness or signed provider receipt exists.

## No release

No main merge, no deploy, Worker, cloud vendor, credential, customer, account, external send/effect or spending. Six P0 remain unhomologated.

**0/6 P0 · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
