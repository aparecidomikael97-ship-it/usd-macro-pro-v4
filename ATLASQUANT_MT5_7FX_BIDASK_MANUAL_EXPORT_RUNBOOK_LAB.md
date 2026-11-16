# AtlasQuant Trader — Manual MT5 historical Bid/Ask export (LAB)

**Status: LAB / AGUARDAR / HARD NO-GO.** This is documentation for a **future, human-initiated** local research task, not an automatic job or authorization to trade. As of 16 November 2026 the user's `am12` remote computer was offline; no actual Pepperstone tick export has been run for this PR.

## Why this exists

M15 candle `spread` is a terminal-reported bar field, **not** the Bid/Ask quote available at a specific moment. The standalone validator `atlasquant_trader_us_macro_mt5_bidask_anchor_archive_lab.py` checks tick-level CSVs and local SHA256 receipts. This new *manual* exporter prepares those original CSVs **only if all 7 USD crosses and all 4 event-relative anchors exist**.

There are 7 crosses: EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD. Frozen anchors are release **minus 15 minutes**, **plus 15**, **plus 60** and **plus 240 minutes**. It requests `COPY_TICKS_INFO` ticks in the 5 seconds before each anchor and stores the last available tick at or before the anchor. Any missing quote, crossed Bid/Ask, wrong UTC or invalid symbol metadata fails the *entire* event.

Frozen events:

| Event root | Release (UTC) | Earliest export with H4 complete |
| --- | --- | --- |
| US_PPI_OCT2026 | 2026-11-13 13:30 | 2026-11-13 17:30 UTC |
| US_CPI_NOV2026 | 2026-12-10 13:30 | 2026-12-10 17:30 UTC |
| US_PPI_NOV2026 | 2026-12-15 13:30 | 2026-12-15 17:30 UTC |

**Do not use any of those event dates as proof of BLS publication or forecast skill.** Consult the official BLS calendar before interpreting the actual economic release. No past economic consensus or historical first availability is authenticated by the MT5 terminal.

## Manual procedure (Windows, locally, *after* user approval)

1. Confirm a working Pepperstone-connected MT5 terminal *on the computer you control*. Check installation path manually; do not paste account credentials into code or GitHub.
2. Keep `AtlasQuant Trader` project source checked out locally. Use a local Python environment that already has the MetaTrader5 package, if available. No package installation is performed by the exporter.
3. Prepare a one-off Python script as below. Set `ATLASQUANT_MT5_TERMINAL` to your actual local `terminal64.exe` path. **Set `ALLOW_MANUAL_EXPORT=True` only after deciding to perform the local data export.**
4. Run **once** for an event whose entire H4 window is in the past. The script may call MetaTrader5 `initialize()`, which can connect to or launch the terminal; this step is **outside** the export library and must be consciously initiated by the operator. There is no account access or order call in the exporter.
5. Inspect the result. On successful local export, the private directory `~/AtlasQuant/LAB/MT5_7FX_BIDASK_ANCHORS/<EVENT_ROOT>/` contains exactly seven `*_BIDASK_ANCHORS.csv` and a `receipt.json`. This path uses a real Windows user home, not a literal `<EVENT_ROOT>` filename. If the target exists, it will not be overwritten.
6. Do **not** upload broker ticks, account details, local manifest or paths to a public PR. Only report whether local replay succeeded and anonymized QA findings.

```python
# Example only: run manually on the user's authorized Windows computer.
from datetime import datetime, timezone
from pathlib import Path
import json, os
import MetaTrader5 as mt5
from atlasquant_trader_us_macro_mt5_bidask_manual_export_lab import (
    export_manual_mt5_7fx_bidask_anchors_lab,
    load_manual_mt5_bidask_receipt_lab,
)

ALLOW_MANUAL_EXPORT = False  # Operator changes to True consciously
EVENT = "US_PPI_OCT2026"
OUTPUT = Path.home() / "AtlasQuant" / "LAB" / "MT5_7FX_BIDASK_ANCHORS"
TERMINAL = os.environ.get("ATLASQUANT_MT5_TERMINAL")

if not ALLOW_MANUAL_EXPORT:
    raise SystemExit("LAB_BLOCKED: no manual export approval")
if not TERMINAL or not Path(TERMINAL).is_file():
    raise SystemExit("LAB_BLOCKED: set a real local MT5 terminal64.exe path")
if not mt5.initialize(path=TERMINAL, timeout=10000):
    raise SystemExit("LAB_BLOCKED: manual MT5 connection failed")
try:
    report = export_manual_mt5_7fx_bidask_anchors_lab(
        mt5, event_root=EVENT, output_root=OUTPUT,
        allow_explicit_manual_export=True,
        clock=lambda: datetime.now(timezone.utc),
    )
    print(report["state"], report["reason"])
    if report["state"] == "LAB_MT5_7FX_LOCAL_BIDASK_ORIGINALS_EXPORTED_NO_TRADING":
        receipt = load_manual_mt5_bidask_receipt_lab(
            archive_root=OUTPUT, event_root=EVENT,
            inspected_at_utc=datetime.now(timezone.utc),
        )
        print("Local replay OK. Seven original pair SHA receipts:", len(receipt.sha256_by_pair))
finally:
    mt5.shutdown()  # Disconnect API session; no trade action
```

## Interpretation and strict limits

- **No interpolation or backfill:** when the terminal lacks a tick in the fixed five-second window, the entire seven-pair event is **NO-GO**. This may be common in sparse markets. Do not move anchors or extend stale quotes to force a result.
- The export uses the terminal's historical `COPY_TICKS_INFO`, not a signed broker audit trail. It cannot establish whether the returned tick stream was originally complete or available at the historical moment.
- The recorded spread is only an observation of `Ask − Bid` at those anchors. **Not executable spread, trade cost, slippage, commission, a fill or P&L.** Historical Bid/Ask does not prove that an order could be filled at either price.
- The labels from `terminal_info.company` are local observations, not independently authenticated broker identity.
- The 28 rows are **correlated observations of one event**, not 28 out-of-sample forecasts. The CPI/PPI December protocol #1984 remains **ABSTAIN** and there is no validated directional bias or accuracy.
- No cron, live signal, autonomous trading, account/position reads, visibility changes or FX28 #1884 campaign modification. Manual export is deliberately not wired to the UI, any automated runner or trading engine.

MetaTrader documentation: https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py
