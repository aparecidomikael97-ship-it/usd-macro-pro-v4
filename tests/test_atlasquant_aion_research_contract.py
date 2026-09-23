from atlasquant_aion_research_contract import validate_research_response,research_unavailable_message

def test_research_requires_answer_and_valid_source():
 r=validate_research_response({"answer":"Resposta atual","sources":[{"title":"Fonte","url":"https://example.com"}]})
 assert r["ok"] and r["citations_required"] is True and len(r["sources"])==1

def test_research_without_sources_is_rejected():
 r=validate_research_response({"answer":"Sem fonte","sources":[]})
 assert not r["ok"] and "SOURCES_MISSING" in r["reasons"]

def test_invalid_urls_do_not_count_as_sources():
 r=validate_research_response({"answer":"x","sources":[{"title":"x","url":"javascript:alert(1)"}]})
 assert not r["ok"] and r["sources"]==[]

def test_unavailable_message_is_explicit():
 r=research_unavailable_message()
 assert not r["ok"] and "ainda não está conectado" in r["answer"]
