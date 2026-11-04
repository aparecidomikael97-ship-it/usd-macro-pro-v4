"""Offline comparator for Nov 4 Copom, anchored to Nov 3 Git blob.

The future result is unknown. Any caller-supplied publication text, URL,
timestamps and SHA256 can be forged. Even a matching sample is NOT an
authenticated official release, market forecast or trading authorization.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha1, sha256
import json
import re
from typing import Any, Mapping
from urllib.parse import urlsplit
from atlasquant_trader_copom_pre_event_lock_lab import EXPECTED, EARLIEST_RELEASE

SCHEMA="ATLASQUANT_TRADER_COPOM_POST_EVENT_CHECK_LAB_V1"
PENDING="LAB_COPOM_POST_EVENT_OFFICIAL_RELEASE_PENDING"
CANDIDATE="LAB_COPOM_POST_EVENT_CANDIDATE_UNATTESTED"
DENIED="LAB_COPOM_POST_EVENT_REFUSED"
PRE_EVENT_COMMIT="1281f21860211e9b6f784c649396aa56d17ecdf5"
PRE_EVENT_BLOB="4f6ff11f05b78d6361b2c1e313ce2e394acfff63"
SAMPLE_KEYS={"source_type","source_url","source_name","content_type",
 "http_status_claim","declared_published_at_utc","claimed_first_seen_at_utc",
 "policy_rate_claim_pct","raw_release_text","raw_release_sha256"}

def _refused(reason):
 return {"schema":SCHEMA,"state":DENIED,"reason":reason,
  "frozen_checkpoint_commit":PRE_EVENT_COMMIT,"frozen_checkpoint_blob":PRE_EVENT_BLOB,
  "original_pre_event_snapshot_matched":False,
  "release_independently_authenticated":False,
  "publication_clock_independently_attested":False,
  "receipt_clock_independently_attested":False,
  "actual_policy_decision_verified":False,"result_scenario":None,
  "candidate_rate_pct":None,"economist_poll_modal_matched":None,
  "economist_share_is_market_probability":False,
  "market_implied_probability":None,"trader_accuracy":None,
  "market_direction":"AGUARDAR","real_oos_eligible":False,
  "can_feed_live_radar":False,"trade_authorized":False,
  "worker_enabled":False,"scheduler_enabled":False,
  "paid_provider_approved":False,"render_configuration_changed":False}

def _blob_id(raw):
 return sha1(b"blob "+str(len(raw)).encode("ascii")+b"\x00"+raw).hexdigest()

def _utc(s):
 if not isinstance(s,str) or not s.endswith("Z") or len(s)>40:return None
 try: d=datetime.fromisoformat(s[:-1]+"+00:00")
 except (ValueError,OverflowError):return None
 return d.astimezone(timezone.utc) if d.utcoffset() is not None else None

def _allowed_bcb_url(url):
 if not isinstance(url,str) or len(url)>350:return False
 try:
  u=urlsplit(url)
  port=u.port
 except ValueError:return False
 return (u.scheme=="https" and u.netloc=="www.bcb.gov.br" and
         u.hostname=="www.bcb.gov.br" and port is None and
         u.username is None and u.password is None and
         not u.query and not u.fragment and
         (u.path.startswith("/detalhenoticia/") or
          u.path.startswith("/controleinflacao/comunicadoscopom/")))

def assess_copom_post_event_candidate_lab(
 original_pre_event_json:Any, result_claim:Any=None, *, evaluated_at:datetime
)->dict[str,Any]:
 """Classify only UNATTESTED result candidates after official release window."""
 if not isinstance(evaluated_at,datetime) or evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
  raise ValueError("Evaluation instant must contain timezone")
 now=evaluated_at.astimezone(timezone.utc)
 if not isinstance(original_pre_event_json,bytes) or _blob_id(original_pre_event_json)!=PRE_EVENT_BLOB:
  return _refused("Not the original Nov3 Git blob of the pre-Copom checkpoint")
 try: snap=json.loads(original_pre_event_json.decode("utf-8"))
 except (UnicodeError,ValueError):return _refused("Malformed original checkpoint")
 if (not isinstance(snap,Mapping) or set(snap)!=set(EXPECTED) or
     any(type(snap[k]) is not type(v) or snap[k]!=v for k,v in EXPECTED.items())):
  return _refused("Original snapshot identity, sources or scenarios not fixed")
 pending={**_refused(""),"state":PENDING,"reason":None,
  "original_pre_event_snapshot_matched":True,
  "pre_event_modal_survey_response":"HOLD_13_75",
  "pre_event_economist_hold_sample":"33/48",
  "pre_event_focus_year_end_selic_pct":"13.50",
  "pre_event_focus_is_next_meeting_probability":False,
  "official_earliest_release_utc":EARLIEST_RELEASE.isoformat(),
  "why_pending":"No independently authenticated BCB Copom communiqué has been supplied"}
 if result_claim is None:return pending
 if now<EARLIEST_RELEASE:
  return _refused("Cannot include future communiqué before first permitted release time")
 if not isinstance(result_claim,Mapping) or set(result_claim)!=SAMPLE_KEYS:
  return _refused("Unsupported post-event record or injected authority fields")
 r=result_claim
 if (r["source_type"]!="OFFICIAL_BCB_TEXT_EXTRACT_UNATTESTED" or
     r["source_name"]!="BANCO_CENTRAL_DO_BRASIL" or
     r["content_type"]!="text/plain; charset=utf-8" or
     type(r["http_status_claim"]) is not int or r["http_status_claim"]!=200 or
     not _allowed_bcb_url(r["source_url"])):
  return _refused("Invalid declared official source or data type")
 publication=_utc(r["declared_published_at_utc"])
 first_seen=_utc(r["claimed_first_seen_at_utc"])
 if publication is None or first_seen is None or not EARLIEST_RELEASE<=publication<=first_seen<=now:
  return _refused("Claimed time sequence impossible or before publication window")
 content=r["raw_release_text"]
 digest=r["raw_release_sha256"]
 if (not isinstance(content,bytes) or not 30<=len(content)<=100000 or
     b"\x00" in content or not isinstance(digest,str) or
     re.fullmatch(r"[a-f0-9]{64}",digest) is None or
     sha256(content).hexdigest()!=digest):
  return _refused("Release text bytes missing or local checksum fails")
 try: data=content.decode("utf-8")
 except UnicodeError:return _refused("Release text is not UTF8")
 if (re.search(r"\bCopom\b",data,re.I) is None or
     re.search(r"\bSelic\b",data,re.I) is None or
     "<script" in data.lower() or "<!doctype" in data.lower()):
  return _refused("Text lacks an unambiguous plain Copom/Selic mention")
 level=r["policy_rate_claim_pct"]
 if not isinstance(level,str) or re.fullmatch(r"(?:[1-9]|[12][0-9])\.[0-9]{2}",level) is None:
  return _refused("Policy rate must be a canonical annual percent string")
 if level.replace(".",",")+"%" not in data:
  return _refused("Claimed policy rate is not mentioned in communiqué text")
 rate=Decimal(level)
 scenario="HOLD_13_75" if rate==Decimal("13.75") else (
          "CUT_25BP_13_50" if rate==Decimal("13.50") else "OTHER")
 return {**pending,"state":CANDIDATE,
  "declared_bcb_source_url":r["source_url"],
  "declared_publication_at_utc":publication.isoformat(),
  "claimed_first_seen_at_utc":first_seen.isoformat(),
  "release_text_local_sha256_matches":True,
  "result_scenario":scenario,"candidate_rate_pct":level,
  "economist_poll_modal_matched":scenario=="HOLD_13_75",
  "actual_policy_decision_verified":False,
  "warning":"Scenario candidate only. Text, URL and clocks may be forged. Check original BCB communication and its publication before stating result. This is not evidence of FX/WIN/WDO predictive accuracy."}

__all__=["SCHEMA","PENDING","CANDIDATE","DENIED","PRE_EVENT_COMMIT",
 "PRE_EVENT_BLOB","assess_copom_post_event_candidate_lab"]
