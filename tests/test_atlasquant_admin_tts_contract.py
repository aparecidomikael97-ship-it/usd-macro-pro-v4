import pytest
from atlasquant_admin_tts_contract import build_admin_tts_request,validate_admin_tts_response

def test_request_is_original_ptbr_and_non_operational():
 r=build_admin_tts_request("Bom dia, Mikael. Sistema normal.")
 assert r["language"]=="pt-BR" and r["profile_id"]=="ATLAS_VOICE_PT_BR_V1"
 assert r["style"]["identity"]=="ORIGINAL_ATLASQUANT" and r["imitate_person_or_character"] is False
 assert r["voice_can_authorize_orders"] is False and r["real_orders_enabled"] is False

def test_request_is_deterministic_for_same_text_and_mode():
 a=build_admin_tts_request("Atualização do sistema",mode="SYSTEM_UPDATE")
 b=build_admin_tts_request("Atualização   do sistema",mode="SYSTEM_UPDATE")
 assert a["request_id"]==b["request_id"]

def test_invalid_mode_or_empty_text_fails_closed():
 with pytest.raises(ValueError):build_admin_tts_request("")
 with pytest.raises(ValueError):build_admin_tts_request("x",mode="IMITATE_JARVIS")

def test_response_requires_same_request_ptbr_audio_and_original_identity():
 req=build_admin_tts_request("Teste")
 good={"request_id":req["request_id"],"language":"pt-BR","audio_ref":"asset://voice/1","imitated_person_or_character":False}
 assert validate_admin_tts_response(req,good)["ok"]
 bad={**good,"language":"en-US","imitated_person_or_character":True}
 r=validate_admin_tts_response(req,bad)
 assert not r["ok"] and {"LANGUAGE_INVALID","VOICE_IDENTITY_INVALID"}.issubset(set(r["reasons"]))
