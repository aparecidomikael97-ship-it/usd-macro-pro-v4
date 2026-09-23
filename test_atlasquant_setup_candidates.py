import unittest
from pathlib import Path

from atlasquant_setup_candidates import build_setup_candidates


class BosChochOrderBlockCandidateTests(unittest.TestCase):
    def institutional(
        self,
        *,
        structure_event="CHOCH",
        structure_side="BUY",
        structure_status="🟢 CHOCH CONFIRMADO",
        structure_score=92,
        ob_status="🟡 ORDER BLOCK ATIVO",
        ob_side="BUY",
        ob_score=68,
        invalidated=False,
        zone_low=1.0990,
        zone_high=1.1000,
    ):
        return {
            "structure":{
                "status":structure_status,
                "score":structure_score,
                "event":structure_event,
                "event_side":structure_side,
                "level":1.1010,
                "break_time":"2026-09-21T20:00:00Z",
            },
            "order_block":{
                "status":ob_status,
                "score":ob_score,
                "side":ob_side,
                "zone_low":zone_low,
                "zone_high":zone_high,
                "origin_time":"2026-09-21T19:30:00Z",
                "mitigation_depth_pct":25.0,
                "invalidated":invalidated,
            },
        }

    def pack(self, institutional, *, side="BUY"):
        return build_setup_candidates(
            pair="EUR/USD",
            side=side,
            ict_snapshot={},
            institutional_snapshot=institutional,
            captured_at="2026-09-21T20:05:00Z",
        )

    def row(self, pack):
        return next(x for x in pack["models"] if x["setup_id"]=="bos-choch-ob")

    def test_valid_bos_choch_plus_order_block_is_explicit_research_candidate(self):
        pack=self.pack(self.institutional())
        row=self.row(pack)
        self.assertTrue(row["research_candidate"])
        self.assertEqual(row["source_model"],"BOS_CHOCH_OB")
        self.assertEqual(row["source_timeframe"],"M15")
        self.assertEqual(row["setup_attribution"],"SOURCE_MODEL_EXPLICIT")
        self.assertEqual(row["score"],68)
        self.assertIn(row,pack["candidates"])
        self.assertFalse(row["paper_trade_created"])
        self.assertFalse(row["automatic_execution"])
        self.assertFalse(row["automatic_promotion"])
        self.assertFalse(row["real_orders_enabled"])

    def test_bos_and_choch_are_both_supported_when_green_and_aligned(self):
        for event,status in (
            ("BOS","🟢 BOS CONFIRMADO"),
            ("CHOCH","🟢 CHOCH CONFIRMADO"),
        ):
            with self.subTest(event=event):
                row=self.row(self.pack(self.institutional(
                    structure_event=event,
                    structure_status=status,
                )))
                self.assertTrue(row["research_candidate"])

    def test_structure_without_valid_order_block_fails_closed(self):
        row=self.row(self.pack(self.institutional(
            ob_status="⚪ SEM ORDER BLOCK VALIDADO",
            ob_side="",
            invalidated=None,
        )))
        self.assertFalse(row["research_candidate"])

    def test_opposite_structure_or_order_block_side_fails_closed(self):
        cases=(
            self.institutional(structure_side="SELL"),
            self.institutional(ob_side="SELL"),
        )
        for institutional in cases:
            with self.subTest(institutional=institutional):
                self.assertFalse(self.row(self.pack(institutional))["research_candidate"])

    def test_invalidated_order_block_fails_closed(self):
        row=self.row(self.pack(self.institutional(
            ob_status="🔴 ORDER BLOCK INVALIDADO",
            invalidated=True,
        )))
        self.assertFalse(row["research_candidate"])

    def test_missing_or_ambiguous_invalidation_flag_fails_closed(self):
        for value in (None,"","unknown","<NA>"):
            with self.subTest(value=value):
                row=self.row(self.pack(self.institutional(invalidated=value)))
                self.assertFalse(row["research_candidate"])

    def test_missing_or_inverted_zone_fails_closed(self):
        cases=(
            self.institutional(zone_low=None,zone_high=1.1000),
            self.institutional(zone_low=1.1010,zone_high=1.1000),
        )
        for institutional in cases:
            with self.subTest(institutional=institutional):
                self.assertFalse(self.row(self.pack(institutional))["research_candidate"])

    def test_wait_side_never_becomes_candidate(self):
        row=self.row(self.pack(self.institutional(),side="WAIT"))
        self.assertFalse(row["research_candidate"])

    def test_no_institutional_snapshot_keeps_fifth_model_observational_only(self):
        pack=build_setup_candidates(
            pair="EUR/USD",
            side="BUY",
            ict_snapshot={
                "crt":{"status":"🟢 CRT CONFIRMADO","score":100,"phase":"DISTRIBUIÇÃO"},
                "ote":{"status":"🟢 DENTRO DO OTE","score":90},
                "amd":{"status":"🟢 AMD / PO3 EM DISTRIBUIÇÃO","score":100,"phase":"DISTRIBUIÇÃO"},
                "fvg":{"status":"🟢 FVG EM TESTE","score":90,"zone_low":1.1,"zone_high":1.2},
            },
            captured_at="2026-09-21T20:05:00Z",
        )
        self.assertEqual(len(pack["models"]),5)
        self.assertEqual(pack["candidate_count"],4)
        self.assertFalse(self.row(pack)["research_candidate"])

    def test_autopilot_refreezes_after_institutional_snapshot_exists(self):
        src=Path("autopilot_v107.py").read_text(encoding="utf-8")
        inst=src.index('_tec["institutional"] = build_institutional_snapshot(')
        refresh=src.index('institutional_snapshot=_tec.get("institutional",{})',inst)
        save=src.index('_old["tecnico"] = _tec',refresh)
        self.assertLess(inst,refresh)
        self.assertLess(refresh,save)


if __name__=="__main__":
    unittest.main()
