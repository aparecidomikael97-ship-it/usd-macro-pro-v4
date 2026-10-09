# AION V2 — three JSONL GitHub Contents PUTs require matching read-after-write

**9 October 2026. Source-only stacked Draft following #1154. No production authority.**

## Gap
The Flight Recorder, Research Evidence and Shadow Mode legacy writers could return `ok=True, reason=SAVED` solely after GitHub HTTP 200/201. A success HTTP status, without verifying the object actually read back, is not adequate to claim that the intended records were saved. This is a source-level gap, not an observed real-world loss.

## Implementation
After the sole existing guarded PUT returns an accepted status, all 3 real application writers now call a pure helper `verify_legacy_jsonl_readback`. It obtains `response.json().content.sha`, validates a 40-character Git SHA-1 blob identifier against the **Git blob SHA of the serialized exact intended UTF-8 JSONL bytes**, and invokes the writer's **already guarded** `_fetch_remote` / `_fetch` to perform a fresh authenticated, no-redirect, strict-status GET of the same branch+path. The returned blob SHA and reserialized records must exactly match the expected SHA/text. No separate new HTTP write or GET client is introduced. Only then can the existing return become `ok=True, reason=SAVED, verified=True, verification=SAME_GITHUB_CONTENTS_ENDPOINT_READ_AFTER_WRITE`.

If returned status, JSON, blob SHA, fresh read, serialization or data comparison fails **after the PUT attempt**, the existing #1153/#1154 handler returns `UNKNOWN_OUTCOME, reconciliation_required=True, safe_to_retry=False, write_attempted=True`, with exception class name only, not credentials or raw response. No retry or resend. HTTP 409/422 return rejected/reconciliation state after only one PUT without readback. No response status is used as replay authority.

The helper is pure-injected and can be tested without network; real caller tests mock first GET, HTTP PUT and second GET with synthetic matching and mismatched Git blob SHA/readback, and assert exact counts and no credential exposure. New pinned source auditor checks that all three actual writers invoke the helper inside their production persist functions. Linux+Windows CI inherits the protected stack, 21 GitHub writes guards, 28 reads, and both paid provider hard-denies.

## Limits
A same-origin GET and a matching SHA is **not independent authenticated witness proof**. A malicious/colluding intermediary can forge both PUT and GET, and 40-char SHA-1 is a legacy Git blob identifier rather than cryptographic owner signature. The code does not attest GitHub's physical durability, cross-worker global idempotency, antirollback, billing settlement, true FIDO2/TPM/owner enrollment, or offline recovery. An upstream caller may still invoke a function twice; no unrelated service is authorized to write. Source-level CI is not deployment certification. Core V1/main intact; no real GitHub application write, owner PC, cost, paid API or Worker activation. Checkpoint Master #1117 **HARD NO-GO**.
