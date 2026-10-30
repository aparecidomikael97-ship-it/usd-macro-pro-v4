# A297 — Independent verifier contract and incident-reopen veto (LAB)

**HARD NO-GO** for live use and **NO-GO integration**. No Worker,
deployment, live order, provider send, customer data, new paid service,
external signer, trusted root, or canonical P0 homologation. All data and
state here are isolated **in-memory laboratory simulations**.

## Why this follows A296

A296 demonstrated that eight *well-formed but unverified* external-proof
claims, including fake Ed25519-shaped bytes, can never establish owner
authority or authorize a real effect. A297 models the next failure
condition: an incident may be **reopened after** an apparently reviewed
plan. Old approval must not remain usable. Also, a failed ACK leaves the
effect's outcome UNKNOWN rather than authorizing retry.

This is a coordinator model, **not** a real independent verifier. Its
in-memory incident journal has no off-host custodian and can be reset by
the host. No production AION guard uses it.

## Fail-closed states

| Local state | Trigger | Behavior |
| --- | --- | --- |
| `TRUST_ROOT_ABSENT` | New local gate; no external root | All effect requests denied |
| `INCIDENT_OPEN` | A unique incident ID is opened/reopened | Generation increments; old plans invalidated |
| `ACK_UNCERTAIN` | A specific intent loses outcome confirmation | Sticky veto; ZERO_AUTO_RESEND |
| Fresh instance after reset | Local state lost | Still no external authority, never GO |

The coordinator keeps only research metadata: current incident,
generation, local epoch note, uncertain outcome flag, and in-memory
journal. Even a duplicated incident event cannot silently increment a
generation; it is recognized as replay.

## Exact recovery-plan contract

A synthetic plan contains:

- `incident_id` and `incident_generation` matching the latest reopened event;
- new 64-hex epoch and bound intent digest;
- fresh 32-hex nonce and short expiry window;
- an A296 evidence pack, validated structurally but never considered
  independently authenticated.

Any stale ID/generation, missing field, expired plan, malformed digest,
or invalid evidence pack is refused.

**Important:** A validly shaped A296 pack containing all eight fake
attestations is ALSO refused with
`STRUCTURAL_EVIDENCE_NOT_EXTERNAL_AUTHORITY`, with
**8 syntactic / 0 authenticated** obligations.

An ACK-uncertain state takes precedence over subsequent recovery reviews
and incident reopening. Neither a new plan nor a duplicate submission
can convert unknown outcome into safe resend.

## Real external-verifier interface still missing

Future independently controlled verification will require all of the
following before a real GO could even be considered:

1. A trusted independently provisioned owner identity and separate
   custodian identity.
2. Public-key validation against roots outside AION host control.
3. A durable off-host signed incident/epoch and nonce log.
4. Identity- and intent-bound revocation after **every** incident
   reopening, with protected recovery authority.
5. Atomic linkage of owner approval, business effect, native SQLite
   VFS/FD, provider response and uncertain ACK handling.
6. Canonical P0 validation and independent review.

No such roots, services or real credentials are configured by A297.
No Boolean, fake signature, reset local journal or all-green CI can
substitute for them. The model intentionally returns HARD NO-GO on
**every** path capable of dispatching a real effect.

## Tests

- Local epoch never grants real authority.
- A unique incident reopening increments the generation and invalidates
  an older syntactically complete plan.
- Eight fake A296 attestations remain unverified and refused.
- Lost ACK remains sticky after a second incident reopening.
- Resetting the local model does not create a trusted root.
- Invalid identifiers, malformed recovery plan, stale epochs/generations,
  expired or forged evidence, and duplicate event IDs are denied.

```bash
python -m unittest -v labs.test_a297_incident_reopen_verifier_gate_lab
python -m unittest -v labs.test_a296_external_authority_evidence_contract_lab
python -m unittest -v labs.test_a295_dual_local_authority_contract_lab
python -m unittest -v labs.test_a294_volatile_witness_sim_lab
python -m unittest -v labs.test_a293_host_sqlite_boundary_lab
python -m unittest -v labs.test_a292_staged_chat_write_inventory_lab
python -m unittest -v labs.test_a291_chat_write_gate_commit_fence_lab
python -m unittest -v labs.test_a290_sqlite_local_write_gate_lab
```

GitHub Actions runs the A297 and A296–A290 LAB suites on standard public
Ubuntu/Windows Python 3.12 runners. All production routes remain
untouched; no new packages or subscriptions.

**Verdict:** GO-LAB on green regression only. **HARD NO-GO operation,
0/6 P0 homologated, ZERO_AUTO_RESEND.**
