"""A158 synthetic dependency audit corruption tests.

No pip install, network, provider action or real package mutation.
The live pip-audit evidence is gathered separately by CI, not fabricated.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.aion_p0_a158_dependency_audit_lab import (
    ROOT, AuditInputRejected, check_requirements, parse_audit_json,
    streamlit_pillow_constraint, decision,
)

REQ = """streamlit==1.64.0
pandas==3.0.6
numpy==2.5.3
requests==2.34.2
altair==6.3.0
pyarrow==25.0.1
pypdf==6.21.1
cryptography==50.0.2
psycopg[binary]==3.3.6
"""
DIST = ["pillow>=7.1.0,<13", "numpy>=1.23,<3", "requests<3"]
NAMES = ("streamlit","pandas","numpy","requests","altair",
         "pyarrow","pypdf","cryptography","psycopg","pillow")
BASELINE_PINS = {
    "streamlit":"1.64.0","pandas":"3.0.6","numpy":"2.5.3",
    "requests":"2.34.2","altair":"6.3.0","pyarrow":"25.0.1",
    "pypdf":"6.21.1","cryptography":"50.0.2","psycopg":"3.3.6",
}
def sample():
    return {
        "dependencies": [
            {"name":n,"version":("6.21.1" if n=="pypdf"
                                else "1.64.0" if n=="streamlit"
                                else "12.3.0" if n=="pillow" else BASELINE_PINS[n]),
             "vulns":([{"id":f"CVE-2026-TEST-{i}"} for i in range(24)]
                      if n=="pillow" else [])}
            for n in NAMES
        ],
        "fixes": [],
    }


class A158DependencyAdvisoryLAB(unittest.TestCase):
    def payload(self,obj=None):
        return json.dumps(obj or sample())

    def verdict(self,obj=None,req=REQ,rc=1,dist=DIST):
        return decision(req,self.payload(obj),rc,dist)

    def fails(self,obj=None,req=REQ,rc=1,dist=DIST):
        v=self.verdict(obj,req,rc,dist)
        self.assertFalse(v["pypdf_specific_partial_gate_passed"],v)
        self.assertFalse(v["canonical_supply_chain_security_gate_homologated"])
        self.assertFalse(v["worker_allowed"])
        self.assertEqual(v["homologated_p0_count"],0)
        self.assertTrue(v["findings"],v)

    def test_01_valid_partial_patch_has_no_go_despite_clean_pypdf(self):
        v=self.verdict()
        self.assertTrue(v["pypdf_specific_partial_gate_passed"],v)
        self.assertTrue(v["pypdf_patch_audit_clear_in_lab"])
        self.assertEqual(v["remaining_pillow_advisory_count"],24)
        self.assertFalse(v["canonical_supply_chain_security_gate_homologated"])
        self.assertFalse(v["full_quality_homologated"])
        self.assertFalse(v["new_security_exception_created"])
        self.assertFalse(v["provider_custody_verified"])
        self.assertEqual(v["verdict"],"HARD_NO_GO_FULL_SECURITY_AUDIT_UNCLOSED")

    def test_02_expected_direct_package_version_is_exact(self):
        found=check_requirements(REQ)
        self.assertEqual(found["pypdf"],"6.21.1")
        self.assertEqual(found["streamlit"],"1.64.0")

    def test_03_pillow_13_declared_incompatible_in_synthetic_metadata(self):
        result=streamlit_pillow_constraint(DIST)
        self.assertFalse(result["pillow_13_supported_by_current_streamlit_metadata"])
        self.assertIn("<13",result["streamlit_declared_pillow_requirement"])

    def test_04_future_streamlit_pillow_13_support_must_be_reported_truthfully(self):
        result=streamlit_pillow_constraint(["pillow>=12,<14"])
        self.assertTrue(result["pillow_13_supported_by_current_streamlit_metadata"])

    def test_05_legacy_pypdf_pin_rejected(self):
        self.fails(req=REQ.replace("pypdf==6.21.1","pypdf==6.19.0"))

    def test_06_malformed_pypdf_pin_rejected(self):
        self.fails(req=REQ.replace("pypdf==6.21.1","pypdf>=6.21.1"))

    def test_07_unpinned_streamlit_dependency_rejected(self):
        self.fails(req=REQ.replace("streamlit==1.64.0","streamlit"))

    def test_08_fake_pillow_override_rejected(self):
        self.fails(req=REQ+"Pillow==13.0.0\n")

    def test_09_duplicate_pypdf_requirement_rejected(self):
        self.fails(req=REQ+"pypdf==6.21.1\n")

    def test_10_requirements_injected_extra_flags_rejected(self):
        self.fails(req=REQ+"--trusted-host pypi.invalid\n")

    def test_11_empty_requirements_rejected(self):
        self.fails(req="")

    def test_12_bool_requirements_rejected(self):
        self.fails(req=True)

    def test_13_duplicate_audit_json_key_rejected(self):
        with self.assertRaises(AuditInputRejected):
            parse_audit_json('{"dependencies":[],"dependencies":[]}',0)

    def test_14_audit_schema_not_dict_rejected(self):
        with self.assertRaises(AuditInputRejected):
            parse_audit_json('[]',0)

    def test_15_missing_audit_dependencies_rejected(self):
        with self.assertRaises(AuditInputRejected):
            parse_audit_json('{"fixes":[]}',0)

    def test_16_empty_audit_report_rejected(self):
        with self.assertRaises(AuditInputRejected):
            parse_audit_json('{"dependencies":[]}',0)

    def test_17_audit_exit_2_is_not_accepted(self):
        with self.assertRaises(AuditInputRejected):
            parse_audit_json(self.payload(),2)

    def test_18_audit_exit_true_bool_is_not_int(self):
        with self.assertRaises(AuditInputRejected):
            parse_audit_json(self.payload(),True)

    def test_19_audit_exit_zero_with_vulns_rejected(self):
        self.fails(rc=0)

    def test_20_audit_exit_one_with_no_vulns_rejected(self):
        value=sample()
        for item in value["dependencies"]:
            item["vulns"]=[]
        self.fails(obj=value)

    def test_21_pypdf_advisory_not_waived(self):
        value=sample()
        value["dependencies"][6]["vulns"]=[{"id":"CVE-2026-PYPDF-REMAINS"}]
        self.fails(obj=value)
        self.assertIn("PYPDF_STILL_HAS_ADVISORIES",self.verdict(value)["findings"])

    def test_22_unexpected_crypto_vulnerability_not_waived(self):
        value=sample()
        value["dependencies"][7]["vulns"]=[{"id":"GHSA-crypto-unsafe"}]
        self.fails(obj=value)

    def test_23_pypdf_audited_version_must_match_requirement(self):
        value=sample()
        value["dependencies"][6]["version"]="6.19.0"
        self.fails(obj=value)

    def test_24_streamlit_audited_version_must_match_requirement(self):
        value=sample()
        value["dependencies"][0]["version"]="1.66.0"
        self.fails(obj=value)

    def test_25_duplicate_package_with_different_case_rejected(self):
        value=sample()
        value["dependencies"].append({"name":"PyPDF","version":"6.21.1","vulns":[]})
        with self.assertRaises(AuditInputRejected):
            parse_audit_json(self.payload(value),1)

    def test_26_missing_pillow_from_report_rejected(self):
        value=sample()
        value["dependencies"]=[x for x in value["dependencies"] if x["name"]!="pillow"]
        self.fails(obj=value)

    def test_27_missing_pypdf_from_report_rejected(self):
        value=sample()
        value["dependencies"]=[x for x in value["dependencies"] if x["name"]!="pypdf"]
        self.fails(obj=value)

    def test_28_invalid_advisory_id_denied(self):
        value=sample()
        value["dependencies"][-1]["vulns"]=[{"id":""}]
        self.fails(obj=value)

    def test_29_duplicate_advisory_id_denied(self):
        value=sample()
        value["dependencies"][-1]["vulns"]=[{"id":"CVE-X"},{"id":"CVE-X"}]
        self.fails(obj=value)

    def test_30_missing_streamlit_pillow_metadata_denied(self):
        self.fails(dist=[])

    def test_31_malformed_streamlit_requirement_denied(self):
        self.fails(dist=["pillow <> 13"])

    def test_32_bool_streamlit_requires_denied(self):
        self.fails(dist=True)

    def test_33_audit_package_version_empty_denied(self):
        value=sample()
        value["dependencies"][0]["version"]=""
        self.fails(obj=value)

    def test_34_unexpected_audit_dependency_fields_denied(self):
        value=sample()
        value["dependencies"][0]["safe"]=True
        self.fails(obj=value)

    def test_35_extra_unsafe_audit_package_included_not_hidden(self):
        value=sample()
        value["dependencies"].append({
            "name":"unsafe-package","version":"0.0.1",
            "vulns":[{"id":"CVE-2026-MISSED-BY-ALLOWED-TWO"}]
        })
        self.fails(obj=value)

    def test_36_empty_pillow_vulns_with_consistent_zero_code_is_not_a_go(self):
        value=sample()
        for item in value["dependencies"]:
            item["vulns"]=[]
        v=self.verdict(value,rc=0)
        self.assertTrue(v["pypdf_specific_partial_gate_passed"])
        self.assertFalse(v["canonical_supply_chain_security_gate_homologated"])
        self.assertEqual(v["remaining_pillow_advisory_count"],0)
        self.assertEqual(v["verdict"],"HARD_NO_GO_FULL_SECURITY_AUDIT_UNCLOSED")

    def test_37_other_direct_pin_change_rejected(self):
        self.fails(req=REQ.replace("cryptography==50.0.2","cryptography==49.0.0"))

    def test_38_extra_direct_package_rejected(self):
        self.fails(req=REQ+"unreviewed_package==1.0.0")

    def test_39_required_psycopg_extra_removal_rejected(self):
        self.fails(req=REQ.replace("psycopg[binary]==3.3.6","psycopg==3.3.6"))

    def test_40_direct_pin_drift_in_altair_rejected(self):
        self.fails(req=REQ.replace("altair==6.3.0","altair==6.2.0"))

    def test_41_missing_cryptography_in_audit_denied(self):
        value=sample()
        value["dependencies"]=[d for d in value["dependencies"]
                               if d["name"]!="cryptography"]
        self.fails(obj=value)
        self.assertIn("DIRECT_AUDIT_PACKAGE_MISSING:cryptography",
                      self.verdict(value)["findings"])

    def test_42_mismatched_cryptography_audit_version_denied(self):
        value=sample()
        next(d for d in value["dependencies"]
             if d["name"]=="cryptography")["version"]="49.0.0"
        self.fails(obj=value)

    def test_43_missing_pyarrow_in_audit_denied(self):
        value=sample()
        value["dependencies"]=[d for d in value["dependencies"]
                               if d["name"]!="pyarrow"]
        self.fails(obj=value)
        self.assertIn("DIRECT_AUDIT_PACKAGE_MISSING:pyarrow",
                      self.verdict(value)["findings"])

    def test_44_psycopg_pin_drift_rejected(self):
        self.fails(req=REQ.replace("psycopg[binary]==3.3.6",
                                   "psycopg[binary]==3.3.5"))


if __name__ == "__main__":
    unittest.main()
