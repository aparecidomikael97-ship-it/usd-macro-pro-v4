from atlasquant_aion_capabilities import aion_capabilities,route_aion_query

def test_aion_identity_and_general_scope_are_official():
 c=aion_capabilities()
 assert c["assistant_name"]=="AION"
 assert c["full_title"]=="AION — Assistente de Voz Inteligente do Atlas Code"
 assert c["language"]=="pt-BR"
 assert c["capabilities"]["general_knowledge"] is True
 assert c["capabilities"]["web_research_when_needed"] is True
 assert c["capabilities"]["atlasquant_context"] is True

def test_aion_never_bypasses_trading_controls():
 c=aion_capabilities()["capabilities"]
 assert c["direct_order_authorization"] is False
 assert c["bypass_gate_or_risk"] is False
 assert c["automatic_production_promotion"] is False
 assert c["financial_transfer"] is False

def test_current_question_routes_to_research_when_available():
 r=route_aion_query("Pesquise as notícias atuais sobre inflação",research_adapter_available=True,atlasquant_context_available=True)
 assert r["route"]=="WEB_RESEARCH" and r["must_cite_sources"] is True

def test_current_question_discloses_when_research_unavailable():
 r=route_aion_query("Qual é a cotação atual?",research_adapter_available=False,atlasquant_context_available=True)
 assert r["route"]=="RESEARCH_UNAVAILABLE" and r["must_disclose_research_unavailable"] is True

def test_atlasquant_question_prefers_internal_context():
 r=route_aion_query("Como está o sistema AtlasQuant agora?",research_adapter_available=True,atlasquant_context_available=True)
 assert r["route"]=="ATLASQUANT_CONTEXT" and r["system_related"] is True

def test_general_non_current_question_routes_to_general_ai():
 r=route_aion_query("Explique fotossíntese",research_adapter_available=False,atlasquant_context_available=False)
 assert r["route"]=="GENERAL_AI"

def test_empty_question_fails_closed():
 r=route_aion_query("",research_adapter_available=True,atlasquant_context_available=True)
 assert r["route"]=="REJECTED" and r["voice_can_authorize_orders"] is False
