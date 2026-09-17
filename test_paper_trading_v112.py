import unittest

import pandas as pd

from paper_trading_v112 import (
    evaluate_pair_checklist,
    run_paper_cycle,
)


class PaperTradingV112Tests(unittest.TestCase):
    def _bars(self, start="2026-09-17T08:00:00Z", n=40, base=1.1000):
        rows = []
        ts = pd.Timestamp(start)
        price = base
        for i in range(n):
            o = price
            c = o + 0.00005
            rows.append({
                "datetime": (ts + pd.Timedelta(minutes=15 * i)).isoformat(),
                "open": o,
                "high": o + 0.00030,
                "low": o - 0.00030,
                "close": c,
            })
            price = c
        return rows

    def _state(self, now, bars=None, m15_status="🟢 GATILHO", adr=45.0):
        bars = bars or self._bars()
        last_dt = pd.Timestamp(bars[-1]["datetime"])
        inputs = {
            "pairs": [{
                "Par": "EUR/USD",
                "Direção": "🟢 COMPRA EUR/USD",
                "Score final": 90.0,
                "Qualidade": 90.0,
                "Índice ranking": 90.0,
            }]
        }
        scanner = {
            "resultados": {
                "EUR/USD": {
                    "m15_fetched_at": last_dt.isoformat(),
                    "tecnico": {
                        "disponivel": True,
                        "dados_disponiveis": True,
                        "h4": {"status": "🟢 CONFIRMA"},
                        "h1": {"status": "🟢 PULLBACK OK"},
                        "m15": {"status": m15_status},
                        "ict": {"readiness": 82.0},
                        "institutional": {"readiness": 84.0},
                        "cache_v110": {"m15": bars},
                    },
                }
            }
        }
        master = {
            "contexts": {
                "EUR/USD": {
                    "updated_at": now.isoformat(),
                    "readiness_grade": "READY",
                    "readiness_score": 78.0,
                    "adr_used_pct": adr,
                    "event_risk": "NORMAL",
                }
            }
        }
        return inputs, scanner, master

    def test_checklist_only_passes_when_everything_is_clear(self):
        now = pd.Timestamp("2026-09-17T18:00:00Z")
        bars = self._bars(start="2026-09-17T08:15:00Z", n=39)
        inputs, scanner, master = self._state(now, bars=bars)
        row = inputs["pairs"][0]
        sp = scanner["resultados"]["EUR/USD"]
        mp = master["contexts"]["EUR/USD"]
        chk = evaluate_pair_checklist("EUR/USD", row, sp, mp, now=now)
        self.assertTrue(chk["all_checks_passed"])
        self.assertTrue(chk["decision"]["executable"])
        self.assertEqual(chk["decision"]["hard_blocks"], [])
        self.assertEqual(chk["decision"]["soft_blocks"], [])

    def test_missing_m15_trigger_blocks_paper_entry(self):
        now = pd.Timestamp("2026-09-17T18:00:00Z")
        bars = self._bars(start="2026-09-17T08:15:00Z", n=39)
        inputs, scanner, master = self._state(now, bars=bars, m15_status="🔴 SEM GATILHO")
        trades, cycle = run_paper_cycle(inputs, scanner, master, now=now)
        self.assertTrue(trades.empty)
        self.assertEqual(cycle["pending_created"], 0)
        self.assertFalse(cycle["checklists"]["EUR/USD"]["passed"])

    def test_signal_waits_next_m15_then_opens_and_closes_at_target(self):
        # Primeiro ciclo: checklist passou, mas não entra no mesmo candle do sinal.
        now1 = pd.Timestamp("2026-09-17T18:00:00Z")
        bars1 = self._bars(start="2026-09-17T08:15:00Z", n=39)
        inputs, scanner1, master1 = self._state(now1, bars=bars1)
        trades1, cycle1 = run_paper_cycle(inputs, scanner1, master1, now=now1)
        self.assertEqual(len(trades1), 1)
        self.assertEqual(trades1.iloc[0]["status"], "WAIT_ENTRY")
        self.assertEqual(cycle1["pending_created"], 1)

        # Segundo ciclo: aparece o M15 seguinte; entrada é no OPEN dele.
        signal_time = pd.Timestamp(trades1.iloc[0]["signal_time"])
        last_close = float(bars1[-1]["close"])
        next_bar = {
            "datetime": signal_time.isoformat(),
            "open": last_close,
            "high": last_close + 0.00020,
            "low": last_close - 0.00020,
            "close": last_close + 0.00002,
        }
        bars2 = bars1 + [next_bar]
        now2 = signal_time + pd.Timedelta(minutes=20)
        inputs, scanner2, master2 = self._state(now2, bars=bars2)
        trades2, cycle2 = run_paper_cycle(inputs, scanner2, master2, trades1, now=now2)
        self.assertEqual(len(trades2), 1)
        self.assertEqual(trades2.iloc[0]["status"], "OPEN")
        self.assertAlmostEqual(float(trades2.iloc[0]["entry_price"]), last_close, places=8)
        self.assertEqual(cycle2["entries_opened"], 1)

        # Terceiro ciclo: candle posterior alcança somente o alvo.
        target = float(trades2.iloc[0]["target_price"])
        stop = float(trades2.iloc[0]["stop_price"])
        entry = float(trades2.iloc[0]["entry_price"])
        future = {
            "datetime": (signal_time + pd.Timedelta(minutes=15)).isoformat(),
            "open": entry,
            "high": target + 0.00001,
            "low": max(stop + 0.00001, entry - 0.00005),
            "close": target,
        }
        bars3 = bars2 + [future]
        now3 = signal_time + pd.Timedelta(minutes=40)
        inputs, scanner3, master3 = self._state(now3, bars=bars3)
        trades3, cycle3 = run_paper_cycle(inputs, scanner3, master3, trades2, now=now3)
        self.assertEqual(len(trades3), 1)
        self.assertEqual(trades3.iloc[0]["status"], "CLOSED")
        self.assertEqual(trades3.iloc[0]["result"], "WIN")
        self.assertAlmostEqual(float(trades3.iloc[0]["realized_r"]), 2.0, places=6)
        self.assertEqual(cycle3["trades_closed"], 1)

    def test_high_adr_soft_block_prevents_simulation(self):
        now = pd.Timestamp("2026-09-17T18:00:00Z")
        bars = self._bars(start="2026-09-17T08:15:00Z", n=39)
        inputs, scanner, master = self._state(now, bars=bars, adr=90.0)
        trades, cycle = run_paper_cycle(inputs, scanner, master, now=now)
        self.assertTrue(trades.empty)
        self.assertFalse(cycle["checklists"]["EUR/USD"]["passed"])
        self.assertTrue(cycle["checklists"]["EUR/USD"]["soft_blocks"])


if __name__ == "__main__":
    unittest.main()
