import unittest
from datetime import datetime,timezone,timedelta
from atlasquant_data_confidence import Observation,reconcile_numeric

NOW=datetime(2026,9,18,20,0,tzinfo=timezone.utc)
class DataConfidenceTests(unittest.TestCase):
    def obs(self,source,value,minutes=1):
        return Observation(source,value,NOW-timedelta(minutes=minutes))
    def test_two_close_sources_confirm(self):
        r=reconcile_numeric([self.obs("A",100),self.obs("B",100.1)],now=NOW,relative_tolerance=.002,min_sources=2)
        self.assertTrue(r["confirmed"])
    def test_future_observation_is_rejected(self):
        future=Observation("future",100,NOW+timedelta(seconds=1))
        r=reconcile_numeric([future,self.obs("A",100)],now=NOW,min_sources=2)
        self.assertFalse(r["confirmed"]); self.assertIn("future",r["rejected_sources"])
    def test_exact_age_boundary_is_stale(self):
        r=reconcile_numeric([self.obs("A",100,120),self.obs("B",100,1)],now=NOW,max_age_minutes=120,min_sources=2)
        self.assertFalse(r["confirmed"])
    def test_invalid_parameters_fail_closed(self):
        cases=[{"max_age_minutes":float("nan")},{"max_age_minutes":-1},{"absolute_tolerance":-1},{"relative_tolerance":float("inf")},{"min_sources":0},{"min_sources":True}]
        for kw in cases:
            with self.subTest(kw=kw):
                r=reconcile_numeric([self.obs("A",100),self.obs("B",100)],now=NOW,**kw)
                self.assertFalse(r["confirmed"]); self.assertEqual(r["quality"],0.0)
    def test_nonfinite_values_are_rejected(self):
        for bad in (float("nan"),float("inf"),float("-inf")):
            with self.subTest(bad=bad):
                r=reconcile_numeric([self.obs("bad",bad),self.obs("A",100)],now=NOW,min_sources=2)
                self.assertFalse(r["confirmed"]); self.assertIn("bad",r["rejected_sources"])
    def test_single_source_never_confirms_when_two_required(self):
        r=reconcile_numeric([self.obs("A",100)],now=NOW,min_sources=2)
        self.assertFalse(r["confirmed"])
        self.assertIsNone(r["golden_value"])

    def test_disagreement_above_tolerance_has_no_golden_value(self):
        r=reconcile_numeric([self.obs("A",100),self.obs("B",110)],now=NOW,relative_tolerance=.002,min_sources=2)
        self.assertFalse(r["confirmed"])
        self.assertIsNone(r["golden_value"])
        self.assertGreater(r["spread"],r["tolerance"])

if __name__=="__main__": unittest.main()
