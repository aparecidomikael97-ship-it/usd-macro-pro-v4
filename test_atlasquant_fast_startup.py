import unittest
from datetime import datetime, timezone, timedelta

from atlasquant_fast_startup import (
    SCHEMA,
    snapshot_age_minutes,
    validate_home_snapshot,
    validated_snapshot_pair_matrix,
    EXPECTED_FX_PAIRS,
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
            "pairs":[
                {"Par":pair,"Direção":("VENDA "+pair if pair.endswith("/USD") else "COMPRA "+pair),"Score final":80-i,"Qualidade":85-i,"Índice ranking":90-i}
                for i,pair in enumerate(EXPECTED_FX_PAIRS)
            ],
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




    def test_validated_snapshot_pair_matrix_recovers_all_seven_pairs(self):
        out=validated_snapshot_pair_matrix(snapshot(),now=self.now,max_age_min=90)
        self.assertTrue(out["ready"])
        self.assertEqual(out["source"],"runtime_snapshot")
        self.assertEqual(len(out["matrix"]),7)
        self.assertEqual(set(out["matrix"]["Par"]),set(EXPECTED_FX_PAIRS))
        self.assertIn("Ranking",out["matrix"].columns)
        self.assertFalse(out["real_orders_enabled"])
        self.assertFalse(out["automatic_execution"])

    def test_snapshot_pair_matrix_rejects_stale_or_incomplete_runtime(self):
        stale=snapshot(generated_at=(self.now-timedelta(minutes=91)).isoformat())
        self.assertFalse(validated_snapshot_pair_matrix(stale,now=self.now,max_age_min=90)["ready"])
        incomplete=snapshot()
        incomplete["inputs"]["pairs"]=incomplete["inputs"]["pairs"][:-1]
        out=validated_snapshot_pair_matrix(incomplete,now=self.now,max_age_min=90)
        self.assertFalse(out["ready"])
        self.assertIn("7 pares",out["reason"])

    def test_invalid_fast_snapshot_keeps_advanced_reachable(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        invalid=src.index('if not check["valid"]:')
        safe=src.index('"page":"SAFE_WAIT"',invalid)
        block=src[invalid:safe]
        self.assertIn('["Iniciante","Avançado"]',block)
        self.assertIn('"handled":False',block)
        self.assertIn('"mode":"Avançado"',block)

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

    def test_fast_beginner_menu_matches_all_open_beginner_destinations(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        self.assertIn('"💰 Investir"',src)
        self.assertIn('render_investment_center("Iniciante")',src)
        pages=src.index('_fast_pages=["🎯 Radar"')
        guard=src.index('if experience_compass_html is not None and page != "🎯 Radar":',pages)
        compass=src.index('experience_compass_html("Iniciante", page)',guard)
        radar=src.index('if page=="🎯 Radar":',compass)
        self.assertLess(pages,guard)
        self.assertLess(guard,compass)
        self.assertLess(compass,radar)

    def test_fast_home_keeps_classic_area_selector_as_compact_fallback_only(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        self.assertIn("_aq_fast_catalog_home=bool(",src)
        self.assertIn('_aq_fast_active_page=="🎯 Radar"',src)
        self.assertIn('with st.expander("Navegação alternativa",expanded=False):',src)
        self.assertIn('page=st.radio("Área",pages,horizontal=True,key="aq_beginner_page",label_visibility="collapsed")',src)
        compact=src.index('with st.expander("Navegação alternativa",expanded=False):')
        normal=src.index('else:\n        page=st.radio("Área"',compact)
        self.assertLess(compact,normal)

    def test_fast_shell_reuses_visible_build_from_authenticated_runtime(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        chrome=src[src.index("def _render_beginner_chrome"):src.index("def render_beginner_shell")]
        self.assertIn('build_id=str(st.session_state.get("atlasquant_visible_build") or "")',chrome)
        self.assertNotIn("RENDER_GIT_COMMIT",chrome)
        self.assertNotIn("GIT_COMMIT",chrome)

    def test_fast_shell_uses_shared_header_as_single_branding_surface(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        shell=src[src.index("def render_beginner_shell"):]

        self.assertNotIn('st.markdown("## 🧭 AtlasQuant")',shell)
        self.assertNotIn("carregamento rápido por snapshot validado",shell)
        self.assertIn("_render_beginner_chrome(app_version, environment, access)",shell)
        self.assertIn('key="aq_fast_refresh"',shell)
        self.assertIn('age_label=f"Runtime atualizado há {age:.0f} min"',shell)

    def test_fast_snapshot_controls_are_contextual_not_global_telemetry(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        shell=src[src.index("def render_beginner_shell"):]

        active=shell.index('_aq_fast_active_page=str(st.session_state.get("aq_beginner_page") or "🎯 Radar")')
        home=shell.index("if _aq_fast_catalog_home:",active)
        offhome=shell.index('with st.expander("Dados do snapshot",expanded=False):',home)
        caption=shell.index('st.caption(f"{age_label}',offhome)
        refresh=shell.index('key="aq_fast_refresh"',home)

        self.assertLess(active,home)
        self.assertLess(home,offhome)
        self.assertLess(offhome,caption)
        self.assertLess(home,refresh)
        self.assertIn("O Radar já mostra estado, idade, atualização e origem",shell)
        self.assertIn('st.expander("Dados do snapshot",expanded=False)',shell)
        self.assertEqual(shell.count('key="aq_fast_refresh"'),2)

    def test_fast_home_uses_reference_cockpit_without_generic_guidance_strips(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        shell=src[src.index("def render_beginner_shell"):]
        self.assertNotIn('experience_mode_overview_html("Iniciante")',shell)
        self.assertNotIn("mobile_navigation_hint_html()",shell)
        self.assertIn("_aq_fast_ticker_items=[]",shell)
        self.assertIn('"score":_finite(_aq_tick.get("Pontuação_Final",_aq_tick.get("score",50)),50)',shell)
        catalog=shell.index("render_premium_catalog(")
        call=shell[catalog:catalog+500]
        self.assertIn("ticker_items=_aq_fast_ticker_items",call)
        self.assertIn("cockpit continua sendo a entrada visual principal",shell)


    def test_fast_beginner_radar_passes_validated_freshness_metadata(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        radar=src.index('if page=="🎯 Radar":')
        block=src[radar:radar+2400]
        self.assertIn('"state":"VALIDATED_SNAPSHOT"',block)
        self.assertIn('"age_minutes":age',block)
        self.assertIn('"refresh_status":"carregamento rápido concluído"',block)
        self.assertIn('"source":"runtime snapshot"',block)
        self.assertIn("freshness=_freshness",block)

    def test_advanced_radar_passes_boot_freshness_without_touching_engine(self):
        from pathlib import Path
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        radar=src.index("if render_home_radar is not None:")
        block=src[radar:radar+2600]
        self.assertIn("_aq_radar_freshness",block)
        self.assertIn('"source"]=_aq_fresh_source',block)
        self.assertIn("freshness=_aq_radar_freshness",block)
        self.assertNotIn("real_orders_enabled=True",block)
        self.assertNotIn("automatic_execution=True",block)

    def test_fast_beginner_compass_never_expands_trading_permissions(self):
        from pathlib import Path
        src=Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        start=src.index('experience_compass_html("Iniciante", page)')
        block=src[start:start+2800]
        self.assertNotIn("real_orders_enabled=True",block)
        self.assertNotIn("automatic_execution=True",block)
        self.assertIn('st.caption("Modo Iniciante não conecta corretora e não envia ordens reais.")',src)

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
        valid_anchor='help="Iniciante abre rápido e mostra só o essencial. Avançado libera todos os diagnósticos."'
        start=src.index(valid_anchor)
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