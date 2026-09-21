import unittest
from pathlib import Path

from atlasquant_setup_candidates import build_setup_candidates


class SetupCandidateAttributionTests(unittest.TestCase):
    def institutional(self, *, structure_side="BUY", ob_status="🟡 ORDER BLOCK ATIVO", ob_side="BUY", invalidated=False):
        return {
            "structure":{
                "status":"🟢 CHOCH CONFIRMADO",
                "score":92,
                "event":"CHOCH",
                "event_side":structure_side,
                "level":1.1010,
                "break_time":"2026-09-21T20:00:00Z",
            },
            "order_block":{
                "status":ob_status,
                "score":68,
                "side":ob_side,
                "zone_low":1.0990,
                "zone_high":1.1000,
                "origin_time":"2026-09-21T19:30:00Z",
                "invalidated":invalidated,
            },
        }

    def pack(self, institutional):
        return build_setup_candidates(
            pair="EUR/USD",
            side="BUY",
            ict_snapshot={},
            institutional_snapshot=institutional,
            captured_at="2026-09-21T20:05:00Z",
        )

    def test_valid_bos_choch_plus_order_block_becomes_explicit_research_candidate(self):
        pack=self.pack(self.institutional())
        row=next(x for x in pack["models"] if x["setup_id"]=="bos-choch-ob")
        self.assertTrue(row["research_candidate"])
        self.assertEqual(row["source_model"],"BOS_CHOCH_OB")
        self.assertEqual(row["source_timeframe"],"M15")
        self.assertEqual(row["setup_attribution"],"SOURCE_MODEL_EXPLICIT")
        self.assertIn(row,pack["candidates"])
        self.assertFalse(row["paper_trade_created"])
        self.assertFalse(row["automatic_execution"])
        self.assertFalse(row["automatic_promotion"])
        self.assertFalse(row["real_orders_enabled"])

    def test_structure_without_valid_order_block_never_becomes_candidate(self):
        pack=self.pack(self.institutional(ob_status="⚪ SEM ORDER BLOCK VALIDADO",ob_side=""))
        row=next(x for x in pack["models"] if x["setup_id"]=="bos-choch-ob")
        self.assertFalse(row["research_candidate"])
        self.assertNotIn(row,pack["candidates"])

    def test_opposite_structure_or_invalidated_order_block_fails_closed(self):
        for institutional in (
            self.institutional(structure_side="SELL"),
            self.institutional(ob_status="🔴 ORDER BLOCK INVALIDADO",invalidated=True),
        ):
            with self.subTest(institutional=institutional):
                pack=self.pack(institutional)
                row=next(x for x in pack["models"] if x["setup_id"]=="bos-choch-ob")
                self.assertFalse(row["research_candidate"])

    def test_autopilot_refreezes_candidates_after_institutional_snapshot_exists(self):
        src=Path("autopilot_v107.py").read_text(encoding="utf-8")
        inst=src.index('_tec["institutional"] = build_institutional_snapshot(')
        refresh=src.index('institutional_snapshot=_tec.get("institutional",{})',inst)
        self.assertLess(inst,refresh)
        self.assertIn('setup_id":"bos-choch-ob"',Path("atlasquant_setup_candidates.py").read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()
