import unittest

from atlasquant_content_pipeline import (
    PLATFORM_VARIANTS,
    approval_preflight,
    content_job,
    provider_readiness,
)


class ContentPipelineTests(unittest.TestCase):
    def test_unconfigured_providers_never_claim_generation(self):
        status = provider_readiness()
        self.assertTrue(all(x["state"] == "NOT_CONFIGURED" for x in status["providers"].values()))
        self.assertFalse(status["publishing_configured"])
        self.assertFalse(status["executes_external_call"])

    def test_mikael_voice_needs_provider_and_consent(self):
        self.assertEqual(
            provider_readiness(mikael_voice=True, mikael_consent=False)["providers"]["mikael_voice"]["state"],
            "NOT_CONFIGURED",
        )
        self.assertEqual(
            provider_readiness(mikael_voice=True, mikael_consent=True)["providers"]["mikael_voice"]["state"],
            "CONFIGURED",
        )

    def test_unknown_rights_block_every_processing_and_publication(self):
        job = content_job("Clip autorizado?", source_reference="local://input")
        self.assertTrue(job["rights_review_required"])
        self.assertTrue(job["automatic_download"] is False)
        self.assertTrue(job["automatic_publication"] is False)
        self.assertTrue(all(x["state"] == "BLOCKED" or x["stage"] == "HUMAN_APPROVAL" for x in job["stages"]))
        self.assertFalse(approval_preflight(job, human_approved=True)["allowed"])

    def test_verified_rights_prepare_all_platform_variants_but_do_not_publish(self):
        job = content_job("Vídeo", rights_state="VERIFIED")
        self.assertEqual(len(job["variants"]), len(PLATFORM_VARIANTS))
        self.assertEqual({x["ratio"] for x in job["variants"]}, {"16:9", "9:16"})
        preflight = approval_preflight(job, human_approved=True)
        self.assertTrue(preflight["allowed"])
        self.assertFalse(preflight["publishes"])
        self.assertFalse(job["automatic_publication"])

    def test_human_approval_is_required_even_with_rights(self):
        job = content_job("Vídeo", rights_state="VERIFIED", formats=["TikTok"])
        self.assertEqual([x["platform"] for x in job["variants"]], ["TikTok"])
        self.assertFalse(approval_preflight(job)["allowed"])
        with self.assertRaises(ValueError):
            content_job("")


if __name__ == "__main__":
    unittest.main()
