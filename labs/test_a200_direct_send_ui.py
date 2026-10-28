"""Current contract, separate from the unchanged historical success expectation."""
import contextlib
import unittest
from unittest.mock import Mock, patch

from atlasquant_neural_tts import transcript_cache_key
import importlib.util
from pathlib import Path
# Load only this UI module with a local Streamlit double; do not contaminate
# sys.modules or claim the full application dependency is available.
spec=importlib.util.spec_from_file_location('_audit_voice_ui',Path(__file__).resolve().parents[1]/'atlasquant_neural_voice_ui.py')
ui=importlib.util.module_from_spec(spec)
with patch.dict('sys.modules', {'streamlit':Mock()}):
    spec.loader.exec_module(ui)

class SendIntegrationTests(unittest.TestCase):
    def test_current_text_contract_all_lanes_and_no_default_transport(self):
        from atlasquant_aion_provider import execute_openai_answer
        from labs.test_a200_direct_send_containment import _fake_environment
        with patch('requests.sessions.Session.request', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            for lane in ('EXTERNAL_FAST', 'EXTERNAL_REASONING'):
                r=execute_openai_answer('public question', lane=lane,
                    budget={'allow_paid':True,'monthly_limit_usd':10},
                    external_feature_enabled=True, request_approved=True,
                    values=_fake_environment())
                self.assertEqual(r['state'],'BLOCKED_SEND_CUSTODY')
                self.assertFalse(r['called'])
                self.assertNotIn('answer',r)
                self.assertNotIn('usage',r)

    def render(self, clicked=False, cached=False):
        fake=Mock()
        fake.session_state={}
        fake.button.return_value=clicked
        fake.spinner.return_value=contextlib.nullcontext()
        if cached:
            fake.session_state['aq_neural_audio_test']={'digest':transcript_cache_key('public audio'), 'audio':b'offline-cache'}
        with patch.object(ui,'st',fake), patch.object(ui,'_setting',side_effect=lambda name,default='': 'FAKE_LAB_ONLY' if name=='OPENAI_API_KEY' else default), patch('requests.sessions.Session.request',side_effect=AssertionError('NETWORK_FORBIDDEN')):
            result=ui.render_neural_voice_player('public audio',key='test')
        return result,fake

    def test_tts_click_reports_custody_without_cache_write_or_fallback(self):
        result,fake=self.render(clicked=True,cached=True)
        self.assertEqual(result['state'],'BLOCKED_SEND_CUSTODY')
        self.assertFalse(result['audio_ready'])
        self.assertFalse(result['browser_speech_fallback'])
        self.assertNotIn('aq_neural_audio_test',fake.session_state)
        fake.audio.assert_not_called()

    def test_cached_audio_remains_offline_without_generate_click(self):
        result,fake=self.render(cached=True)
        self.assertEqual(result['state'],'AUDIO_READY')
        fake.audio.assert_called_once_with(b'offline-cache',format='audio/mp3')

    def test_unrelated_error_remains_provider_error(self):
        with patch.object(ui,'generate_neural_speech',side_effect=RuntimeError('synthetic failure')):
            result,fake=self.render(clicked=True)
        self.assertEqual(result['state'],'PROVIDER_ERROR')
        fake.audio.assert_not_called()

    def test_transcript_remains_ready_without_generate_click(self):
        result,fake=self.render()
        self.assertEqual(result['state'],'READY_TO_GENERATE')
        self.assertFalse(result['audio_ready'])
        fake.audio.assert_not_called()

if __name__=='__main__': unittest.main()
