# AION V2 — dual-signed captured response-ID high-watermark and GET-only review

**2026-10-09**. New **reference-only** Draft based on #1137, itself based on #1136→#1125. **NO-GO:** no real owner/witness enrollment, external service, merge, deploy, paid API, HTTP GET, Windows/TPM, new costs or installation.

## Why this exists

#1137 captures a **caller-asserted** already received provider response ID or batch ID into a restorable local SQLite database and produces strict offline GET-only relative paths. If that database is rolled back, the captured ID can disappear or an older ID can reappear. A local content hash without a genuinely independent, durably committed monotonic witness is not proof of freshness.

This Draft defines **exact signed READs of the capture registry's own sequence and full snapshot** from two cryptographic roles, **PRIMARY_WITNESS** and **SECONDARY_ANCHOR**, and binds them to the separately verified *dispatch journal* signed heads (#1134). All keys, reads and challenges remain disposable caller-supplied CI fixtures. Their mathematical equality is **not** trusted external freshness.

## Implemented mathematical protocol

`atlasquant_aion_v2_captured_id_dual_witness_reference.py`:

- `local_capture_commitment`: checks local capture file integrity and reads its full canonical snapshot in a single local SQLite `BEGIN IMMEDIATE` transaction, with the target nonce's exact captured event digest, while separately verifying the matching source dispatch-journal intent and persisted original claim sequence. It does **not** make those two SQLite databases a distributed atomic transaction.
- `unsigned_capture_witness_candidate`: constructs a closed, domain-separated candidate signing payload. No actual key generation, signing, remote READ or CAS.
- Signed READ includes exact owner, tenant, workspace, policy/month, registry generation digest, V2 nonce, distinct caller challenges and minimum witness epoch, witness epoch, captured-ID sequence, full capture database snapshot SHA256, ID event SHA256 or `NO_CAPTURE_YET`, original dispatch-journal sequence+hash+claim sequence and exact signed V2 intent/full resolved request digest.
- `review_double_witnessed_capture_for_offline_get` verifies distinct signatures and roles, compares the two signed heads, the current *local* captured-ID state, and **both separately signed dispatch-journal heads**. It BLOCKS when capture DB is behind/ahead of signed heads, two signers lag/fork, local state differs, journal diverges, no ID was captured or any signature/scope/challenge is invalid. Only a math match of a captured record may return **fixed relative GET-only route data** revalidated through #1137. A GET plan is **never a network capability**.
- `review_one_step_capture_anchor_preflight`: pure exact predecessor `NO_CAPTURE_YET` sequence 0 to `CAPTURE_RECORDED_LOCAL_ONLY` sequence 1, keeping source journal and signed request immutable, with changed snapshot/event digest, dual signed READs and same witness epoch. Returns **uncommitted math-only candidate**; it never claims a remote CAS, durable external witness or safe GET.

## Synthetic attack and crash tests

- Local captured-ID file rolled back to **before capture**, but signed newer heads retained → **BLOCK LOCAL_CAPTURE_RESTORED_BEHIND_WITNESSES**.
- Capture written locally while signed witness heads still report zero → **BLOCK UNANCHORED_LOCAL_CAPTURE_ADVANCE**, no implied recovery.
- Primary ahead/behind secondary → BLOCK for crash window or rollback. Same sequence with different captured-ID digest → BLOCK fork.
- Source dispatch journal changed after capture, but old signed heads replayed → BLOCK (separate journal witness verification).
- Malicious tenant/policy/nonce/repository pin, downgraded minimum epoch, stale challenge, role swap, signed request digest mismatch, signed fields removed/injected, missing witness, corrupt SQLite row, unexpected route format → BLOCK.
- A replacement caller-supplied **secondary public pin and matching forged signature** can still yield `TWO_SIGNED_CAPTURE_HEADS_MATH_MATCH_UNTRUSTED_NO_NETWORK`; **this is a deliberate counterexample**, not a trust guarantee. Replaying **both** historical witness heads plus an old matching local database can also pass math. Nothing here creates genuine external antirollback.
- Fixture-only no-network test raises if `requests.get`, `requests.post` or the AION provider execution function is called, even on a mathematically valid match.

## Explicit limitations

A true independent witness must be protected by administration and keys that cannot be restored or replaced together with the local PC/journal/captured-ID DB; public pin enrollment/revocation, unpredictable consumed nonces, server-authenticated fresh reads, remote monotonic compare-and-swap and auditable cross-domain crash recovery are all **not implemented**. Nor is a genuine provider response ID proven to have been received or authenticated. An API SDK may have hidden retries; no production transport is integrated or audited here.

Even a production **read-only GET** of a previously known response ID would need explicit network credential policies and TLS/host/redirect controls, and still would not prove payment settlement or exactly-once processing of a prior billable POST. If original ID was never received before crash, no mechanism here invents a safe recovery.

**All runtime authority fields permanently false:** owner presence, public signer keys enrolled, witness freshness, independent antirollback, actual response ID authenticity, externally committed capture CAS, HTTP GET sent, POST sent, automatic retry, actual billing and safe-to-resume.

Core V1 and `main` unchanged. New work stays in Draft branch; **no merge, deploy, account, paid key, installer, cloud service or local host execution**.

## Longer-term safe admission gates

A trusted owner ceremony must enroll four independent roles (#1131) and a protected monotonically increasing trust registry (#1132). Provider signatures/real authenticated receipts need documented supported sources (#1135–#1136). The one-shot dispatch journal (#1133) and capture-ID journal (#1137) must each be **externally protected** before a future read-only adapter can be considered. Real provider SDK retry defaults and transport controls require separate audit; no new services may exceed the combined infrastructure limit of R$200/month without an explicit decision.
