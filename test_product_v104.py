from pathlib import Path
import unittest

try:
    import streamlit  # noqa
except Exception:
    import sys, types
    st = types.ModuleType("streamlit")
    st.session_state = {}
    sys.modules["streamlit"] = st

from product_v104 import choose_ab_variant, history_limit, freshness_by_frequency, HISTORY_MAP, ROADMAP


class ProductV104Tests(unittest.TestCase):
    def test_ab_variant_is_deterministic(self):
        self.assertEqual(choose_ab_variant("abc"), choose_ab_variant("abc"))
        self.assertIn(choose_ab_variant("abc"), ("A", "B"))

    def test_history_limits(self):
        self.assertGreater(history_limit("5 anos", "daily"), history_limit("1 ano", "daily"))
        self.assertEqual(history_limit("1 ano", "monthly"), 13)

    def test_monthly_freshness(self):
        label, dot, age = freshness_by_frequency("2026-08-31", "monthly", "2026-09-14")
        self.assertEqual((label, dot, age), ("ATUAL", "🟢", 14))

    def test_daily_stale(self):
        label, dot, _ = freshness_by_frequency("2026-09-01", "daily", "2026-09-14")
        self.assertEqual((label, dot), ("DESATUALIZADO", "🔴"))

    def test_required_content(self):
        self.assertIn("CPI / IPC", HISTORY_MAP)
        self.assertIn("PIB", HISTORY_MAP)
        self.assertGreaterEqual(len(ROADMAP), 6)

    def test_wireframe_avoids_deprecated_components_html(self):
        src = Path("product_v104.py").read_text(encoding="utf-8")
        self.assertNotIn("components.v1.html", src)
        self.assertIn('st.image(WIREFRAME_SVG.encode("utf-8"), width="stretch")', src)


if __name__ == "__main__":
    unittest.main()
