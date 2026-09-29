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
