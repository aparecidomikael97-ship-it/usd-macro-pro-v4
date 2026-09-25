from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from atlasquant_aion_learning import new_learning_episode, settle_learning_episode
from atlasquant_aion_memory import default_checkpoint, ensure_operating_checkpoint, update_wisdom_checkpoint
from atlasquant_aion_wisdom import (
    candidate_from_learning_episode,
    new_wisdom_entry,
    normalize_wisdom_entry,
    search_wisdom,
    upsert_wisdom_entry,
    wisdom_digest,
    wisdom_review_state,
    wisdom_summary,
)


def test_confirmed_wisdom_requires_evidence():
    with pytest.raises(ValueError):
        new_wisdom_entry(
            "Fonte",
            "Afirmação forte",
            truth_state="CONFIRMED",
            confidence_pct=90,
        )


def test_normalizer_downgrades_unsupported_confirmed_claim():
    row = {
        "topic": "Sem fonte",
        "insight": "Não pode continuar CONFIRMED sem evidência.",
        "truth_state": "CONFIRMED",
        "confidence_pct": 99,
        "created_at": "2026-09-25T12:00:00+00:00",
    }
    out = normalize_wisdom_entry(row)
    assert out["truth_state"] == "UNKNOWN"
    assert out["automatic_rule_change"] is False
    assert out["real_orders_enabled"] is False


def test_learning_episode_becomes_review_candidate_not_rule():
    episode = new_learning_episode(
        "USD após CPI",
        prediction="USD_UP",
        confidence_pct=70,
        evidence_refs=["calendar:cpi-1"],
        model_version="AION-test",
    )
    settled = settle_learning_episode(
        episode,
        actual_outcome="USD_UP",
        outcome_note="Resultado observado.",
        settled_at="2026-09-25T12:00:00+00:00",
    )
    candidate = candidate_from_learning_episode(
        settled,
        created_by="ADMIN",
    )
    assert candidate["truth_state"] == "INFERENCE"
    assert candidate["manual_review_required"] is True
    assert candidate["automatic_promotion"] is False
    assert candidate["source_episode_ids"] == [settled["episode_id"]]


def test_review_due_and_summary():
    now = datetime(2026, 9, 25, 15, tzinfo=timezone.utc)
    past = (now - timedelta(days=1)).isoformat()
    future = (now + timedelta(days=30)).isoformat()
    due = new_wisdom_entry(
        "Macro",
        "Revisar esta lição.",
        truth_state="INFERENCE",
        evidence_refs=["ref:1"],
        review_due_at=past,
        created_at="2026-09-20T00:00:00+00:00",
    )
    current = new_wisdom_entry(
        "Segurança",
        "Guardian continua bloqueando ação automática.",
        truth_state="CONFIRMED",
        evidence_refs=["repo:test"],
        review_due_at=future,
        created_at="2026-09-20T00:00:01+00:00",
    )
    assert wisdom_review_state(due, now=now.isoformat()) == "DUE"
    assert wisdom_review_state(current, now=now.isoformat()) == "CURRENT"
    summary = wisdom_summary([due, current], now=now.isoformat())
    assert summary["review_due"] == 1
    assert summary["by_truth_state"]["CONFIRMED"] == 1


def test_upsert_digest_search_and_checkpoint_integration():
    first = new_wisdom_entry(
        "Checkpoint Mestre",
        "A sabedoria precisa preservar origem, confiança e revisão.",
        truth_state="INFERENCE",
        evidence_refs=["docs:checkpoint"],
        applies_to=["memória", "AION"],
        created_at="2026-09-25T12:00:00+00:00",
    )
    rows = upsert_wisdom_entry([], first)
    assert len(rows) == 1
    assert wisdom_digest(rows) == wisdom_digest(rows)
    assert search_wisdom("checkpoint memoria", rows)[0]["wisdom_id"] == first["wisdom_id"]

    checkpoint = update_wisdom_checkpoint(default_checkpoint(), entries=rows)
    normalized = ensure_operating_checkpoint(checkpoint)
    assert normalized["wisdom"]["entries"][0]["wisdom_id"] == first["wisdom_id"]
    assert normalized["wisdom"]["digest"] == wisdom_digest(rows)
    assert normalized["checkpoint_version"] >= 8
