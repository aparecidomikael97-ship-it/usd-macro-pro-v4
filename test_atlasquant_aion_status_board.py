import unittest

from atlasquant_aion_status_board import build_master_status_board, status_rows


class AtlasQuantAionMasterStatusBoardTests(unittest.TestCase):
    def base(self, **kwargs):
        payload={
            "checkpoint":{
                "operating":{"tasks":[]},
                "entitlements":{"records":[]},
                "continuity":{"missions":[],"handoffs":[]},
                "durable_tasks":{"records":[]},
            },
            "runtime_result":{
                "status":"CONFIRMED",
                "integrity":{"state":"CONFIRMED","matched":7,"total":7},
            },
            "provider":{"state":"ZERO_COST_LOCAL"},
            "feature_flags":{},
            "system_context":{
                "truth_state":"CONFIRMED",
                "source_build":"abc123",
            },
            "market_context":{"fresh_confirmed":False,"summary":""},
            "account_entitlement_audit":{
                "schema":"ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1",
                "accounts_total":2,
                "active_user_accounts":2,
                "effective_user_accounts":2,
                "user_accounts_without_effective_entitlement":0,
                "duplicate_effective_user_accounts":0,
                "orphan_effective_entitlements":0,
            },
            "working_dirty":False,
        }
        payload.update(kwargs)
        return build_master_status_board(**payload)

    def by_id(self,board,item_id):
        return next(x for x in board["items"] if x["id"]==item_id)

    def test_current_process_build_can_be_confirmed_without_claiming_market(self):
        board=self.base()
        self.assertEqual(self.by_id(board,"app_runtime")["state"],"CONFIRMED")
        self.assertEqual(self.by_id(board,"market_freshness")["state"],"UNKNOWN")
        self.assertTrue(board["has_unresolved"])

    def test_missing_build_evidence_stays_unknown(self):
        board=self.base(system_context={"truth_state":"CONFIRMED","source_build":""})
        self.assertEqual(self.by_id(board,"app_runtime")["state"],"UNKNOWN")

    def test_feature_off_is_blocked_not_confirmed(self):
        board=self.base(feature_flags={"social_publish":False})
        item=self.by_id(board,"social_publish")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertIn("desligada",item["detail"])

    def test_enabled_external_feature_without_evidence_is_dependency(self):
        board=self.base(feature_flags={"social_publish":True})
        item=self.by_id(board,"social_publish")
        self.assertEqual(item["state"],"EXTERNAL_DEPENDENCY")
        self.assertNotEqual(item["state"],"CONFIRMED")

    def test_external_feature_needs_explicit_confirmation(self):
        board=self.base(
            feature_flags={"social_publish":True},
            system_context={
                "truth_state":"CONFIRMED",
                "source_build":"abc123",
                "social_publish_confirmed":True,
            },
        )
        self.assertEqual(self.by_id(board,"social_publish")["state"],"CONFIRMED")

    def test_real_trading_is_always_blocked(self):
        board=self.base(feature_flags={"real_broker_execution":True})
        item=self.by_id(board,"real_broker_execution")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertFalse(board["real_orders_enabled"])

    def test_dirty_checkpoint_is_visible_as_blocked_until_persisted(self):
        board=self.base(working_dirty=True)
        item=self.by_id(board,"working_checkpoint")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertIn("não confirmadas",item["detail"])

    def test_entitlement_registry_presence_does_not_claim_active_access(self):
        board=self.base()
        item=self.by_id(board,"entitlement_registry")
        self.assertEqual(item["state"],"CONFIRMED")
        self.assertIn("não significa acesso comercial ativo",item["detail"])

    def test_clean_commercial_access_audit_is_confirmed_only_with_confirmed_runtime(self):
        board=self.base()
        item=self.by_id(board,"commercial_access_audit")
        self.assertEqual(item["state"],"CONFIRMED")
        self.assertIn("não prova pagamento",item["detail"])

        board=self.base(runtime_result={"status":"UNAVAILABLE"})
        item=self.by_id(board,"commercial_access_audit")
        self.assertEqual(item["state"],"UNKNOWN")

    def test_commercial_access_mismatch_is_blocked_without_enforcement(self):
        board=self.base(account_entitlement_audit={
            "schema":"ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1",
            "accounts_total":3,
            "active_user_accounts":2,
            "effective_user_accounts":1,
            "user_accounts_without_effective_entitlement":1,
            "duplicate_effective_user_accounts":0,
            "orphan_effective_entitlements":0,
        })
        item=self.by_id(board,"commercial_access_audit")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertIn("1 USER sem direito efetivo",item["detail"])
        self.assertFalse(board["automatic_external_actions"])

    def test_commercial_access_dirty_checkpoint_never_turns_green(self):
        board=self.base(working_dirty=True)
        item=self.by_id(board,"commercial_access_audit")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertIn("alterações locais",item["detail"])

    def test_commercial_access_without_active_user_population_stays_unknown(self):
        board=self.base(account_entitlement_audit={
            "schema":"ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1",
            "accounts_total":2,
            "active_user_accounts":0,
            "effective_user_accounts":0,
            "user_accounts_without_effective_entitlement":0,
            "duplicate_effective_user_accounts":0,
            "orphan_effective_entitlements":0,
        })
        item=self.by_id(board,"commercial_access_audit")
        self.assertEqual(item["state"],"UNKNOWN")
        self.assertIn("nenhuma conta USER ativa",item["detail"])

    def test_external_model_ready_requires_flag_too(self):
        board=self.base(
            provider={"state":"EXTERNAL_READY"},
            feature_flags={"external_llm":False},
        )
        self.assertEqual(self.by_id(board,"external_llm")["state"],"BLOCKED")
        board=self.base(
            provider={"state":"EXTERNAL_READY"},
            feature_flags={"external_llm":True},
        )
        self.assertEqual(self.by_id(board,"external_llm")["state"],"CONFIRMED")

    def test_entitlement_states_route_to_subscriptions_workspace(self):
        board=self.base(feature_flags={"entitlement_activation":False})
        self.assertEqual(self.by_id(board,"entitlement_activation")["area"],"subscriptions")
        self.assertEqual(self.by_id(board,"payment_provider")["area"],"subscriptions")
        self.assertEqual(self.by_id(board,"entitlement_registry")["area"],"subscriptions")
        self.assertEqual(self.by_id(board,"commercial_access_audit")["area"],"subscriptions")

    def test_checkpoint_integrity_mismatch_is_blocked_and_actionable(self):
        board=self.base(runtime_result={
            "status":"CONFIRMED",
            "integrity":{
                "state":"MISMATCH",
                "mismatches":["studio"],
                "matched":5,
                "total":6,
            },
        })
        item=self.by_id(board,"checkpoint_integrity")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertIn("studio",item["detail"])
        self.assertIn("Não sobrescrever",item["next_action"])

    def test_checkpoint_v7_migration_is_visible_without_claiming_corruption(self):
        board=self.base(runtime_result={
            "status":"CONFIRMED",
            "integrity":{
                "state":"MIGRATION_REQUIRED",
                "migration_items":["checkpoint_version 6 < 7","continuity ausente"],
                "matched":6,
                "total":7,
            },
        })
        item=self.by_id(board,"checkpoint_integrity")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertIn("migração",item["detail"].lower())
        self.assertIn("V7",item["next_action"])

    def test_v7_continuity_is_confirmed_only_with_runtime_integrity(self):
        board=self.base()
        item=self.by_id(board,"mission_continuity")
        self.assertEqual(item["state"],"CONFIRMED")
        self.assertIn("Checkpoint V7",item["detail"])

        board=self.base(runtime_result={
            "status":"CONFIRMED",
            "integrity":{
                "state":"MIGRATION_REQUIRED",
                "migration_items":["continuity ausente"],
            },
        })
        item=self.by_id(board,"mission_continuity")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertIn("migração V7",item["next_action"])

    def test_durable_task_continuity_is_confirmed_when_runtime_is_clean(self):
        board=self.base()
        item=self.by_id(board,"durable_task_continuity")
        self.assertEqual(item["state"],"CONFIRMED")
        self.assertIn("sem bloqueio",item["detail"])
        self.assertEqual(item["area"],"development")

    def test_durable_task_blocker_is_visible_and_does_not_claim_resume_execution(self):
        checkpoint={
            "operating":{"tasks":[]},
            "entitlements":{"records":[]},
            "continuity":{"missions":[],"handoffs":[]},
            "durable_tasks":{
                "records":[{
                    "durable_task_id":"DUR-TEST",
                    "title":"Revisar AION",
                    "objective":"Validar continuidade",
                    "domain":"development",
                    "state":"BLOCKED",
                    "steps":[{
                        "step_id":"S001",
                        "title":"Revisar bloqueio",
                        "state":"BLOCKED",
                        "blocker":"Aprovação necessária",
                    }],
                    "cursor":0,
                    "revision":2,
                    "blocker":"Aprovação necessária",
                    "next_action":"Revisar bloqueio",
                    "created_at":"2026-09-27T00:00:00+00:00",
                    "updated_at":"2026-09-27T00:01:00+00:00",
                }],
            },
        }
        board=self.base(checkpoint=checkpoint)
        item=self.by_id(board,"durable_task_continuity")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertIn("1 bloqueada",item["detail"])
        self.assertIn("não autoriza",item["next_action"])
        self.assertFalse(item["executes_action"])

    def test_durable_task_structure_without_confirmed_runtime_stays_unknown(self):
        board=self.base(runtime_result={"status":"UNAVAILABLE"})
        item=self.by_id(board,"durable_task_continuity")
        self.assertEqual(item["state"],"UNKNOWN")
        self.assertIn("persistência runtime",item["detail"])

    def test_missing_durable_task_structure_stays_unknown(self):
        checkpoint={
            "operating":{"tasks":[]},
            "entitlements":{"records":[]},
            "continuity":{"missions":[],"handoffs":[]},
        }
        board=self.base(checkpoint=checkpoint)
        item=self.by_id(board,"durable_task_continuity")
        self.assertEqual(item["state"],"UNKNOWN")
        self.assertIn("não foi confirmada",item["detail"])

    def test_status_rows_are_presentation_only(self):
        board=self.base()
        rows=status_rows(board)
        self.assertTrue(rows)
        self.assertIn("Estado",rows[0])
        self.assertFalse(board["automatic_external_actions"])


    def test_system_health_center_is_wired_and_fails_closed_without_six_domains(self):
        board=self.base()
        center=board["system_health_center"]
        self.assertEqual(center["state"],"UNKNOWN")
        self.assertIn("sources",center["unresolved_domains"])
        self.assertIn("workers",center["unresolved_domains"])
        item=self.by_id(board,"system_health_center")
        self.assertEqual(item["state"],"UNKNOWN")
        self.assertFalse(center["executes_action"])
        self.assertFalse(center["real_trading_enabled"])

    def test_system_health_center_confirms_only_with_explicit_six_domain_evidence(self):
        system_context={
            "truth_state":"CONFIRMED",
            "source_build":"abc123",
            "source_mesh":{
                "market_state":"HEALTHY",
                "market_live_confirmed":True,
                "observation_count":8,
                "fallback_or_unavailable":0,
            },
            "notification_health":{
                "state":"HEALTHY",
                "confirmed":True,
                "detail":"Canal interno confirmado.",
                "unresolved":0,
                "freshness_attested":True,
                "freshness_source":"notification_probe",
            },
            "worker_health":{
                "state":"HEALTHY",
                "confirmed":True,
                "detail":"Worker verificado.",
                "unresolved":0,
                "freshness_attested":True,
                "freshness_source":"worker_probe",
            },
            "critical_surfaces":{
                "all_ok":True,
                "counts":{
                    "OK":3,
                    "DEGRADED":0,
                    "UNAVAILABLE":0,
                    "STALE_BUILD":0,
                    "UNKNOWN":0,
                },
                "items":[
                    {"id":"home_radar","state":"OK"},
                    {"id":"advanced_radar","state":"OK"},
                    {"id":"master_panel","state":"OK"},
                ],
            },
        }
        board=self.base(system_context=system_context)
        center=board["system_health_center"]
        self.assertEqual(center["state"],"HEALTHY")
        self.assertTrue(center["all_confirmed_healthy"])
        self.assertEqual(center["healthy_domains"],6)
        item=self.by_id(board,"system_health_center")
        self.assertEqual(item["state"],"CONFIRMED")
        self.assertIn("6/6",item["detail"])

    def test_source_fallback_degrades_health_without_claiming_confirmation(self):
        system_context={
            "truth_state":"CONFIRMED",
            "source_build":"abc123",
            "source_mesh":{
                "market_state":"DEGRADED",
                "market_live_confirmed":False,
                "observation_count":8,
                "fallback_or_unavailable":2,
            },
            "notification_health":{"state":"HEALTHY","confirmed":True,"freshness_attested":True,"freshness_source":"notification_probe"},
            "worker_health":{"state":"HEALTHY","confirmed":True,"freshness_attested":True,"freshness_source":"worker_probe"},
            "critical_surfaces":{
                "all_ok":True,
                "counts":{"OK":3,"DEGRADED":0,"UNAVAILABLE":0,"STALE_BUILD":0,"UNKNOWN":0},
                "items":[{"id":"a"},{"id":"b"},{"id":"c"}],
            },
        }
        board=self.base(system_context=system_context)
        center=board["system_health_center"]
        source=next(x for x in center["items"] if x["id"]=="sources")
        self.assertEqual(source["state"],"DEGRADED")
        self.assertFalse(source["confirmed"])
        self.assertEqual(center["state"],"DEGRADED")
        self.assertEqual(self.by_id(board,"system_health_center")["state"],"UNKNOWN")

    def test_explicit_worker_health_without_freshness_proof_stays_unknown(self):
        board=self.base(system_context={
            "truth_state":"CONFIRMED",
            "source_build":"abc123",
            "worker_health":{"state":"HEALTHY","confirmed":True},
        })
        center=board["system_health_center"]
        worker=next(x for x in center["items"] if x["id"]=="workers")
        self.assertEqual(worker["state"],"UNKNOWN")
        self.assertIn("FRESHNESS_NOT_CONFIRMED",worker["reasons"])



    def test_queues_are_unknown_when_checkpoint_runtime_is_not_confirmed(self):
        board=self.base(runtime_result={"status":"UNAVAILABLE"})
        center=board["system_health_center"]
        queue=next(x for x in center["items"] if x["id"]=="queues")
        self.assertEqual(queue["state"],"UNKNOWN")
        self.assertFalse(queue["confirmed"])

    def test_notifications_do_not_become_healthy_from_live_event_engine_alone(self):
        system_context={
            "truth_state":"CONFIRMED",
            "source_build":"abc123",
            "live_event_intelligence":{
                "state":"READY",
                "continuous_runtime_confirmed":True,
                "alert_count":4,
            },
        }
        board=self.base(system_context=system_context)
        center=board["system_health_center"]
        notifications=next(x for x in center["items"] if x["id"]=="notifications")
        self.assertEqual(notifications["state"],"DEGRADED")
        self.assertFalse(notifications["confirmed"])
        self.assertIn("entrega externa",notifications["detail"])



    def test_aion_core_health_stays_unknown_without_explicit_evidence(self):
        board=self.base()
        snap=board["aion_core_health"]
        item=self.by_id(board,"aion_core_health")
        self.assertEqual(snap["integrity_state"],"UNKNOWN")
        self.assertEqual(item["state"],"UNKNOWN")
        self.assertFalse(snap["external_action_executed"])
        self.assertFalse(snap["execution_allowed"])
        self.assertFalse(snap["executes_provider_call"])
        self.assertFalse(snap["executes_billing"])
        self.assertFalse(snap["real_orders_enabled"])

    def test_aion_core_health_confirms_only_from_explicit_good_subsystems(self):
        board=self.base(system_context={
            "truth_state":"CONFIRMED",
            "source_build":"abc123",
            "aion_core_health":{
                "core_version":"2.4",
                "schema_version":"V22",
                "journal_status":"VALID",
                "checkpoint_status":"VALIDATED",
                "recovery_status":"RECOVERED",
                "memory_status":"HEALTHY",
                "audit_chain_status":"VERIFIED",
                "pending_missions":2,
                "blocked_missions":0,
                "waiting_approval":0,
                "ready_handoffs":1,
            },
        })
        snap=board["aion_core_health"]
        item=self.by_id(board,"aion_core_health")
        self.assertEqual(snap["integrity_state"],"OK")
        self.assertEqual(item["state"],"CONFIRMED")
        self.assertIn("journal=VALID",item["detail"])
        self.assertIn("pendentes=2",item["detail"])
        self.assertFalse(board["automatic_external_actions"])

    def test_aion_core_health_integrity_ok_still_blocks_on_pending_approval(self):
        board=self.base(system_context={
            "truth_state":"CONFIRMED",
            "source_build":"abc123",
            "aion_core_health":{
                "core_version":"2.4",
                "schema_version":"V22",
                "journal_status":"VALID",
                "checkpoint_status":"VALIDATED",
                "recovery_status":"RECOVERED",
                "memory_status":"HEALTHY",
                "audit_chain_status":"VERIFIED",
                "blocked_missions":0,
                "waiting_approval":1,
            },
        })
        snap=board["aion_core_health"]
        item=self.by_id(board,"aion_core_health")
        self.assertEqual(snap["integrity_state"],"OK")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertIn("aprovações pendentes",item["next_action"])
        self.assertFalse(snap["execution_allowed"])
        self.assertFalse(board["automatic_external_actions"])

    def test_aion_core_health_tamper_is_blocked_without_repair_or_execution(self):
        board=self.base(system_context={
            "truth_state":"CONFIRMED",
            "source_build":"abc123",
            "aion_core_health":{
                "core_version":"2.4",
                "schema_version":"V22",
                "journal_status":"TAMPER_DETECTED",
                "checkpoint_status":"VALID",
                "recovery_status":"RECOVERED",
                "memory_status":"VALIDATED",
                "audit_chain_status":"MISMATCH",
                "blocked_missions":1,
            },
        })
        snap=board["aion_core_health"]
        item=self.by_id(board,"aion_core_health")
        self.assertEqual(snap["integrity_state"],"DEGRADED")
        self.assertEqual(item["state"],"BLOCKED")
        self.assertIn("não repara nem executa",item["next_action"])
        self.assertFalse(snap["external_action_executed"])
        self.assertFalse(snap["execution_allowed"])
        self.assertFalse(board["real_orders_enabled"])

    def test_cost_center_is_unknown_without_explicit_cost_evidence(self):
        board=self.base()
        center=board["cost_center"]
        self.assertEqual(center["state"],"UNKNOWN")
        self.assertEqual(self.by_id(board,"cost_center")["state"],"UNKNOWN")
        self.assertFalse(center["automatic_charge"])
        self.assertFalse(center["executes_action"])

    def test_model_budget_usage_is_estimate_not_confirmed_spend(self):
        checkpoint={
            "operating":{"tasks":[]},
            "entitlements":{"records":[]},
            "continuity":{"missions":[],"handoffs":[]},
            "durable_tasks":{"records":[]},
            "aion":{
                "model_budget":{
                    "spent_usd_estimate":4.25,
                    "monthly_limit_usd":20,
                    "allow_paid":False,
                }
            },
        }
        board=self.base(checkpoint=checkpoint)
        center=board["cost_center"]
        self.assertEqual(center["state"],"PARTIAL")
        self.assertEqual(center["confirmed_monthly_usd"],0.0)
        self.assertEqual(center["estimated_monthly_usd"],4.25)
        self.assertEqual(self.by_id(board,"cost_center")["state"],"UNKNOWN")
        self.assertIn("estimado US$ 4.25",self.by_id(board,"cost_center")["detail"])

    def test_explicit_confirmed_costs_can_confirm_compact_cost_row(self):
        system_context={
            "truth_state":"CONFIRMED",
            "source_build":"abc123",
            "cost_evidence":[
                {
                    "id":"server",
                    "label":"Servidor",
                    "category":"infrastructure",
                    "truth_state":"CONFIRMED",
                    "amount":12.0,
                    "currency":"USD",
                    "period":"MONTHLY",
                    "source":"invoice:server",
                },
                {
                    "id":"data",
                    "label":"Dados",
                    "category":"market_data",
                    "truth_state":"CONFIRMED",
                    "amount":8.0,
                    "currency":"USD",
                    "period":"MONTHLY",
                    "source":"invoice:data",
                },
            ],
        }
        board=self.base(system_context=system_context)
        center=board["cost_center"]
        self.assertEqual(center["state"],"CONFIRMED")
        self.assertEqual(center["confirmed_monthly_usd"],20.0)
        self.assertEqual(center["confirmed_cost_per_user_usd"],10.0)
        item=self.by_id(board,"cost_center")
        self.assertEqual(item["state"],"CONFIRMED")
        self.assertIn("US$ 20.00/mês",item["detail"])
        self.assertIn("US$ 10.00",item["detail"])

    def test_mixed_confirmed_and_estimated_costs_never_turn_compact_row_confirmed(self):
        system_context={
            "truth_state":"CONFIRMED",
            "source_build":"abc123",
            "cost_evidence":[
                {
                    "id":"server",
                    "label":"Servidor",
                    "category":"infrastructure",
                    "truth_state":"CONFIRMED",
                    "amount":10,
                    "currency":"USD",
                    "period":"MONTHLY",
                    "source":"invoice",
                },
                {
                    "id":"voice",
                    "label":"Voz",
                    "category":"voice_tts",
                    "truth_state":"ESTIMATED",
                    "amount":5,
                    "currency":"USD",
                    "period":"MONTHLY",
                    "source":"pricing-page",
                },
            ],
        }
        board=self.base(system_context=system_context)
        self.assertEqual(board["cost_center"]["state"],"PARTIAL")
        self.assertEqual(self.by_id(board,"cost_center")["state"],"UNKNOWN")



if __name__=="__main__":
    unittest.main()
