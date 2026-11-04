"""Daily refresh schedule is an inert, auditable proposal, never a Worker."""
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from atlasquant_trader_master_refresh_plan import (
    BRT, SCHEMA, SLOTS, day_slots, planned_refreshes,
)
from atlasquant_trader_master_refresh_ui import master_refresh_plan_html
from atlasquant_trader_radar_compact_ui import trader_radar_html

AT = datetime(2026, 11, 2, 8, 36, tzinfo=BRT)


class MasterRefreshPlanTests(unittest.TestCase):
    def test_daily_windows_are_brt_and_utc(self):
        rows = day_slots(date(2026, 11, 2))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["at_brt"], "2026-11-02T06:35:00-03:00")
        self.assertEqual(rows[0]["at_utc"], "2026-11-02T09:35:00+00:00")
        self.assertEqual(rows[1]["kind"], "SÉRIES OFICIAIS")
        self.assertTrue(all(item["state"] == "PLANEJADO_NÃO_EXECUTADO" for item in rows))
        self.assertFalse(any(item["trade_authorized"] for item in rows))

    def test_never_active_even_if_provider_flags_true(self):
        env = {
            "ATLASQUANT_CALENDAR_EODHD_ENABLED": "1",
            "ATLASQUANT_MASTER_OFFICIAL_DATA_ENABLED": "1",
            "ATLASQUANT_CALENDAR_MAX_CALLS_PER_DAY": "4",
        }
        plan = planned_refreshes(at=AT, days=2, env=env)
        self.assertTrue(plan["calendar_provider_enabled"])
        self.assertTrue(plan["official_provider_enabled"])
        self.assertFalse(plan["background_executor_enabled"])
        self.assertFalse(plan["job_scheduled"])
        self.assertEqual(plan["external_requests"], 0)
        self.assertFalse(plan["aion_worker_enabled"])
        self.assertFalse(plan["trade_authorized"])
        self.assertEqual(plan["budget_state"], "CABE_NO_LIMITE_POR_PROCESSO")

    def test_disabled_providers_are_not_implicitly_activated(self):
        plan = planned_refreshes(at=AT, days=1, env={})
        self.assertEqual(plan["schema"], SCHEMA)
        self.assertFalse(plan["calendar_provider_enabled"])
        self.assertFalse(plan["official_provider_enabled"])
        self.assertEqual(plan["state"], "NÃO ATIVADO · SIMULAÇÃO DE JANELAS")

    def test_calendar_slots_reserve_on_demand_capacity(self):
        self.assertEqual(sum(i[0] == "CALENDÁRIO" for i in SLOTS), 3)
        self.assertEqual(sum(i[0] == "SÉRIES OFICIAIS" for i in SLOTS), 1)
        plan = planned_refreshes(at=AT, env={})
        self.assertEqual(plan["calendar_slots_per_day"], 3)
        self.assertEqual(plan["on_demand_reserve"], 1)
        self.assertEqual(plan["calendar_process_cap"], 4)
        self.assertEqual(plan["budget_state"], "CABE_NO_LIMITE_POR_PROCESSO")
        insufficient = planned_refreshes(
            at=AT, env={"ATLASQUANT_CALENDAR_MAX_CALLS_PER_DAY": "2"})
        self.assertEqual(insufficient["budget_state"], "LIMITE_INSUFICIENTE")

    def test_next_upcoming_slot_from_eight_thirty_six(self):
        plan = planned_refreshes(at=AT, days=1, env={})
        self.assertEqual(plan["next_slot"]["at_brt"][11:16], "10:45")
        self.assertEqual(len(plan["slots"]), 4)

    def test_next_day_rollover_and_week_horizon(self):
        now = AT.replace(hour=18, minute=0)
        one = planned_refreshes(at=now, days=1, env={})
        self.assertIsNone(one["next_slot"])
        week = planned_refreshes(at=now, days=7, env={})
        self.assertEqual(week["next_slot"]["at_brt"], "2026-11-03T06:35:00-03:00")
        self.assertEqual(len(week["slots"]), 28)

    def test_timezone_conversion_does_not_move_brt_clock(self):
        utc_time = datetime(2026, 11, 2, 11, 36, tzinfo=timezone.utc)
        self.assertEqual(planned_refreshes(at=utc_time, env={})["date_brt"],
                         "2026-11-02")
        self.assertEqual(planned_refreshes(at=utc_time, env={})["next_slot"]["at_brt"][11:16],
                         "10:45")

    def test_naive_time_or_invalid_horizon_rejected(self):
        for val in (0, 8, True, "7"):
            with self.subTest(days=val):
                with self.assertRaises(ValueError):
                    planned_refreshes(at=AT, days=val)
        with self.assertRaises(ValueError):
            planned_refreshes(at=datetime(2026, 11, 2, 8, 36))
        with self.assertRaises(ValueError):
            day_slots(datetime(2026, 11, 2, 8, 36))

    def test_ui_is_explicitly_not_a_scheduler(self):
        html = master_refresh_plan_html(planned_refreshes(at=AT, days=1, env={}))
        self.assertIn("AINDA NÃO ATIVADO", html)
        self.assertIn("não executa essas consultas com o aplicativo fechado", html)
        self.assertIn("06:35 BRT", html)
        self.assertIn("10:45 BRT", html)
        self.assertIn("SÉRIES OFICIAIS", html)
        self.assertNotIn("<button", html)
        self.assertNotIn("Agendamento ativo", html)

    def test_master_approved_shell_remains_unchanged(self):
        html = trader_radar_html(selected="master")
        self.assertIn('data-visual-reference="approved-20261102-v1"', html)
        self.assertIn("Atualização diária · planejamento", html)
        self.assertIn("Indicadores oficiais · Brasil e EUA", html)
        self.assertIn("AINDA NÃO ATIVADO", html)
        self.assertIn("Nenhuma observação foi simulada", html)


if __name__ == "__main__":
    unittest.main()
