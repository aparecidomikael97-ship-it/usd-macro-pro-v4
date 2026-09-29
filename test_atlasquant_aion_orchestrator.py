import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_aion_capabilities import CapabilityRegistry, default_registry
from atlasquant_aion_orchestrator import (
    build_aion_result,
    orchestrate,
    prepare_reviewed_mission,
    validate_specialist_result,
)
from atlasquant_aion_truth import assess_truth
from atlasquant_aion_agent_review_protocol import seal_mission_review_message


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
    def reviewer_contexts():
        return {
            "PRIME": {
                "role": "PRIME",
                "agent_id": "prime-1",
                "tenant_id": "tenant-a",
                "workspace_id": "central",
                "capabilities": ["REVIEW"],
            },
            "SHADOW": {
                "role": "SHADOW",
                "agent_id": "shadow-1",
                "tenant_id": "tenant-a",
                "workspace_id": "central",
                "capabilities": ["REVIEW"],
            },
            "SENTINEL": {
                "role": "SENTINEL",
                "agent_id": "sentinel-1",
                "tenant_id": "tenant-a",
                "workspace_id": "central",
                "capabilities": ["REVIEW"],
            },
        }

    def review_message(
        self,
        role,
        binding,
        verdict="AGREE",
        *,
        plan_version=None,
        mission_id=None,
        approval_refs=None,
        nonce_suffix="",
    ):
        contexts = self.reviewer_contexts()
        sealed = seal_mission_review_message(
            verdict=verdict,
            mission_id=binding["mission_id"] if mission_id is None else mission_id,
            plan_version=binding["plan_version"] if plan_version is None else plan_version,
            trusted_context=contexts[role],
            evidence_refs=["evidence-1"],
            approval_refs=list(approval_refs or []),
            issued_at=NOW.isoformat(),
            nonce=f"{role.lower()}-{binding['mission_id']}-{nonce_suffix or verdict.lower()}",
            risk_level=binding["blast_radius"]["level"],
            confidence="HIGH",
        )
        self.assertEqual(sealed["state"], "SEALED")
        return sealed["message"]

    def preview(self, objective="Explique o contexto com cuidado.", **kwargs):
        params = {
            "access": self.access,
            "trusted_context": self.trusted,
            "trusted_reviewer_contexts": self.reviewer_contexts(),
            "evidence_refs": ["evidence-1"],
            "evidence_verifier": self.verified,
            "now": NOW,
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
        message = self.review_message("PRIME", preview)
        out = self.preview(review_messages=[message])
        self.assertEqual(out["state"], "READY_FOR_GUARDIAN")
        self.assertEqual(out["review"]["state"], "ACCEPT_PLAN")
        self.assertEqual(out["review_protocol"]["state"], "PASS")
        self.assertEqual(
            out["review_protocol"]["message_reports"][0]["authorization"],
            "NONE",
        )
        self.assertTrue(out["eligible_for_guardian"])
        self.assertFalse(out["guardian_called"])
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["grants_permission"])

    def test_code_change_requires_prime_shadow_sentinel_and_approval_evidence(self):
        preview = self.preview("Corrigir bug no código da interface.")
        self.assertEqual(preview["blast_radius"]["level"], "HIGH")
        self.assertEqual(preview["task_class"], "CRITICAL")
        self.assertEqual(
            preview["required_roles"],
            ["PRIME", "SHADOW", "SENTINEL"],
        )
        partial = self.preview(
            "Corrigir bug no código da interface.",
            review_messages=[
                self.review_message(
                    "PRIME",
                    preview,
                    approval_refs=["approval-1"],
                )
            ],
            approval_refs=["approval-1"],
            approval_verifier=self.verified,
        )
        self.assertEqual(partial["state"], "BLOCK")
        self.assertEqual(partial["review_protocol"]["state"], "PASS")
        self.assertIn("MISSING_REVIEWER:SHADOW", partial["review"]["blockers"])
        self.assertIn("MISSING_REVIEWER:SENTINEL", partial["review"]["blockers"])

        full = self.preview(
            "Corrigir bug no código da interface.",
            review_messages=[
                self.review_message(
                    "PRIME",
                    preview,
                    approval_refs=["approval-1"],
                ),
                self.review_message(
                    "SHADOW",
                    preview,
                    approval_refs=["approval-1"],
                ),
                self.review_message(
                    "SENTINEL",
                    preview,
                    approval_refs=["approval-1"],
                ),
            ],
            approval_refs=["approval-1"],
            approval_verifier=self.verified,
        )
        self.assertEqual(full["state"], "READY_FOR_GUARDIAN")
        self.assertTrue(full["eligible_for_guardian"])
        self.assertFalse(full["guardian_called"])
        self.assertFalse(full["external_action_executed"])

    def test_shadow_challenge_escalates_instead_of_picking_a_side(self):
        preview = self.preview("Corrigir bug no código da interface.")
        out = self.preview(
            "Corrigir bug no código da interface.",
            review_messages=[
                self.review_message(
                    "PRIME",
                    preview,
                    approval_refs=["approval-1"],
                ),
                self.review_message(
                    "SHADOW",
                    preview,
                    verdict="CHALLENGE",
                    approval_refs=["approval-1"],
                ),
                self.review_message(
                    "SENTINEL",
                    preview,
                    approval_refs=["approval-1"],
                ),
            ],
            approval_refs=["approval-1"],
            approval_verifier=self.verified,
        )
        self.assertEqual(out["state"], "ESCALATE")
        self.assertIn("DIVERGENCE:SHADOW", out["review"]["blockers"])
        self.assertFalse(out["eligible_for_guardian"])

    def test_review_bound_to_old_plan_version_is_blocked_by_protocol(self):
        preview = self.preview("Corrigir bug no código da interface.")
        stale = self.review_message(
            "PRIME",
            preview,
            plan_version="old-plan",
            approval_refs=["approval-1"],
        )
        out = self.preview(
            "Corrigir bug no código da interface.",
            review_messages=[stale],
            approval_refs=["approval-1"],
            approval_verifier=self.verified,
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertEqual(out["reason"], "PROTOCOL_FIREWALL_BLOCKED")
        self.assertIsNone(out["review"])
        self.assertTrue(
            any(
                "REVIEW_PLAN_MISMATCH" in item
                for item in out["review_protocol"]["blockers"]
            )
        )

    def test_replayed_review_message_is_blocked_before_adjudication(self):
        preview = self.preview()
        message = self.review_message("PRIME", preview)
        out = self.preview(
            review_messages=[message],
            seen_message_digests=[message["digest"]],
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertEqual(out["reason"], "PROTOCOL_FIREWALL_BLOCKED")
        self.assertIsNone(out["review"])
        self.assertTrue(
            any("REPLAY" in item for item in out["review_protocol"]["blockers"])
        )

    def test_spoofed_review_identity_is_blocked_before_adjudication(self):
        preview = self.preview()
        forged = dict(self.review_message("PRIME", preview))
        forged["role"] = "SENTINEL"
        out = self.preview(review_messages=[forged])
        self.assertEqual(out["state"], "BLOCK")
        self.assertEqual(out["reason"], "PROTOCOL_FIREWALL_BLOCKED")
        self.assertIsNone(out["review"])
        protocol_blockers = out["review_protocol"]["blockers"]
        self.assertTrue(
            any(
                "DIGEST_INVALID" in item or "SPOOFED_AGENT" in item
                for item in protocol_blockers
            )
        )

    def test_raw_review_bypass_is_not_part_of_mission_gate_signature(self):
        with self.assertRaises(TypeError):
            self.preview(
                reviews=[{
                    "role": "PRIME",
                    "agent_id": "prime-1",
                    "verdict": "AGREE",
                }],
            )

    def test_blocked_deploy_mission_never_reaches_review_or_guardian(self):
        out = self.preview(
            "Faça deploy em produção agora.",
            feature_flags={
                "external_llm": True,
                "production_deploy": False,
            },
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertEqual(out["reason"], "MISSION_NOT_READY")
        self.assertIsNone(out["review"])
        self.assertFalse(out["eligible_for_guardian"])
        self.assertFalse(out["guardian_called"])
        self.assertFalse(out["executes_action"])


if __name__ == "__main__":
    unittest.main()
