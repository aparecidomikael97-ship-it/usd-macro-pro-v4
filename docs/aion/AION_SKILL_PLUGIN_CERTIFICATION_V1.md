# AION Skill / Plugin Certification V1

This contract is offline and non-executing.

It reuses the existing `CapabilityRegistry` and Tool Hub instead of creating a
competing registry. Certification is metadata only: it does not activate a
skill, connector, tool, entitlement, paid provider or external action.

A manifest is checked for:

- stable skill/version identity;
- current-tenant scope only;
- trusted workspace membership;
- registered capabilities and tools;
- role/scope non-expansion;
- declared risk not lower than the highest referenced capability risk;
- exact booleans for network, side effects, approval and rollback;
- explicit cost class;
- secret references that are identifiers, never secret values;
- test evidence;
- provenance verification;
- explicit human review for final CERTIFIED state.

Lifecycle:

`CANDIDATE -> TESTED -> CERTIFIED -> SUSPENDED/REVOKED`

- certification assessment seals the normalized manifest to the trusted
  tenant/workspace and emits both a manifest fingerprint and a
  `record_fingerprint` over the full certification record;
- `SUSPEND` requires an intact CERTIFIED record, exact ADMIN approval and a
  reason;
- `REVOKE` accepts an intact CERTIFIED or SUSPENDED record under the same
  exact administrative gate;
- `REVOKED` is terminal in this transition contract;
- a modified state/evidence payload invalidates `record_fingerprint`;
- cross-tenant/workspace lifecycle replay is blocked.

CERTIFIED never means auto-execute.


## Tool Hub bridge

`atlasquant_aion_skill_tool_bridge.py` connects certification to the existing
Tool Hub preflight without turning certification into authority.

A skill may reach `plan_tool_call` only when:

- the bridge receives an existing sealed certification record, not a raw
  manifest;
- the record state is exactly `CERTIFIED`;
- the full `record_fingerprint` and manifest fingerprint both match;
- the record is bound to the current trusted tenant/workspace;
- sealed test/provenance/human-review evidence remains present;
- the manifest is revalidated against the current Capability Registry and Tool
  Hub so stale certification cannot widen authority after policy drift;
- the requested tool is declared by that exact certified manifest;
- the tool belongs to one of the manifest workspaces;
- connector-backed tools declare `network_required=true`.

A SUSPENDED or REVOKED record stops before Tool Hub, even if its underlying
manifest would still pass a fresh structural assessment.

After that, Tool Hub still independently checks source authority, authenticated
admin posture, Guardian, connector readiness, scope, tests, rollback,
uncertainty, impact and side effects.

A CERTIFIED skill therefore still cannot:

- issue commands merely because it is certified;
- activate a connector;
- execute a tool;
- widen permissions;
- create entitlements;
- enable billing, publication, deployment or real trading.

External AI/tool output remains content, not authority, even when the manifest
itself is certified.
