import unittest

from atlasquant_voice_assistant import (
    assistant_context,
    beginner_script,
    advanced_script,
    classify_question,
    answer_question,
    browser_speech_html,
    browser_mic_assistant_html,
)


def row():
    return {
        "pair":"EUR/USD",
        "action":"VENDA",
        "bias":"VENDA",
        "state":"CONTEXTO VÁLIDO",
        "reason":"USD está mais forte e a estrutura maior está alinhada.",
        "next_action":"Aguardar gatilho válido no M15.",
        "priority":84,
        "quality":78,
        "data_score":92,
        "data_ready":True,
        "h4":"confirma venda",
        "h1":"confirma venda",
        "m15":"aguardando gatilho",
        "w1":"baixista",
        "d1":"baixista",
        "gate":"B",
        "event":"ALTO",
        "movement":"MODERADO · ADR 63%",
        "news":"USD favorecido",
        "target":"SSL 1.16500",
        "pd_zone":"PREMIUM",
        "sweep_type":"BSL",
        "sweep_level":"PDH",
        "ict_read":72,
        "inst_read":81,
        "strength_diff":-18.5,
        "up":["fator contrário de curto prazo"],
        "down":["USD mais forte","H4 confirma venda"],
        "positives":["estrutura coerente"],
        "hard_blocks":[],
        "soft_blocks":["M15 ainda sem gatilho"],
        "blockers":["M15 ainda sem gatilho"],
    }


def macro():
    return {
        "usd_score":64,
        "fed":{"tom":"Restritivo","forca":0.42},
        "event":{"disponivel":True,"evento":"PCE","data_txt":"30/09/2026","impacto":"ALTO"},
    }


class AtlasQuantVoiceAssistantTests(unittest.TestCase):
    def test_beginner_is_short_and_does_not_dump_advanced_stack(self):
        ctx=assistant_context(row(),macro_context=macro())
        text=beginner_script(ctx)
        self.assertIn("EUR/USD",text)
        self.assertIn("favorece baixa",text)
        self.assertIn("não uma garantia",text)
        self.assertNotIn("W1",text)
        self.assertNotIn("Premium",text)
        self.assertLess(len(text),700)

    def test_advanced_explains_macro_technical_liquidity_and_invalidation(self):
        ctx=assistant_context(row(),macro_context=macro())
        text=advanced_script(ctx)
        self.assertIn("Fed: tom Restritivo",text)
        self.assertIn("W1 baixista",text)
        self.assertIn("M15 aguardando gatilho",text)
        self.assertIn("sweep BSL",text)
        self.assertIn("PREMIUM",text)
        self.assertIn("M15 ainda sem gatilho",text)
        self.assertIn("não executa ordens",text)

    def test_question_classifier_handles_requested_use_cases(self):
        cases={
            "Por que esse viés está de venda?":"why",
            "O que pode deixar esse viés errado?":"wrong",
            "Quais fatores estão contra?":"against",
            "Como está o Fed e os juros?":"macro",
            "Como está o FVG e o MSS?":"technical",
            "Onde está a liquidez e o sweep?":"liquidity",
            "Tem notícia importante?":"event",
            "Os dados estão stale?":"data",
            "Qual é o próximo passo agora?":"next",
        }
        for q,expected in cases.items():
            with self.subTest(q=q):
                self.assertEqual(classify_question(q),expected)

    def test_wrong_bias_answer_is_explicitly_uncertain_and_safe(self):
        ctx=assistant_context(row(),macro_context=macro())
        out=answer_question("Será que esse viés pode estar errado?",ctx,mode="Avançado")
        self.assertEqual(out["category"],"wrong")
        self.assertIn("pode estar errado",out["answer"].casefold())
        self.assertIn("não trata esse viés como certeza",out["answer"].casefold())
        self.assertIn("m15 ainda sem gatilho",out["answer"].casefold())
        self.assertFalse(out["real_orders_enabled"])
        self.assertFalse(out["automatic_execution"])
        self.assertFalse(out["changes_model_state"])

    def test_beginner_question_never_turns_into_execution_instruction(self):
        ctx=assistant_context(row(),macro_context=macro())
        out=answer_question("O que eu faço agora?",ctx,mode="Iniciante")
        self.assertIn("leitura do atlasquant",out["answer"].casefold())
        self.assertIn("não uma garantia",out["answer"].casefold())
        self.assertFalse(out["real_orders_enabled"])

    def test_browser_speech_compatibility_shim_never_invokes_device_tts(self):
        html=browser_speech_html('</script><script>alert("x")</script>',key="x")
        self.assertNotIn('</script><script>alert',html)
        self.assertNotIn("speechSynthesis",html)
        self.assertNotIn("SpeechSynthesisUtterance",html)
        self.assertIn("player neural oficial",html)

    def test_browser_speech_shim_explicitly_says_device_voice_is_disabled(self):
        html=browser_speech_html("Teste.",key="profile")
        self.assertIn("Voz do navegador desativada",html)
        self.assertIn("player neural oficial",html)
        self.assertNotIn("Google Português",html)

    def test_browser_mic_has_text_safe_context_and_no_order_api(self):
        bad=row()
        bad["reason"]='</script><script>alert("x")</script>'
        ctx=assistant_context(bad,macro_context=macro())
        html=browser_mic_assistant_html(ctx,key="eurusd")
        self.assertNotIn('</script><script>alert',html)
        self.assertIn("SpeechRecognition",html)
        self.assertNotIn("speechSynthesis",html)
        self.assertNotIn("SpeechSynthesisUtterance",html)
        self.assertNotIn("fetch(",html)
        self.assertNotIn("XMLHttpRequest",html)

    def test_microphone_only_recognizes_and_never_speaks_with_device_voice(self):
        ctx=assistant_context(row(),macro_context=macro())
        html=browser_mic_assistant_html(ctx,key="samevoice")
        self.assertIn("SpeechRecognition",html)
        self.assertIn("player neural",html)
        self.assertNotIn("speechSynthesis",html)
        self.assertNotIn("SpeechSynthesisUtterance",html)

    def test_missing_context_stays_descriptive_not_invented(self):
        ctx=assistant_context({"pair":"USD/JPY","action":"NÃO OPERAR"})
        out=answer_question("Como está o macro?",ctx,mode="Avançado")
        self.assertIn("não disponível",out["answer"].casefold())
        self.assertFalse(out["real_orders_enabled"])


if __name__=="__main__":
    unittest.main()