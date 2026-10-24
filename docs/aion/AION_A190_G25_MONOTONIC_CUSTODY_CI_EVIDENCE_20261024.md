# A190 G25 — Monotonic custody witness contract LAB CI evidence

Date: 2026-10-24. Exact tested SHA `96edbe808da85496f7534c3314e3d2b508a461ef`.

## Verified CI
- [GitHub Actions #40121023813](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40121023813): completed SUCCESS.
- Ubuntu job `120952369141`: **18/18**.
- Windows job `120952369473`: **18/18**.
- Total: **36 executions of 18 distinct synthetic tests**.

## Contract
A synthetic `TrustedHighWaterMark` requires semantic key, sequence, and digest to match a challenge-bound Ed25519 witness statement. A missing floor, lower witness sequence, stale floor, wrong digest/semantic key, signature tamper, replay, local rollback or deleted journal deny. A matching floor returns only `UNCERTAIN_ZERO_AUTO_RESEND`, never SEND/RETRY.

## RED finding
`G25_HOST_CONTROLLED_FLOOR_RED=OLD_JOURNAL_OLD_FLOOR_MATCH`: the same host can roll back BOTH journal and host-supplied high-water mark. A fresh signature for the old state passes the synthetic contract and returns UNCERTAIN. This does **not** demonstrate that a truly independent external monotonic service can be rolled back. It demonstrates the absence of independent custody in the LAB.

## Limitations
The high-water mark is an in-memory test fixture, not an externally controlled monotonic log. No external root provisioning, actual independent witness, real AION integration, atomic first-send reservation, H0 restart proof or provider effects. Canonical Quality/Security not rerun. No main/merge/deploy/Worker/customer/credentials/spend.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
