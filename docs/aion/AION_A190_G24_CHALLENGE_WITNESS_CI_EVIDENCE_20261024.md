# A190 G24 — Ed25519 challenge-bound witness LAB evidence

Date: 2026-10-24. Exact tested SHA `7de6ec2efc09cc6c77ac6a5041b1a68ff0468a9e`.

## CI
- [GitHub Actions #40120259588](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40120259588): completed SUCCESS.
- Ubuntu job `120950060687`: **18/18**.
- Windows job `120950060889`: **18/18**.
- Total: **36 executions of 18 distinct tests**.

## Verified in isolated synthetic LAB
- Verifier-generated 32-byte CSPRNG challenge is cryptographically bound to canonical witness statement using Ed25519.
- An old signed response replayed against a different challenge is rejected.
- Wrong root, unpinned signing key, signature modification, modified signed sequence/phase/digest, local rollback, missing local journal and invalid challenge are rejected.
- **RED** `G24_FRESH_NONCE_OLD_HISTORY_RED=SIGNER_CAN_ATTEST_ROLLBACK`: a compromised or rollback-capable signer can issue a *new valid signature* on a *new challenge* for an *old journal*. The G20 recovery contract returns `UNCERTAIN_ZERO_AUTO_RESEND`, **not SEND**.

## Limitations
A fresh challenge proves response binding to a challenge, not freshness of the signed *history*. The witness and ephemeral private key are in-process synthetic test fixtures. There is no independent externally pinned root, externally monotonic counter, quorum, trusted custody or provider attestation. No real AION runtime integration, no atomic first-send reservation, no H0 rollback protection. Canonical Quality/Security not rerun. No merge/main, deploy, Worker, customer, provider, credentials or spending.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
