import unittest

from atlasquant_aion_observability import (
    append_event,
    execution_event,
    is_secret_key,
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

    def test_portuguese_secret_names_and_text_are_redacted(self):
        self.assertTrue(is_secret_key("senha"))
        self.assertTrue(is_secret_key("senha_admin"))
        self.assertTrue(is_secret_key("chave_de_api"))
        self.assertTrue(is_secret_key("segredo"))
        cleaned=redact_text("senha=minha-senha segredo=oculto chave_de_api=valorprivado")
        self.assertNotIn("minha-senha",cleaned)
        self.assertNotIn("oculto",cleaned)
        self.assertNotIn("valorprivado",cleaned)

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

    def test_execution_event_has_correlation_without_secret_payload(self):
        event=execution_event(
            request_id="REQ-1",
            task_id="TASK-2",
            domain="development",
            capability="development.inspect",
            tool="repository.read",
            duration_ms=12.5,
            status="BLOCKED",
            risk="HIGH",
            approved=False,
            fallback="local",
            confidence=42,
            message="token=supersecretvalue",
            error="TimeoutError: api_key=anothersecret",
        )
        self.assertEqual(event["request_id"],"REQ-1")
        self.assertEqual(event["task_id"],"TASK-2")
        self.assertEqual(event["duration_ms"],12.5)
        self.assertEqual(event["approval"],"NOT_APPROVED")
        self.assertNotIn("supersecretvalue",str(event))
        self.assertNotIn("anothersecret",str(event))


if __name__=="__main__":
    unittest.main()
