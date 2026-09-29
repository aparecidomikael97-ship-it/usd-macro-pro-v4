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

`CANDIDATE -> TESTED -> CERTIFIED`

`SUSPENDED` and `REVOKED` are reserved lifecycle states for a later
governance layer. This module does not perform those transitions.

CERTIFIED never means auto-execute.


## Tool Hub bridge

`atlasquant_aion_skill_tool_bridge.py` connects certification to the existing
Tool Hub preflight without turning certification into authority.

A skill may reach `plan_tool_call` only when:

- the manifest state is exactly `CERTIFIED`;
- the requested tool is declared by that exact certified manifest;
- the tool belongs to one of the manifest workspaces;
- connector-backed tools declare `network_required=true`;
- capability/tool/scope/risk checks already passed certification.

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
