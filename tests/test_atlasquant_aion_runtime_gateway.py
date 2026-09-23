from atlasquant_aion_runtime_gateway import runtime_gateway_status,build_runtime_adapters

class Resp:
 def __init__(self,status_code=200,data=None):
  self.status_code=status_code;self._data=data or {}
 def json(self):return self._data

def test_missing_urls_mean_adapters_not_configured():
 r=runtime_gateway_status({})
 assert not r["general_ai_configured"] and not r["web_research_configured"]
 assert r["credentials_exposed"] is False

def test_production_rejects_plain_http_external_backends():
 env={"ATLASQUANT_ENV":"PRODUCTION","AION_GENERAL_AI_URL":"http://example.com/ai","AION_WEB_RESEARCH_URL":"http://example.com/search"}
 r=runtime_gateway_status(env)
 assert not r["general_ai_configured"] and not r["web_research_configured"]
 assert not r["general_ai_url_valid"] and not r["web_research_url_valid"]

def test_dev_allows_localhost_http_for_local_integration():
 env={"ATLASQUANT_ENV":"DEV","AION_GENERAL_AI_URL":"http://localhost:9999/ai"}
 assert runtime_gateway_status(env)["general_ai_configured"]

def test_general_adapter_sends_token_only_in_header_and_returns_no_secret_metadata():
 calls=[]
 def post(url,**kwargs):
  calls.append((url,kwargs))
  return Resp(200,{"answer":"ok"})
 env={
  "ATLASQUANT_ENV":"PRODUCTION",
  "AION_GENERAL_AI_URL":"https://aion.example.com/ai",
  "AION_RUNTIME_TOKEN":"super-secret",
 }
 pack=build_runtime_adapters(env=env,request_post=post)
 out=pack["general_ai_adapter"](question="oi",memory=[{"role":"user","content":"x"}])
 assert out=={"answer":"ok"}
 headers=calls[0][1]["headers"]
 assert headers["Authorization"]=="Bearer super-secret"
 assert "super-secret" not in str(pack["status"])

def test_research_adapter_requests_sources():
 calls=[]
 def post(url,**kwargs):
  calls.append(kwargs["json"])
  return Resp(200,{"answer":"atual","sources":[{"title":"f","url":"https://example.com"}]})
 env={"AION_WEB_RESEARCH_URL":"https://aion.example.com/search"}
 pack=build_runtime_adapters(env=env,request_post=post)
 out=pack["web_research_adapter"](question="pesquise hoje",memory=[])
 assert out["answer"]=="atual" and calls[0]["require_sources"] is True

def test_http_error_is_fail_closed():
 def post(url,**kwargs):return Resp(503,{})
 env={"AION_GENERAL_AI_URL":"https://aion.example.com/ai"}
 pack=build_runtime_adapters(env=env,request_post=post)
 try:
  pack["general_ai_adapter"](question="x",memory=[])
 except RuntimeError as exc:
  assert "503" in str(exc)
 else:
  raise AssertionError("expected RuntimeError")
