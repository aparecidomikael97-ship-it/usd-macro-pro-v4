import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_aion_capabilities import CapabilityRegistry, default_registry
from atlasquant_aion_critical_review import seal_agent_message
from atlasquant_aion_orchestrator import (
    build_aion_result,
    orchestrate,
    prepare_reviewed_mission,
    validate_specialist_result,
)
from atlasquant_aion_truth import assess_truth


NOW = datetime(2026, 9, 27, 5, 0, tzinfo=timezone.utc)


class CapabilityRegistryTests(unittest.TestCase):
    def test_registry_routes_from_declared_metadata(self):
        routed = default_registry().route(
            "Compare CPI, juros e impacto macro no dólar",
            domain_hint="macro",
        )
        self.assertEqual(routed[0]["capability_id"], "macro.explain")
        self.assertIn("cpi", routed[0]["matched_metadata"])

    def test_custom_capability_routes_without_router_code_change(self):
        registry = CapabilityRegistry([])
        registry.register({
            "capability_id": "support.triage",
            "specialist": "support",
            "domains": ["support"],
            "description": "Triagem de atendimento e dúvidas.",
            "inputs": ["question"],
            "outputs": ["triage"],
            "allowed_roles": ["USER"],
            "aliases": ["atendimento", "duvida"],
        })
        self.assertEqual(
            registry.route("Preciso de atendimento para uma dúvida")[0]["capability_id"],
            "support.triage",
        )

    def test_invalid_and_duplicate_capabilities_fail_closed(self):
        registry = CapabilityRegistry([])
        with self.assertRaises(ValueError):
            registry.register({"capability_id": "../bad", "specialist": "x"})
        valid = {
            "capability_id": "test.safe", "specialist": "test",
            "inputs": [], "outputs": [], "allowed_roles": ["ADMIN"],
        }
        registry.register(valid)
        with self.assertRaises(ValueError):
            registry.register(valid)


class TruthAssessmentTests(unittest.TestCase):
    def test_missing_source_and_timestamp_downgrade_confirmation(self):
        out = assess_truth([{
            "claim": "market",
            "truth_state": "CONFIRMED",
            "value": "open",
            "time_sensitive": True,
        }], now=NOW)
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertIn("CONFIRMATION_DOWNGRADED", out["records"][0]["issues"])

    def test_stale_data_never_looks_current(self):
        out = assess_truth([{
            "claim": "price",
            "truth_state": "CONFIRMED",
            "value": 1.2,
            "source": "provider",
            "timestamp": (NOW - timedelta(minutes=10)).isoformat(),
            "ttl_seconds": 60,
        }], now=NOW)
        self.assertEqual(out["freshness"], "STALE")
        self.assertEqual(out["status"], "UNKNOWN")

    def test_conflicting_confirmed_sources_are_not_arbitrarily_resolved(self):
        timestamp = NOW.isoformat()
        out = assess_truth([
            {"claim": "rate", "truth_state": "CONFIRMED", "value": 4, "source": "official-a", "timestamp": timestamp, "ttl_seconds": 600},
            {"claim": "rate", "truth_state": "CONFIRMED", "value": 5, "source": "official-b", "timestamp": timestamp, "ttl_seconds": 600},
        ], now=NOW)
        self.assertEqual(out["conflict_state"], "CONFLICT")
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertLessEqual(out["confidence"]["score"], 30)


