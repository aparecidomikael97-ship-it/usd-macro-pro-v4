from datetime import datetime,timezone
import pytest
from atlasquant_aion_memory import append_memory,memory_context,sanitize_metadata

NOW=datetime(2026,9,23,18,tzinfo=timezone.utc)

def test_memory_is_bounded_and_keeps_recent_turns():
 rows=[]
 for i in range(6):
  rows=append_memory(rows,role="user" if i%2==0 else "assistant",text=f"m{i}",now=NOW,max_messages=4)
 assert [x["text"] for x in rows]==["m2","m3","m4","m5"]

def test_memory_redacts_common_secrets():
 rows=append_memory([],role="user",text="teste",metadata={"access_token":"x","nested":{"api_key":"y","topic":"ok"}},now=NOW)
 assert "access_token" not in rows[0]["metadata"]
 assert rows[0]["metadata"]["nested"]=={"topic":"ok"}

def test_memory_context_respects_roles_and_char_budget():
 rows=[
  {"role":"user","text":"abc"},
  {"role":"assistant","text":"def"},
  {"role":"system","text":"nao entra"},
 ]
 ctx=memory_context(rows,max_chars=100)
 assert ctx==[{"role":"user","content":"abc"},{"role":"assistant","content":"def"}]

def test_invalid_memory_inputs_fail_closed():
 with pytest.raises(ValueError):append_memory([],role="system",text="x")
 with pytest.raises(ValueError):append_memory([],role="user",text="")
 with pytest.raises(ValueError):memory_context([],max_chars=20)
