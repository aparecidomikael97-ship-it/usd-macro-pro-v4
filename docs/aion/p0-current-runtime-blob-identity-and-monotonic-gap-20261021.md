# AION P0 — A132: current runtime Git blob identity required (LAB)

2026-10-21. Isolated Draft stacked upon PR #1415.
No real runtime recovery, GitHub PUT, production credentials, Global Worker,
new paid supplier, merge or deployment was approved or performed.

## RED-first observation

The load_runtime_checkpoint function previously returned status CONFIRMED
after base64/JSON/integrity checks, while assigning the GitHub response sha
by coercion to string. The reader did not establish that the declared SHA
identified the decoded checkpoint bytes.

Consequences observed in synthetic tests:
- Absent, malformed, boolean, numeric or plausible-looking false SHA could
  accompany a valid checkpoint body and be presented as CONFIRMED.
- An approved recovery call given a matching but false 40-hex SHA could pass
  the A129 fresh-target agreement, then reach historical readback and a
  mocked save despite false blob identity.

RED-first job: https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39668760715
Ubuntu before fix: 13 tests, 10 FAIL and 3 PASS. All network calls
and persistence in new tests are mocks. No actual GitHub runtime write,
malicious activity or supplier execution was demonstrated.

## Narrow correction

Before declaring current runtime CONFIRMED:
1. Base64 decode under existing byte-size limits.
2. Require sha as a string of exactly 40 ASCII hex characters.
3. Compute SHA-1 of the Git blob header plus the exact decoded bytes.
4. Reject absent, malformed, divergent or wrong-type SHA with ERROR,
   checkpoint=None and sha empty; cannot reach historical candidate review.
5. Preserve normal read-only public GET, uppercase SHA and wrapped base64.

The same consistency check exists in A131 for historical contents.
A132 closes the corresponding current-runtime path. It does NOT prove
a head is the newest or exclude replay of old, self-consistent Git blobs.

## Verification and independent-proof boundary

A132 includes 13 new adversarial tests plus original memory/recovery suites,
A127/A128/A129/A130/A131, A126 and H0 A79, on Ubuntu and Windows.
The canonical original 588-module Quality and Security A74 workflows
are triggered unchanged by adding only this LAB branch to their selector.

Only exact HEAD/workflow logs count as test evidence. An old checkpoint with
a correct old SHA may appear valid if the GitHub branch head is rewound.
An independent externally enrolled non-forking sequence/epoch head witness
is still necessary. A self-signed document or hash beside the checkpoint
is NOT independent authority. SHA-1 is native to Git blob identifiers and
does not provide independent authenticity or collision-resistant proof
against a sophisticated malicious collision.

HARD NO-GO · 0/6 P0 homologated · Worker OFF · ZERO_AUTO_RESEND.
Previous canonical Quality baseline: 6,895 tests, 6,810 PASS, 51 FAIL,
34 ERROR. Do not claim a new baseline until canonical jobs finish.
