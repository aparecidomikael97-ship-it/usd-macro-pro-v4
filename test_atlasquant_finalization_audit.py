from pathlib import Path
import unittest


AUDIT_PATH = Path("docs/continuidade/FINALIZATION_AUDIT_STATUS.md")


class FinalizationAuditSafetyTests(unittest.TestCase):
    def test_audit_keeps_trading_and_release_safety_invariants(self):
        text = AUDIT_PATH.read_text(encoding="utf-8")

        required = (
            "Fail-closed behavior remains a release requirement.",
            "Real broker order execution must remain disabled.",
            "Small samples must not automatically change strategies, gates, or weights.",
            "Credentials and repository/runtime secrets are outside this audit and must not be modified",
            "The application is **not declared production-complete by this document**.",
            "Any failing quality check blocks further promotion until diagnosed and corrected.",
        )
        for statement in required:
            with self.subTest(statement=statement):
                self.assertIn(statement, text)


if __name__ == "__main__":
    unittest.main()