class CentralOrchestratorTests(unittest.TestCase):
    def test_core_to_specialist_to_validator_flow(self):
        preflight = orchestrate(
            "Explique o contexto do Radar Forex",
            context={"role": "USER", "experience_mode": "BEGINNER", "domain_hint": "market"},
        )
        self.assertEqual(preflight["selected_capability"]["specialist"], "market")
        self.assertEqual(preflight["decision"]["state"], "READY")
        self.assertTrue(preflight["critic_required"])
        validated = validate_specialist_result(preflight, {
            "response": "Contexto observado.",
            "evidence": [{
                "claim": "radar",
                "truth_state": "CONFIRMED",
                "value": "available",
                "source": "AtlasQuant Radar",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ttl_seconds": 3600,
            }],
        })
        self.assertEqual(validated["state"], "PASS")

    def test_user_cannot_use_admin_or_developer_capability(self):
        for capability in ("admin.status", "development.inspect"):
            out = orchestrate(
                "status",
                context={"role": "USER"},
                requested_capability=capability,
            )
            self.assertEqual(out["decision"]["state"], "BLOCKED")
            self.assertIn("PERMISSION_DENIED", out["decision"]["blockers"])

    def test_unknown_capability_and_unavailable_tool_fail_closed(self):
        out = orchestrate(
            "execute ferramenta desconhecida",
            context={"role": "ADMIN"},
            requested_capability="unknown.tool",
        )
        self.assertEqual(out["decision"]["state"], "BLOCKED")
        self.assertIn("INVALID_CAPABILITY", out["decision"]["blockers"])

    def test_critical_action_needs_approval_and_real_trade_stays_blocked(self):
        out = orchestrate(
            "envie uma ordem real",
            context={"role": "ADMIN"},
            requested_capability="market.explain",
            requested_action="real_trade",
            approved=True,
            feature_flags={"real_broker_execution": True},
        )
        self.assertEqual(out["decision"]["state"], "BLOCKED")
        self.assertIn("REAL_TRADING_BLOCKED", out["decision"]["blockers"])
        self.assertFalse(out["real_orders_enabled"])

    def test_capability_flags_control_specialists_but_never_enable_external_or_real_trade(self):
        out = orchestrate(
            "inspecione código",
            context={"role": "ADMIN"},
            requested_capability="development.inspect",
            feature_flags={
                "AION_DEV_ENABLED": False,
                "AION_EXTERNAL_ACTIONS_ENABLED": True,
                "REAL_TRADING_ENABLED": True,
            },
        )
        self.assertEqual(out["decision"]["state"], "BLOCKED")
        self.assertIn("CAPABILITY_FLAG_DISABLED", out["decision"]["blockers"])
        self.assertFalse(out["feature_flags"]["AION_EXTERNAL_ACTIONS_ENABLED"])
        self.assertFalse(out["feature_flags"]["REAL_TRADING_ENABLED"])

    def test_beginner_and_advanced_share_logic_but_change_presentation(self):
        beginner = orchestrate("Explique o mercado", context={"role": "USER", "experience_mode": "BEGINNER"})
        advanced = orchestrate("Explique o mercado", context={"role": "USER", "experience_mode": "ADVANCED"})
        self.assertEqual(
            beginner["selected_capability"]["capability_id"],
            advanced["selected_capability"]["capability_id"],
        )
        self.assertTrue(beginner["presentation"]["technical_details_hidden"])
        self.assertFalse(advanced["presentation"]["technical_details_hidden"])

    def test_missing_specialist_evidence_is_revised(self):
        preflight = orchestrate("pesquise", context={"role": "USER"})
        validated = validate_specialist_result(preflight, {"response": "Sem fonte"})
        self.assertEqual(validated["state"], "REVISE")
        self.assertIn("RESULT_WITHOUT_CONFIRMED_EVIDENCE", validated["issues"])

    def test_unified_result_validates_local_and_external_paths(self):
        preflight = orchestrate("Explique a arquitetura do projeto")
        result = build_aion_result(
            preflight,
            answer="A arquitetura está documentada.",
            evidence=[{
                "claim": "architecture",
                "value": "documented",
                "truth_state": "CONFIRMED",
                "source": "docs/aion/ARCHITECTURE.md",
                "source_tier": "PRIMARY",
                "time_sensitive": False,
            }],
            provider_state="LOCAL_DETERMINISTIC",
        )
        self.assertEqual(result["schema"], "ATLASQUANT_AION_RESULT_V1")
        self.assertEqual(result["provider_state"], "LOCAL_DETERMINISTIC")
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["automatic_memory_write"])


