import pytest
from datetime import datetime,timezone
from atlasquant_aion_social_media import (
 social_platform_registry,build_social_content_job,submit_for_review,approve_content,
 publication_policy,normalize_social_metrics
)

NOW=datetime(2026,9,23,18,tzinfo=timezone.utc)

def job():
 return build_social_content_job(platforms=["instagram","youtube","tiktok"],title="Macro da semana",
 objective="Educar e apresentar o AtlasQuant",now=NOW)

def test_registry_covers_three_priority_social_platforms():
 r=social_platform_registry()
 assert set(r["platforms"])=={"instagram","youtube","tiktok"}
 assert r["publish_requires_explicit_approval"] is True

def test_content_cannot_publish_before_review_and_approval():
 j=job()
 p=publication_policy(j,connected_platforms=["instagram","youtube","tiktok"])
 assert not p["publish_allowed"] and "CONTENT_NOT_APPROVED" in p["reasons"]

def test_review_requires_real_content_evidence():
 with pytest.raises(ValueError):submit_for_review(job())

def test_approved_unchanged_content_can_publish_only_to_connected_platforms():
 j=job();d=dict(j["deliverables"]);d["script"]="Roteiro final";j["deliverables"]=d
 j=submit_for_review(j);j=approve_content(j,approved_by="Mikael",now=NOW)
 blocked=publication_policy(j,connected_platforms=["instagram","youtube"])
 assert not blocked["publish_allowed"] and any("tiktok" in x for x in blocked["reasons"])
 allowed=publication_policy(j,connected_platforms=["instagram","youtube","tiktok"])
 assert allowed["publish_allowed"] and allowed["explicit_approval_required"] is True

def test_edit_after_approval_invalidates_publication():
 j=job();d=dict(j["deliverables"]);d["script"]="Versão A";j["deliverables"]=d
 j=submit_for_review(j);j=approve_content(j,approved_by="Mikael",now=NOW)
 d=dict(j["deliverables"]);d["script"]="Versão B alterada";j["deliverables"]=d
 p=publication_policy(j,connected_platforms=["instagram","youtube","tiktok"])
 assert not p["publish_allowed"] and "CONTENT_CHANGED_AFTER_APPROVAL" in p["reasons"]

def test_metrics_are_normalized_without_claiming_missing_values():
 m=normalize_social_metrics("instagram",{"followers":1200,"views":5000,"likes":300,"captured_at":"2026-09-23T18:00:00+00:00"})
 assert m["followers"]==1200 and m["views"]==5000 and m["likes"]==300
 assert "subscribers" not in m

def test_social_module_never_inherits_trading_authority():
 r=social_platform_registry()
 assert r["real_orders_enabled"] is False and r["voice_can_authorize_orders"] is False
