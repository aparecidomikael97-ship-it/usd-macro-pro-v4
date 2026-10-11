"""V6 offline consolidation adversarial tests: PASS always means HARD NO-GO."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from atlasquant_aion_first_install_preparation_v6.consolidation import (
    AUTHORITY_KEYS, BOUNDARY_CONFLICTS, EXPECTED_GATES, PHYSICAL_STEPS,
    REFERENCES, _repository_sources, review_consolidation,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json"
SOURCES = {path for _, path, _ in REFERENCES}


class ConsolidationV6Tests(TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def review(self, manifest=None, artifacts=None):
        return review_consolidation(
            self.manifest if manifest is None else manifest,
            present_artifacts=SOURCES if artifacts is None else artifacts,
        )

    def no_go(self, packet):
        self.assertEqual(packet["status"], "HARD_NO_GO")
        self.assertEqual(packet["authority"], "NONE")
        for flag in (
            "inventory_authorized", "installation_authorized",
            "physical_validation_performed", "windows_hardware_accessed",
            "credentials_or_biometrics_accessed", "network_called",
            "source_provenance_independent", "worker_authorized",
            "merge_or_deploy_authorized", "spending_approved",
        ):
            with self.subTest(flag=flag):
                self.assertIs(packet[flag], False)

    def test_actual_manifest_twenty_blocked_and_roles_complete(self):
        out = self.review()
        self.no_go(out)
        self.assertEqual(out["issues"], [])
        self.assertEqual(out["manifest_known_gate_ids"], 20)
        self.assertEqual(out["all_evidence_gates_unresolved"], 20)
        self.assertEqual(out["manifest_receipts_independently_verified"], 0)
        self.assertEqual(len(out["artifact_source_roles"]), len(REFERENCES))
        self.assertTrue(all(a["source_present"] for a in out["artifact_source_roles"]))

    def test_generation_registry_exact_one_role_per_file(self):
        self.assertEqual(set(x[0] for x in REFERENCES), {"V1","V2","V3","V4","V5"})
        self.assertEqual(len({x[1] for x in REFERENCES}), len(REFERENCES))
        self.assertEqual(len({x[2] for x in REFERENCES}), len(REFERENCES))
        self.assertEqual(len(SOURCES), 13)

    def test_four_phases_cover_all_gates_without_duplicating(self):
        p = self.review()["four_evidence_phases"]
        self.assertEqual(len(p), 4)
        ids = [g for phase in p for g in phase["gate_ids"]]
        self.assertEqual(len(ids), 20)
        self.assertEqual(set(ids), EXPECTED_GATES)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(phase["evidence_verified"] == 0 for phase in p))

    def test_false_authorization_cannot_be_set_by_manifest(self):
        for flag in AUTHORITY_KEYS:
            with self.subTest(flag=flag):
                fake = deepcopy(self.manifest)
                fake[flag] = True
                out = self.review(fake)
                self.no_go(out)
                self.assertIn("UNTRUSTED_AUTHORITY_CLAIM:" + flag, out["issues"])

    def test_all_twenty_declared_verified_remain_unverified(self):
        bogus = deepcopy(self.manifest)
        for entry in bogus["evidence_gates"]:
            entry["state"] = "VERIFIED"
            entry["evidence_uri"] = "SECRET_FAKE://REDACT_123"
            entry["evidence_sha256"] = "a" * 64
            entry["independent_verifier"] = "FAKE_OWNER_DEVICE_PRIVATE"
        out = self.review(bogus)
        self.no_go(out)
        self.assertEqual(out["manifest_receipts_independently_verified"], 0)
        self.assertEqual(len([x for x in out["issues"] if x.startswith("UNVERIFIED_GATE_ASSERTION:")]),20)
        blob = json.dumps(out)
        self.assertNotIn("SECRET_FAKE", blob)
        self.assertNotIn("FAKE_OWNER_DEVICE_PRIVATE", blob)

    def test_missing_and_duplicate_evidence_fail_closed(self):
        fake = deepcopy(self.manifest)
        fake["evidence_gates"][-1] = deepcopy(fake["evidence_gates"][0])
        out = self.review(fake)
        self.no_go(out)
        self.assertIn("EVIDENCE_COVERAGE_INCOMPLETE", out["issues"])
        self.assertIn("EVIDENCE_ID_UNKNOWN_OR_DUPLICATE", out["issues"])

    def test_forged_new_gate_does_not_expand_authority(self):
        fake = deepcopy(self.manifest)
        fake["evidence_gates"][0]["id"] = "IMMEDIATE_DEPLOY"
        out = self.review(fake)
        self.no_go(out)
        self.assertIn("EVIDENCE_COVERAGE_INCOMPLETE", out["issues"])

    def test_missing_source_is_reported_without_guessing_code_status(self):
        subset = SOURCES - {"atlasquant_aion_first_install_preparation_v5/receipt_admission.py"}
        out = self.review(artifacts=subset)
        self.no_go(out)
        self.assertIn("REFERENCE_SOURCE_MISSING", out["issues"])
        self.assertIn("disposable_witness_receipt_sqlite", out["missing_source_roles"])

    def test_invalid_manifest_types_and_roles_still_no_go(self):
        for data in (None, [], "", {}, {"status":"GO"}, {"evidence_gates":"ALL_VERIFIED"}):
            with self.subTest(data=str(type(data))):
                packet = review_consolidation(data, present_artifacts=SOURCES)
                self.no_go(packet)
                self.assertTrue(packet["issues"])
        packet=review_consolidation(self.manifest,present_artifacts="EVERYTHING_PRESENT")
        self.no_go(packet)
        self.assertIn("SOURCE_INVENTORY_INVALID",packet["issues"])

    def test_proposal_does_not_contain_executable_steps_or_hardware_claims(self):
        steps = self.review()["physical_protocol"]
        self.assertEqual(steps, list(PHYSICAL_STEPS))
        self.assertTrue(all(step["performed"] is False for step in steps))
        self.assertTrue(all("intent" in step and "id" in step for step in steps))
        self.assertEqual(self.review()["next_action"], "SEPARATE_OWNER_APPROVAL_OF_READONLY_INVENTORY_SCOPE")

    def test_known_two_ledgers_joint_restore_and_custody_risks_are_retained(self):
        ids={risk["id"] for risk in BOUNDARY_CONFLICTS}
        self.assertIn("V3_V5_TWO_LOCAL_SQLITE_LEDGERS",ids)
        self.assertIn("JOINT_ROLLBACK_OF_ALL_LOCAL_ARTIFACTS",ids)
        self.assertIn("V4_V5_CALLER_OWNED_TRUST_INPUTS",ids)

    def test_pure_review_never_connects_or_executes_software(self):
        before = deepcopy(self.manifest)
        with patch("socket.socket.connect", side_effect=AssertionError("NO_NETWORK")), \
             patch("socket.socket.connect_ex", side_effect=AssertionError("NO_NETWORK")), \
             patch("subprocess.run",side_effect=AssertionError("NO_EXEC")), \
             patch("subprocess.Popen",side_effect=AssertionError("NO_EXEC")):
            self.no_go(self.review())
        self.assertEqual(self.manifest,before)

    def test_reader_references_only_allowlisted_source_files(self):
        available=_repository_sources(ROOT)
        self.assertEqual(available,SOURCES)

    def test_static_source_imports_no_windows_probe_network_or_shell(self):
        import atlasquant_aion_first_install_preparation_v6.consolidation as module
        parsed = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imports = [
            item.names[0].name.split(".")[0] if isinstance(item,ast.Import)
            else (item.module or "").split(".")[0]
            for item in ast.walk(parsed) if isinstance(item,(ast.Import,ast.ImportFrom))
        ]
        self.assertFalse({"subprocess","socket","requests","winreg","ctypes","os"} & set(imports))


if __name__=="__main__":
    main()
