"""Strict *provisional* December CPI/PPI consensus semantic candidates, LAB.

Two independently claimed captured pages (TD Economics, Trading Economics)
must agree on the SAME event, NOV 2026 reference period, monthly SA percentage,
release time, and headline/core values. TD "Consensus Forecast" and "Last
Period" columns are distinct. TE "Previous", "Consensus", and provider-owned
"Forecast" columns are NOT interchangeable. A populated "Actual" column on
a pre-release TE calendar is forbidden.

IMPORTANT: December source HTML editions have NOT been archived or inspected
as of 2026-11-15. Labels/DOM mapping are conservative *hypotheses* inferred
from the prior archived PPI study. Positive synthetic tests validate parser
logic only. Real source version / polling methodology, publisher first-seen,
an independently witnessed directional prediction, and FX price outcomes are
NOT authenticated. No candidate in this module is permitted to become an
operational Macro Motor A bias, prediction or trading signal.

This is a pure offline source interpreter: no disk/network/MT5/writes/jobs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import (
    EVENTS, OriginalPreEventSourceClaim,
    inspect_us_dec2026_pre_event_consensus_custody_lab,
)
from atlasquant_trader_us_ppi_pre_event_preview_lab import _Tables as _TDTables

SCHEMA = "ATLASQUANT_US_DEC2026_CONSENSUS_SEMANTIC_CANDIDATE_LAB_V1"
_EVENT = {
    "US_CPI_NOV2026": {
        "date_short": "Dec 10", "date_te": "2026-12-10",
        "week_title": "Upcoming Economic Releases and Events: Dec 7 - 11, 2026",
        "td_names": ("CPI All Items", "CPI Ex Food and Energy"),
        "te_routes": ("/united-states/inflation-rate-mom",
                      "/united-states/core-inflation-rate-mom"),
        "te_labels": ("Inflation Rate MoM NOV", "Core Inflation Rate MoM NOV"),
    },
    "US_PPI_NOV2026": {
        "date_short": "Dec 15", "date_te": "2026-12-15",
        "week_title": "Upcoming Economic Releases and Events: Dec 14 - 18, 2026",
        "td_names": ("PPI Final Demand", "PPI Ex Food and Energy"),
        "te_routes": ("/united-states/producer-price-inflation-mom",
                      "/united-states/core-producer-prices-mom"),
        "te_labels": ("PPI MoM NOV", "Core PPI MoM NOV"),
    },
}
_TD_HEADER = (
    "Release Date", "Time*", "", "Economic Indicator/Event",
    "Data for Period", "Units", "Consensus Forecast", "Last Period",
)
_TE_HEADER = ("Actual", "Previous", "Consensus", "Forecast")
_NUMBER = re.compile(r"[+-]?(?:0|[1-9][0-9]?)(?:\.[0-9]{1,3})?\Z")


class _ScopedTDTables(_TDTables):
    """Keep TD header/title/metric rows on the SAME concrete table.

    _TDTables historically joins rows from every <table> into one flat list.
    That permits a consensus header from an unrelated table to label numbers
    from another table. Table IDs preserve source structure without reading
    arbitrary page text as a survey.
    """
    def __init__(self) -> None:
        super().__init__()
        self.table_stack: list[int] = []
        self.table_id = 0
        self.row_table_ids: list[int | None] = []
        self.pending_row_table: int | None = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table" and not self.hidden:
            self.table_id += 1
            self.table_stack.append(self.table_id)
        elif tag == "tr" and not self.hidden:
            self.pending_row_table = (self.table_stack[-1]
                                      if self.table_stack else None)
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        before = len(self.rows)
        super().handle_endtag(tag)
        if tag == "tr" and len(self.rows) != before:
            self.row_table_ids.append(self.pending_row_table)
            self.pending_row_table = None
        elif tag == "table" and not self.hidden:
            if not self.table_stack:
                raise ValueError("UNMATCHED_TD_TABLE_END")
            self.table_stack.pop()


def _utc(dt: Any) -> datetime | None:
    if type(dt) is not datetime or dt.tzinfo is None:
        return None
    try:
        return dt.astimezone(timezone.utc) if dt.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _number(v: Any, *, te_percent: bool) -> str | None:
    if type(v) is not str:
        return None
    if te_percent:
        if not v.endswith("%"):
            return None
        v = v[:-1]
    if _NUMBER.fullmatch(v) is None:
        return None
    try:
        n = Decimal(v)
        if not n.is_finite() or not -10 <= n <= 20:
            return None
        if n == 0:
            return "0"
        return format(n.normalize(), "f")
    except (InvalidOperation, OverflowError, ValueError):
        return None


class _TERowReader(HTMLParser):
    """Read only exact target rows, preserving outer td boundaries."""
    def __init__(self, target_routes: tuple[str, str]):
        super().__init__(convert_charrefs=True)
        self.routes = set(target_routes)
        self.headers: list[str] = []
        self.header_table_ids: list[int | None] = []
        self.header_row_ids: list[int | None] = []
        self.row_table_ids: list[int | None] = []
        self.open_tr_ids: list[int] = []
        self.next_tr_id = 0
        self.table_stack: list[int] = []
        self.table_id = 0
        self.current_row_table: int | None = None
        self.current_header_table: int | None = None
        self.current_header_row: int | None = None
        self.th: list[str] | None = None
        self.active = False
        self.depth = 0
        self.key = ""
        self.date_class = ""
        self.cells: list[str] = []
        self.cell: list[str] | None = None
        self.rows: list[tuple[str, str, tuple[str, ...]]] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        tag=tag.lower()
        a=dict(attrs)
        if tag in ("script","style","svg","noscript"):
            self.hidden += 1
            return
        if self.hidden:
            return
        if tag=="table":
            self.table_id+=1
            self.table_stack.append(self.table_id)
        if tag=="tr":
            self.next_tr_id+=1
            self.open_tr_ids.append(self.next_tr_id)
        if tag=="th" and not self.active:
            if self.th is not None:
                raise ValueError("NESTED_TABLE_HEADER")
            self.th=[]
            self.current_header_table=(self.table_stack[-1]
                                       if self.table_stack else None)
            self.current_header_row=(self.open_tr_ids[-1]
                                     if self.open_tr_ids else None)
        if tag=="tr" and not self.active and a.get("data-url") in self.routes:
            self.active=True
            self.depth=1
            self.key=a["data-url"]
            self.cells=[]
            self.date_class=""
            self.current_row_table=(self.table_stack[-1]
                                     if self.table_stack else None)
            return
        if not self.active:
            return
        if tag=="tr":
            self.depth+=1
        elif tag=="td" and self.depth==1:
            if self.cell is not None:
                raise ValueError("OVERLAPPING_OUTER_TD")
            self.cell=[]
            if not self.cells:
                self.date_class=a.get("class","")

    def handle_data(self, data):
        if self.hidden:
            return
        if self.th is not None and not self.active:
            self.th.append(data)
        if self.active and self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        tag=tag.lower()
        if tag in ("script","style","svg","noscript") and self.hidden:
            self.hidden-=1
            return
        if self.hidden:
            return
        if tag=="th" and self.th is not None:
            self.headers.append(" ".join(" ".join(self.th).split()))
            self.header_table_ids.append(self.current_header_table)
            self.header_row_ids.append(self.current_header_row)
            self.current_header_table=None
            self.current_header_row=None
            self.th=None
        if tag=="table":
            if not self.table_stack:
                raise ValueError("UNMATCHED_TE_TABLE_END")
            self.table_stack.pop()
        if tag=="tr":
            if not self.open_tr_ids:
                raise ValueError("UNMATCHED_TE_ROW_END")
            self.open_tr_ids.pop()
        if not self.active:
            return
        if tag=="td" and self.depth==1 and self.cell is not None:
            self.cells.append(" ".join(" ".join(self.cell).split()))
            self.cell=None
        elif tag=="tr":
            self.depth-=1
            if self.depth==0:
                if self.cell is not None:
                    raise ValueError("UNCLOSED_OUTER_CELL")
                self.rows.append((self.key,self.date_class,tuple(self.cells)))
                self.row_table_ids.append(self.current_row_table)
                self.current_row_table=None
                self.active=False


def _td_values(raw: bytes, *, root: str) -> dict[str, tuple[str, str]] | None:
    spec = _EVENT[root]
    try:
        doc=_ScopedTDTables()
        doc.feed(raw.decode("cp1252","strict"))
        doc.close()
        if (doc.cell is not None or doc.row is not None
                or doc.table_stack
                or len(doc.row_table_ids)!=len(doc.rows)):
            return None
    except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
        return None
    header_positions=[i for i, row in enumerate(doc.rows) if row==_TD_HEADER]
    if len(header_positions)!=1:
        return None
    table_id=doc.row_table_ids[header_positions[0]]
    if table_id is None:
        return None
    if not any(
        doc.row_table_ids[i]==table_id
        and any(spec["week_title"] in cell for cell in row)
        for i, row in enumerate(doc.rows)
    ):
        return None
    parsed: dict[str, tuple[str,str]]={}
    for kind, name in zip(("headline","core"),spec["td_names"]):
        matches=[i for i,r in enumerate(doc.rows)
                 if len(r)==8 and r[3]==name]
        if len(matches)!=1 or doc.row_table_ids[matches[0]]!=table_id:
            return None
        r=doc.rows[matches[0]]
        if (r[0]!=spec["date_short"] or r[1]!="8:30" or r[2]!=""
                or r[4]!="Nov" or r[5]!="M/M % Chg."):
            return None
        consensus,previous=_number(r[6],te_percent=False),_number(r[7],te_percent=False)
        if consensus is None or previous is None:
            return None
        parsed[kind]=(consensus,previous)
    return parsed


def _te_values(raw: bytes, *, root: str) -> dict[str, tuple[str, str, str]] | None:
    spec = _EVENT[root]
    try:
        doc=_TERowReader(spec["te_routes"])
        doc.feed(raw.decode("utf-8","strict"))
        doc.close()
        if (doc.active or doc.cell is not None or doc.th is not None
                or doc.table_stack or doc.open_tr_ids
                or len(doc.row_table_ids)!=len(doc.rows)
                or len(doc.header_table_ids)!=len(doc.headers)
                or len(doc.header_row_ids)!=len(doc.headers)):
            return None
    except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
        return None
    if len(doc.rows)!=2 or not doc.row_table_ids:
        return None
    table_id=doc.row_table_ids[0]
    if (table_id is None
            or any(i!=table_id for i in doc.row_table_ids)):
        return None
    # Four labels must be one physical <tr> header, within the target
    # <table>. Flattening headers across rows permits a second form of
    # consensus-header laundering, even when table IDs agree.
    own_headers=[(h, row_id)
                 for h, owner, row_id in zip(
                     doc.headers,doc.header_table_ids,doc.header_row_ids)
                 if owner==table_id]
    if (len(own_headers)!=len(_TE_HEADER)
            or tuple(h for h,_ in own_headers)!=_TE_HEADER
            or any(row_id is None or row_id!=own_headers[0][1]
                   for _,row_id in own_headers)):
        return None
    parsed: dict[str,tuple[str,str,str]]={}
    for kind, route, label in zip(
        ("headline","core"),spec["te_routes"],spec["te_labels"]
    ):
        matched=[r for r in doc.rows if r[0]==route]
        if len(matched)!=1:
            return None
        _, date_class, cells=matched[0]
        if (not re.search(r"(?:^|\s)"+re.escape(spec["date_te"])+r"(?:\s|$)",date_class)
                or len(cells)!=10 or cells[0]!="01:30 PM"
                or cells[2]!=label or cells[3]!=""):
            return None
        previous, consensus, forecast=(
            _number(cells[i],te_percent=True) for i in (4,5,6)
        )
        if any(v is None for v in (previous,consensus,forecast)):
            return None
        parsed[kind]=(consensus,previous,forecast)
    return parsed


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema":SCHEMA, "state":"LAB_DEC2026_CONSENSUS_SEMANTICS_BLOCKED_HARD_NO_GO",
        "reason":reason,"frozen_economic_event_denominator":2,
        "events":[{
            "event_root":root,
            "reference_period":period,
            "release_utc":t.isoformat(),
            "locally_reconciled_two_source_bytes":False,
            "provisional_consensus_headline_mom_sa_pct":None,
            "provisional_consensus_core_mom_sa_pct":None,
            "td_previous_headline_mom_pct":None,
            "te_provider_forecast_headline_mom_pct":None,
            "td_html_sha256_local_claim":None,
            "te_html_sha256_local_claim":None,
            "source_semantic_schema_approved_on_real_december_html":False,
            "publisher_first_seen_independently_authenticated":False,
            "provider_poll_methodology_independently_authenticated":False,
            "consensus_eligible_for_fx_prediction":False,
            "independent_validated_fx_forecast":False,
        } for root,_,period,t in EVENTS],
        "local_two_source_candidate_event_count":0,
        "economic_consensus_pre_event_independently_authenticated":0,
        "registered_directional_fx_predictions":0,
        "independent_fx_oos_trials":0,
        "win_rate":None,
        "fx_bias":None,"calibrated_probability":None,
        "operational_bias":"AGUARDAR",
        "trade_authorized":False,"publishable":False,
        "no_hindsight_claims":True,
        "fx28_original_672_slots_modified":False,
        "http_requests":0,"file_writes":0,"mt5_calls":0,
    }


def inspect_dec2026_consensus_semantic_candidate_lab(
    *, source_snapshots: Any, inspected_at_utc: Any,
) -> dict[str,Any]:
    """Tentative column interpretation; never promotes figures into Motor A."""
    out=_blocked("SOURCE_OR_TIME_NOT_DOCUMENTARILY_ACCEPTABLE")
    now=_utc(inspected_at_utc)
    if now is None:
        return out
    custody=inspect_us_dec2026_pre_event_consensus_custody_lab(
        snapshots=source_snapshots, research_cutoff_utc=now)
    if (custody.get("state") != "LAB_DEC2026_PRE_EVENT_SOURCE_CUSTODY_ONLY_NO_GO"
            or custody.get("frozen_upcoming_economic_event_denominator") !=2
            or custody.get("trade_authorized") is not False):
        return out
    if type(source_snapshots) not in (tuple,list):
        return out
    bykey={}
    for s in source_snapshots:
        if type(s) is not OriginalPreEventSourceClaim:
            return out
        if _utc(s.finished_at_utc) is not None and _utc(s.finished_at_utc)<=now:
            bykey[(s.event_root,s.provider)]=s
    result=[]
    n=0
    for base in out["events"]:
        root=base["event_root"]
        td=bykey.get((root,"TD_ECONOMICS"))
        te=bykey.get((root,"TRADING_ECONOMICS"))
        if td is None or te is None:
            result.append(base)
            continue
        tdv=_td_values(td.html_original_bytes,root=root)
        tev=_te_values(te.html_original_bytes,root=root)
        if tdv is None or tev is None:
            return _blocked("ISSUER_ROW_PERIOD_METRIC_OR_COLUMN_SCOPE_NOT_RECONCILED")
        for k in ("headline","core"):
            if tdv[k][0]!=tev[k][0] or tdv[k][1]!=tev[k][1]:
                return _blocked("TWO_SOURCES_CONSENSUS_OR_PREVIOUS_DISAGREE")
        row={**base,
            "locally_reconciled_two_source_bytes":True,
            "provisional_consensus_headline_mom_sa_pct":tdv["headline"][0],
            "provisional_consensus_core_mom_sa_pct":tdv["core"][0],
            "td_previous_headline_mom_pct":tdv["headline"][1],
            "te_provider_forecast_headline_mom_pct":tev["headline"][2],
            "td_html_sha256_local_claim":sha256(td.html_original_bytes).hexdigest(),
            "te_html_sha256_local_claim":sha256(te.html_original_bytes).hexdigest(),
        }
        result.append(row)
        n+=1
    out.update({
        "state":"LAB_DEC2026_TWO_SOURCE_PROVISIONAL_SEMANTICS_ONLY_HARD_NO_GO",
        "reason":"STRUCTURAL_COLUMNS_MATCH_SYNTHETIC_SCHEMA_REAL_DECEMBER_VERSION_NOT_AUTHENTICATED",
        "events":result,
        "local_two_source_candidate_event_count":n,
    })
    return out


__all__ = (
    "SCHEMA","inspect_dec2026_consensus_semantic_candidate_lab",
)
