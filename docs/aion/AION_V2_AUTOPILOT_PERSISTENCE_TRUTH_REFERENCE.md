# AION — Persistence-truth reference and Autopilot health source review

**Independent review lane; Draft only.** Builds on source-only #1164,
tracks issue #1163. This module makes no HTTP call and does not import,
configure or run Autopilot, Streamlit, any market provider or Windows host.

## What the review checks

- Runtime code creates \`healthy\` with \`len(errors)<8\`, so some errors can
  coexist with the status flag. This flag must NOT be used as a receipt.
- Autopilot constructs the status payload BEFORE attempting to write the
  status file. A status payload cannot prove its own remote storage.
- The ordinary main() return 0 is not a per-sink write certificate.
- For the twelve already inventoried generic Autopilot sinks, the reference
  accepts synthetic per-sink observations and reports missing, unverified,
  conflict, UNKNOWN and conditional skip separately. No untrusted report
  grants authority.
- Even all twelve "REPORTED_MATCHING_READBACK" observations cannot establish
  independent response origin, monotonic custody or remote durability.
- A new sink not in the pinned list immediately receives a blocker.

## Scope / interpretation

The reference cannot tell whether a remote write actually happened. It
cannot certify GitHub endpoint identity, external witness, the exact bytes
written, restart or cross-process CAS. It always sets safe_to_retry=false,
safe_to_resume=false, safe_to_deploy=false and
independent_attestation_verified=false.

A completed **GitHub Actions job** is a test result, not remote data
persistence. Keep separate:
(1) job completion,
(2) each sink's verified readback,
(3) independently durable multi-process admission,
(4) authorized operational release.

## Future integration

Do not wire this reference as a source of permissions or turn an inventory
report into a live safety gate. The owner's Codex worktree is separately
consolidating Shadow/Research and #1156/#1161/#1162. First reconcile those
branches, then design a real consumer of trusted evidence and staged
degradation UX. Do not silently flip the current production healthy status
without an approved migration and backward-compatibility tests.

#1117 remains HARD NO-GO. No merge, deploy, Worker, paid APIs, Windows host,
TPM/FIDO2 or Core V1 changes.
