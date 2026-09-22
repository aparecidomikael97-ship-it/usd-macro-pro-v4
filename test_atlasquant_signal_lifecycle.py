import unittest
import pandas as pd

from atlasquant_signal_lifecycle import (
    M15_FRESH_MINUTES,
    advance_signal_lifecycle,
    annotate_packs_with_lifecycle,
    derive_signal_view,
    format_signal_time,
)


NOW=pd.Timestamp("2026-09-22T12:00:00Z")


def pack(*, side="BUY", age=10, executable=False, sufficient=True, state="🟡 QUASE PRONTO", hard_blocks=None):
    ts=NOW-pd.Timedelta(minutes=age) if age is not None else None
    return {
        "pair":"EUR/USD",
        "side":side,
        "direction":"🟢 COMPRA EUR/USD" if side=="BUY" else "🔴 VENDA EUR/USD" if side=="SELL" else "⚪ AGUARDAR",
        "state":state,
        "executable":executable,
        "technical_timestamp":"" if ts is None else ts.isoformat(),
        "technical_age":age,
        "stale_technical":[],
        "hard_blocks":list(hard_blocks or []),
        "data_ready":{
            "sufficient":sufficient,
            "timeframes":{"m15":{"fresh":bool(age is not None and age<=M15_FRESH_MINUTES)}},
        },
    }


class AtlasQuantSignalLifecycleTests(unittest.TestCase):
    def test_possible_reading_has_time_age_and_bounded_validity(self):
        view=derive_signal_view(pack(age=12),now=NOW)
        self.assertEqual(view["status_code"],"POSSIBLE")
        self.assertIn("AGUARDANDO GATILHO",view["status_label"])
        self.assertEqual(view["age_minutes"],12)
        self.assertAlmostEqual(view["remaining_minutes"],M15_FRESH_MINUTES-12)
        self.assertIn("UTC",view["reference_display"])
        self.assertFalse(view["automatic_execution"])

    def test_executable_fresh_reading_is_confirmed(self):
        view=derive_signal_view(
            pack(age=5,executable=True,sufficient=True,state="🟢 EXECUTÁVEL"),
            now=NOW,
        )
        self.assertEqual(view["status_code"],"CONFIRMED")
        self.assertTrue(view["is_current_confirmation"])

    def test_old_directional_reading_expires_instead_of_looking_current(self):
        view=derive_signal_view(pack(age=61,executable=True),now=NOW)
        self.assertEqual(view["status_code"],"EXPIRED")
        self.assertTrue(view["requires_revalidation"])
        self.assertEqual(view["remaining_minutes"],0.0)

    def test_missing_timestamp_never_invents_confirmation_time(self):
        view=derive_signal_view(pack(age=None,executable=True),now=NOW)
        self.assertEqual(view["status_code"],"UNVERIFIED")
        self.assertEqual(view["reference_at"],"")
        self.assertEqual(view["reference_display"],"horário não comprovado")
        self.assertFalse(view["is_current_confirmation"])

    def test_hard_block_overrides_possible_but_not_timestamp_integrity(self):
        view=derive_signal_view(pack(age=10,hard_blocks=["EVENTO"]),now=NOW)
        self.assertEqual(view["status_code"],"BLOCKED")
        self.assertIn("NÃO ENTRAR",view["status_label"])

    def test_lifecycle_records_first_confirmation_transition(self):
        first=advance_signal_lifecycle({},[pack(age=10)],now=NOW)
        row=first["pairs"]["EUR/USD"]
        self.assertEqual(row["status_code"],"POSSIBLE")
        self.assertTrue(row["observed_at"])
        self.assertFalse(row["confirmed_at"])

        later=NOW+pd.Timedelta(minutes=3)
        second=advance_signal_lifecycle(
            first,
            [pack(age=13,executable=True,sufficient=True,state="🟢 EXECUTÁVEL")],
            now=later,
        )
        row2=second["pairs"]["EUR/USD"]
        self.assertEqual(row2["status_code"],"CONFIRMED")
        self.assertEqual(row2["confirmed_at"],later.isoformat())
        self.assertEqual(row2["observed_at"],row["observed_at"])
        self.assertTrue(any(x["to_status"]=="CONFIRMED" for x in second["transitions"]))

    def test_direction_change_creates_new_generation_and_resets_confirmation(self):
        first=advance_signal_lifecycle(
            {},
            [pack(age=5,executable=True,sufficient=True,state="🟢 EXECUTÁVEL")],
            now=NOW,
        )
        later=NOW+pd.Timedelta(minutes=2)
        sell=pack(side="SELL",age=7,executable=False,state="🟡 QUASE PRONTO")
        second=advance_signal_lifecycle(first,[sell],now=later)
        row=second["pairs"]["EUR/USD"]
        self.assertEqual(row["side"],"SELL")
        self.assertEqual(row["generation"],first["pairs"]["EUR/USD"]["generation"]+1)
        self.assertFalse(row["confirmed_at"])
        self.assertEqual(row["observed_at"],later.isoformat())

    def test_annotation_uses_current_freshness_not_old_persisted_status(self):
        old=advance_signal_lifecycle(
            {},
            [pack(age=5,executable=True,sufficient=True,state="🟢 EXECUTÁVEL")],
            now=NOW,
        )
        stale_now=NOW+pd.Timedelta(minutes=70)
        stale_pack=pack(age=75,executable=True,sufficient=False,state="🟢 EXECUTÁVEL")
        annotated=annotate_packs_with_lifecycle([stale_pack],old,now=stale_now)
        self.assertEqual(annotated[0]["signal_lifecycle"]["status_code"],"EXPIRED")
        self.assertTrue(annotated[0]["signal_lifecycle"]["confirmed_at"])

    def test_format_supports_explicit_timezone_without_changing_source(self):
        text=format_signal_time("2026-09-22T12:00:00Z","America/Manaus")
        self.assertEqual(text,"22/09/2026 08:00 America/Manaus")


if __name__=="__main__":
    unittest.main()
