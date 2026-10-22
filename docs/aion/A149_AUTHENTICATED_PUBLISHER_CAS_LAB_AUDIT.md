# AION P0 A149 — authenticated publisher and one-time challenge (LAB audit)

> **HARD NO-GO. 0/6 P0 homologated.** A149 is an ISOLATED SYNTHETIC
> LAB protocol, NOT a trusted witness or a real provider authorization.
> No merge, deploy, Worker, network, provider, real user/owner signing key
> or external operation.

## Source / evidence / exact test accounting

- Stacked Draft PR [#1433](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1433),
  based on A148 [#1432](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1432).
- Branch: \`lab/aion-p0-a149-authenticated-witness-cas-20261022\`.
- Executable candidate commit: \`2e25ed00e837a0e860c8d3c36f68e3f79027cb79\`.
- Evidence: [Actions #39759407472](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39759407472),
  both **Windows and Ubuntu SUCCESS**, verified logs for exact suites and no skips.
- Counted runner: \`python -B tests/run_aion_a149_counted_lab.py\`.
- Suites: A145 4+12+10 = 26; A146 20+13 = 33; A147 50;
  A148 40; A149 **50**. Cumulative **199 tests per operating system**.
- Realistic scope: only toy isolated SQLite stores + synthetic Ed25519
  keys + subprocess command input; no independent trust/failure domain.

## A149 modeled flow

\`\`\`text
(1) SYNTHETIC OWNER/TEST HARNESS ENROLLMENT, ONCE:
    witness DB initialized with one "publisher_key_id" and Ed25519 public key
    signer private key stored locally; NO production key custody.

(2) CHALLENGE:
    Witness writes cryptographically random 128-bit challenge_id and returns
    its epoch, ledger_id, current sequence and current digest.

(3) SIGNED REQUEST:
    Publisher signs a strictly canonical/domain-separated payload containing
    ledger_id, epoch, publisher_key_id, challenge_id, request_id,
    expected_sequence, expected_digest, next_sequence and next_digest.
    Requests MUST NOT nominate their own trusted public key.

(4) ONE TRANSACTION in the simulated witness SQLite:
    BEGIN IMMEDIATE -> validate pinned publisher key / Ed25519 signature ->
    consume existing unconsumed challenge -> verify epoch, sequence, digest ->
    reject reused request ID -> advance high-water exactly once ->
    write a durable receipt with the request digest -> COMMIT.

(5) LOST ACK / CRASH:
    On uncertain response, use read_receipt(request_id) READ-ONLY.
    It returns a witness Ed25519 signed publication receipt only if committed.
    NO automatic retry, no provider effect inferred, no authorizing action.

(6) RESTART DECISION:
    Previous A146/A147 consistency gate continues to return only
    LAB_HARD_BLOCKED or LAB_QUARANTINE_MANUAL_REVIEW, even on matched signatures.
\`\`\`

## Important successful adversarial checks (A149)

| Control | Modeled positive/negative behavior |
|---|---|
| Pinned publisher Ed25519 key | wrong signing key and mutated envelope rejected |
| Issuer binding | ledger_id, publisher_key_id and epoch mismatch denied |
| Challenge provenance | unknown challenge or challenge mismatched to request denied |
| Challenge one-time consumption | replay rejected after commit, even on new process |
| Request uniqueness | request_id cannot be reused for a subsequent advancement |
| CAS and concurrency | competing same-sequence publishers cannot both advance |
| Atomicity | receipt, consumed challenge and high-water commit together |
| Crash BEFORE commit | no committed receipt or new sequence |
| Crash AFTER commit, response lost | valid signed receipt and new sequence persist |
| Signed publication receipt | request_id, challenge, sequence, digest and request hash bound under witness key |
| Read-only receipt lookup | lookups do not execute publication or provider action |
| LAB and Worker flags | engine only operates with LAB=1, Worker=0, external_execution=0 |
| JSON subprocess boundary | extra fields, duplicate JSON keys and unsigned commands refused |
| A147 local first-intent uncertain | second local intent remains blocked despite matching signed witness |

## Negative proofs / NO-GO blockers

**1. Publisher key pinning is not independently trusted.** In this LAB,
the enrolled publisher key is kept in MUTABLE witness SQLite. A local
operator with write access can replace the key and submit a correctly
signed malicious request. Test 30 intentionally demonstrates this. Real
deployment requires immutable/out-of-band policy pinning plus authenticated
enrollment, revocation and rotation.

**2. Witness freshness is still false under storage rollback.**
Old SQLite snapshots can restore the challenge table, high-water and
receipt absence together. The witness private key can still sign old
state; signature validity is NOT monotonicity or independent time.
A real independent rollback-resistant domain is missing.

**3. Challenge expiration is NOT implemented.** A challenge is random,
durable and one-time but has no TTL or externally attested expiry;
unused challenges can be kept until that ledger head changes. Test 31
exposes this as a negative capability gap. Any production policy must
define time, cancellation, multi-challenge handling and partition
semantics without trusting the local user's clock alone.

**4. Receiver lacks independently authenticated transport and identity.**
Local subprocess stdio is not mutually authenticated external transport.
Owner presence, FIDO2/Windows Hello intent binding, scope/roles, tenant
isolation and multi-publisher authorization remain unproven.

**5. No provider-effect evidence, at-most-once supplier semantics or
reconciliation.** A witness receipt proves only a synthetic CAS commit,
not whether a bank, exchange, remote API or Worker performed any action.
The first external operation must remain UNKNOWN if the acknowledgement
is lost; zero automatic resend.

**6. Cross-storage atomicity is absent.** A local SQLite transaction and
witness SQLite transaction do not share a distributed commit. No claim of
durable external reservation or transaction completion follows from
the current tests.

## Roadmap / rigorous approval criteria

- A150 (LAB candidate): separately pinned authorization policy,
  authenticated enrollment and revocation; bounded challenge lease with
  safe expiry semantics; adversarial epoch/rotation/replay tests.
- Subsequent independent witness design: real separate failure/recovery
  authority; monotonic append-only service or hardware trust root; signed
  challenge and durable counter after power loss / restore / key rotation.
- Authoritative provider reconciliation: signed request ID, exact
  at-most-once reservation, no response-retry inference, trusted
  read-only external effect confirmation.
- Integration gate: full H0 on Windows hardware, restart, recovery,
  owner approval, no self-attestation and independent adversarial review.

**HARD NO-GO; 0/6 P0 homologated.** Keep all Draft PRs unmerged and
all LAB execution offline with synthetic keys and events.
