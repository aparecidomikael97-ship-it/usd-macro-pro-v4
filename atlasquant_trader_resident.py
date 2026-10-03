"""Read-only adapter from the existing validated runtime snapshot to Trader UI."""
import math
import json
from pathlib import Path


def resident_trader_state(snapshot, *, now=None, series_state=None):
    from atlasquant_fast_startup import validate_home_snapshot
    from atlasquant_home_radar import home_rows_from_packs
    from atlasquant_radar_board import compose_fx_board
    from atlasquant_interface_final import eligible_fx_population, temporal_signal_status

    empty = {"atlasquant_reference_fx_population": {},
             "atlasquant_validated_market_items": []}
    check = validate_home_snapshot(snapshot, now=now)
    if not check["valid"]:
        return empty
    snapshot = check["snapshot"]
    fast_boot = snapshot["inputs"]["fast_boot"]
    stamp = snapshot.get("runtime_generated_at") or snapshot.get("generated_at")
    history = home_rows_from_packs(snapshot["packs"])
    board = compose_fx_board(history,
                             ranking=fast_boot["ranking"])
    population = {"rows": board["rows"], "history": history,
                  "market_map": [{key: pack.get(key) for key in
                      ("pair","w1","d1","pd_zone","event","levels","map_current","technical_timestamp")}
                      for pack in snapshot["packs"] if isinstance(pack,dict)],
                  "macro_context": {key: fast_boot[key] for key in ("fed", "macro_eua")},
                  "macro_as_of": snapshot["inputs"].get("generated_at") or snapshot.get("generated_at"),
                  "freshness": {
        "state": "VALIDATED_SNAPSHOT", "generated_at": stamp,
        "source": "runtime snapshot"}}
    items = []
    for row in eligible_fx_population(population, now=now)["ranked"]:
        item = {"asset": row["pair"], "validated": True,
                "source": row["evidence_source"], "as_of": stamp,
                "score": row["priority"]}
        # Display the engine's action; a blocked buy/sell remains neutral.
        bias = {"COMPRA": "Compra", "VENDA": "Venda", "NEUTRO": "Neutro",
                "NÃO OPERAR": "Neutro", "NAO OPERAR": "Neutro"}.get(row.get("action"))
        if bias:
            item["bias"] = bias
        items.append(item)
    published = {item["asset"] for item in items}
    for row in history:
        if row["pair"] in published:
            continue
        signal = row.get("signal") or {}
        if not signal.get("reference_at") and signal.get("status_code") == "UNVERIFIED":
            continue
        items.append({"asset": row["pair"], "validated": True,
                      "source": row.get("evidence_source") or "runtime snapshot",
                      "as_of": stamp, "last_bias": row.get("bias", "AGUARDAR"),
                      "temporal_state": temporal_signal_status(signal, now=now)})
    for row in fast_boot["ranking"]:
        if not isinstance(row, dict) or row.get("Código") != "USD":
            continue
        score = row.get("Pontuação_Final")
        if isinstance(score, bool):
            break
        try:
            score = float(score)
        except (TypeError, ValueError):
            break
        if math.isfinite(score):
            items.append({"asset": "DXY", "validated": True, "score": score,
                          "as_of": snapshot["inputs"].get("generated_at") or snapshot.get("generated_at"), "source": "runtime snapshot / força USD"})
        break
    # Never call cached_series/_load: those can fetch GitHub. Reuse only a
    # supplied resident cache or the collector's already-present local artifact.
    if series_state is None:
        from twelve_cache_v1108 import SERIES_PATH
        try:
            path = Path(SERIES_PATH)
            series_state = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError):
            series_state = {}
    if isinstance(series_state, dict):
        from twelve_cache_v1108 import read_series
        from atlasquant_compact_cockpit import TRADER_ASSETS
        by_asset = {item["asset"]: item for item in items}
        for asset in TRADER_ASSETS:
            try:
                frame, _ = read_series(series_state, asset, "15min", 30, now=now)
            except (TypeError, ValueError, KeyError, AttributeError):
                continue
            if frame.empty:
                continue
            item = by_asset.get(asset, {"asset": asset, "validated": True})
            item.update({"price": float(frame.iloc[-1]["close"]),
                         "series": [float(v) for v in frame["close"]],
                         "quote_source": "twelve_series_v1108 / closed M15",
                         "quote_as_of": frame.attrs["source_fetched_at"]})
            # Quote freshness is independently checked by the existing cache.
            item.setdefault("source", item["quote_source"])
            item.setdefault("as_of", item["quote_as_of"])
            if asset not in by_asset:
                items.append(item)
                by_asset[asset] = item
    return {"atlasquant_reference_fx_population": population,
            "atlasquant_validated_market_items": items}


def hydrate_trader_resident_state(session_state, snapshot):
    # Clear previously accepted evidence too: a failed refresh cannot retain it.
    session_state["atlasquant_reference_fx_population"] = {}
    session_state["atlasquant_validated_market_items"] = []
    try:
        session_state.update(resident_trader_state(snapshot))
    except (TypeError, ValueError, KeyError, AttributeError):
        # Malformed resident artifacts stay absent, never repaired by this adapter.
        pass
