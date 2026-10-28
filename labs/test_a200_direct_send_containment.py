"""Offline containment proofs; no authority or remote acceptance is simulated."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

def _fake_environment():
    return {"AION_MODEL_PROVIDER":"openai", "OPENAI_API_KEY":"FAKE_LAB_ONLY",
        "AION_OPENAI_FAST_MODEL":"fake-fast", "AION_OPENAI_REASONING_MODEL":"fake-reason",
        "AION_OPENAI_INPUT_USD_PER_MTOK":"1", "AION_OPENAI_OUTPUT_USD_PER_MTOK":"2"}

class _AcceptedThenLostAck:
    def __init__(self): self.calls=0
    def post(self,*a,**k):
        self.calls+=1
        raise RuntimeError("synthetic accepted then lost ack")

def _ask(fake):
    from atlasquant_aion_provider import execute_openai_answer
    return execute_openai_answer("public question",lane="EXTERNAL_FAST",
        budget={"allow_paid":True,"monthly_limit_usd":10}, external_feature_enabled=True,
        request_approved=True,values=_fake_environment(),session=fake)

from atlasquant_aion_provider import execute_openai_answer
from atlasquant_neural_tts import (generate_neural_speech, validate_transcript,
    transcript_cache_key, neural_voice_identity, provider_configured)

ROOT = Path(__file__).resolve().parents[1]

class ContainmentGreen(unittest.TestCase):
    def invoke(self, route, fake):
        if route == 'text':
            result = _ask(fake)
            self.assertEqual(result['state'], 'BLOCKED_SEND_CUSTODY')
            self.assertIs(result['called'], False)
        else:
            with self.assertRaisesRegex(RuntimeError, '^BLOCKED_SEND_CUSTODY:'):
                generate_neural_speech('synthetic public audio', api_key='FAKE_LAB_ONLY')

    def test_missing_custody_and_lost_ack_transport_never_entered(self):
        for route in ('text', 'voice'):
            with self.subTest(route=route):
                fake = _AcceptedThenLostAck()
                with patch('requests.sessions.Session.request', side_effect=AssertionError('NETWORK_FORBIDDEN')), patch('atlasquant_neural_tts.requests.post', fake.post):
                    for _ in range(3):
                        self.invoke(route, fake)
                self.assertEqual(fake.calls, 0)

    def test_concurrent_invocations_zero_send(self):
        for route in ('text', 'voice'):
            fake = _AcceptedThenLostAck()
            with patch('requests.sessions.Session.request', side_effect=AssertionError('NETWORK_FORBIDDEN')), patch('atlasquant_neural_tts.requests.post', fake.post):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(lambda _: self.invoke(route, fake), range(32)))
            self.assertEqual(fake.calls, 0)

    def test_actual_process_death_and_restart_zero_send(self):
        # A forbidden fake SEND would exit 91. Instead containment returns,
        # then the child dies explicitly (92); a fresh interpreter repeats it.
        code = '''
import os, sys
from unittest.mock import patch
from labs.test_a200_direct_send_containment import _ask
from atlasquant_neural_tts import generate_neural_speech
class Forbidden:
    def post(self, *a, **k): os._exit(91)
with patch('requests.sessions.Session.request', side_effect=AssertionError('NETWORK_FORBIDDEN')), patch('atlasquant_neural_tts.requests.post', Forbidden().post):
    if sys.argv[1] == 'text':
        r = _ask(Forbidden())
        assert r['called'] is False and r['state'] == 'BLOCKED_SEND_CUSTODY'
    else:
        try: generate_neural_speech('synthetic public audio', api_key='FAKE_LAB_ONLY')
        except RuntimeError as e: assert str(e).startswith('BLOCKED_SEND_CUSTODY:')
        else: raise AssertionError('TTS escaped containment')
os._exit(92)
'''
        for route in ('text', 'voice'):
            for _ in range(2):
                child = subprocess.run([sys.executable, '-B', '-c', code, route], cwd=ROOT, capture_output=True, text=True, timeout=30)
                self.assertEqual(child.returncode, 92, child.stderr)

    def test_existing_disabled_decisions(self):
        base = dict(prompt='public question', lane='EXTERNAL_FAST', budget={'allow_paid': True, 'monthly_limit_usd': 10}, external_feature_enabled=True, request_approved=True, values=_fake_environment())
        cases = [({'external_feature_enabled': False}, 'BLOCKED_FEATURE_FLAG'),
                 ({'request_approved': False}, 'BLOCKED_APPROVAL'),
                 ({'values': dict(_fake_environment(), AION_MODEL_PROVIDER='offline')}, 'BLOCKED_PROVIDER_CONFIG'),
                 ({'budget': {'allow_paid': False}}, 'BLOCKED_BUDGET')]
        for changes, state in cases:
            with patch('requests.sessions.Session.request', side_effect=AssertionError('NETWORK_FORBIDDEN')):
                result = execute_openai_answer(**dict(base, **changes))
            self.assertEqual(result['state'], state)
            self.assertFalse(result['called'])
        with self.assertRaisesRegex(RuntimeError, 'configurado'):
            generate_neural_speech('public audio', api_key='')

    def test_voice_preflight_and_forged_caller_custody(self):
        from atlasquant_neural_tts import NeuralVoiceConfig
        with patch('requests.post') as post:
            with self.assertRaises(ValueError):
                generate_neural_speech('',api_key='FAKE_LAB_ONLY')
            with self.assertRaises(ValueError):
                generate_neural_speech('public',api_key='FAKE_LAB_ONLY',config=NeuralVoiceConfig(endpoint='https://invalid.example'))
            values=dict(_fake_environment(), SEND_CUSTODY=True, reservation='approved', AION_SEND_ENABLED='true')
            result=execute_openai_answer('public',lane='EXTERNAL_FAST',budget={'allow_paid':True,'monthly_limit_usd':10,'custody':True},external_feature_enabled=True,request_approved=True,values=values)
            self.assertEqual(result['state'],'BLOCKED_SEND_CUSTODY')
        post.assert_not_called()

    def test_pure_local_voice_functions(self):
        with patch('requests.sessions.Session.request', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            self.assertEqual(validate_transcript('  hello  '), 'hello')
            with self.assertRaises(ValueError): validate_transcript('')
            self.assertEqual(transcript_cache_key('hello'), transcript_cache_key(' hello '))
            self.assertNotEqual(transcript_cache_key('hello'), transcript_cache_key('other'))
            self.assertFalse(neural_voice_identity()['browser_speech_fallback'])
            self.assertFalse(provider_configured(''))
            self.assertTrue(provider_configured('FAKE_LAB_ONLY'))

if __name__ == '__main__': unittest.main()
