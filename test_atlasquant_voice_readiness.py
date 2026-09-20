import unittest

from atlasquant_voice_readiness import (
    voice_contract_ready,
    contextual_voice_contract_ready,
    contextual_voice_requirements,
    voice_readiness,
    voice_requirements,
)

class AtlasQuantVoiceReadinessTests(unittest.TestCase):
    def test_internal_contract_is_complete(self):
        self.assertTrue(voice_contract_ready())
        self.assertEqual(
            {x["id"] for x in voice_requirements()},
            {"explicit-provider","exact-transcript","secrets","manual-action","fail-closed","no-trading-side-effect"},
        )

    def test_provider_is_required_only_for_external_neural_tts(self):
        pending=voice_readiness(False)
        self.assertTrue(pending["contract_ready"])
        self.assertTrue(pending["contextual_contract_ready"])
        self.assertTrue(pending["in_app_voice_ready"])
        self.assertFalse(pending["provider_configured"])
        self.assertFalse(pending["neural_tts_ready"])
        self.assertFalse(pending["voice_ready"])

        ready=voice_readiness(True)
        self.assertTrue(ready["voice_ready"])
        self.assertTrue(ready["neural_tts_ready"])

    def test_contextual_assistant_contract_is_complete(self):
        self.assertTrue(contextual_voice_contract_ready())
        self.assertEqual(
            {x["id"] for x in contextual_voice_requirements()},
            {"context-bound","beginner-advanced","device-speech","text-fallback","question-safety"},
        )

    def test_voice_layer_never_changes_trading(self):
        for provider in (False,True):
            status=voice_readiness(provider)
            self.assertFalse(status["automatic_tts"])
            self.assertFalse(status["microphone_required"])
            self.assertTrue(status["text_fallback"])
            self.assertFalse(status["trading_side_effects"])
            self.assertFalse(status["real_orders_changed"])

    def test_security_requirements_are_explicit(self):
        text=" ".join(x["detail"] for x in voice_requirements()).casefold()
        self.assertIn("tokens e chaves",text)
        self.assertIn("não pode liberar gate",text)
        self.assertIn("ação do usuário",text)

if __name__=="__main__":
    unittest.main()
