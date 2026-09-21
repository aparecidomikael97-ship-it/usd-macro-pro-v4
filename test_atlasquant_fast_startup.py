import unittest
from datetime import datetime, timezone, timedelta

from atlasquant_fast_startup import (
    SCHEMA,
    snapshot_age_minutes,
    validate_home_snapshot,
    load_home_snapshot,
)


def snapshot(*, generated_at=None, real_orders=False, automatic_execution=False):
    now=datetime(2026,9,20,1,30,tzinfo=timezone.utc)
    generated_at=generated_at or (now-timedelta(minutes=30)).isoformat()
    return {
        "schema":SCHEMA,
        "generated_at":generated_at,
        "packs":[{"pair":"EUR/USD","direction":"VENDA"}],
        "inputs":{
            "fast_boot":{
                "ranking":[{"Código":"USD","Pontuação_Final":60}],
                "fed":{"tom":"Restritivo","forca":0.4},
                "macro_eua":{"Juros do Fed":4.25},
                "dados_moedas":{"USD":{"juros":4.25}},
                "usd_detalhado":{"score":60},
            },
            "macro_context":{"event":{"disponivel":False}},
        },
        "safety":{
            "real_orders":real_orders,
            "automatic_execution":automatic_execution,
        },
    }


class FastStartupTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,9,20,1,30,tzinfo=timezone.utc)

    def test_fresh_safe_snapshot_is_valid(self):
        out=validate_home_snapshot(snapshot(),now=self.now,max_age_min=90)
        self.assertTrue(out["valid"])
        self.assertAlmostEqual(out["age_minutes"],30.0,places=2)
        self.assertFalse(out["real_orders_enabled"])
        self.assertFalse(out["automatic_execution"])

    def test_runtime_timestamp_can_refresh_fast_home_without_rewriting_macro_timestamp(self):
        s=snapshot(generated_at=(self.now-timedelta(hours=12)).isoformat())
        s["runtime_generated_at"]=(self.now-timedelta(minutes=8)).isoformat()
        out=validate_home_snapshot(s,now=self.now,max_age_min=90)
        self.assertTrue(out["valid"])
        self.assertAlmostEqual(out["age_minutes"],8.0,places=2)
        self.assertAlmostEqual(out["input_age_minutes"],720.0,places=2)

    def test_stale_runtime_timestamp_still_fails_closed(self):
        s=snapshot()
        s["runtime_generated_at"]=(self.now-timedelta(minutes=91)).isoformat()
        out=validate_home_snapshot(s,now=self.now,max_age_min=90)
        self.assertFalse(out["valid"])
        self.assertIn("stale",out["errors"])

    def test_stale_snapshot_fails_closed(self):
        old=(self.now-timedelta(minutes=91)).isoformat()
        out=validate_home_snapshot(snapshot(generated_at=old),now=self.now,max_age_min=90)
        self.assertFalse(out["valid"])
        self.assertIn("stale",out["errors"])

    def test_future_timestamp_fails_closed(self):
        future=(self.now+timedelta(minutes=5)).isoformat()
        self.assertIsNone(snapshot_age_minutes(snapshot(generated_at=future),now=self.now))
        out=validate_home_snapshot(snapshot(generated_at=future),now=self.now)
        self.assertFalse(out["valid"])
        self.assertIn("generated_at",out["errors"])

    def test_missing_fast_boot_contract_fails_closed(self):
        s=snapshot()
        s["inputs"]["fast_boot"].pop("ranking")
        out=validate_home_snapshot(s,now=self.now)
        self.assertFalse(out["valid"])
        self.assertIn("fast_boot.ranking",out["errors"])

    def test_live_execution_claim_is_rejected(self):
        for key in ("real_orders","automatic_execution"):
            with self.subTest(key=key):
                kwargs={key:True}
                out=validate_home_snapshot(snapshot(**kwargs),now=self.now)
                self.assertFalse(out["valid"])
                self.assertIn(key,out["errors"])

    def test_wrong_schema_is_rejected(self):
        s=snapshot(); s["schema"]="OTHER"
        out=validate_home_snapshot(s,now=self.now)
        self.assertFalse(out["valid"])
        self.assertIn("schema",out["errors"])


    def test_snapshot_loader_timeout_is_bounded_for_fast_boot(self):
        import inspect
        signature=inspect.signature(load_home_snapshot)
        self.assertEqual(signature.parameters["timeout"].default,4.0)
        src=inspect.getsource(load_home_snapshot)
        self.assertIn("min(float(timeout),8.0)",src)
        self.assertIn("if token:",src)

    def test_fast_loader_records_non_trading_observability(self):
        import inspect
        src=inspect.getsource(load_home_snapshot)
        self.assertIn('"_fast_boot_observability"',src)
        self.assertIn('"load_ms"',src)
        self.assertIn('_with_obs(r.json(),"raw")',src)
        self.assertIn('_with_obs(obj,"api")',src)
        self.assertNotIn("real_orders_enabled",src)
        self.assertNotIn("automatic_execution",src)

    def test_beginner_shell_persists_startup_observability_only_after_valid_snapshot(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        validate_pos=src.index("check=validate_home_snapshot(snapshot)")
        obs_pos=src.index('st.session_state["atlasquant_fast_boot_observability"]')
        self.assertLess(validate_pos,obs_pos)
        block=src[obs_pos:src.index("st.markdown(",obs_pos)]
        self.assertIn('"snapshot_valid":True',block)
        self.assertIn('"mode":"Iniciante"',block)

    def test_main_attempts_fast_shell_before_heavy_provider_boot(self):
        from pathlib import Path
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        shell=src.index("load_home_snapshot(")
        macro=src.index("macro_eua = carregar_macro_eua()")
        fed=src.index("fed = carregar_narrativa_fed()")
        currencies=src.index("dados_moedas = carregar_dados_moedas()")
        self.assertLess(shell,macro)
        self.assertLess(shell,fed)
        self.assertLess(shell,currencies)
        between=src[shell:macro]
        self.assertIn('if bool(_fast_result.get("handled",False)):',between)
        self.assertIn("st.stop()",between)

    def test_advanced_transition_does_not_force_extra_streamlit_rerun(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        start=src.index("mode=st.radio(")
        end=src.index('age=float(check["age_minutes"] or 0.0)',start)
        block=src[start:end]
        self.assertIn('"handled":False',block)
        self.assertIn('"mode":"Avançado"',block)
        self.assertNotIn("st.rerun()",block)

    def test_headless_autopilot_never_uses_fast_shell(self):
        from pathlib import Path
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn('os.getenv("USD_MACRO_AUTOPILOT", "") != "1"',src)


if __name__=="__main__":
    unittest.main()