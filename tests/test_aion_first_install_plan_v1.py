"""Offline first-install plan regression. Green means NO-GO is preserved."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from atlasquant_aion_first_install_plan_v1 import (
    AUTHORITY_FLAGS, PHASES, build_first_install_plan,
)
MANIFEST=Path(__file__).resolve().parents[1]/"docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json"

class FirstInstallPlanTests(unittest.TestCase):
    def setUp(self):
        self.source=json.loads(MANIFEST.read_text(encoding="utf-8"))
    def test_actual_manifest_has_four_phases_and_no_go(self):
        plan=build_first_install_plan(self.source)
        self.assertEqual(plan["status"],"HARD_NO_GO")
        self.assertEqual(plan["authority"],"NONE")
        self.assertEqual(plan["integrity"],"CONSISTENT_BLOCKED_MANIFEST")
        self.assertEqual(plan["issues"],[])
        self.assertEqual(plan["evidence_gate_count"],20)
        self.assertEqual(plan["unresolved_gate_count"],20)
        self.assertEqual(len(plan["phases"]),4)
        self.assertEqual(sum(x["required_count"] for x in plan["phases"]),20)
        self.assertFalse(plan["installation_authorized"])
        self.assertFalse(plan["worker_authorized"])
        self.assertFalse(plan["independent_verification_performed"])
    def test_each_phase_never_claims_complete(self):
        for phase in build_first_install_plan(self.source)["phases"]:
            with self.subTest(phase=phase["phase"]):
                self.assertFalse(phase["complete"])
                self.assertEqual(phase["required_count"],phase["blocked_count"])
    def test_pure_function_preserves_input(self):
        m=copy.deepcopy(self.source)
        build_first_install_plan(m)
        self.assertEqual(m,self.source)
    def test_owner_and_deploy_fake_flags_dont_promote(self):
        for key in AUTHORITY_FLAGS:
            with self.subTest(key=key):
                m=copy.deepcopy(self.source)
                m[key]=True
                p=build_first_install_plan(m)
                self.assertEqual(p["status"],"HARD_NO_GO")
                self.assertIn("UNTRUSTED_AUTHORITY_CLAIM:"+key,p["issues"])
    def test_fake_verified_rows_never_unlock_and_receipts_not_disclosed(self):
        m=copy.deepcopy(self.source)
        secret="SECRET_SHOULD_NOT_ECHO_821"
        for row in m["evidence_gates"]:
            row.update({"state":"VERIFIED","evidence_uri":secret,
                        "evidence_sha256":secret,"independent_verifier":secret})
        p=build_first_install_plan(m)
        self.assertEqual(p["status"],"HARD_NO_GO")
        self.assertEqual(p["unresolved_gate_count"],20)
        self.assertFalse(p["installation_authorized"])
        self.assertNotIn(secret,json.dumps(p))
        self.assertEqual(len([i for i in p["issues"] if i.startswith("UNVERIFIED_EVIDENCE_STATUS:")]),20)
    def test_dropped_and_duplicate_gate_invalidates_manifest(self):
        m=copy.deepcopy(self.source)
        m["evidence_gates"][-1]=copy.deepcopy(m["evidence_gates"][0])
        p=build_first_install_plan(m)
        self.assertEqual(p["integrity"],"UNTRUSTED_OR_INCONSISTENT_MANIFEST")
        self.assertTrue(any("DUPLICATE" in issue for issue in p["issues"]))
        self.assertTrue(any("MISSING" in issue for issue in p["issues"]))
    def test_unknown_gate_cannot_grant_scope(self):
        m=copy.deepcopy(self.source)
        m["evidence_gates"][0]["id"]="FAKE_GO_NOW"
        p=build_first_install_plan(m)
        self.assertTrue(any("UNKNOWN_EVIDENCE_ID" in issue for issue in p["issues"]))
        self.assertEqual(p["status"],"HARD_NO_GO")
    def test_empty_malformed_and_untrusted_inputs_fail_closed(self):
        for m in (None,"HUMAN_OWNER",{},[],{"schema":"bad"},{"evidence_gates":"wrong"}):
            with self.subTest(raw=repr(m)):
                p=build_first_install_plan(m)
                self.assertEqual(p["status"],"HARD_NO_GO")
                self.assertEqual(p["authority"],"NONE")
                self.assertEqual(p["unresolved_gate_count"],20)
                self.assertTrue(p["issues"])
    def test_no_network_or_private_io_for_in_memory_plan(self):
        with patch("socket.socket.connect",side_effect=AssertionError("NO_NETWORK")), \
             patch("socket.socket.connect_ex",side_effect=AssertionError("NO_NETWORK")):
            p=build_first_install_plan(self.source)
        self.assertFalse(p["external_side_effects"])
    def test_all_groups_cover_exactly_twenty_nonoverlapping_ids(self):
        all_ids=[x for ids in PHASES.values() for x in ids]
        self.assertEqual(len(all_ids),20)
        self.assertEqual(len(set(all_ids)),20)
        self.assertEqual(set(all_ids),{x["id"] for x in self.source["evidence_gates"]})

if __name__=="__main__":
    unittest.main()
