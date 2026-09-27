import inspect
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from atlasquant_advanced_boot import (
    CACHED_SNAPSHOT,
    DEFAULT_SOURCE_TIMEOUTS,
    LIVE_REFRESH,
    STALE_REJECTED,
    collect_source_refresh,
    peek_live_refresh,
    provenance_banner_html,
    publish_live_refresh,
    reset_live_refresh_for_tests,
    resolve_advanced_open,
    start_live_refresh,
)
from atlasquant_fast_startup import DEFAULT_MAX_AGE_MIN, load_home_snapshot
from atlasquant_runtime_store import DEFAULT_RUNTIME_BRANCH, resolve_runtime_branch
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
        self.assertIn('_aq_warm_status == "idle"', src)
        self.assertNotIn('in {"idle", "failed"}', src)
        self.assertIn('"dados_moedas": 50.0', src)
        self.assertIn("_aq_refresh_noted", src)
        self.assertIn("pacote anterior mantido", src)
        self.assertIn("falhou sem substituir o snapshot", src)
        call = src.index("_fast_snapshot = load_home_snapshot(")
        window = src[max(0, call - 700):call]
        self.assertIn("resolve_runtime_branch", window)
        self.assertIn("_fast_branch", window)

    def test_sources_run_concurrently_and_a_slow_one_does_not_hold_the_rest(self):
        lock = threading.Lock()
        spans = {}

        def make(name):
            def loader():
                started_at = time.perf_counter()
                time.sleep(0.25)
                finished_at = time.perf_counter()
                with lock:
                    spans[name] = (started_at, finished_at)
                return {name: 1}
            return loader

        started = time.perf_counter()
        outcome = collect_source_refresh({
            "macro_eua": make("macro_eua"),
            "fed": make("fed"),
            "dados_moedas": make("dados_moedas"),
        })
        elapsed = time.perf_counter() - started
        self.assertTrue(outcome["publishable"])
        self.assertLess(elapsed, 0.6)
        self.assertGreater(max(end for _, end in spans.values()) - min(start for start, _ in spans.values()), 0.2)
        self.assertLess(max(start for start, _ in spans.values()), min(end for _, end in spans.values()))
        self.assertFalse(outcome["real_orders_enabled"])
        self.assertFalse(outcome["automatic_execution"])
        self.assertEqual(set(outcome["payload"]), {"macro_eua", "fed", "dados_moedas"})

        def fast_macro():
            return {"juros": 1}

        def fast_fed():
            return {"tom": "Neutro"}

        def slow_fx():
            time.sleep(1.2)
            return {"USD": {"juros": 1}}

        started = time.perf_counter()
        slow = collect_source_refresh(
            {"macro_eua": fast_macro, "fed": fast_fed, "dados_moedas": slow_fx},
            timeouts={"macro_eua": 0.35, "fed": 0.35, "dados_moedas": 0.4},
        )
        self.assertLess(time.perf_counter() - started, 0.9)
        self.assertEqual(slow["sources"]["macro_eua"]["state"], "ok")
        self.assertEqual(slow["sources"]["fed"]["state"], "ok")
        self.assertEqual(slow["sources"]["dados_moedas"]["state"], "slow")
        self.assertIn("lenta", slow["error"])
        self.assertIn("dados_moedas", slow["error"])
        self.assertFalse(slow["publishable"])
        self.assertIsNone(slow["payload"])

    def test_one_source_failure_stays_isolated_and_incomplete_payload_is_not_published(self):
        def ok_macro():
            return {"juros": 4.25}

        def bad_fed():
            raise RuntimeError("fed down")

        def ok_fx():
            return {"USD": {"juros": 4.25}}

        failed = collect_source_refresh({
            "macro_eua": ok_macro,
            "fed": bad_fed,
            "dados_moedas": ok_fx,
        })
        self.assertEqual(failed["sources"]["macro_eua"]["state"], "ok")
        self.assertEqual(failed["sources"]["dados_moedas"]["state"], "ok")
        self.assertEqual(failed["sources"]["fed"]["state"], "failed")
        self.assertIn("RuntimeError", failed["sources"]["fed"]["detail"])
        self.assertIn("fed", failed["error"])
        self.assertNotIn("value", failed["sources"]["fed"])
        self.assertFalse(failed["publishable"])
        self.assertIsNone(failed["payload"])
        self.assertFalse(failed["real_orders_enabled"])
        self.assertFalse(failed["automatic_execution"])

        for bad in ({}, None, ["not-a-mapping"]):
            with self.subTest(bad=bad):
                empty = collect_source_refresh({
                    "macro_eua": ok_macro,
                    "fed": lambda value=bad: value,
                    "dados_moedas": ok_fx,
                })
                self.assertEqual(empty["sources"]["fed"]["state"], "empty")
                self.assertIn("vazia", empty["error"])
                self.assertFalse(empty["publishable"])
                self.assertIsNone(empty["payload"])

        good = {
            "macro_eua": {"Juros do Fed": 4.25},
            "fed": {"tom": "Neutro"},
            "dados_moedas": {"USD": {"juros": 4.25}},
        }
        publish_live_refresh(good)
        before = peek_live_refresh()["result"]
        publish_live_refresh({"macro_eua": {"a": 1}, "fed": {}, "dados_moedas": {"b": 1}})
        self.assertEqual(peek_live_refresh()["result"], before)
        self.assertEqual(peek_live_refresh()["status"], "ready")

    def test_failed_refresh_keeps_the_previous_valid_package(self):
        good = {
            "macro_eua": {"Juros do Fed": 4.25},
            "fed": {"tom": "Neutro"},
            "dados_moedas": {"USD": {"juros": 4.25}},
        }
        publish_live_refresh(good)

        def ok():
            return {"juros": 9}

        def bad():
            raise RuntimeError("fed caiu")

        self.assertEqual(start_live_refresh({
            "macro_eua": ok,
            "fed": bad,
            "dados_moedas": ok,
        }, force=True), "running")
        warm = {}
        for _ in range(40):
            warm = peek_live_refresh()
            if warm["status"] != "running" and warm["sources"]:
                break
            time.sleep(0.05)
        self.assertEqual(warm["status"], "retained")
        self.assertEqual(warm["result"], good)
        self.assertEqual(warm["sources"]["fed"]["state"], "failed")
        self.assertEqual(warm["sources"]["macro_eua"]["state"], "ok")
        self.assertEqual(warm["sources"]["dados_moedas"]["state"], "ok")
        self.assertIn("fed", warm["error"])
        self.assertIn("RuntimeError", warm["error"])
        self.assertFalse(warm["real_orders_enabled"])
        self.assertFalse(warm["automatic_execution"])
        banner = provenance_banner_html({
            "state": LIVE_REFRESH,
            "refresh_status": "pacote anterior mantido; " + warm["error"],
        })
        self.assertIn("Pacote anterior mantido", banner)
        self.assertIn("#1a1406", banner)
        self.assertNotIn("Fontes atualizadas", banner)

    def test_fast_boot_snapshot_stays_on_runtime_branch_inside_the_freshness_window(self):
        self.assertEqual(DEFAULT_RUNTIME_BRANCH, "atlasquant-runtime")
        self.assertEqual(resolve_runtime_branch(None, None), "atlasquant-runtime")
        self.assertEqual(resolve_runtime_branch("main", "main"), "atlasquant-runtime")
        self.assertEqual(
            inspect.signature(load_home_snapshot).parameters["branch"].default,
            "atlasquant-runtime",
        )
        self.assertEqual(DEFAULT_MAX_AGE_MIN, 90.0)
        self.assertEqual(DEFAULT_SOURCE_TIMEOUTS, {"macro_eua": 25.0, "fed": 25.0, "dados_moedas": 50.0})
        fresh = resolve_advanced_open(snapshot(), now=self.now)
        self.assertTrue(fresh["use_cache"])
        self.assertLess(fresh["resolve_ms"], 50)
        stale = resolve_advanced_open(
            snapshot(generated_at=(self.now - timedelta(minutes=91)).isoformat()),
            now=self.now,
        )
        self.assertEqual(stale["state"], STALE_REJECTED)
        self.assertFalse(stale["use_cache"])

    def _wait_status(self, expected: str) -> bool:
        for _ in range(40):
            if peek_live_refresh()["status"] == expected:
                return True
            time.sleep(0.05)
        return False


if __name__ == "__main__":
    unittest.main()
