import pathlib
import unittest


ROOT=pathlib.Path(__file__).resolve().parent


class AtlasQuantBasicProLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=(ROOT/"pair_intelligence_v110.py").read_text(encoding="utf-8")

    def test_mode_is_resolved_before_central_details(self):
        mode=self.src.index('_aq_view_mode = str(st.session_state.get("atlasquant_view_mode", "Básico"))')
        details=self.src.index("render_data_confidence(packs, auto)")
        self.assertLess(mode,details)

    def test_data_confidence_is_pro_only(self):
        block='if _is_pro:\n        render_data_confidence(packs, auto)'
        self.assertIn(block,self.src)

    def test_regime_is_captured_for_all_modes(self):
        capture=self.src.index("_regime_result = capture_regime_detector(best)")
        render=self.src.index("render_regime_detector(best, capture_result=_regime_result)")
        basic_return=self.src.index("if not _is_pro:")
        self.assertLess(capture,render)
        self.assertLess(capture,basic_return)

    def test_confluence_and_explain_are_pro_only(self):
        block='if _is_pro:\n        render_confluence_map(best)\n        render_context_explain(best)'
        self.assertIn(block,self.src)

    def test_basic_keeps_safety_event_and_plan(self):
        safety=self.src.index("render_safety_core(")
        event=self.src.index("_event_result = render_next_event")
        plan=self.src.index("render_operational_plan(best)")
        basic_return=self.src.index("if not _is_pro:")
        self.assertLess(event,basic_return)
        self.assertLess(safety,basic_return)
        self.assertLess(plan,basic_return)

    def test_flight_capture_happens_before_basic_return(self):
        capture=self.src.index('_flight_capture = capture_flight_recorder')
        basic_return=self.src.index("if not _is_pro:")
        self.assertLess(capture,basic_return)


if __name__=="__main__":
    unittest.main()
