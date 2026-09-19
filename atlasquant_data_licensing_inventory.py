"""AtlasQuant data-source licensing inventory.

Technical inventory only. Presence in code, public availability or an API key is
not evidence of commercial redistribution rights. Every provider remains
unverified until a human records the applicable commercial terms.
"""
from __future__ import annotations

from typing import Any

SCHEMA="ATLASQUANT_DATA_LICENSING_INVENTORY_V1"

DATA_SOURCES=(
    {"id":"fred","name":"FRED","usage":"macroeconomic series, release dates and H.10 FX references","kind":"API","commercial_license_verified":False},
    {"id":"bcb-sgs","name":"Banco Central do Brasil / SGS","usage":"Brazil macroeconomic series","kind":"API","commercial_license_verified":False},
    {"id":"newsapi","name":"NewsAPI","usage":"news retrieval when configured","kind":"API","commercial_license_verified":False},
    {"id":"eodhd","name":"EODHD Economic Events","usage":"economic-event consensus/actual/previous when configured","kind":"API","commercial_license_verified":False},
    {"id":"twelve-data","name":"Twelve Data","usage":"M15 technical market data for scanner/autopilot when configured","kind":"API","commercial_license_verified":False},
    {"id":"google-news-rss","name":"Google News RSS","usage":"news-title retrieval","kind":"RSS","commercial_license_verified":False},
    {"id":"google-translate","name":"Google Translate public endpoint","usage":"best-effort text translation","kind":"HTTP endpoint","commercial_license_verified":False},
    {"id":"federal-reserve-calendar","name":"Federal Reserve","usage":"FOMC calendar references","kind":"official schedule","commercial_license_verified":False},
    {"id":"ism-calendar","name":"ISM","usage":"manufacturing/services release calendar references","kind":"official schedule","commercial_license_verified":False},
)

def data_source_inventory()->list[dict[str,Any]]:
    return [dict(x) for x in DATA_SOURCES]

def data_inventory_ready()->bool:
    required={"fred","bcb-sgs","newsapi","eodhd","twelve-data","google-news-rss","google-translate","federal-reserve-calendar","ism-calendar"}
    ids=[str(x["id"]) for x in DATA_SOURCES]
    return set(ids)==required and len(ids)==len(set(ids)) and all(x.get("usage") and x.get("kind") for x in DATA_SOURCES)

def data_licensing_status()->dict[str,Any]:
    rows=data_source_inventory()
    verified=sum(1 for x in rows if x.get("commercial_license_verified") is True)
    return {
        "schema":SCHEMA,
        "inventory_ready":data_inventory_ready(),
        "sources":len(rows),
        "commercially_verified":verified,
        "all_commercial_licenses_verified":bool(rows and verified==len(rows)),
        "manual_review_required":True,
        "automatic_license_assumption":False,
    }

__all__=["SCHEMA","DATA_SOURCES","data_source_inventory","data_inventory_ready","data_licensing_status"]
