import atlasquant_support_center as s

def test_support_minimum_ready():
    assert s.support_minimum_ready() is True
    rows=s.support_catalog()
    assert len(rows)>=5
    assert {x["id"] for x in rows}>={"app-access","stale-data","paper-trading","pwa-install","security"}

def test_support_topic_is_safe_and_actionable():
    row=s.support_topic("security")
    assert row is not None
    text=" ".join(row["actions"]).lower()
    assert "não habilita trading real" in text
    assert "senha" in text or "token" in text

def test_unknown_support_topic():
    assert s.support_topic("does-not-exist") is None
