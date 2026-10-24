# A190 G23 — Pinned Ed25519 witness verifier LAB CI evidence

Date: 2026-10-24. Exact tested SHA `7bd4c1fa4d5fa93056f41e9998694a474f178b1a`.

## CI
- [GitHub Actions #40120102538](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40120102538): completed SUCCESS.
- Ubuntu job `120949591433`: **16/16**.
- Windows job `120949591631`: **16/16**.
- Total: **32 executions of 16 distinct tests**.

## Confirmed
- Real Ed25519 mathematical signature verification via `cryptography==46.0.3` in the isolated workflow.
- Synthetic test private keys are generated ephemerally; public key pin is supplied independently of the attestation payload *inside the test harness*, not externally provisioned.
- Bit-flipped signature, self-signed attacker key, wrong pin, modified signed sequence/phase/digest, missing pin/signature and modified local history are rejected.
- **RED** `G23_SIGNED_REPLAY_RED=VALID_OLD_SIGNATURE_NOT_FRESHNESS_PROOF`: an authentic signed *old* attestation with a matching rolled-back local journal passes signature verification. The recovery contract returns `UNCERTAIN_ZERO_AUTO_RESEND`, **never SEND**.

## Strict limits
This is a test of signature correctness, **not** an independent external witness. There is no independent monotonic sequence, externally controlled key provisioning, fresh external attestation or real AION production integration. An old authentic signature is not a freshness proof. No provider dispatch, first-send reservation, H0 availability or P0 closure. Canonical Quality/Security not rerun; no main/merge/deploy/Worker/customer/credentials/spending.

**0/6 P0 homologated · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
