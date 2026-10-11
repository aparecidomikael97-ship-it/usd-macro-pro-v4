import json
from pathlib import Path
import unittest
from atlasquant_aion_first_install_preparation.plan import review_evidence_plan

class ManifestMetadataTests(unittest.TestCase):
    def test_reproduced_invalid_metadata_now_rejected(self):
        path=Path(__file__).resolve().parents[1]/'docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json'
        m=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(review_evidence_plan(m)['state'],'REFERENCE_COLLECTION_PLAN_UNTRUSTED')
        for key,value in [('baseline_pr',True),('baseline_pr',0),('baseline_pr','1184'),('budget_brl_monthly_cap','unbounded'),('budget_brl_monthly_cap',True),('budget_brl_monthly_cap',201),('budget_brl_monthly_cap',-1),('date','not-a-date'),('date','20261010')]:
            with self.subTest(key=key,value=value):
                changed=dict(m);changed[key]=value
                out=review_evidence_plan(changed)
                self.assertEqual(out['state'],'BLOCKED');self.assertEqual(out['unresolved_gate_count'],20)
