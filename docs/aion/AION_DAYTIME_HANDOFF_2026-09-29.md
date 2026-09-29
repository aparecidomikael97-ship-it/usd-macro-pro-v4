# AION Core — Daytime Handoff 2026-09-29

## Base

This daytime branch is stacked on PR #335 at:

`c1537ca0ef95973132f658f3a3805ab798fd49ca`

Branch:

`chatgpt/aion-daytime-hardening-v1`

No merge, deploy, production activation, paid provider or real trading is part of this work.

## Changes prepared during daytime

### Exact boolean command gates

`atlasquant_aion_command_orchestrator.py`

- `execute` must be exact boolean True before a local handler runs.
- `authenticated_admin` is forwarded as True only when the caller supplied exact True.
- truthy strings do not grant execution/admin posture.

### Exact readiness in capability planner

`atlasquant_aion_capability_planner.py`

The following evidence now requires exact True:

- market live confirmation;
- social connector readiness;
- marketplace connector readiness;
- production connector readiness;
- broker connector readiness;
- feature flags used by the planner;
- Guardian allowed/requires-approval outputs.

The planner remains non-executing.

### Capability registry hardening

`atlasquant_aion_capabilities.py`

- negative, boolean, textual and non-finite costs are rejected instead of silently becoming zero;
- `requires_confirmation` accepts only exact True;
- malformed feature-flag overrides fail closed;
- external-actions and real-trading flags remain immutable-off in this release.

### Tool Hub authority hardening

`atlasquant_aion_tool_hub.py`

- admin and approval booleans passed to authority/safety checks are exact;
- connector readiness uses exact True;
- ambiguous external-side-effect metadata is treated conservatively;
- tool output remains content, not authority.

### RT19 partial improvement

`atlasquant_aion_memory.py` and `atlasquant_aion_recovery.py`

`requests` is no longer a top-level import. Network dependency is loaded only inside the runtime GitHub read/write functions. Core import tests were extended so memory/recovery can import when `requests` is unavailable.

Business-specific normalization is still lazy and remains a known optional-domain coupling when the business checkpoint section is actually used.

## Tests added/extended

- `test_atlasquant_aion_command_orchestrator.py`
- `test_atlasquant_aion_capability_planner.py`
- `test_atlasquant_aion_capabilities.py`
- `test_atlasquant_aion_tool_hub.py`
- `test_atlasquant_aion_core_independence.py`

Full local suite has NOT yet been run on this branch. Cursor must validate before propagation.

## Verified supply-chain facts for RT20

Official GitHub refs verified on 2026-09-29:

- `actions/checkout@v7` -> `3d3c42e5aac5ba805825da76410c181273ba90b1`
- `actions/setup-python@v7` -> `5fda3b95a4ea91299a34e894583c3862153e4b97`
- `actions/upload-artifact@v4` -> `ea165f8d65b6e75b540449e92b4886f43607fa02`

Do not invent SHAs for other Actions.

The last green #326 Python 3.12 CI resolved these direct runtime packages:

- streamlit 1.64.0
- pandas 3.0.6
- numpy 2.5.3
- requests 2.34.2
- pyarrow 25.0.1

The green supply-chain job resolved:

- pip-audit 2.10.1
- bandit 1.9.4
- cyclonedx-bom 7.4.0

These are evidence of a green baseline, not proof that future upgrades are safe.

## Night implementation order

1. Validate this daytime branch with targeted tests, full discover, compileall and diff-check.
2. Fix any regression before propagating.
3. Merge the validated daytime branch non-destructively into the top of the current Cursor stack.
4. Finish the remaining privilege-widening truthiness audit.
5. Integrate Memory Quarantine through a versioned checkpoint namespace with integrity coverage.
6. Connect existing executor/worker receipts to Action Receipt as an envelope; do not replace child receipts.
7. Connect Model Registry at an orchestration/bridge layer. Do not create a direct router -> registry import because the registry already imports router helpers.
8. Gate worker/orchestrator plans with Loop Governor before work begins.
9. Continue RT19 dependency reduction without a megarefactor.
10. RT20: pin only verified Actions; add reproducible dependency constraints/tool pins and persist the SBOM as an artifact.
11. Only after the above, implement Skill/Plugin Certification reusing CapabilityRegistry and Tool Hub.

## Skill/Plugin certification architecture

Do not create a competing capability registry.

A skill/plugin manifest should reference existing:

- capability ids;
- tool ids;
- workspace ids;
- tenant scope;
- Guardian action;
- risk;
- cost class;
- side effects;
- network requirement;
- secret references by identifier only;
- approval requirement;
- rollback support;
- tests/provenance.

Certification must not activate a connector, widen a permission, create an entitlement or execute a tool.

Suggested lifecycle, only if no equivalent existing state is found:

`CANDIDATE -> TESTED -> CERTIFIED -> SUSPENDED/REVOKED`

Unknown or malformed privilege metadata must fail closed.

## Remaining non-verified items

- full CI on stacked PRs;
- runtime integration of quarantine, receipts, model registry and loop governor;
- concurrent workers;
- partial checkpoint writes on disk;
- operational restore;
- CodeQL;
- full main ruleset/required checks;
- production behavior.

