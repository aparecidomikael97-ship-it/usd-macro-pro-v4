# AION — Host-Policy Provenance Gate V1 (EXACT ANCHOR, PREPARE ONLY)

**CI-only Draft. No real Windows trust-store changes, no real keys,
no protected host anchor provisioned, no install/merge/deploy.**

## Problem solved at the contract/crypto layer
#1096's owner + independent witness + proposed-root Ed25519 ceremony
received key fingerprints, host/device policy, epoch, prior-root and expected
binary/manifest digests as separate caller-provided arguments. A caller may
supply matching attacker-created values. This is NOT independently sourced
host trust.

This PR introduces a strict host policy snapshot, signed by a **separate**
Ed25519 policy authority, domain-separated from ceremony signatures.

### Required external trust BEFORE consuming any request
The local host must already supply out of band:
- independently pinned policy authority public key + fingerprint;
- *exact* protected policy digest and exact protected policy epoch;
- independently pinned owner registry root public key;
- a trustworthy current time and a durable ceremony nonce store.

None may come from the incoming collector, policy or browser request.
The proposed public key is only data, not a trust anchor.

### Validating the policy
- Canonical, bounded UTF-8 JSON with exact fields and no duplicate fields;
- policy schema/purpose and strict identity/epoch/digest types;
- signed max 24-hour validity, expiration and stale-date checks;
- protected policy epoch must match **exactly**; old policy rejected;
- SHA-256 over domain-separated entire policy raw bytes must equal
  protected digest **exactly**, rejecting forks under same epoch;
- proper genesis/previous policy digest shape and protected collector
  epoch/previous root;
- authoritative signature under separately pinned authority public key;
- independent owner registry root fingerprint and witness public key match
  signed values, and signer roles are distinct.

Only AFTER the host-policy gate passes does this module call #1096.
The #1096 ceremony obtains its expected identity, witness, epoch, prior
collector root and approved binary/manifest **from the signed policy**,
not directly from untrusted claimant fields.

### Deliberately not proven
- Caller parameters named "independently_pinned" are still just parameters.
  Pure code cannot ensure the caller retrieved them from protected Windows
  storage rather than the same attacker that supplied the proposal.
- A protected *exact* current policy digest/epoch still needs a real
  storage design with ACL, recovery, TPM/protected-monotonic-anchor validation,
  rollback/fork handling, durable attestation and explicit owner enrollment.
- Approved binary/manifest digests in policy do NOT prove physical executable
  measurement or physical collector neutrality. This gate separately requires
  external binary and manifest observation digests with strict syntax and exact
  match to the signed approved values. Those measurements must be supplied
  by an independently trusted measurement source; a pure Python function
  cannot authenticate that source or turn synthetic CI measurements into
  actual physical provenance.
- No proof that holder of an Ed25519 private key is a specific human,
  no actual enrollment, and no physical 12/12 #1049, 16/16 #1087 network proofs.
- A coherent synthetic signed snapshot is just a coherent signed snapshot;
  not an independently measured real device. The source must be independently
  established, then audited on real hardware with narrow authorization.

Maximum state:
HOST_ANCHORED_COLLECTOR_CEREMONY_PREPARED_UNTRUSTED

All authority and physical proof booleans stay FALSE:
protected_host_source_independently_verified,
hardware_antirollback_verified, owner_real_identity_enrolled,
collector_root_enrolled_in_production, collector_launch_authorized,
physical_attestation_verified, network_deny_verified, safe_to_resume,
installer_authorized, build_authorized, deploy_authorized,
host_trust_state_modified.

## Follow-up physical requirements (not covered by this approval)
1. Choose protected policy root/anchor custody model separate from collector,
   including owner authentication, rotation, recovery and witness.
2. Separate HUMAN_OWNER approval to enroll any real root or alter Windows trust.
3. Test anchor readback/rollback resistance from an actually protected source,
   crash recovery and unauthorized user denial.
4. Bind physical observer and its trusted collector binary/manifest to 12
   sandbox proof requirements and 16 network surfaces.

No writes to main, Render, Worker, privileged Windows APIs or runtime here.