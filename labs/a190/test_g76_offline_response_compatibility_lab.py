"""G76: offline interpretation is never first-send authority."""
import unittest
from unittest.mock import Mock, patch

from atlasquant_aion_provider import (
    execute_openai_answer, parse_openai_response, provider_config,
    estimate_request_cost, _build_openai_headers,
)
from atlasquant_neural_tts import (
    build_neural_speech_payload, parse_neural_speech_response,
    generate_neural_speech, NeuralVoiceConfig, VOICE_INSTRUCTIONS,
    _build_neural_speech_headers,
)


class G76OfflineResponseCompatibilityLab(unittest.TestCase):
    def setUp(self):
        for target in ("requests.sessions.Session.request", "requests.post",
                       "requests.request", "socket.socket.connect",
                       "socket.socket.connect_ex", "socket.create_connection"):
            guard=patch(target,side_effect=AssertionError("G76_FORBIDDEN_NETWORK"))
            mock=guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(mock.assert_not_called)
        self.values={
            "AION_MODEL_PROVIDER":"openai", "OPENAI_API_KEY":"FAKE_G76_ONLY",
            "AION_OPENAI_FAST_MODEL":"synthetic-fast",
            "AION_OPENAI_REASONING_MODEL":"synthetic-reasoning",
            "AION_OPENAI_INPUT_USD_PER_MTOK":"1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK":"2",
        }
        self.cfg=provider_config(self.values)
        self.estimate=estimate_request_cost("synthetic public text",config=self.cfg)

    def parse(self,response):
        return parse_openai_response(response,config=self.cfg,
            model="synthetic-reasoning",estimate=self.estimate)

    def assert_send_blocked(self):
        transport=Mock()
        result=execute_openai_answer("synthetic public text",
            lane="EXTERNAL_REASONING",budget={"allow_paid":True,"monthly_limit_usd":10},
            external_feature_enabled=True,request_approved=True,
            values=self.values,session=transport)
        self.assertEqual(result["state"],"BLOCKED_FIRST_SEND_AUTHORITY_UNAVAILABLE")
        self.assertFalse(result["called"])
        transport.post.assert_not_called()
        with self.assertRaisesRegex(RuntimeError,"^G75_EXTERNAL_FIRST_SEND_AUTHORITY_UNAVAILABLE$"):
            generate_neural_speech("synthetic public text",api_key="FAKE_G76_ONLY")

    def test_success_json_keeps_usage_truth_and_no_action(self):
        response=Mock(status_code=200)
        response.json.return_value={"id":"offline-fixture", "output":[
            {"content":[{"type":"output_text","text":" First "},
                         {"type":"output_text","text":"Second"}]}],
            "usage":{"input_tokens":100,"output_tokens":50}}
        result=self.parse(response)
        self.assertEqual(result["answer"],"First\nSecond")
        self.assertEqual(result["response_id"],"offline-fixture")
        self.assertEqual(result["usage"]["actual_cost_usd_estimate"],0.0002)
        self.assertEqual(result["truth_state"],"MODEL_OUTPUT_UNVERIFIED")
        for key in ("called","executes_action","real_orders_enabled"):
            self.assertFalse(result[key])
        self.assert_send_blocked()

    def test_text_http_401_does_not_read_sensitive_body(self):
        response=Mock(status_code=401)
        response.json.side_effect=AssertionError("body must not be read")
        result=self.parse(response)
        self.assertEqual(result["state"],"PROVIDER_HTTP_ERROR")
        self.assertEqual(result["http_status"],401)
        self.assertFalse(result["called"])
        self.assertNotIn("FAKE_G76_ONLY",str(result))
        response.json.assert_not_called()
        self.assert_send_blocked()

    def test_invalid_json_payload_and_empty_output_remain_distinct(self):
        for payload,state in (([],"PROVIDER_INVALID_PAYLOAD"),
                              ({},"PROVIDER_EMPTY_OUTPUT")):
            with self.subTest(state=state):
                response=Mock(status_code=200)
                response.json.return_value=payload
                result=self.parse(response)
                self.assertEqual(result["state"],state)
                self.assertFalse(result["called"])
        response.json.side_effect=ValueError("private detail")
        result=self.parse(response)
        self.assertEqual(result["state"],"PROVIDER_INVALID_JSON")
        self.assertNotIn("private detail",str(result))
        self.assert_send_blocked()

    def test_convenience_output_text_is_offline_only(self):
        response=Mock(status_code=200)
        response.json.return_value={"output_text":" offline answer "}
        result=self.parse(response)
        self.assertEqual(result["answer"],"offline answer")
        self.assertFalse(result["called"])
        self.assert_send_blocked()

    def test_audio_success_header_variants_preserve_exact_bytes(self):
        for content_type in ("audio/mpeg", "AUDIO/WAV", "application/octet-stream", ""):
            with self.subTest(content_type=content_type):
                response=Mock(status_code=200,content=b"synthetic-audio",
                              headers={"content-type":content_type})
                self.assertEqual(parse_neural_speech_response(response),b"synthetic-audio")
        self.assert_send_blocked()

    def test_audio_empty_and_wrong_content_type_are_rejected(self):
        for content,content_type,error in ((b"","audio/mpeg","vazio"),
                                          (b"{}","application/json","inesperado")):
            with self.subTest(error=error):
                response=Mock(status_code=200,content=content,
                              headers={"content-type":content_type})
                with self.assertRaisesRegex(RuntimeError,error):
                    parse_neural_speech_response(response)
        self.assert_send_blocked()

    def test_audio_http_401_is_sanitized(self):
        class Unauthorized:
            status_code=401
            @property
            def content(self):
                raise AssertionError("private provider body must not be read")
        with self.assertRaisesRegex(RuntimeError,"HTTP 401") as ctx:
            parse_neural_speech_response(Unauthorized())
        self.assertEqual(str(ctx.exception),"falha do provedor neural (HTTP 401)")
        self.assert_send_blocked()

    def test_text_headers_preserve_exact_historical_data_without_authority(self):
        headers=_build_openai_headers("FAKE_G76_TEXT_ONLY")
        self.assertEqual(headers,{"Authorization":"Bearer FAKE_G76_TEXT_ONLY",
                                  "Content-Type":"application/json"})
        headers["first_send_authorized"]=True
        self.assert_send_blocked()
        self.assertEqual(_build_openai_headers("FAKE_G76_TEXT_ONLY"),
                         {"Authorization":"Bearer FAKE_G76_TEXT_ONLY",
                          "Content-Type":"application/json"})

    def test_tts_headers_preserve_exact_historical_data_without_authority(self):
        headers=_build_neural_speech_headers("FAKE_G76_TTS_ONLY")
        self.assertEqual(headers,{"Authorization":"Bearer FAKE_G76_TTS_ONLY",
                                  "Content-Type":"application/json"})
        headers["first_send_authorized"]=True
        self.assert_send_blocked()
        self.assertEqual(_build_neural_speech_headers("FAKE_G76_TTS_ONLY"),
                         {"Authorization":"Bearer FAKE_G76_TTS_ONLY",
                          "Content-Type":"application/json"})

    def test_configured_tts_payload_exact_fields_speed_and_no_secret(self):
        payload=build_neural_speech_payload("Exact transcript.",
            config=NeuralVoiceConfig(speed=1.25))
        self.assertEqual(payload,{
            "model":"gpt-4o-mini-tts","voice":"cedar","input":"Exact transcript.",
            "instructions":VOICE_INSTRUCTIONS,"response_format":"mp3","speed":1.25})
        self.assertEqual(set(payload),{"model","voice","input","instructions","response_format","speed"})
        self.assertNotIn("FAKE_G76_ONLY",str(payload))
        self.assert_send_blocked()

    def test_payload_is_exact_data_without_send_authority(self):
        payload=build_neural_speech_payload("Exact transcript.")
        self.assertEqual(set(payload),{"model","voice","input","instructions","response_format","speed"})
        self.assertEqual(payload["speed"],0.96)
        self.assertEqual(payload["instructions"],VOICE_INSTRUCTIONS)
        self.assertNotIn("FAKE_G76_ONLY",str(payload))
        self.assertEqual(payload["input"],"Exact transcript.")
        self.assertEqual(payload["model"],"gpt-4o-mini-tts")
        self.assertEqual(payload["voice"],"cedar")
        self.assertEqual(payload["response_format"],"mp3")
        self.assertNotIn("Authorization",str(payload))
        for _ in range(3):
            self.assert_send_blocked()


if __name__=="__main__":
    unittest.main()
