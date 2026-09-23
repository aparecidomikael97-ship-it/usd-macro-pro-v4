from datetime import datetime,timezone
from atlasquant_admin_voice_profile import admin_voice_profile
from atlasquant_admin_voice_briefing import build_admin_voice_briefing

def admin(state="NORMAL",entries=True):
 return {"system_state":state,"release_state":"RC_ELIGIBLE" if state=="NORMAL" else "BLOCKED",
 "new_entries_allowed":entries,"banner":"OPERACIONAL" if state=="NORMAL" else f"SISTEMA {state}",
 "health_reasons":[]}

def test_voice_profile_is_original_ptbr_and_never_authorizes_orders():
 p=admin_voice_profile()
 assert p["language"]=="pt-BR" and p["voice_identity"]=="ORIGINAL_ATLASQUANT"
 assert p["imitates_public_figure_or_character"] is False
 assert p["voice_can_authorize_orders"] is False and p["real_orders_enabled"] is False

def test_opening_briefing_greets_by_daypart_and_is_ptbr():
 r=build_admin_voice_briefing(admin(),user_name="Mikael",now=datetime(2026,9,23,8,tzinfo=timezone.utc))
 assert r["spoken_text"].startswith("Bom dia, Mikael.")
 assert r["language"]=="pt-BR" and r["auto_play_on_admin_open"] is True

def test_protected_system_is_spoken_as_blocked_not_released():
 a=admin("PROTECTED",False);a["health_reasons"]=["MARKET_DATA_HEARTBEAT_STALE"]
 r=build_admin_voice_briefing(a,user_name="Mikael",now=datetime(2026,9,23,13,tzinfo=timezone.utc))
 text=r["spoken_text"].lower()
 assert "sistema está protegido" in text and "novas entradas estão bloqueadas" in text
 assert r["mode"]=="IMPORTANT_ALERT" and r["voice_can_authorize_orders"] is False

def test_changes_macro_alerts_and_opportunities_are_layered():
 r=build_admin_voice_briefing(admin(),changes_since_last_login=["Quality tests verdes","Radar atualizado"],
 macro_summary=["Dólar com viés macro de alta"],important_alerts=["Evento de alto impacto às 14 horas"],
 opportunities=[{"pair":"EUR/USD","executable":False,"operational_status":"PREPARANDO"}])
 text=r["spoken_text"]
 assert "Desde o seu último acesso" in text and "Resumo de mercado" in text
 assert "Pontos que precisam da sua atenção" in text and "EUR/USD" in text

def test_high_score_never_turns_voice_into_order_authorization():
 r=build_admin_voice_briefing(admin("PROTECTED",False),
 opportunities=[{"pair":"GBP/USD","quality_score":100,"executable":True,"operational_status":"LIBERADO PELO MODELO"}])
 assert r["voice_can_authorize_orders"] is False and r["real_orders_enabled"] is False
 assert "não considera novas entradas autorizadas" in r["spoken_text"]
