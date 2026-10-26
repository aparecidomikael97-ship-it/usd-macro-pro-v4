# AION G106 — Final local custody verification (LAB)

Date: 2026-10-26. Base: G105 Draft #1596. Code fix commit: `740f2e05b5fb7533b13c196a9efd1f4dd5876181`. PR #1597 stays Draft.

**RED first:** [run 40349179242](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40349179242) — Windows 54 tests, 5 FAIL; Ubuntu 54 tests, 5 FAIL. The previous G104 contract could accept a signed post-reservation observation even when the host's local SQLite custody changed while the observation was being produced.

**Minimal LAB fix:** only `aion_chat/pinned_external_enrollment_g102_lab.py` changed. After checking a signed postproof, the guard rereads local custody and requires exact, matching integer high-water/count. Missing, altered, unavailable or inconsistent checkpoint fails closed. A prior local reservation remains uncertain/spent, not safe to retry.

**Focused GREEN:** [run 40349411003](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40349411003) — Windows 54/54 PASS and Ubuntu 54/54 PASS. Five new adversarial cases plus inherited G102/G104 methods; 54 includes duplicated inherited test discovery, not 54 unique controls.

**Original A184 canonical checks on same source:** [run 40349411039](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40349411039) — Ubuntu Quality 6449/6449 PASS; Security unittest 368/368 PASS; Security pytest 2825/2825 PASS; dependency pip-audit reports no known vulnerabilities. Both external requirement jobs still fail all five genuine independent-trust acceptance tests.

**Limits:** final local read is not an atomic external lock or native SQLite VFS attestation. Synthetic attestation keys and state do not prove real independent custody or protection from later rollback. No real provider send, Worker or deployment took place.

**0/6 P0 HOMOLOGATED · HARD NO-GO · NO MERGE/DEPLOY/LIVE SEND/FUNDS.**
