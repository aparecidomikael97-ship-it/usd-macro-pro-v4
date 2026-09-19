import atlasquant_support_center as s

def test_support_minimum_ready():
    assert s.support_minimum_ready() is True
    rows=s.support_catalog()
    assert len(rows)>=10
    assert {x["id"] for x in rows}>={"first-steps","app-access","stale-data","paper-trading","pwa-install","security","voice","academy-media","billing","public-launch"}

def test_first_steps_prioritizes_data_and_safety():
    row=s.support_topic("first-steps")
    assert row is not None
    text=" ".join(row["actions"]).lower()
    assert "qualidade dos dados" in text
    assert "safety core" in text
    assert "hard block" in text

def test_support_topic_is_safe_and_actionable():
    row=s.support_topic("security")
    assert row is not None
    text=" ".join(row["actions"]).lower()
    assert "não habilita trading real" in text
    assert "senha" in text or "token" in text

def test_commercial_support_topics_preserve_external_boundaries():
    voice=s.support_topic("voice")
    billing=s.support_topic("billing")
    launch=s.support_topic("public-launch")
    assert voice is not None and "provedor TTS externo" in " ".join(voice["actions"])
    assert billing is not None and "não significa" in " ".join(billing["actions"])
    assert launch is not None and "não equivale a pacote assinado/publicado" in " ".join(launch["actions"])
    joined=" ".join(" ".join(x["actions"]) for x in (voice,billing,launch)).lower()
    assert "ordem real habilitada" not in joined

def test_unknown_support_topic():
    assert s.support_topic("does-not-exist") is None
