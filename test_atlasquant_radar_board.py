import unittest

import pandas as pd

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_radar_board import (
    CRYPTO_UNIVERSE,
    FX_MONITORED_COUNT,
    INDEX_UNIVERSE,
    TOP_FX_LIMIT,
    compose_fx_board,
    crypto_ranking,
    highlight_top_fx,
    index_ranking,
    rank_fx_population,
    strengths_from_records,
)
from atlasquant_session_profiles import (
    SESSION_FILTER_OPTIONS,
    filter_label_for_profile,
    prioritize_rows_for_session,
    profile_for_filter,
)


def _ranking():
    return pd.DataFrame({
        "Código": ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"],
        "Pontuação_Final": [80, 60, 74, 30, 48, 44, 58, 36],
    })


def _pack(pair, priority, action="COMPRA"):
    return {
        "pair": pair,
        "action": action,
        "bias": action if action != "NÃO OPERAR" else "NEUTRO",
        "priority": priority,
        "data_score": 80,
        "quality": 70,
        "session_bucket": "NEW_YORK",
        "asset_class": "FX",
    }


class AtlasQuantRadarBoardTests(unittest.TestCase):
    def test_board_always_monitors_twenty_eight_forex_pairs(self):
        board = compose_fx_board([], _ranking())
        self.assertEqual(board["monitored"], FX_MONITORED_COUNT)
        self.assertEqual(board["monitored"], 28)
        self.assertEqual([row["pair"] for row in board["rows"]], list(OFFICIAL_PAIRS))
        self.assertTrue(all(row["asset_class"] == "FX" for row in board["rows"]))
        self.assertFalse(board["real_orders_enabled"])
        self.assertFalse(board["automatic_execution"])

    def test_missing_ranking_keeps_pairs_visible_and_fail_closed(self):
        board = compose_fx_board([_pack("EUR/USD", 90)], None)
        self.assertEqual(board["monitored"], 28)
        self.assertEqual(board["institutional"], 1)
        self.assertEqual(board["missing"], 27)
        self.assertFalse(board["macro_ready"])
        missing = next(row for row in board["rows"] if row["pair"] == "GBP/JPY")
        self.assertEqual(missing["action"], "NÃO OPERAR")
        self.assertFalse(missing["real_orders_enabled"])

    def test_incomplete_strengths_do_not_invent_a_macro_board(self):
        self.assertIsNone(strengths_from_records([{"Código": "USD", "Pontuação_Final": 80}]))
        self.assertIsNone(strengths_from_records([
            {"Código": code, "Pontuação_Final": float("nan")}
            for code in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
        ]))

    def test_top_ten_is_dynamic_and_excludes_other_asset_classes(self):
        low = [_pack(pair, 10 + index) for index, pair in enumerate(OFFICIAL_PAIRS[:7])]
        board = compose_fx_board(low, _ranking())
        ordered = sorted(board["rows"], key=lambda row: row["priority"], reverse=True)
        top = highlight_top_fx(ordered, TOP_FX_LIMIT)
        self.assertEqual(len(top), 10)
        self.assertEqual(TOP_FX_LIMIT, 10)
        self.assertNotEqual(top[0]["pair"], ordered[-1]["pair"])
        self.assertTrue(all(row["asset_class"] == "FX" for row in top))
        self.assertTrue(all(row["pair"] in OFFICIAL_PAIRS for row in top))
        reshuffled = sorted(board["rows"], key=lambda row: row["priority"])
        other = highlight_top_fx(reshuffled, 10)
        self.assertEqual([row["pair"] for row in top], [row["pair"] for row in other])
        self.assertEqual(
            [row["pair"] for row in top],
            [row["pair"] for row in rank_fx_population(board["rows"])[:10]],
        )
        self.assertEqual(len({row["pair"] for row in top}), 10)

    def test_duplicate_and_unknown_inputs_never_remove_official_pairs(self):
        records = [
            _pack("EUR/USD", 80),
            _pack("EUR/USD", 99),
            _pack("USD/XXX", 100),
            {"pair": "", "priority": 100},
        ]
        board = compose_fx_board(records, None)
        self.assertEqual(len(board["rows"]), 28)
        self.assertEqual(len({row["pair"] for row in board["rows"]}), 28)
        self.assertEqual(set(row["pair"] for row in board["rows"]), set(OFFICIAL_PAIRS))
        eurusd = next(row for row in board["rows"] if row["pair"] == "EUR/USD")
        self.assertEqual(eurusd["priority"], 80)

    def test_absent_technical_source_never_becomes_artificial_confidence(self):
        board = compose_fx_board([], _ranking())
        self.assertEqual(len(board["rows"]), 28)
        for row in board["rows"]:
            self.assertFalse(row["data_ready"])
            self.assertEqual(row["action"], "NÃO OPERAR")
            self.assertEqual(row["confidence"], "BAIXA")
            self.assertIsNone(row["score_components"]["technical"])
            self.assertEqual(row["pipeline"]["technical"], "SEM DADOS")
            self.assertFalse(row["real_orders_enabled"])
            self.assertFalse(row["automatic_execution"])

    def test_pipeline_components_are_explicit_and_never_authorize_orders(self):
        ready = _pack("EUR/USD", 88)
        ready.update({"data_ready": True, "strength_diff": 20, "h4": "BUY", "h1": "BUY", "m15": "BUY"})
        row = next(r for r in compose_fx_board([ready], _ranking())["rows"] if r["pair"] == "EUR/USD")
        self.assertEqual(row["pipeline"]["data"], "CONFIRMADO")
        self.assertEqual(row["pipeline"]["technical"], "CONFIRMADO")
        self.assertEqual(row["pipeline"]["macro"], "CONFIRMADO")
        self.assertEqual(row["confidence"], "ALTA")
        self.assertEqual(row["score_components"]["technical"], 88)
        self.assertFalse(row["real_orders_enabled"])
        self.assertFalse(row["automatic_execution"])

    def test_indices_and_cryptos_stay_in_separate_rankings(self):
        indices = index_ranking([
            {"symbol": "NAS100", "score": 80},
            {"symbol": "DXY", "score": 55},
        ])
        cryptos = crypto_ranking([{"symbol": "ETH/USD", "score": 70}])
        self.assertEqual([row["symbol"] for row in indices[:2]], ["NAS100", "DXY"])
        self.assertEqual([item[0] for item in INDEX_UNIVERSE], [row["symbol"] for row in index_ranking()])
        self.assertEqual(cryptos[0]["symbol"], "ETH/USD")
        self.assertEqual([item[0] for item in CRYPTO_UNIVERSE], [row["symbol"] for row in crypto_ranking()])
        fx = {row["pair"] for row in compose_fx_board([], _ranking())["rows"]}
        self.assertTrue(fx.isdisjoint({row["symbol"] for row in indices}))
        self.assertTrue(fx.isdisjoint({row["symbol"] for row in cryptos}))
        self.assertTrue(all(row["action"] == "NÃO OPERAR" for row in indices + cryptos))
        self.assertTrue(all(row["real_orders_enabled"] is False for row in indices + cryptos))

    def test_day_night_and_both_filters_only_reorder(self):
        self.assertEqual(SESSION_FILTER_OPTIONS, ("Ambos", "Noite", "Dia"))
        self.assertEqual(profile_for_filter("Ambos"), "Todos os horários")
        self.assertEqual(profile_for_filter("Noite"), "Noite/madrugada · Ásia + Londres")
        self.assertEqual(profile_for_filter("Dia"), "Dia · Nova York + continuidade")
        self.assertEqual(filter_label_for_profile("Dia · Nova York + continuidade"), "Dia")
        asia = {"pair": "AUD/USD", "action": "COMPRA", "priority": 40, "data_score": 50, "session_bucket": "ASIA"}
        ny = {"pair": "EUR/USD", "action": "COMPRA", "priority": 90, "data_score": 50, "session_bucket": "NEW_YORK"}
        both = prioritize_rows_for_session([ny, asia], profile_for_filter("Ambos"))
        night = prioritize_rows_for_session([ny, asia], profile_for_filter("Noite"))
        day = prioritize_rows_for_session([ny, asia], profile_for_filter("Dia"))
        self.assertEqual(both[0]["pair"], "EUR/USD")
        self.assertEqual(night[0]["pair"], "AUD/USD")
        self.assertEqual(day[0]["pair"], "EUR/USD")
        self.assertEqual(night[0]["action"], "COMPRA")
        self.assertEqual(night[1]["action"], "COMPRA")
        self.assertEqual(len(night), 2)

    def test_unreadable_priority_sorts_last_without_crashing(self):
        rows = [
            {"pair": "EUR/USD", "action": "COMPRA", "priority": "n/d", "data_score": None, "session_bucket": "ASIA"},
            {"pair": "GBP/USD", "action": "COMPRA", "priority": float("nan"), "data_score": "x", "session_bucket": "ASIA"},
            {"pair": "AUD/USD", "action": "COMPRA", "priority": 12, "data_score": 5, "session_bucket": "ASIA"},
        ]
        out = prioritize_rows_for_session(rows, profile_for_filter("Ambos"))
        self.assertEqual(out[0]["pair"], "AUD/USD")
        self.assertEqual(len(out), 3)
        self.assertEqual(out[1]["priority"], "n/d")

    def test_macro_only_pair_cannot_become_an_authorized_trade(self):
        board = compose_fx_board([], _ranking())
        macro = next(row for row in board["rows"] if row["coverage"] == "macro")
        self.assertEqual(macro["action"], "NÃO OPERAR")
        self.assertIn("NÃO OPERAR", macro["reason"])
        self.assertFalse(macro["data_ready"])
        self.assertFalse(macro["automatic_execution"])


if __name__ == "__main__":
    unittest.main()
