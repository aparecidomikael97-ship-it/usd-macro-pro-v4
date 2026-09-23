from atlasquant_aion_orchestrator import answer_aion

ADMIN={"system_state":"NORMAL","release_state":"RC_ELIGIBLE","new_entries_allowed":True,"health_reasons":[]}

def test_atlasquant_question_uses_internal_source_of_truth():
 r=answer_aion("Como está o sistema AtlasQuant?",admin_state=ADMIN)
 assert r["route"]=="ATLASQUANT_CONTEXT" and r["source_of_truth"]=="ATLASQUANT"
 assert "NORMAL" in r["answer"]

def test_current_general_question_uses_research_and_requires_sources():
 def web(**kwargs):
  return {"answer":"Informação atualizada","sources":[{"title":"Fonte oficial","url":"https://example.com"}],"researched_at":"2026-09-23T18:00:00+00:00"}
 r=answer_aion("Pesquise a notícia atual sobre tecnologia",admin_state=ADMIN,web_research_adapter=web)
 assert r["route"]=="WEB_RESEARCH" and r["ok"]
 assert r["citations_required"] is True and len(r["sources"])==1

def test_research_adapter_without_sources_fails_validation():
 def web(**kwargs): return {"answer":"sem fontes","sources":[]}
 r=answer_aion("Pesquise a notícia atual",web_research_adapter=web)
 assert r["route"]=="WEB_RESEARCH" and not r["ok"] and "SOURCES_MISSING" in r["reasons"]

def test_general_ai_route_uses_injected_adapter_only():
 def general(**kwargs): return {"answer":"Fotossíntese converte energia luminosa."}
 r=answer_aion("Explique fotossíntese",general_ai_adapter=general)
 assert r["route"]=="GENERAL_AI" and r["ok"] and "Fotossíntese" in r["answer"]

def test_general_ai_absence_is_disclosed_not_fabricated():
 r=answer_aion("Explique fotossíntese")
 assert r["route"]=="GENERAL_AI_UNAVAILABLE" and not r["ok"]

def test_unconnected_youtube_is_explicit():
 r=answer_aion("AION, procure no YouTube macroeconomia",connections={"youtube":False})
 assert r["route"]=="EXTERNAL_PLATFORM" and "ainda não está conectado" in r["answer"]

def test_connected_spotify_write_returns_pending_approval_not_execution():
 r=answer_aion("AION, toque minha playlist no Spotify",connections={"spotify":True})
 assert r["route"]=="EXTERNAL_PLATFORM_CONFIRMATION"
 assert r["confirmation_required"] is True
 assert r["pending_action"]["state"]=="PENDING_APPROVAL"
 assert r["voice_can_authorize_orders"] is False and r["real_orders_enabled"] is False


def test_connected_youtube_read_uses_connector_adapter():
 def connector(**kwargs):
  assert kwargs["provider"]=="youtube" and kwargs["action_class"]=="READ"
  return {"ok":True,"answer":"Encontrei 3 vídeos relevantes."}
 r=answer_aion(
  "AION, procure no YouTube macroeconomia",
  connections={"youtube":True},
  connector_adapter=connector,
 )
 assert r["route"]=="EXTERNAL_PLATFORM_READ" and r["ok"]
 assert "3 vídeos" in r["answer"] and r["source_of_truth"]=="EXTERNAL_PLATFORM"

def test_connected_platform_without_runtime_adapter_is_not_faked():
 r=answer_aion(
  "AION, procure no YouTube macroeconomia",
  connections={"youtube":True},
 )
 assert r["route"]=="EXTERNAL_PLATFORM_ADAPTER_UNAVAILABLE" and not r["ok"]
 assert "ainda não está conectado" in r["answer"]
