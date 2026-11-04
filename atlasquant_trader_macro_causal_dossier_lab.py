"""Macro surprise evidence for 8 currencies and 28 FX pairs, offline LAB.

Pairs a previously assembled *unattested* news/calendar context with explicitly
synthetic macro actual-vs-consensus receipts. The result exposes where a
release is above/below a predeclared consensus, without treating the sign as
the reason for a currency's strength or as a directional trade signal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from copy import deepcopy
import re

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_macro_surprise_pit_lab import (
    SCHEMA as MACRO_SCHEMA, PRE_KEYS, ACTUAL_KEYS,
    build_macro_point_in_time_evidence_lab,
)
from atlasquant_trader_news_pair_context_lab import SCHEMA as NEWS_SCHEMA
from atlasquant_trader_official_rss_capture_lab import SOURCES, _official_url
from atlasquant_trader_macro_event_exposure_lab import build_macro_event_exposure_lab
from atlasquant_trader_macro_event_exposure_v2_lab import build_macro_event_exposure_v2_lab

SCHEMA = "ATLASQUANT_TRADER_MACRO_CAUSAL_DOSSIER_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
WINDOW = {"D1": timedelta(days=1), "W1": timedelta(days=7),
          "MN1": timedelta(days=30)}
MAX_EVENTS = 64
MAX_HEADLINES_PER_FRAME = 1400
HEX24 = re.compile(r"^[0-9a-f]{24}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _stamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 45:
        return None
    try:
        p = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return p.astimezone(timezone.utc) if p.tzinfo is not None and p.utcoffset() is not None else None


def _refused(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "rows": [], "pair_count": 0, "currencies": {},
        "published_macro_receipts_attested": False,
        "official_news_source_authenticated": False,
        "calendar_realtime_verified": False,
        "forecast_accuracy_verified": False,
        "relative_strength_independently_verified": False,
        "strength_causation_proven": False,
        "contrary_evidence_independently_reviewed": False,
        "probability_calibrated": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "scheduler_enabled": False,
        "worker_enabled": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _news_card_valid(card: Any, *, now: datetime,
                     base: str, quote: str, horizon: str) -> bool:
    if (not isinstance(card, Mapping) or card.get("operational_bias") != "AGUARDAR"
            or card.get("base_currency_strength_reason") != "NAO_COMPROVADO"
            or card.get("quote_currency_strength_reason") != "NAO_COMPROVADO"
            or card.get("counterevidence") != "NAO_AUTENTICADA"
            or card.get("news_not_proof_of_currency_direction") is not True
            or card.get("trailing_news_window_not_candle_forecast") is not True
            or card.get("documentary_news_window") != "TRAILING_" + horizon
            or not isinstance(card.get("news_articles_from_supplied_feeds"), list)
            or len(card["news_articles_from_supplied_feeds"]) > MAX_HEADLINES_PER_FRAME
            or card.get("news_article_count") != len(card["news_articles_from_supplied_feeds"])
            or not isinstance(card.get("event_exposures_documentary"), list)):
        return False
    for art in card["news_articles_from_supplied_feeds"]:
        if not isinstance(art, Mapping):
            return False
        currency, src = art.get("currency"), art.get("source_id")
        published = _stamp(art.get("publisher_claimed_at_utc"))
        captured = _stamp(art.get("captured_at_utc"))
        uri = art.get("official_url_claimed")
        if (not isinstance(currency, str) or currency not in (base, quote)
                or not isinstance(src, str) or src not in SOURCES
                or SOURCES[src]["currency"] != currency
                or art.get("topic") != SOURCES[src]["topic"]
                or not _official_url(uri, SOURCES[src]["hostname"])
                or published is None or not now - WINDOW[horizon] <= published <= now
                or captured is None or captured > now
                or published > captured + timedelta(minutes=5)
                or not isinstance(art.get("article_id"), str)
                or HEX24.fullmatch(art["article_id"]) is None
                or not isinstance(art.get("revision_sha256"), str)
                or HEX64.fullmatch(art["revision_sha256"]) is None
                or art.get("source_origin_verified") is not False
                or art.get("directional_inference") != "AGUARDAR"):
            return False
    return True


def _news_report_valid(report: Any, now: datetime) -> bool:
    if not isinstance(report, Mapping):
        return False
    if (report.get("schema") != NEWS_SCHEMA
            or report.get("state") != "LAB_NEWS_CONTEXT_FOR_REVIEW_ONLY"
            or _stamp(report.get("as_of_utc")) != now
            or report.get("pair_count") != len(OFFICIAL_PAIRS)
            or report.get("currency_count") != len(CURRENCIES)
            or report.get("bias_horizons") != list(HORIZONS)
            or any(report.get(flag) is not False for flag in (
                "g8_official_news_coverage_complete",
                "source_original_bytes_archived",
                "source_identity_independently_verified",
                "publication_latency_verified",
                "cause_of_currency_strength_verified",
                "counterevidence_authenticated",
                "economic_calendar_realtime_verified",
                "currency_bias_operational",
                "can_feed_live_radar", "trade_authorized", "worker_enabled",
                "scheduler_enabled", "publishable"))):
        return False
    rows = report.get("rows")
    if (not isinstance(rows, list) or len(rows) != len(OFFICIAL_PAIRS)
            or any(not isinstance(row, Mapping) for row in rows)):
        return False
    seen = set()
    for row in rows:
        pair = row.get("pair")
        if not isinstance(pair, str) or pair not in OFFICIAL_PAIRS or pair in seen:
            return False
        seen.add(pair)
        base, quote = split_pair(pair)
        if (row.get("base") != base or row.get("quote") != quote
                or row.get("trade_authorized") is not False
                or not isinstance(row.get("horizons"), Mapping)
                or set(row["horizons"]) != set(HORIZONS)
                or any(not _news_card_valid(row["horizons"][h], now=now,
                                            base=base, quote=quote, horizon=h)
                       for h in HORIZONS)):
            return False
    if seen != set(OFFICIAL_PAIRS):
        return False
    # The upstream matrix uses precisely one of the two documentary calendar
    # vintages. No article/headline may silently forge calendar events.
    try:
        candidates = (build_macro_event_exposure_lab(at=now),
                      build_macro_event_exposure_v2_lab(at=now))
    except ValueError:
        return False
    for calendar in candidates:
        expected = {(entry["pair"], entry["horizon"]): entry
                    for entry in calendar["fx_rows"]}
        if all(
            row["horizons"][h]["event_exposures_documentary"] ==
            expected[(row["pair"], h)]["event_exposures"]
            and row["horizons"][h]["calendar_risk_status_documentary"] ==
            expected[(row["pair"], h)]["risk_status"]
            for row in rows for h in HORIZONS
        ):
            return True
    return False


def _macro_receipt_ok(book: Any, now: datetime) -> bool:
    if (not isinstance(book, Mapping) or book.get("schema") != MACRO_SCHEMA
            or book.get("state") not in (
                "LAB_MACRO_FUTURE_SCHEDULE_ONLY", "LAB_MACRO_RELEASED_SYNTHETIC")
            or any(book.get(flag) is not False for flag in (
                "provider_attested", "immutable_receipt_attested",
                "real_macro_history_verified", "predictive_edge_proven",
                "trade_authorized", "worker_enabled", "scheduler_enabled"))
            or book.get("macro_currency_direction") != "UNDETERMINED"):
        return False
    ev = book.get("freeze_evidence")
    if not isinstance(ev, Mapping) or ev.get("state") != "LAB_SYNTHETIC_EVIDENCE":
        return False
    try:
        pre = {"state": "LAB_SYNTHETIC_MACRO_PRE", "event_id": ev["evidence_id"],
               "currency": ev["currency"], "indicator_id": ev["indicator_id"],
               "unit": ev["unit"], "source": ev["source"],
               "previous": ev["previous"], "consensus": ev["consensus"],
               "previous_captured_at_utc": ev["previous_captured_at_utc"],
               "consensus_captured_at_utc": ev["consensus_captured_at_utc"],
               "scheduled_release_at_utc": ev["scheduled_release_at_utc"],
               "deadband_predeclared": ev["deadband_predeclared"]}
        if set(pre) != PRE_KEYS:
            return False
        actual = None
        if book["state"] == "LAB_MACRO_RELEASED_SYNTHETIC":
            actual = {"state": "LAB_SYNTHETIC_MACRO_ACTUAL",
                      "event_id": ev["evidence_id"], "actual": ev["actual"],
                      "released_at_utc": ev["released_at_utc"],
                      "captured_at_utc": ev["captured_at_utc"],
                      "source": ev["actual_source"]}
            if set(actual) != ACTUAL_KEYS:
                return False
        regenerated = build_macro_point_in_time_evidence_lab(
            pre, actual, forecast_issued_at=now, evaluated_at=now)
    except (KeyError, ValueError, TypeError, OverflowError):
        return False
    # Compare whole reconstructed evidence. Do not accept caller modifications
    # to actual, surprise, direction, timing or readiness booleans.
    return dict(book) == regenerated


def build_macro_causal_dossier_lab(
    news_pair_context: Any, macro_receipts: Any, *, at: datetime,
) -> dict[str, Any]:
    """Show surprise *claims* and evidence gaps, without any live strength bias."""
    if (not isinstance(at, datetime) or at.tzinfo is None
            or at.utcoffset() is None):
        raise ValueError("Evaluation requires a timezone-aware clock")
    now = at.astimezone(timezone.utc)
    if not _news_report_valid(news_pair_context, now):
        return _refused("UNSAFE_NEWS_CALENDAR_CONTEXT")
    if (not isinstance(macro_receipts, (list, tuple))
            or len(macro_receipts) > MAX_EVENTS):
        return _refused("MACRO_RECEIPTS_MISSING_OR_UNBOUNDED")
    indexed = {}
    for receipt in macro_receipts:
        if not _macro_receipt_ok(receipt, now):
            return _refused("INVALID_SYNTHETIC_MACRO_RECEIPT")
        ev = receipt["freeze_evidence"]
        identity = ev["evidence_id"]
        if identity in indexed:
            return _refused("DUPLICATE_EVENT_OR_CONSENSUS_VINTAGE")
        indexed[identity] = receipt

    currency_books = {}
    for currency in CURRENCIES:
        own = [r for r in indexed.values() if r["freeze_evidence"]["currency"] == currency]
        own.sort(key=lambda r: (r["freeze_evidence"]["scheduled_release_at_utc"],
                                r["freeze_evidence"]["evidence_id"]))
        currency_books[currency] = {
            "currency": currency,
            "synthetic_receipt_count": len(own),
            "released_claim_count": sum(r["state"] == "LAB_MACRO_RELEASED_SYNTHETIC" for r in own),
            "scheduled_future_claim_count": sum(r["state"] == "LAB_MACRO_FUTURE_SCHEDULE_ONLY" for r in own),
            "strength_reason_confirmed": False,
            "source_custody_verified": False,
            "opposite_currency_comparison_calibrated": False,
        }

    pairs = []
    old_pairs = {row["pair"]: row for row in news_pair_context["rows"]}
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        frame_set = {}
        for horizon in HORIZONS:
            window_begin = now - WINDOW[horizon]
            future_end = now + WINDOW[horizon]
            released_claims = []
            scheduled_claims = []
            for currency in (base, quote):
                for receipt in indexed.values():
                    ev = receipt["freeze_evidence"]
                    if ev["currency"] != currency:
                        continue
                    if receipt["state"] == "LAB_MACRO_RELEASED_SYNTHETIC":
                        released = _stamp(ev["released_at_utc"])
                        if released is not None and window_begin <= released <= now:
                            released_claims.append({
                                "currency": currency, "event_id": ev["evidence_id"],
                                "indicator": ev["indicator_id"], "unit": ev["unit"],
                                "previous_synthetic": ev["previous"],
                                "consensus_synthetic": ev["consensus"],
                                "actual_synthetic": ev["actual"],
                                "actual_minus_consensus": receipt["surprise"],
                                "surprise_class": receipt["surprise_comparison"],
                                "released_at_utc": ev["released_at_utc"],
                                "consensus_captured_at_utc": ev["consensus_captured_at_utc"],
                                "release_verified": False,
                                "strength_direction": "AGUARDAR",
                            })
                    else:
                        announced = _stamp(ev["scheduled_release_at_utc"])
                        if announced is not None and now < announced <= future_end:
                            scheduled_claims.append({
                                "currency": currency, "event_id": ev["evidence_id"],
                                "indicator": ev["indicator_id"],
                                "scheduled_release_at_utc": ev["scheduled_release_at_utc"],
                                "no_actual_observed": True,
                            })
            released_claims.sort(key=lambda x: (x["released_at_utc"], x["event_id"]),
                                 reverse=True)
            scheduled_claims.sort(key=lambda x: (x["scheduled_release_at_utc"],
                                  x["event_id"]))
            signs = {x["surprise_class"] for x in released_claims}
            conflicting_raw_signs = ("ABOVE_CONSENSUS" in signs
                                     and "BELOW_CONSENSUS" in signs)
            old = old_pairs[pair]["horizons"][horizon]
            frame_set[horizon] = {
                "macro_surprise_claims": released_claims,
                "future_releases_claimed": scheduled_claims,
                "mixed_above_below_consensus_claims": conflicting_raw_signs,
                "mixed_surprise_signs_do_not_prove_currency_contradiction": True,
                "news_documentary_count": old["news_article_count"],
                "calendar_risk_status_documentary": old["calendar_risk_status_documentary"],
                "relative_vs_macro_hypothesis_synthetic": old["macro_vs_relative_comparison_synthetic"],
                "base_currency_strength_cause": "NAO_COMPROVADA",
                "quote_currency_strength_cause": "NAO_COMPROVADA",
                "independent_counterevidence": "PENDENTE",
                "policy_expectations_market_response_verified": False,
                "actual_values_source_attested": False,
                "oos_relative_strength_calibrated": False,
                "operational_bias": "AGUARDAR",
            }
        pairs.append({"pair": pair, "base": base, "quote": quote,
                      "horizons": frame_set, "trade_authorized": False})

    report = _refused("SYNTHETIC_MACRO_SURPRISE_IS_NOT_CAUSAL_FX_EVIDENCE")
    report.update({
        "state": "LAB_CAUSAL_EVIDENCE_GAPS_ONLY",
        "as_of_utc": now.isoformat(),
        "rows": pairs, "pair_count": len(pairs),
        "currencies": currency_books, "currency_count": len(currency_books),
        "synthetic_event_count": len(indexed),
        "time_windows_are_documentary_not_price_candles": True,
        "three_daily_updates_running": False,
        "note": ("Acima/abaixo do consenso = diferenca numerica sintetica, "
                 "nao impacto de juros, fluxo ou direcao de moeda. Sem fonte "
                 "autenticada, contraprovas, matriz FX independente e OOS."),
    })
    return report


__all__ = ["SCHEMA", "HORIZONS", "build_macro_causal_dossier_lab"]
