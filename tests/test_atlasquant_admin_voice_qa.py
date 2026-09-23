from atlasquant_admin_voice_qa import answer_admin_question

ADMIN={"system_state":"PROTECTED","release_state":"BLOCKED","new_entries_allowed":False,
"health_reasons":["MARKET_DATA_HEARTBEAT_STALE"]}

def test_system_question_uses_authoritative_state_and_never_authorizes():
 r=answer_admin_question("Por que o sistema está protegido?",admin_state=ADMIN)
 assert r["intent"]=="SYSTEM" and "PROTECTED" in r["answer"] and "não estão autorizadas" in r["answer"]
 assert r["voice_can_authorize_orders"] is False and r["real_orders_enabled"] is False

def test_changes_question_does_not_invent_history():
 r=answer_admin_question("O que mudou desde meu último acesso?",admin_state=ADMIN,changes=[])
 assert r["intent"]=="CHANGES" and "não há um histórico confiável" in r["answer"]

def test_radar_question_only_reports_supplied_rows():
 r=answer_admin_question("Como está o radar?",admin_state=ADMIN,
 opportunities=[{"pair":"EUR/USD","operational_status":"PREPARANDO"},{"pair":"GBP/JPY","operational_status":"BLOQUEADO"}])
 assert r["intent"]=="RADAR" and "EUR/USD: PREPARANDO" in r["answer"] and "GBP/JPY: BLOQUEADO" in r["answer"]

def test_paper_and_release_are_descriptive_only():
 p=answer_admin_question("Como está o Paper?",admin_state=ADMIN,paper_summary={"state":"PROTECTED","active_count":2,"management_mode":"SAFE_ONLY"})
 assert p["intent"]=="PAPER" and "SAFE_ONLY" in p["answer"]
 rel=answer_admin_question("Podemos publicar em produção?",admin_state=ADMIN)
 assert rel["intent"]=="RELEASE" and "não promove produção" in rel["answer"]

def test_help_fallback_is_bounded():
 r=answer_admin_question("Olá",admin_state=ADMIN)
 assert r["intent"]=="HELP" and "sistema" in r["answer"]
