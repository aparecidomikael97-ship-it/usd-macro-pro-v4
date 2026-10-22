"""A159: adversarial package-pair and audit-output no-waiver controls.

All advisory payloads in this suite are synthetic and distinct from live
pip-audit evidence. A passing source test is NEVER a production P0 approval.
"""
from importlib import metadata
import json
from pathlib import Path
import unittest

from tools.aion_p0_a158_dependency_audit_lab import (
    ROOT, AuditInputRejected, check_requirements, parse_audit_json,
    decision, streamlit_pillow_constraint,
)

REQ=(ROOT/"requirements.txt").read_text(encoding="utf-8")
BASE=("streamlit==1.64.0\n"
      "pypdf==6.21.1\n"
      "pandas==3.0.6\nnumpy==2.5.3\nrequests==2.34.2\n"
      "altair==6.3.0\npyarrow==25.0.1\ncryptography==50.0.2\n"
      "psycopg[binary]==3.3.6\n")

def fake_audit(pillow_version="13.0.0",streamlit_version="1.66.1",
               pypdf_version="6.21.1",alerted=None):
    alerted=alerted or {}
    rows=[]
    pinned={
        "streamlit":streamlit_version,"pypdf":pypdf_version,
        "pillow":pillow_version,"pandas":"3.0.6","numpy":"2.5.3",
        "requests":"2.34.2","altair":"6.3.0","pyarrow":"25.0.1",
        "cryptography":"50.0.2","psycopg":"3.3.6",
    }
    for name,version in pinned.items():
        rows.append({"name":name,"version":version,
                     "vulns":[{"id":f"CVE-2026-{name.upper()}-{x}"}
                              for x in range(alerted.get(name,0))]})
    return json.dumps({"dependencies":rows,"fixes":[]})


