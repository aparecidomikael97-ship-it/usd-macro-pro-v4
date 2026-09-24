import unittest

from atlasquant_aion_observability import (
    append_event,
    new_event,
    observability_summary,
    redact_text,
)


class AtlasQuantAionObservabilityTests(unittest.TestCase):
    def test_common_secrets_are_redacted(self):
        text="Bearer abcdefghijklmnopqrstuvwxyz token=supersecretvalue sk-abcdefghijklmnop"
        cleaned=redact_text(text)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz",cleaned)
        self.assertNotIn("supersecretvalue",cleaned)
        self.assertNotIn("sk-abcdefghijklmnop",cleaned)
        self.assertIn("[REDACTED]",cleaned)

    def test_event_evidence_is_redacted(self):
        event=new_event(
            "deploy",
            "token=myverysecretvalue",
            severity="WARNING",
            evidence={"authorization":"Bearer abcdefghijklmnopqrstuvwxyz"},
        )
        self.assertNotIn("myverysecretvalue",event["message"])
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz",str(event["evidence"]))

    def test_summary_counts_severity_and_truth(self):
        rows=[]
        rows=append_event(rows,new_event("one","ok",severity="INFO",truth_state="CONFIRMED",created_at="2026-09-23T01:00:00+00:00"))
        rows=append_event(rows,new_event("two","warn",severity="WARNING",truth_state="UNKNOWN",created_at="2026-09-23T01:01:00+00:00"))
        summary=observability_summary(rows)
        self.assertEqual(summary["total"],2)
        self.assertEqual(summary["by_severity"]["WARNING"],1)
        self.assertEqual(summary["by_truth"]["UNKNOWN"],1)
        self.assertEqual(summary["important_recent"][0]["event_type"],"two")


if __name__=="__main__":
    unittest.main()
