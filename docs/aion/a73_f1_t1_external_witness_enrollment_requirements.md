# A73 — F1/T1 External Source Witness: precise enrollment requirements (NO-GO)

**2026-10-14 — design and lab-only protective code. There is NO witness enrolled here.**

## Why this is necessary
Current `runtime_posture=PASS` asserts only a locally consistent checkpoint, branch policy, payload SHA/digests, and worker namespace. Current GitHub `GET` "CONFIRMED" asserts a successful read/decode; an internally recalculated digest and a GitHub content SHA do **not** establish which external custodian controls the resource, its tenant/workspace identity, the freshest known branch head, or non-rollback. A73 adds a mandatory `INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED` blocker to `activation_readiness_snapshot` so even locally green runtime/CI pulses and fabricated `witness_verified` values cannot produce an operator-facing "READY" stage.

## F1: source ownership and identity (future, not implemented by A73)
A resource-enrollment authority **external to both the mutable runtime checkpoint and the executing worker** must authenticate and pin the exact tuple:

- owner identifier, tenant and workspace identifiers; account identity and account/issuer for any external producer
- canonical GitHub repository numeric ID (not just name), repo owner ID, allowed branch `atlasquant-runtime`, exact path `dados/aion/checkpoint_master.json`
- branch ref at trustworthy observation time; verified current commit OID plus tree/blob identity (GitHub content SHA alone cannot stand in for branch current-head attestation)
- expected checkpoint domain, content digest, version/epoch and monotonic sequence
- witness issuer ID and independently pinned verification key ID/version, validity/not-before/revocation and signature algorithm
- freshness window and replay nonce with independent consumption

An arbitrary key in source files, a local JSON field `source_authenticity_verified=true`, a self-signed receipt, `ADMIN` session, GitHub credentials or the caller's expected tuple **cannot** bootstrap this trust. No public verification key may be accepted from the same claimed witness payload. Enrollment requires HUMAN_OWNER approval and separately verified provider/account/issuer binding.

## T1: antirollback (future, not implemented by A73)
A physically/logically independent witness must maintain a **durable append-only or monotonic high-water mark** for (repo ID, branch, path, owner, tenant, workspace). Each signed response must bind the **same fresh nonce**, exact scope, previous witnessed epoch/sequence/head, new epoch/sequence/head, cryptographic content digest, issued/expires timestamps, and independently validated current GitHub branch head.

A witness receipt can be perfectly signed and still **insufficient** if:
- the witness has no independent custody or if the same caller controls both runtime and purported witness,
- it signs a stale/local observation instead of performing current authenticated branch-head readback,
- the sequence/epoch/head is older, forked, reused, future, or absent,
- a restore/rollback resets witness state or stale head is accepted,
- tenant A presents tenant B's valid receipt,
- nonce/time/signer/key status/revocation/repository identity is unverifiable,
- a provider output is optimistic or has UNKNOWN result without definitive independently verified receipt.

A single current SHA/digest and read-after-write CAS are **not** sufficient. Witness service/out-of-host custody, trust anchor/key custody, read API integrity, failure semantics, restore recovery, offline mode and independent auditor must be selected and tested. Until then, all antirollback/owner-source claims remain FALSE/BLOCKED.

## Required fail-closed safety matrix
1. Wrong repo owner/repo ID, branch, path, tenant, workspace or issuer -> `SOURCE_UNBOUND` before Worker execution.
2. Local checkpoint PASS, self-recomputed digest, fake ADMIN or `witness: VERIFIED` -> `INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED`.
3. Stale, missing, malformed, conflicting, swapped, revoked or untrusted signed evidence -> `PROOF_INVALID`, `STALE` or `REVOKED`, never `READY`.
4. Monotonic epoch/sequence/head mismatch, reused nonce, branch rollback, restore or stale writer -> `ROLLBACK_OR_REPLAY_BLOCKED`.
5. Readback unavailable, UNKNOWN_OUTCOME, timeout or inability to establish independent freshness -> BLOCKED, no auto-retry or automatic clear.
6. Provider/producer account receipt, irreversible external effect and HUMAN_OWNER F2 must have their **own** independent checks. Witness source proof is necessary but not sufficient to dispatch.

## Integration sequence and budget boundaries
1. Keep the A47/A48 effect/CAS hard stops and A73 operator-readiness hard stop.
2. Review a concrete outside trust anchor and current-head/readback custodian (including privacy, exact cost, service availability and independent administrative control). Do not create accounts/subscriptions or spend without explicit owner approval.
3. In a further isolated Draft, implement and independently verify signed F1/T1 records against out-of-band keys with strict domain separation and serialisation, antirollback nonce/high-water marks, atomic durable write semantics, replay/restore tests on Linux and physical Windows under separately approved conditions.
4. Wire source witness gate into actual pre-GET or pre-CAS boundary with threat modeling for TOCTOU, stale reads, branch changes, auth failures and provider outage. Never add a local bypass, magic flag, or mock-positive option.
5. Re-run original Security and full Quality plus original A12/A16 when real ZIPs available; independent physical verification of both witness and owner remains obligatory.

## Status
A73 **does not establish independent witness evidence**. It only fixes a dangerous *readiness false-positive claim*. It intentionally makes historic mock-only `READY_FOR_ADMIN_ARMING` and `READY_FOR_FLAG_ENABLE` expectations obsolete without editing, skipping or waiving their tests. No installation, Worker, Render, secret, TPM, deployment or external payment is authorized. **0/6 P0 homologated; 20/20 HARD NO-GO.**
