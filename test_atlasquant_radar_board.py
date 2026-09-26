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
        self.assertNotEqual([row["pair"] for row in top], [row["pair"] for row in other])

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

    def test_macro_only_pair_cannot_become_an_authorized_trade(self):
        board = compose_fx_board([], _ranking())
        macro = next(row for row in board["rows"] if row["coverage"] == "macro")
        self.assertEqual(macro["action"], "NÃO OPERAR")
        self.assertIn("NÃO OPERAR", macro["reason"])
        self.assertFalse(macro["data_ready"])
        self.assertFalse(macro["automatic_execution"])


if __name__ == "__main__":
    unittest.main()
