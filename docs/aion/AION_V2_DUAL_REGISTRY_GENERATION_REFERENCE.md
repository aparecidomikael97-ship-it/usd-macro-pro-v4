# AION V2 — dual-signed key-registry generation checkpoint (reference V1)

**09 October 2026.** Parent: Draft #1131 on #1130–#1119. **Security posture: NO-GO** for owner enrollment, paid provider calls, Cloudflare/AWS activation, merge, deploy or installer.

## Specific risk after #1131

The four-role Ed25519 roster in #1131 checks the exact signature, owner-approved rotation and cumulative public-key revocation set. But its `expected_previous_roster`, approved owner public key and generation are **caller supplied**. A privileged attacker could restore a previous key-registry record, resurrect a revoked collector/witness key or present a stale generation to the model gateway. Signature math alone cannot distinguish a legitimate previous generation from a restored one.

## Proposed mathematical protocol

`atlasquant_aion_v2_registry_dual_generation_reference.py` defines domain-separated signed READs for **both** previously enrolled witness and anchor roles, each bound to:

- full owner / tenant / workspace and a distinct challenge nonce supplied by the verifier;
- independently pinned signer key ID, signed minimum accepted registry epoch and reported registry epoch;
- strictly increasing roster generation, exact `roster_sha256`, `previous_roster_sha256`;
- the hash of the **cumulative, canonical, sorted revoked public-key fingerprint set**, not just the currently active four keys.

The verifier uses `authority_roster` as a **separate previous trust input** and extracts the primary/secondary signer pins from it, never opportunistically from the proposed new untrusted roster. It checks signed challenges and exact protocol schemas, rejects signer substitution, key reuse, malformed key roles/domains and old revoked key activation. It compares the independent head attestations and separately compares the locally loaded roster.

| Case | Simulated verdict |
|---|---|
| Both signed heads and local roster exactly agree | `REGISTRY_TWO_SIGNED_GENERATIONS_MATCH_MATH_ONLY_UNTRUSTED` |
| Primary generation behind second anchor | BLOCK `PRIMARY_REGISTRY_ROLLBACK` |
| Primary generation ahead before second anchor acknowledgment | BLOCK `PRIMARY_REGISTRY_AHEAD_OF_SECOND_ANCHOR` |
| Same generation, different roster/revocation digest | BLOCK `SAME_GENERATION_REGISTRY_FORK` |
| Local registry behind both heads | BLOCK `LOCAL_REGISTRY_ROLLBACK_BEHIND_SIGNED_HEADS` |
| Local registry ahead / mismatched key or revocation set | BLOCK; no automatic reconciliation |
| Missing witness, stale nonce, role-swapped signature, lower signed epoch | BLOCK |

`review_anchored_rotation_preflight` first verifies the **PREVIOUS roster** matches **BOTH** signed head fixtures, then runs #1131 four-role verification of the new generation, prior-owner approval, new role-specific proof of possession and mandatory cumulative revocations. The result is **an uncommitted preflight candidate only**. This reference never writes to either witness nor updates any actual identity or key registry.

## Critical limitations and deliberate counterexamples

**No independent trust has been created.** The claimed trusted `authority_roster`, test nonce, minimum epoch and both signatures are supplied by CI/caller; no FIDO2/Windows Hello enrollment, physical owner presence, protected trust root, trusted clock, network authentication, challenge consumption or protected signers.

Two mathematically valid signatures are not independent if one attacker controls both signing keys, pins, fake heads or Cloudflare/AWS administrative accounts. The tests deliberately prove that a fully restored set of **both** old heads plus the old local roster can pass math again; a forged genesis root with forged witness and anchor public pins can also pass. A genuinely separate monotonic **protected trust generation floor** is required to reject that attack. Not implemented.

There is **no atomic cross-cloud registry generation transaction**. If the primary witness advanced and the second did not, block all model dispatch until separately reviewed recovery; never silently roll back either signer, auto-upgrade secondary from local data or infer that a paid API call never happened. New key roles only become active after both independently verified commit receipts and revocation propagation — not simply when this reference reports a valid rotation proposal.

A production trust registry requires independent enrollment and custody of genuine HUMAN_OWNER / COLLECTOR / PRIMARY_WITNESS / SECONDARY_ANCHOR keys, protected previous owner root and monotonic generation, distributed CAS with durable revocation acknowledgments, true fresh authenticated READ with unpredictable consumed nonces and reliable unknown-outcome reconciliation. It must be designed within the **R$200/month whole-system infrastructure budget** and must receive explicit owner authorization before provisioning or any paid service.

## CI

Synthetic Ed25519 fixtures and GitHub-hosted Windows/Linux only, rerun of #1131 key proof/revocation suite and prior two-head CAS/nonce/request binding/provider regressions. Tests include local-registry restore with newer signed heads, primary/secondary behind/ahead, same-generation fork, changed revocations, owner key rotation requiring old owner, forged initial owner root, stale challenge, missing head, and cases where both heads and registry are restored together.

**All real authority flags are permanently FALSE in this reference:** no owner identity or presence verified, no trust registry write, no cloud service, no paid model call, no billing, no independent antirollback, no installer and no safe-to-resume.

**No merge, no deploy, no Windows physical device actions, no secrets or keys enrolled.**