class A159PinnedSecurityPairLAB(unittest.TestCase):
    def result(self,req=REQ,payload=None,rc=0,requires=None):
        return decision(req,payload if payload is not None else fake_audit(),
                        rc,requires if requires is not None
                        else ["pillow>=9.2.0,<14","numpy>=1.25"])

    def reject(self,req=REQ,payload=None,rc=0,requires=None):
        output=self.result(req,payload,rc,requires)
        self.assertFalse(output["pypdf_specific_partial_gate_passed"],output)
        self.assertTrue(output["findings"],output)
        self.assertIs(output["worker_allowed"],False)
        self.assertIs(output["canonical_supply_chain_security_gate_homologated"],False)
        return output

    def test_01_real_requirements_are_reviewed_security_pair(self):
        r=check_requirements(REQ)
        self.assertEqual(r["streamlit"],"1.66.1")
        self.assertEqual(r["pillow"],"13.0.0")
        self.assertEqual(r["pypdf"],"6.21.1")

    def test_02_real_installed_streamlit_version(self):
        self.assertEqual(metadata.version("streamlit"),"1.66.1")

    def test_03_real_installed_pillow_version(self):
        self.assertEqual(metadata.version("Pillow"),"13.0.0")

    def test_04_real_installed_pypdf_version(self):
        self.assertEqual(metadata.version("pypdf"),"6.21.1")

    def test_05_upstream_metadata_explicitly_accepts_pillow_13(self):
        current=streamlit_pillow_constraint(metadata.requires("streamlit"))
        self.assertTrue(current["pillow_13_supported_by_current_streamlit_metadata"])
        self.assertIn("<14",current["streamlit_declared_pillow_requirement"])

    def test_06_valid_zero_advisories_is_not_owner_approval(self):
        v=self.result()
        self.assertTrue(v["pypdf_specific_partial_gate_passed"],v)
        self.assertEqual(v["remaining_pillow_advisory_count"],0)
        self.assertEqual(v["findings"],[])
        self.assertFalse(v["canonical_supply_chain_security_gate_homologated"])
        self.assertFalse(v["worker_allowed"])
        self.assertFalse(v["automatic_resend_allowed"])
        self.assertFalse(v["provider_custody_verified"])
        self.assertEqual(v["homologated_p0_count"],0)
        self.assertTrue(v["verdict"].startswith("HARD_NO_GO"))

    def test_07_still_reject_old_streamlit_plus_pillow13(self):
        self.reject(req=REQ.replace("streamlit==1.66.1","streamlit==1.64.0"))

    def test_08_still_reject_new_streamlit_plus_vulnerable_pillow(self):
        self.reject(req=REQ.replace("Pillow==13.0.0","Pillow==12.3.0"))

    def test_09_still_reject_new_streamlit_without_explicit_pillow_pin(self):
        self.reject(req=REQ.replace("Pillow==13.0.0\n",""))

    def test_10_still_reject_unreviewed_future_streamlit(self):
        self.reject(req=REQ.replace("streamlit==1.66.1","streamlit==1.66.2"))

    def test_11_still_reject_streamlit_1_65(self):
        self.reject(req=REQ.replace("streamlit==1.66.1","streamlit==1.65.0"))

    def test_12_still_reject_unreviewed_future_pillow(self):
        self.reject(req=REQ.replace("Pillow==13.0.0","Pillow==13.0.1"))

    def test_13_still_reject_major_streamlit_2(self):
        self.reject(req=REQ.replace("streamlit==1.66.1","streamlit==2.0.0"))

    def test_14_still_reject_unfixed_pypdf(self):
        self.reject(req=REQ.replace("pypdf==6.21.1","pypdf==6.19.0"))

    def test_15_still_reject_unbounded_pypdf(self):
        self.reject(req=REQ.replace("pypdf==6.21.1","pypdf>=6.21.1"))

    def test_16_still_reject_unbounded_pillow(self):
        self.reject(req=REQ.replace("Pillow==13.0.0","Pillow>=13"))

    def test_17_still_reject_duplicate_pillow_pins(self):
        self.reject(req=REQ+"pillow==13.0.0\n")

    def test_18_still_reject_unreviewed_direct_dependency(self):
        self.reject(req=REQ+"--extra-index-url https://invalid.example\n")

    def test_19_still_reject_pillow_advisory_reappearance(self):
        v=self.reject(payload=fake_audit(alerted={"pillow":1}),rc=1)
        self.assertIn("PATCHED_PILLOW_HAS_UNRESOLVED_ADVISORIES",v["findings"])

    def test_20_still_reject_pypdf_advisory_reappearance(self):
        v=self.reject(payload=fake_audit(alerted={"pypdf":1}),rc=1)
        self.assertIn("PYPDF_STILL_HAS_ADVISORIES",v["findings"])

    def test_21_still_reject_streamlit_advisory(self):
        self.reject(payload=fake_audit(alerted={"streamlit":1}),rc=1)

    def test_22_still_reject_crypto_advisory(self):
        self.reject(payload=fake_audit(alerted={"cryptography":1}),rc=1)

    def test_23_still_reject_both_pillow_and_pypdf_advisories(self):
        self.reject(payload=fake_audit(alerted={"pillow":2,"pypdf":1}),rc=1)

    def test_24_still_reject_fake_zero_exit_with_cve(self):
        self.reject(payload=fake_audit(alerted={"pillow":1}),rc=0)

    def test_25_still_reject_fake_failure_exit_with_zero_vulns(self):
        self.reject(payload=fake_audit(),rc=1)

    def test_26_still_reject_installed_pillow_mismatch(self):
        self.reject(payload=fake_audit(pillow_version="12.3.0"))

    def test_27_still_reject_installed_streamlit_mismatch(self):
        self.reject(payload=fake_audit(streamlit_version="1.64.0"))

    def test_28_still_reject_installed_pypdf_mismatch(self):
        self.reject(payload=fake_audit(pypdf_version="6.19.0"))

    def test_29_still_reject_false_upstream_streamlit_metadata(self):
        v=self.reject(requires=["pillow>=7.1.0,<13"])
        self.assertIn("UPSTREAM_STREAMLIT_PILLOW13_INCOMPATIBLE",v["findings"])

    def test_30_still_reject_missing_pillow_metadata(self):
        self.reject(requires=["numpy>=1.25.0"])

    def test_31_still_reject_forged_duplicate_pillow_metadata(self):
        self.reject(requires=["pillow>=9.2,<14","pillow<14,>=9.2"])

    def test_32_still_reject_wrong_pillow_13_marker_syntax(self):
        self.reject(requires=["pillow =>13"])

    def test_33_still_reject_malformed_audit_payload(self):
        self.reject(payload="<notjson>")

    def test_34_still_reject_json_duplicate_audit_key(self):
        self.reject(payload='{"dependencies":[],"dependencies":[]}')

    def test_35_still_reject_empty_audit_report(self):
        self.reject(payload='{"dependencies":[]}')

    def test_36_still_reject_missing_streamlit_package(self):
        doc=json.loads(fake_audit())
        doc["dependencies"]=[d for d in doc["dependencies"] if d["name"]!="streamlit"]
        self.reject(payload=json.dumps(doc))

    def test_37_still_reject_missing_pypdf_package(self):
        doc=json.loads(fake_audit())
        doc["dependencies"]=[d for d in doc["dependencies"] if d["name"]!="pypdf"]
        self.reject(payload=json.dumps(doc))

    def test_38_still_reject_missing_pillow_package(self):
        doc=json.loads(fake_audit())
        doc["dependencies"]=[d for d in doc["dependencies"] if d["name"]!="pillow"]
        self.reject(payload=json.dumps(doc))

    def test_39_still_reject_skipped_pillow_audit(self):
        doc=json.loads(fake_audit())
        next(d for d in doc["dependencies"] if d["name"]=="pillow")["skip_reason"]="not-analyzed"
        self.reject(payload=json.dumps(doc))

    def test_40_still_reject_duplicate_pillow_audit_entry(self):
        doc=json.loads(fake_audit())
        doc["dependencies"].append(dict(next(d for d in doc["dependencies"] if d["name"]=="pillow")))
        self.reject(payload=json.dumps(doc))


if __name__=="__main__":
    unittest.main()
