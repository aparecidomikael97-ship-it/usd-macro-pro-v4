import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from atlasquant_advanced_boot import (
    CACHED_SNAPSHOT,
    LIVE_REFRESH,
    STALE_REJECTED,
    peek_live_refresh,
    provenance_banner_html,
    publish_live_refresh,
    reset_live_refresh_for_tests,
    resolve_advanced_open,
    start_live_refresh,
)
from test_atlasquant_fast_startup import snapshot


class AdvancedBootTests(unittest.TestCase):
    def setUp(self):
        reset_live_refresh_for_tests()
        self.now = datetime(2026, 9, 20, 1, 30, tzinfo=timezone.utc)

    def tearDown(self):
        reset_live_refresh_for_tests()

    def test_valid_snapshot_opens_without_calling_providers(self):
        started = time.perf_counter()
        decision = resolve_advanced_open(snapshot(), now=self.now)
        elapsed = time.perf_counter() - started
        self.assertTrue(decision["use_cache"])
        self.assertEqual(decision["state"], CACHED_SNAPSHOT)
        self.assertLess(elapsed, 0.05)
        self.assertLess(decision["resolve_ms"], 50)
        self.assertIsInstance(decision["ranking"], pd.DataFrame)
        self.assertIn("Código", decision["ranking"].columns)
        self.assertEqual(decision["macro_eua"]["Juros do Fed"], 4.25)
        self.assertFalse(decision["real_orders_enabled"])
        self.assertFalse(decision["automatic_execution"])
        banner = provenance_banner_html(decision)
        self.assertIn("Leitura em cache", banner)
        self.assertIn("não trata o cache como coleta ao vivo", banner)
        self.assertIn("#1a1406", banner)
        self.assertNotIn("invented", banner)

    def test_expired_snapshot_is_not_painted_as_current(self):
        old = (self.now - timedelta(minutes=91)).isoformat()
        decision = resolve_advanced_open(snapshot(generated_at=old), now=self.now)
        self.assertFalse(decision["use_cache"])
        self.assertEqual(decision["state"], STALE_REJECTED)
        self.assertIsNone(decision["macro_eua"])
        self.assertIsNone(decision["ranking"])
        banner = provenance_banner_html(decision)
        self.assertIn("Snapshot antigo rejeitado", banner)
        self.assertIn("não apresenta dado vencido como atual", banner)

    def test_first_open_without_cache_requires_live_path(self):
        for empty in (None, {}, {"schema": "OTHER"}):
            with self.subTest(empty=empty):
                decision = resolve_advanced_open(empty, now=self.now)
                self.assertFalse(decision["use_cache"])
                self.assertIsNone(decision["dados_moedas"])
                self.assertNotEqual(decision["state"], CACHED_SNAPSHOT)

    def test_unsafe_snapshot_never_becomes_the_cached_open(self):
        decision = resolve_advanced_open(snapshot(real_orders=True), now=self.now)
        self.assertFalse(decision["use_cache"])
        self.assertFalse(decision["real_orders_enabled"])
        self.assertFalse(decision["automatic_execution"])

    def test_slow_refresh_returns_immediately_and_unavailable_source_stays_empty(self):
        gate = threading.Event()

        def slow():
            gate.wait(2)
            return {"juros": 1}

        started = time.perf_counter()
        status = start_live_refresh({"macro_eua": slow, "fed": slow, "dados_moedas": slow})
        self.assertEqual(status, "running")
        self.assertLess(time.perf_counter() - started, 0.4)
        self.assertIsNone(peek_live_refresh()["result"])
        gate.set()
        self.assertTrue(self._wait_status("ready"))
        self.assertEqual(peek_live_refresh()["result"]["macro_eua"]["juros"], 1)

        reset_live_refresh_for_tests()

        def down():
            raise TimeoutError("fonte indisponivel")

        start_live_refresh({"macro_eua": down, "fed": down, "dados_moedas": down})
        self.assertTrue(self._wait_status("failed"))
        failed = peek_live_refresh()
        self.assertIsNone(failed["result"])
        self.assertIn("TimeoutError", failed["error"])

    def test_ready_refresh_is_not_started_again(self):
        calls = []

        def loader():
            calls.append(1)
            return {"valor": 1}

        publish_live_refresh({
            "macro_eua": {"Juros do Fed": 4.25},
            "fed": {"tom": "Neutro"},
            "dados_moedas": {"USD": {"juros": 4.25}},
        })
        self.assertEqual(
            start_live_refresh({"macro_eua": loader, "fed": loader, "dados_moedas": loader}),
            "ready",
        )
        self.assertEqual(calls, [])
        banner = provenance_banner_html({
            "state": LIVE_REFRESH,
            "generated_at": peek_live_refresh()["finished_at"],
        })
        self.assertIn("Fontes atualizadas", banner)

    def test_main_keeps_live_loaders_after_the_fast_shell_stop(self):
        src = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        shell = src.index("load_home_snapshot(")
        macro = src.index("macro_eua = carregar_macro_eua()")
        fed = src.index("fed = carregar_narrativa_fed()")
        currencies = src.index("dados_moedas = carregar_dados_moedas()")
        self.assertLess(shell, macro)
        self.assertLess(macro, fed)
        self.assertLess(fed, currencies)
        between = src[shell:macro]
        self.assertIn("st.stop()", between)
        self.assertIn("resolve_advanced_open(", between)
        self.assertIn('os.getenv("USD_MACRO_AUTOPILOT", "") != "1"', between)
        self.assertIn("não trata o cache como coleta ao vivo", Path("atlasquant_advanced_boot.py").read_text(encoding="utf-8"))
        css = Path("atlasquant_ui_v1.py").read_text(encoding="utf-8")
        self.assertIn("color: #1a1406 !important", css)
        self.assertIn('color: #182230 !important', css)
        self.assertIn("Ler o que será falado", Path("atlasquant_voice_assistant.py").read_text(encoding="utf-8"))
        self.assertIn("render_top_voice_access", src)
        radar = Path("atlasquant_home_radar.py").read_text(encoding="utf-8")
        self.assertLess(radar.index("render_contextual_voice_assistant("), radar.index("### Top 10 em observação"))
        self.assertIn("Ranking de criptos", radar)
        self.assertIn("Autopilot/headless sem confirmação saudável", Path("atlasquant_central_brief.py").read_text(encoding="utf-8"))
        self.assertIn("Pipeline institucional completo ainda não cobre este par.", Path("atlasquant_radar_board.py").read_text(encoding="utf-8"))

    def _wait_status(self, expected: str) -> bool:
        for _ in range(40):
            if peek_live_refresh()["status"] == expected:
                return True
            time.sleep(0.05)
        return False


if __name__ == "__main__":
    unittest.main()
