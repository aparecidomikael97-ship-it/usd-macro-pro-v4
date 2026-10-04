"""Read-only adapter from the existing validated runtime snapshot to Trader UI."""
import math
import json
from pathlib import Path


def resident_trader_state(snapshot, *, now=None, series_state=None, runtime_status=None):
    from atlasquant_runtime_presentation import snapshot_presentation, finite_positive, stamp_age
    from atlasquant_home_radar import home_rows_from_packs
    from atlasquant_radar_board import compose_fx_board
    from atlasquant_interface_final import eligible_fx_population, temporal_signal_status

    empty = {"atlasquant_reference_fx_population": {},
             "atlasquant_validated_market_items": []}
    check = snapshot_presentation(snapshot, now=now)
    if check["state"] == "INVALID":
        return empty
    snapshot = check["snapshot"]
    fast_boot = snapshot["inputs"]["fast_boot"]
    stamp = snapshot.get("runtime_generated_at") or snapshot.get("generated_at")
    history = home_rows_from_packs(snapshot["packs"])
    board = compose_fx_board(history,
                             ranking=fast_boot["ranking"])
    population = {"rows": board["rows"], "history": history,
                  "snapshot_state":check['state'],"snapshot_age_minutes":check['age_minutes'],
                  "runtime":snapshot.get('runtime') or {},
                  "runtime_status":dict(runtime_status or {}),
                  "ict_history":[{key:pack.get(key) for key in ('pair','ict','ict_read','ict_label','ict_fresh','technical_timestamp')} for pack in snapshot['packs']],
                  "market_map": [{key: pack.get(key) for key in
                      ("pair","w1","d1","pd_zone","event","levels","map_current","technical_timestamp")}
                      for pack in snapshot["packs"] if isinstance(pack,dict)],
                  "macro_context": {key: fast_boot[key] for key in ("fed", "macro_eua")},
                  "macro_as_of": snapshot["inputs"].get("generated_at") or snapshot.get("generated_at"),
                  "freshness": {
        "state": "VALIDATED_SNAPSHOT" if check['state']=='VALIDATED_CURRENT' else 'STALE_HISTORY', "generated_at": stamp,
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
            items.append({"asset": "DXY", "validated": True, "macro_score": score,
                          "score": score,
                          "as_of": snapshot["inputs"].get("generated_at") or snapshot.get("generated_at"), "source": "runtime snapshot / força USD"})
        break
    by_asset={item['asset']:item for item in items}
    for pack in snapshot['packs']:
        pair=pack['pair']; item=by_asset.get(pair)
        if item is None:
            signal=pack.get('signal_lifecycle') or {}
            if not (finite_positive(pack.get('price')) and stamp_age(pack.get('technical_timestamp'),now=now) is not None) and not signal:
                continue
            item={'asset':pair,'validated':True,'source':'runtime pack','as_of':stamp,
                  'last_bias':{'BUY':'COMPRA','SELL':'VENDA','WAIT':'AGUARDAR'}.get(pack.get('side'),pack.get('direction','AGUARDAR')),
                  'temporal_state':temporal_signal_status(pack.get('signal_lifecycle'),now=now)}
            items.append(item);by_asset[pair]=item
        price_stamp=pack.get('technical_timestamp')
        if finite_positive(pack.get('price')) and stamp_age(price_stamp,now=now) is not None:
            item.update(last_price=pack['price'],last_price_at=price_stamp)
        item['presentation_state']='HISTORICAL_STALE' if check['state']=='STALE_HISTORY' or pair not in published else 'CURRENT'
    if check['state']=='STALE_HISTORY':
        for item in items: item['presentation_state']='HISTORICAL_STALE'
    for strip in snapshot.get('market_strip') or []:
        if not isinstance(strip,dict) or strip.get('asset') not in by_asset: continue
        item=by_asset[strip['asset']]
        times=strip.get('series_timestamps') or []; closes=strip.get('closes') or []
        ages=[stamp_age(value,now=now) for value in times]
        if strip.get('source')!='scanner/cache_v110/m15' or strip.get('closed_candles') is not True or strip.get('series_timeframe')!='M15': continue
        if len(times)!=len(closes) or len(closes)<2 or any(age is None or age<15 for age in ages) or any(not finite_positive(v) for v in closes): continue
        if any(ages[i]<=ages[i+1] for i in range(len(ages)-1)): continue
        series_current=check['state']=='VALIDATED_CURRENT' and ages[-1]<70
        item.update(series_source=strip['source'],series_as_of=times[-1],series_timestamps=times[-30:])
        item['series' if series_current else 'historical_series']=closes[-30:]
        item['series_state']='CURRENT' if series_current else 'HISTORICAL_STALE'
        if finite_positive(strip.get('last_price')) and stamp_age(strip.get('last_price_at'),now=now) is not None:
            item.update(last_price=strip['last_price'],last_price_at=strip['last_price_at'])
            if check['state']=='VALIDATED_CURRENT' and stamp_age(strip['last_price_at'],now=now)<70:
                item.update(price=strip['last_price'],quote_as_of=strip['last_price_at'],quote_source=strip['source'])
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


def hydrate_trader_resident_state(session_state, snapshot, runtime_status=None):
    # Clear previously accepted evidence too: a failed refresh cannot retain it.
    session_state["atlasquant_reference_fx_population"] = {}
    session_state["atlasquant_validated_market_items"] = []
    try:
        session_state.update(resident_trader_state(snapshot,runtime_status=runtime_status))
    except (TypeError, ValueError, KeyError, AttributeError):
        # Malformed resident artifacts stay absent, never repaired by this adapter.
        pass
