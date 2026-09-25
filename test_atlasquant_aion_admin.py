import unittest
from pathlib import Path

from atlasquant_aion_admin import AION_ADMIN_CSS, AION_WORKSPACES, _attention_queue


class AtlasQuantAionAdminTests(unittest.TestCase):
    def test_futuristic_ui_is_css_only_and_mobile_safe(self):
        self.assertIn("perspective", AION_ADMIN_CSS)
        self.assertIn("radial-gradient", AION_ADMIN_CSS)
        self.assertIn("@media(max-width:760px)", AION_ADMIN_CSS)
        self.assertIn("prefers-reduced-motion", AION_ADMIN_CSS)
        self.assertNotIn("MutationObserver", AION_ADMIN_CSS)
        self.assertNotIn("document.querySelector", AION_ADMIN_CSS)

    def test_admin_uses_stable_single_workspace_navigation(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertEqual(len(AION_WORKSPACES),9)
        self.assertIn('st.selectbox(',src)
        self.assertIn('"Área AION"',src)
        self.assertIn('key="aion_admin_workspace"',src)
        self.assertNotIn("tabs = st.tabs(",src)
        self.assertIn("uma área por vez",src)
        for label in AION_WORKSPACES:
            self.assertIn(f'selected_workspace == "{label}"',src)

    def test_central_operations_map_covers_all_nine_workspaces_without_actions(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("def _workspace_overview_items(", src)
        self.assertIn("def _render_workspace_overview(", src)
        self.assertIn("Mapa Operacional AION", src)
        for label in AION_WORKSPACES:
            self.assertIn(f'"name": "{label}"', src)
        self.assertIn("O mapa é somente leitura", src)
        self.assertIn("não aprova, publica, cobra, provisiona acesso nem envia ordens", src)
        self.assertIn('state": "REAL BLOQUEADO"', src)

    def test_central_operations_map_has_mobile_layout(self):
        self.assertIn(".aion-workspace-grid", AION_ADMIN_CSS)
        self.assertIn("@media(max-width:430px)", AION_ADMIN_CSS)
        self.assertIn("grid-template-columns:1fr", AION_ADMIN_CSS)

    def test_central_attention_queue_prioritizes_approvals_and_maps_area(self):
        board={
            "attention":[
                {
                    "area":"subscriptions",
                    "label":"Auditoria comercial",
                    "state":"UNKNOWN",
                    "next_action":"Confirmar runtime.",
                }
            ]
        }
        inbox={
            "status":"CONFIRMED",
            "next_items":[
                {
                    "priority":"P0",
                    "area":"studio",
                    "title":"Publicar vídeo",
                    "status":"WAITING_APPROVAL",
                }
            ],
        }
        rows=_attention_queue(board,inbox,limit=8)
        self.assertEqual(rows[0]["source"],"APROVAÇÃO")
        self.assertEqual(rows[0]["area"],"🎬 Studio")
        self.assertEqual(rows[1]["area"],"🔐 Assinaturas")
        self.assertIn("nenhuma aprovação é automática",rows[0]["next_action"])

    def test_central_next_action_is_read_only(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Próxima Ação AION",src)
        self.assertIn("Fila consolidada de atenção",src)
        self.assertIn("não aprova",src)
        self.assertIn("não provisiona acesso",src)
        self.assertIn("_render_attention_queue(status_board, approval_inbox)",src)

    def test_central_memory_guardian_posture_is_read_only_and_fail_closed(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Memória & Guardian",src)
        self.assertIn("checkpoint_integrity_report(checkpoint)",src)
        self.assertIn("guardian_posture(access, feature_flags=flags)",src)
        self.assertIn("runtime_write_preflight(runtime_result)",src)
        self.assertIn("A matriz é calculada com approved=False",src)
        self.assertIn("não sobrescreve esse estado automaticamente",src)
        self.assertIn('"checkpoint_integrity_state"',src)
        self.assertIn('"guardian_blocked_now"',src)

    def test_central_exposes_read_only_security_incident_center(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Centro de Segurança & Incidentes",src)
        self.assertIn("collect_incidents(",src)
        self.assertIn("incident_center_rows(snapshot)",src)
        self.assertIn("incident_response_plan(selected)",src)
        self.assertIn("Rollback",src)
        self.assertIn("Isso não dispara rollback automaticamente.",src)
        self.assertIn("rotação automática de segredo: NÃO",src)
        self.assertIn('"incident_center_total"',src)
        self.assertIn('"incident_center_has_critical"',src)
        self.assertIn('"incident_center_rollback_review"',src)

    def test_laboratory_shows_incident_posture_without_enabling_features(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Segurança / resposta a incidente",src)
        self.assertIn("rollback automático: NÃO",src)
        self.assertIn("nenhuma feature externa é ativada como tentativa de diagnóstico",src)

    def test_central_exposes_checkpoint_v7_continuity_and_handoff(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Continuidade & Handoff",src)
        self.assertIn("continuity_briefing(",src)
        self.assertIn("Onde paramos:",src)
        self.assertIn("último handoff registrado no Checkpoint",src)
        self.assertIn('"continuity_active_missions"',src)
        self.assertIn('"continuity_handoff_count"',src)

    def test_development_persists_structured_missions_without_executing_them(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Missões persistentes",src)
        self.assertIn("new_mission(",src)
        self.assertIn("upsert_mission(",src)
        self.assertIn("transition_mission(",src)
        self.assertIn("update_continuity_checkpoint(",src)
        self.assertIn("mission_registered",src)
        self.assertIn("mission_updated",src)

    def test_secretary_registers_handoff_only_in_working_checkpoint_until_saved(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Handoff da sessão",src)
        self.assertIn("build_session_handoff(",src)
        self.assertIn("append_handoff(",src)
        self.assertIn("Registrar handoff no Checkpoint",src)
        self.assertIn("persistência definitiva ainda exige salvar o Checkpoint",src)
        self.assertIn("session_handoff_recorded",src)

    def test_admin_console_requires_admin_and_keeps_external_actions_guarded(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("if not is_admin(access_map):", src)
        self.assertIn("guardian_decision(", src)
        self.assertIn("feature_flag_snapshot", src)
        self.assertIn("save_runtime_checkpoint(", src)
        self.assertIn("approved=True", src)
        self.assertIn("real_orders_enabled", src)

    def test_admin_console_contains_all_approved_workspaces(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        for label in (
            "🧠 Central",
            "🗂️ Secretaria",
            "📈 Trading",
            "🎬 Studio",
            "💼 Negócios",
            "🧪 Laboratório",
            "🛠️ Desenvolvimento",
            "🔐 Assinaturas",
            "🎟️ Promoções",
        ):
            self.assertIn(label, src)

    def test_secretary_uses_working_checkpoint_and_audit_events(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("_working_checkpoint(", src)
        self.assertIn("_set_working_checkpoint(", src)
        self.assertIn("_render_secretary(", src)
        self.assertIn("new_task(", src)
        self.assertIn("approve_task(", src)
        self.assertIn("_record_working_event(", src)
        self.assertIn("Observabilidade / auditoria", src)

    def test_checkpoint_save_clears_dirty_only_after_verified_readback(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        success = src.index('if result.get("saved") and result.get("verified"):')
        block = src[success:success+950]
        self.assertIn('saved_checkpoint = ensure_operating_checkpoint(result.get("checkpoint"))', block)
        self.assertIn('_set_working_checkpoint(saved_checkpoint, dirty=False)', block)
        self.assertIn("Checkpoint Mestre salvo, relido e confirmado no runtime.", block)
        self.assertIn("As alterações locais continuam marcadas como pendentes.",src)

    def test_checkpoint_persistence_preflight_fails_closed_before_save_button(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("runtime_write_preflight(runtime_result)",src)
        self.assertIn("persistence_blocked = bool(conflict or not persistence_preflight.get(\"allowed\"))",src)
        self.assertIn("disabled=persistence_blocked",src)
        self.assertIn("As alterações locais continuam marcadas como pendentes.",src)
        self.assertIn("result.get(\"saved\") and result.get(\"verified\")",src)
        self.assertIn("result.get(\"checkpoint\")",src)


    def test_dirty_checkpoint_detects_runtime_conflict_before_save(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("_WORKING_CONFLICT_KEY", src)
        self.assertIn("Conflito detectado:", src)
        self.assertIn("persistence_blocked = bool(conflict or not persistence_preflight.get(\"allowed\"))", src)
        self.assertIn("disabled=persistence_blocked", src)
        self.assertIn("não vai sobrescrever a versão nova automaticamente", src)
        self.assertIn("Descartar alterações locais e recarregar runtime", src)

    def test_development_exposes_guarded_versioned_checkpoint_recovery(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Recuperação / Rollback do Checkpoint",src)
        self.assertIn("list_checkpoint_revisions(",src)
        self.assertIn("load_checkpoint_revision(",src)
        self.assertIn("recovery_preflight(runtime_result, candidate)",src)
        self.assertIn('"restore_checkpoint"',src)
        self.assertIn("restore_checkpoint_revision(",src)
        self.assertIn("Confirmo que revisei esta versão",src)
        self.assertIn("Não existe restauração automática.",src)
        self.assertIn("Há alterações locais ainda não persistidas",src)
        self.assertIn("checkpoint_recovery_restored",Path("atlasquant_aion_recovery.py").read_text(encoding="utf-8"))

    def test_promotions_heading_no_longer_mixes_subscriptions_workspace(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn('st.markdown("### 🎟️ Promoções")',src)
        self.assertNotIn('st.markdown("### 🎟️ Assinaturas & Promoções")',src)

    def test_laboratory_exposes_budget_router_without_enabling_billing(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Roteador de inteligência / orçamento", src)
        self.assertIn("Teto mensal máximo para IA externa (USD)", src)
        self.assertIn("Permitir solicitações pagas dentro do teto", src)
        self.assertIn("set_budget_policy(", src)
        self.assertIn("route_intelligence(", src)
        self.assertIn("Definir teto não gera cobrança", src)

    def test_central_records_router_decision_before_local_answer(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        route=src.index("route = route_intelligence(")
        answer=src.index("answer = local_answer(",route)
        self.assertLess(route,answer)
        self.assertIn('st.session_state["aion_last_route"] = route',src)
        self.assertIn("Roteamento:",src)

    def test_contextual_voice_exists_for_all_aion_workspaces(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(src.count("_context_voice("),9)
        for area in (
            "Central","Secretaria","Trading","Studio",
            "Negócios","Laboratório","Desenvolvimento","Assinaturas","Promoções",
        ):
            self.assertIn(f'"{area}",', src)
        self.assertIn("nunca toca sozinha", src)
        self.assertIn("pode consumir esse serviço", src)

    def test_external_model_path_is_opt_in_and_cost_guarded(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Usar inteligência externa nesta pergunta", src)
        self.assertIn("Aprovo esta solicitação externa dentro do teto informado", src)
        self.assertIn("execute_openai_answer(", src)
        self.assertIn("estimated_request_cost_usd=estimated_cost", src)
        self.assertIn("record_model_spend_estimate(", src)
        self.assertIn("MODEL_OUTPUT_UNVERIFIED", Path("atlasquant_aion_provider.py").read_text(encoding="utf-8"))
        self.assertIn("nenhuma chamada paga será feita", src)

    def test_studio_is_persistent_and_publication_stays_guarded(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("new_content_project(", src)
        self.assertIn("update_studio_checkpoint(", src)
        self.assertIn("approve_project(", src)
        self.assertIn("script_blueprint(", src)
        self.assertIn("publication_preflight(", src)
        self.assertIn("Publicados confirmados", src)
        self.assertIn("execução ainda não ocorre nesta tela", src)

    def test_business_is_persistent_evidence_based_and_marketplace_guarded(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("new_product_candidate(", src)
        self.assertIn("update_business_checkpoint(", src)
        self.assertIn("trend_assessment(", src)
        self.assertIn("marketplace_preflight(", src)
        self.assertIn("Tendências confirmadas", src)
        self.assertIn("Nenhum produto é chamado de tendência ou mais vendido sem fonte confirmada.", src)

    def test_promotions_workspace_is_persistent_copy_once_and_provider_guarded(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("new_campaign(", src)
        self.assertIn("update_promotions_checkpoint(", src)
        self.assertIn("approve_campaign(", src)
        self.assertIn("activation_preflight(", src)
        self.assertIn("exibição única da sessão", src)
        self.assertIn("hash do código", src)
        self.assertIn("não ativa acesso real", src)
        self.assertIn("Ativas confirmadas", src)

    def test_entitlement_registry_is_persistent_separate_and_fail_closed(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("new_entitlement_request(", src)
        self.assertIn("update_entitlements_checkpoint(", src)
        self.assertIn("approve_entitlement_request(", src)
        self.assertIn("entitlement_activation_preflight(", src)
        self.assertIn("Assinaturas & Entitlements", src)
        self.assertIn("não altera conta nem libera acesso", src.lower())
        self.assertIn("não muda USER/SALES/ADMIN", src)
        self.assertIn("ACTIVE_CONFIRMED exige evidência concreta", src)
        self.assertIn("entitlement_activation", src)

    def test_account_entitlement_audit_is_read_only_and_visible_to_admin(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("audit_account_entitlements(", src)
        self.assertIn("Auditoria Conta × Entitlement", src)
        self.assertIn("somente leitura", src)
        self.assertIn("não revoga nem concede acesso", src)
        self.assertIn("Enforcement: DESLIGADO", src)
        self.assertIn("provisionamento automático: NÃO", src)
        self.assertIn("revogação automática: NÃO", src)

    def test_account_entitlement_audit_is_shared_with_master_status_board(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("account_entitlement_audit = audit_account_entitlements(", src)
        self.assertIn("account_entitlement_audit=account_entitlement_audit", src)
        self.assertIn("account_entitlement_audit,", src)
        self.assertIn('"commercial_access_audit_needs_review"', src)

    def test_master_status_board_is_visible_and_truth_labeled(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("build_master_status_board(", src)
        self.assertIn("status_rows(", src)
        self.assertIn("Painel Mestre de Estado", src)
        self.assertIn("CONFIRMADO exige evidência desta execução", src)
        self.assertIn("DEPENDÊNCIA EXTERNA exige conector/prova", src)
        self.assertIn("Pendências do Painel Mestre", src)
        self.assertIn('"status_board_counts"', src)
        self.assertIn('"status_board_has_unresolved"', src)

    def test_unified_approval_inbox_is_visible_without_auto_approval(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("collect_approval_inbox(", src)
        self.assertIn("approval_rows(", src)
        self.assertIn("Central de Aprovações", src)
        self.assertIn("não aprova nem executa ações", src)
        self.assertIn("área indicada no item", src)
        self.assertIn('"approval_inbox_total"', src)
        self.assertIn('"approval_inbox_has_pending"', src)

    def test_personal_aion_readiness_panel_is_visible_but_non_provisioning(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("tenant_readiness_summary(", src)
        self.assertIn("tenant_policy_snapshot(", src)
        self.assertIn("AION pessoal · isolamento por assinante", src)
        self.assertIn("Meu AION ainda NÃO está ativado", src)
        self.assertIn("não cria tenant", src)
        self.assertIn("não grava memória pessoal", src)
        self.assertIn("não provisiona acesso", src)
        self.assertIn("Persistência pessoal em produção", src)
        self.assertIn("NÃO CONFIRMADA", src)
        self.assertIn("Provedor externo automático", src)
        self.assertIn("Cobrança automática", src)
        self.assertIn("Trading real", src)

    def test_subscriptions_shows_privacy_lifecycle_readiness_without_activation(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Privacidade & ciclo de vida do AION pessoal",src)
        self.assertIn("tenant_privacy_readiness()",src)
        self.assertIn("tenant_privacy_policy_snapshot()",src)
        self.assertIn("Exclusão automática",src)
        self.assertIn("Persistência pessoal",src)
        self.assertIn("Compliance legal afirmado",src)
        self.assertIn("Nenhum dado pessoal é criado, exportado ou excluído por este painel.",src)
        self.assertIn('"tenant_privacy_contract_ready"',src)

    def test_business_panel_labels_unconnected_sales_as_unconfirmed(self):
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("não representam vendas confirmadas", src)
        self.assertIn("integrações de pedidos não estiverem conectadas", src)


    def test_workspace_dispatch_is_fault_isolated_and_does_not_echo_raw_exception(self):
        from pathlib import Path
        src=Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        start=src.index("workspace_error_type =")
        end=src.index('with st.expander("Política Custo Zero")',start)
        block=src[start:end]
        self.assertIn("try:",block)
        self.assertIn("except Exception as exc:",block)
        self.assertIn("type(exc).__name__",block)
        self.assertIn("erro isolado",block)
        self.assertIn("Nenhuma permissão operacional foi ampliada",block)
        self.assertNotIn("str(exc)",block)
        self.assertNotIn("repr(exc)",block)
        self.assertNotIn("st.exception(",block)

    def test_foundation_fallbacks_are_unknown_read_only_and_hide_raw_messages(self):
        from pathlib import Path
        src=Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("def _unknown_account_entitlement_audit",src)
        self.assertIn("def _unknown_status_board",src)
        self.assertIn("def _unknown_approval_inbox",src)
        self.assertIn('"truth_state": "UNKNOWN"',src)
        self.assertIn('"state": "UNKNOWN"',src)
        self.assertIn('"automatic_approval": False',src)
        self.assertIn('"real_orders_enabled": False',src)
        self.assertIn('"foundation_status": "DEGRADED_SAFE"',src)
        start=src.index("foundation_diagnostics:")
        end=src.index("selected_workspace = st.selectbox",start)
        block=src[start:end]
        self.assertIn("except Exception as exc:",block)
        self.assertIn("type(exc).__name__",block)
        self.assertNotIn("str(exc)",block)
        self.assertNotIn("repr(exc)",block)
        self.assertNotIn("st.exception(",block)

    def test_unknown_approval_inbox_never_claims_zero_pending_is_confirmed(self):
        from pathlib import Path
        src=Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        start=src.index("def _render_approval_inbox")
        end=src.index("def _render_central",start)
        block=src[start:end]
        self.assertIn('get("status") or "CONFIRMED"',block)
        self.assertIn('"UNKNOWN"',block)
        self.assertIn("não pôde ser confirmada",block)
        self.assertIn("Nenhuma ausência de item",block)

if __name__ == "__main__":
    unittest.main()