class ReviewedMissionGateTests(unittest.TestCase):
    trusted = {
        "tenant_id": "tenant-a",
        "workspace_id": "central",
        "role": "ADMIN",
    }
    access = {"role": "ADMIN"}

    @staticmethod
    def verified(refs):
        return {"state": "VERIFIED", "bound_refs": list(refs)}

    @staticmethod
    def assignments():
        return {
            "PRIME": "prime-1",
            "SHADOW": "shadow-1",
            "SENTINEL": "sentinel-1",
        }

    def message_contexts(self):
        return {
            role: {
                "role": role,
                "agent_id": agent_id,
                "workspace_id": "central",
                "tenant_id": "tenant-a",
                "capabilities": ["DRAFT"],
            }
            for role, agent_id in self.assignments().items()
        }

    def review(self, role, binding, verdict="AGREE"):
        return {
            "role": role,
            "agent_id": self.assignments()[role],
            "verdict": verdict,
            "tenant_id": "tenant-a",
            "workspace_id": "central",
            "task_ref": binding["mission_id"],
            "plan_version": binding["plan_version"],
        }

    def protocol_messages(self, binding, *, requested_action=None):
        contexts = self.message_contexts()
        action = requested_action or (
            f"review_mission:{binding['mission_id']}:{binding['plan_version']}"
        )
        risk = binding["blast_radius"]["level"]
        approvals = ["approval-1"] if risk in {"HIGH", "CRITICAL"} else []
        out = {}
        for role in binding["required_roles"]:
            sealed = seal_agent_message(
                {
                    "capability": "DRAFT",
                    "requested_action": action,
                    "evidence_refs": ["evidence-1"],
                    "confidence": "HIGH",
                    "risk_level": risk,
                    "permissions": ["DRAFT"],
                    "approval_refs": approvals,
                    "issued_at": NOW.isoformat(),
                    "nonce": f"{role.lower()}-{binding['plan_version']}",
                    "content": "Independent review information only.",
                },
                trusted_context=contexts[role],
            )
            self.assertEqual(sealed["state"], "SEALED")
            out[role] = sealed["message"]
        return out

    def critical_protocol(self, binding):
        return {
            "review_messages": self.protocol_messages(binding),
            "trusted_message_contexts": self.message_contexts(),
            "now": NOW,
            "approval_refs": ["approval-1"],
            "approval_verifier": self.verified,
        }

    def preview(self, objective="Explique o contexto com cuidado.", **kwargs):
        params = {
            "access": self.access,
            "trusted_context": self.trusted,
            "evidence_refs": ["evidence-1"],
            "evidence_verifier": self.verified,
            "feature_flags": {
                "external_llm": True,
                "production_deploy": True,
                "social_publish": True,
                "marketplace_publish": True,
            },
            "system_context": {
                "provider": {"state": "EXTERNAL_READY"},
                "runtime_checkpoint": {"status": "CONFIRMED"},
                "integrations": {
                    "production_connected": True,
                    "social_connected": True,
                    "marketplace_connected": True,
                },
                "source_mesh": {"market_live_confirmed": True},
            },
        }
        params.update(kwargs)
        return prepare_reviewed_mission(objective, **params)

    def test_simple_mission_requires_prime_before_guardian(self):
        out = self.preview()
        self.assertEqual(out["state"], "REVIEW_REQUIRED")
        self.assertEqual(out["task_class"], "SIMPLE")
        self.assertEqual(out["required_roles"], ["PRIME"])
        self.assertFalse(out["eligible_for_guardian"])
        self.assertFalse(out["guardian_called"])
        self.assertFalse(out["executes_action"])

    def test_prime_acceptance_only_makes_simple_plan_eligible_for_guardian(self):
        preview = self.preview()
        out = self.preview(
            reviews=[self.review("PRIME", preview)],
            trusted_assignments=self.assignments(),
        )
        self.assertEqual(out["state"], "READY_FOR_GUARDIAN")
        self.assertEqual(out["protocol"]["state"], "NOT_REQUIRED")
        self.assertEqual(out["review"]["state"], "ACCEPT_PLAN")
        self.assertTrue(out["eligible_for_guardian"])
        self.assertFalse(out["guardian_called"])
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["grants_permission"])

    def test_code_change_requires_protocol_and_three_independent_reviewers(self):
        preview = self.preview("Corrigir bug no código da interface.")
        self.assertEqual(preview["blast_radius"]["level"], "HIGH")
        self.assertEqual(preview["task_class"], "CRITICAL")
        self.assertEqual(
            preview["required_roles"],
            ["PRIME", "SHADOW", "SENTINEL"],
        )

        no_protocol = self.preview(
            "Corrigir bug no código da interface.",
            reviews=[
                self.review("PRIME", preview),
                self.review("SHADOW", preview),
                self.review("SENTINEL", preview),
            ],
            trusted_assignments=self.assignments(),
            approval_refs=["approval-1"],
            approval_verifier=self.verified,
            now=NOW,
        )
        self.assertEqual(no_protocol["state"], "BLOCK")
        self.assertEqual(no_protocol["reason"], "AGENT_PROTOCOL_BLOCKED")
        self.assertIsNone(no_protocol["review"])
        self.assertIn(
            "PROTOCOL_MESSAGE_MISSING:PRIME",
            no_protocol["protocol"]["blockers"],
        )

        partial = self.preview(
            "Corrigir bug no código da interface.",
            reviews=[self.review("PRIME", preview)],
            trusted_assignments=self.assignments(),
            **self.critical_protocol(preview),
        )
        self.assertEqual(partial["protocol"]["state"], "PASS")
        self.assertEqual(partial["state"], "BLOCK")
        self.assertIn("MISSING_REVIEWER:SHADOW", partial["review"]["blockers"])
        self.assertIn("MISSING_REVIEWER:SENTINEL", partial["review"]["blockers"])

        full = self.preview(
            "Corrigir bug no código da interface.",
            reviews=[
                self.review("PRIME", preview),
                self.review("SHADOW", preview),
                self.review("SENTINEL", preview),
            ],
            trusted_assignments=self.assignments(),
            **self.critical_protocol(preview),
        )
        self.assertEqual(full["protocol"]["state"], "PASS")
        self.assertTrue(all(
            row["authorization"] == "NONE"
            for row in full["protocol"]["messages"]
        ))
        self.assertEqual(full["state"], "READY_FOR_GUARDIAN")
        self.assertTrue(full["eligible_for_guardian"])
        self.assertFalse(full["guardian_called"])
        self.assertFalse(full["external_action_executed"])

    def test_protocol_message_must_bind_to_exact_mission_plan(self):
        preview = self.preview("Corrigir bug no código da interface.")
        wrong = self.protocol_messages(
            preview,
            requested_action="review_mission:other:old-plan",
        )
        out = self.preview(
            "Corrigir bug no código da interface.",
            reviews=[
                self.review("PRIME", preview),
                self.review("SHADOW", preview),
                self.review("SENTINEL", preview),
            ],
            trusted_assignments=self.assignments(),
            review_messages=wrong,
            trusted_message_contexts=self.message_contexts(),
            now=NOW,
            approval_refs=["approval-1"],
            approval_verifier=self.verified,
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertEqual(out["reason"], "AGENT_PROTOCOL_BLOCKED")
        self.assertTrue(any(
            item.endswith(":MISSION_BINDING_MISMATCH")
            for item in out["protocol"]["blockers"]
        ))
        self.assertIsNone(out["review"])

    def test_protocol_replay_is_blocked_before_adjudication(self):
        preview = self.preview("Corrigir bug no código da interface.")
        messages = self.protocol_messages(preview)
        out = self.preview(
            "Corrigir bug no código da interface.",
            reviews=[
                self.review("PRIME", preview),
                self.review("SHADOW", preview),
                self.review("SENTINEL", preview),
            ],
            trusted_assignments=self.assignments(),
            review_messages=messages,
            trusted_message_contexts=self.message_contexts(),
            seen_message_digests=[messages["PRIME"]["digest"]],
            now=NOW,
            approval_refs=["approval-1"],
            approval_verifier=self.verified,
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertTrue(any(
            item == "PROTOCOL:PRIME:REPLAY"
            for item in out["protocol"]["blockers"]
        ))
        self.assertIsNone(out["review"])

    def test_shadow_challenge_escalates_instead_of_picking_a_side(self):
        preview = self.preview("Corrigir bug no código da interface.")
        out = self.preview(
            "Corrigir bug no código da interface.",
            reviews=[
                self.review("PRIME", preview),
                self.review("SHADOW", preview, verdict="CHALLENGE"),
                self.review("SENTINEL", preview),
            ],
            trusted_assignments=self.assignments(),
            **self.critical_protocol(preview),
        )
        self.assertEqual(out["protocol"]["state"], "PASS")
        self.assertEqual(out["state"], "ESCALATE")
        self.assertIn("DIVERGENCE:SHADOW", out["review"]["blockers"])
        self.assertFalse(out["eligible_for_guardian"])

    def test_review_bound_to_old_plan_version_is_blocked(self):
        preview = self.preview("Corrigir bug no código da interface.")
        stale = self.review("PRIME", preview)
        stale["plan_version"] = "old-plan"
        out = self.preview(
            "Corrigir bug no código da interface.",
            reviews=[
                stale,
                self.review("SHADOW", preview),
                self.review("SENTINEL", preview),
            ],
            trusted_assignments=self.assignments(),
            **self.critical_protocol(preview),
        )
        self.assertEqual(out["protocol"]["state"], "PASS")
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("REVIEW_PLAN:PRIME", out["review"]["blockers"])

    def test_blocked_deploy_mission_never_reaches_protocol_review_or_guardian(self):
        out = self.preview(
            "Faça deploy em produção agora.",
            feature_flags={
                "external_llm": True,
                "production_deploy": False,
            },
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertEqual(out["reason"], "MISSION_NOT_READY")
        self.assertIsNone(out["protocol"])
        self.assertIsNone(out["review"])
        self.assertFalse(out["eligible_for_guardian"])
        self.assertFalse(out["guardian_called"])
        self.assertFalse(out["executes_action"])


if __name__ == "__main__":
    unittest.main()
