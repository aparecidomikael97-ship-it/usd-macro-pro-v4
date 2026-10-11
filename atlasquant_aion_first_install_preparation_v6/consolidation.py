"""AION V1-V5 consolidated NO-GO inventory, not a physical Windows collector.

Only reads PUBLIC tracked repository sources when called via CLI. No OS
fingerprinting, privileges, credentials, hardware APIs, network, installers,
actual owner identity, provenance enrollment, external witness or Worker.
Success means checklist consistency, never install readiness.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from atlasquant_aion_first_install_plan_v1 import PHASES
from atlasquant_aion_first_install_preparation.plan import DEPENDENCIES

SCHEMA = "AION_V1_V5_CONSOLIDATION_PHYSICAL_PROTOCOL_V1"
EVIDENCE_MANIFEST = "docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json"
# Each artifact is registered once. The role describes the LIMIT of its
# reference, not a claim of production assurance or independently held data.
REFERENCES = (
    ("V1", "atlasquant_aion_first_install_preparation/ceremony.py", "synthetic_identity_intent"),
    ("V1", "atlasquant_aion_first_install_preparation/windows.py", "synthetic_windows_controls"),
    ("V1", "atlasquant_aion_first_install_preparation/plan.py", "dependency_order"),
    ("V2", "atlasquant_aion_first_install_preparation_v2/webauthn_reference.py", "offline_webauthn_math"),
    ("V2", "atlasquant_aion_first_install_preparation_v2/causal_readback_reference.py", "offline_causal_readback"),
    ("V2", "atlasquant_aion_first_install_preparation_v2/evidence_dossier_reference.py", "synthetic_private_dossier"),
    ("V3", "atlasquant_aion_first_install_preparation_v3/ledger_storage.py", "disposable_credential_ledger_sqlite"),
    ("V3", "atlasquant_aion_first_install_preparation_v3/webauthn_ledger_reference.py", "durable_local_challenge_consumption"),
    ("V4", "atlasquant_aion_first_install_preparation_v4/commitments.py", "signed_state_commitment_fixture"),
    ("V4", "atlasquant_aion_first_install_preparation_v4/signed_anchors.py", "fixture_pin_nonce_signature_review"),
    ("V4", "atlasquant_aion_first_install_preparation_v4/recovery_bridge.py", "read_only_multi_fixture_comparison"),
    ("V5", "atlasquant_aion_first_install_preparation_v5/receipt_admission.py", "disposable_witness_receipt_sqlite"),
    ("V5", "atlasquant_aion_first_install_preparation_v5/epoch_root_reference.py", "mathematical_root_epoch_candidate"),
)
EXPECTED_GATES = frozenset(item for group in PHASES.values() for item in group)
PHYSICAL_STEPS = (
    {"id": "OWNER_APPROVAL_SCOPE", "intent": "Require a separate, explicit owner authorization for a named host, operator, time window and exact read-only actions", "performed": False},
    {"id": "READONLY_WINDOWS_INVENTORY", "intent": "Only after approval, examine Windows edition/build, patching and security capabilities without collecting keys, PIN or biometric material", "performed": False},
    {"id": "SIGNED_INSTALLER_DOCUMENT_REVIEW", "intent": "Only after approval, verify offline candidate artifact signature, publisher and provenance without running the installer", "performed": False},
    {"id": "ISOLATION_RECOVERY_TEST_PROPOSAL", "intent": "Design disposable A/B tenant, ACL, egress and restore experiments; do not run any experiment", "performed": False},
    {"id": "INDEPENDENT_WITNESS_PROCUREMENT_REVIEW", "intent": "Obtain external trust, custody, CAS, immutability, freshness and rollback proofs through a separately approved process", "performed": False},
    {"id": "PRIVACY_FINOPS_RELEASE_REVIEW", "intent": "Require LGPD assessment, complete quote, separate spend and release decisions; no purchase or deployment", "performed": False},
)
BOUNDARY_CONFLICTS = (
    {
      "id": "V3_V5_TWO_LOCAL_SQLITE_LEDGERS",
      "severity": "HIGH_IF_CONNECTED_WITHOUT_ATOMIC_PROTOCOL",
      "review": "V3 credential/challenge ledger and V5 witness receipt ledger are independent lab databases; never claim cross-DB atomicity or automatically bridge a successful ACK."
    },
    {
      "id": "V4_V5_CALLER_OWNED_TRUST_INPUTS",
      "severity": "HIGH",
      "review": "Pinned fixture keys, floor, revocations, timestamps and three process/file labels are not out-of-band root enrollment, institutional custody or trusted freshness."
    },
    {
      "id": "JOINT_ROLLBACK_OF_ALL_LOCAL_ARTIFACTS",
      "severity": "HIGH",
      "review": "A privileged joint restore of ledger, nonce state, signed heads and retained floors can remain self-consistent; an independently administered monotonic anchor is missing."
    },
    {
      "id": "V1_OWNER_SIMULATION_NOT_REAL_IDENTITY",
      "severity": "HIGH",
      "review": "HUMAN_OWNER claims in V1/V2 fixtures and mathematical WebAuthn assertions do not enroll a physical person, FIDO2 credential or Windows device."
    },
)
AUTHORITY_KEYS = (
    "production_trust_verified", "worker_authorized", "remote_witness_configured",
    "independent_custody_verified", "full_quote_brl_verified",
    "provider_approved", "owner_approved_spend", "owner_approved_deploy",
    "automatic_retry_authorized",
)


def review_consolidation(manifest: Any, *, present_artifacts: Any) -> dict[str, Any]:
    """Bounded, public-only report. No possible authority success branch."""
    problems: list[str] = []
    if type(manifest) is not dict:
        manifest = {}
        problems.append("MANIFEST_TYPE_INVALID")
    if (manifest.get("schema") != "AION_EXTERNAL_CHECKPOINT_WITNESS_EVIDENCE_MANIFEST_V1"
        or manifest.get("status") != "HARD_NO_GO"
        or manifest.get("mode") != "NO_AUTHORITY"):
        problems.append("MANIFEST_NO_GO_CONTRACT_MISMATCH")
    for name in AUTHORITY_KEYS:
        if manifest.get(name) is not False:
            problems.append("UNTRUSTED_AUTHORITY_CLAIM:" + name)
    rows = manifest.get("evidence_gates")
    if type(rows) is not list or len(rows) != 20:
        rows = []
        problems.append("EXACT_TWENTY_GATES_REQUIRED")
    known: set[str] = set()
    missing_evidence: list[str] = []
    for row in rows:
        if type(row) is not dict or type(row.get("id")) is not str:
            problems.append("EVIDENCE_ROW_OR_ID_INVALID")
            continue
        identifier = row["id"]
        if identifier not in EXPECTED_GATES or identifier in known:
            problems.append("EVIDENCE_ID_UNKNOWN_OR_DUPLICATE")
            continue
        known.add(identifier)
        if (row.get("state") != "BLOCKED"
            or any(row.get(k) is not None for k in
                   ("evidence_uri", "evidence_sha256", "independent_verifier"))):
            problems.append("UNVERIFIED_GATE_ASSERTION:" + identifier)
        missing_evidence.append(identifier)
    if known != EXPECTED_GATES:
        problems.append("EVIDENCE_COVERAGE_INCOMPLETE")
    if (type(present_artifacts) is not set
        or len(present_artifacts) > 1000
        or any(type(p) is not str for p in present_artifacts)):
        present_artifacts = set()
        problems.append("SOURCE_INVENTORY_INVALID")
    required_paths = {path for _, path, _ in REFERENCES}
    absent = sorted(required_paths - present_artifacts)
    if absent:
        problems.append("REFERENCE_SOURCE_MISSING")
    if len(REFERENCES) != len(required_paths) or len(set(x[2] for x in REFERENCES)) != len(REFERENCES):
        problems.append("ROLE_REGISTRY_DUPLICATION")
    if set(DEPENDENCIES) != EXPECTED_GATES:
        problems.append("DEPENDENCY_REGISTRY_MISMATCH")
    # Static role labels are not code execution tests. Avoid echoing
    # arbitrary manifest values, source paths outside the known registry,
    # credentials, owner identity or candidate host attributes.
    return {
        "schema": SCHEMA,
        "status": "HARD_NO_GO",
        "authority": "NONE",
        "inventory_authorized": False,
        "installation_authorized": False,
        "physical_validation_performed": False,
        "windows_hardware_accessed": False,
        "credentials_or_biometrics_accessed": False,
        "network_called": False,
        "source_provenance_independent": False,
        "external_witness_mathematically_or_institutionally_enrolled": False,
        "worker_authorized": False,
        "merge_or_deploy_authorized": False,
        "spending_approved": False,
        "all_evidence_gates_unresolved": len(EXPECTED_GATES),
        "manifest_known_gate_ids": len(known),
        "manifest_receipts_independently_verified": 0,
        "artifact_source_roles": [
            {"generation": version, "role": role, "source_present": path in present_artifacts}
            for version, path, role in REFERENCES
        ],
        "missing_source_roles": [
            role for _, path, role in REFERENCES if path in absent
        ],
        "four_evidence_phases": [
            {"phase": phase, "gate_ids": list(ids), "evidence_verified": 0}
            for phase, ids in PHASES.items()
        ],
        "boundary_risks": list(BOUNDARY_CONFLICTS),
        "physical_protocol": list(PHYSICAL_STEPS),
        "issues": sorted(set(problems)),
        "next_action": "SEPARATE_OWNER_APPROVAL_OF_READONLY_INVENTORY_SCOPE",
        "explanation": "Source presence and offline tests cannot approve physical inventory, installation or any external trust decision.",
    }


def _repository_sources(root: Path) -> set[str]:
    # Only fixed allowlisted tracked-source paths; no recursive scanning
    # of user files, registry, Windows device, environment or secrets.
    found: set[str] = set()
    for _, path, _ in REFERENCES:
        target = root / path
        if target.is_file() and not target.is_symlink():
            found.add(path)
    return found


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        raw = (root / EVIDENCE_MANIFEST).read_text(encoding="utf-8")
        if len(raw) > 100_000:
            raise ValueError("MANIFEST_OVERSIZE")
        manifest = json.loads(raw)
    except (OSError, ValueError, UnicodeError, TypeError):
        manifest = None
    report = review_consolidation(manifest, present_artifacts=_repository_sources(root))
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    # 0 means preparatory NO-GO manifest consistent; NEVER operational GO.
    return 0 if not report["issues"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
