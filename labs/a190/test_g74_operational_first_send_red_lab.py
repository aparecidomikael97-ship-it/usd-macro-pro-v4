"""P0-3 RED characterization: live external transports lack witnessed first-send admission.

Tests are intentionally FAILING against the existing operational boundary.
Only fake transports are used; no provider, HTTP, credentials, funds, or Worker.
Do not reinterpret RED as a release gate that may be waived.
"""
import unittest
from unittest.mock import patch

from atlasquant_aion_provider import execute_openai_answer
from atlasquant_neural_tts import generate_neural_speech


class _AcceptedThenLostAck:
    """Synthetic remote effect occurs, then the response is lost."""

    def __init__(self):
        self.calls = 0

    def post(self, *args, **kwargs):
        self.calls += 1
        raise TimeoutError("G74_SYNTHETIC_ACCEPTED_THEN_ACK_LOST")


def _fake_environment():
    return {
        "AION_MODEL_PROVIDER": "openai",
        "OPENAI_API_KEY": "FAKE_G74_LAB_ONLY",
        "AION_OPENAI_FAST_MODEL": "synthetic-fast",
        "AION_OPENAI_REASONING_MODEL": "synthetic-reasoning",
        "AION_OPENAI_INPUT_USD_PER_MTOK": "1.0",
        "AION_OPENAI_OUTPUT_USD_PER_MTOK": "1.0",
        "AION_OPENAI_MAX_OUTPUT_TOKENS": "100",
    }


def _ask(transport):
    return execute_openai_answer(
        "synthetic public question",
        lane="EXTERNAL_FAST",
        budget={"allow_paid": True, "monthly_limit_usd": 10},
        external_feature_enabled=True,
        request_approved=True,
        values=_fake_environment(),
        session=transport,
    )


class G74UnwitnessedSendRed(unittest.TestCase):
    def test_text_no_reservation_must_block_before_first_post(self):
        transport = _AcceptedThenLostAck()
        result = _ask(transport)
        self.assertEqual(
            transport.calls, 0,
            "G74_TEXT_RED: approved budget is not a first-attempt witness",
        )
        self.assertFalse(result["called"])

    def test_text_lost_ack_must_not_allow_second_post(self):
        transport = _AcceptedThenLostAck()
        first = _ask(transport)
        second = _ask(transport)
        self.assertLessEqual(
            transport.calls, 1,
            "G74_TEXT_REPLAY_RED: no durable UNKNOWN or first-send reservation",
        )
        self.assertNotEqual(second.get("state"), "ANSWER_READY")

    def test_voice_no_reservation_must_block_before_first_post(self):
        transport = _AcceptedThenLostAck()
        with patch("atlasquant_neural_tts.requests.post", transport.post):
            with self.assertRaises(TimeoutError):
                generate_neural_speech("synthetic public audio", api_key="FAKE_G74_LAB_ONLY")
        self.assertEqual(
            transport.calls, 0,
            "G74_VOICE_RED: success-only audio cache is not a reservation",
        )

    def test_voice_lost_ack_must_not_allow_second_post(self):
        transport = _AcceptedThenLostAck()
        with patch("atlasquant_neural_tts.requests.post", transport.post):
            for _ in range(2):
                with self.assertRaises(TimeoutError):
                    generate_neural_speech("synthetic public audio", api_key="FAKE_G74_LAB_ONLY")
        self.assertLessEqual(
            transport.calls, 1,
            "G74_VOICE_REPLAY_RED: same transcript sent twice after lost ACK",
        )


if __name__ == "__main__":
    unittest.main()
