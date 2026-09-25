import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from atlasquant_aion_memory import (
    APPROVED_AION_FOUNDATION,
    FOUNDATION_REVISION,
    RuntimeConfig,
    canonical_documents,
    canonical_memory_summary,
    checkpoint_digest,
    checkpoint_integrity_report,
    checkpoint_source_digest,
    default_checkpoint,
    ensure_operating_checkpoint,
    load_runtime_checkpoint,
    merged_checkpoint,
    runtime_write_preflight,
    save_runtime_checkpoint,
    search_canonical_memory,
    update_business_checkpoint,
    update_entitlements_checkpoint,
    update_continuity_checkpoint,
    update_learning_checkpoint,
    update_portable_core_checkpoint,
    update_vault_checkpoint,
    update_tool_hub_checkpoint,
    update_durable_tasks_checkpoint,
    update_knowledge_graph_checkpoint,
    synchronize_knowledge_graph_checkpoint,
    update_evaluation_lab_checkpoint,
    update_wisdom_checkpoint,
    update_live_event_journal_checkpoint,
    update_operating_checkpoint,
    update_promotions_checkpoint,
    update_studio_checkpoint,
)


class AtlasQuantAionMemoryTests(unittest.TestCase):
    def test_static_foundation_contains_truth_cost_and_context_separation(self):
        joined = " ".join(APPROVED_AION_FOUNDATION).lower()
        self.assertIn("verdade", joined)
        self.assertIn("custo zero", joined)
        self.assertIn("studio", joined)
        self.assertIn("negócios", joined)
        self.assertIn("checkpoint", joined)
        self.assertIn("execução real", joined)
        self.assertIn("tô no computador", joined)
        self.assertIn("render", joined)
        self.assertIn("build identity", joined)
        self.assertIn("aprendizado controlado", joined)
        self.assertIn("champion", joined)
        self.assertIn("promoção automática", joined)
        self.assertIn("reliability guardian", joined)
        self.assertIn("fallback pago automático", joined)
        self.assertIn("rollback", joined)
        self.assertIn("source mesh", joined)
        self.assertIn("fallback", joined)
        self.assertIn("live_confirmed", joined)
        self.assertIn("runtime snapshot", joined)
        self.assertIn("cognitive orchestrator", joined)
        self.assertIn("deep research", joined)
        self.assertIn("critic", joined)
        self.assertIn("chain-of-thought", joined)
        self.assertIn("live event intelligence", joined)
        self.assertIn("breaking alert", joined)
        self.assertIn("hypothesis", joined)
        self.assertIn("24/7", joined)
        self.assertIn("policy engine", joined)
        self.assertIn("prompt injection", joined)
        self.assertIn("portable core", joined)
        self.assertIn("aion vault", joined)
        self.assertIn("autonomy budget", joined)
        self.assertIn("falsification engine", joined)
        self.assertIn("motor universal de performance", joined)
        self.assertIn("codex", joined)
        self.assertIn("cursor", joined)
        self.assertIn("claude code", joined)
        self.assertIn("dev fusion engine", joined)
        self.assertIn("elite developer stack", joined)
        self.assertIn("creative fusion studio", joined)
        self.assertIn("antivírus", joined)
        self.assertIn("digital twin", joined)
        self.assertIn("proof of safety", joined)
        self.assertIn("salvar, amarrar", joined)

    def test_canonical_loader_reads_project_files_and_foundation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CONTEXTO_DO_PROJETO.md").write_text("AtlasQuant checkpoint mestre", encoding="utf-8")
            (root / "HISTORICO_DE_ALTERACOES.md").write_text("Histórico AtlasQuant", encoding="utf-8")
            docs = canonical_documents(root)
            paths = {d["path"] for d in docs}
            self.assertIn("CONTEXTO_DO_PROJETO.md", paths)
            self.assertIn("HISTORICO_DE_ALTERACOES.md", paths)
            self.assertIn("AION_APPROVED_FOUNDATION_2026-09-25", paths)
            summary = canonical_memory_summary(root)
            self.assertEqual(summary["status"], "CONFIRMED")
            self.assertGreaterEqual(summary["document_count"], 3)

    def test_continuity_loader_includes_home_pc_render_priority_checkpoint(self):
        docs = canonical_documents(Path(__file__).resolve().parent)
        paths = {d["path"] for d in docs}
        expected = "docs/continuidade/PRIORIDADE_RENDER_AO_CHEGAR_EM_CASA_2026-09-24.md"
        self.assertIn(expected, paths)
        hits = search_canonical_memory(
            "tô no computador Render Deploy Hook",
            base_dir=Path(__file__).resolve().parent,
        )
        self.assertTrue(any(h["path"] == expected for h in hits))

    def test_memory_search_returns_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CONTEXTO_DO_PROJETO.md").write_text(
                "AION deve usar Checkpoint Mestre para desenvolvimento e memória.",
                encoding="utf-8",
            )
            hits = search_canonical_memory("checkpoint desenvolvimento", base_dir=root)
            self.assertTrue(hits)
            self.assertIn("path", hits[0])
            self.assertIn("excerpt", hits[0])
            self.assertIn("sha256", hits[0])

    def test_checkpoint_merges_current_approved_foundation_without_losing_legacy_items(self):
        old = {
            "checkpoint_version": 8,
            "project": "AtlasQuant",
            "approved_foundation": ["Regra legada preservada."],
            "aion": {},
        }
        upgraded = ensure_operating_checkpoint(old)
        joined = " ".join(upgraded["approved_foundation"]).lower()
        self.assertIn("regra legada preservada", joined)
        self.assertIn("aion portable core", joined)
        self.assertIn("creative fusion studio", joined)
        self.assertIn("motor universal de performance", joined)
        self.assertEqual(upgraded["aion"]["foundation_revision"], FOUNDATION_REVISION)
        self.assertGreaterEqual(upgraded["checkpoint_version"], 12)

    def test_default_checkpoint_is_safe_and_has_no_real_trading(self):
        cp = default_checkpoint()
        self.assertFalse(cp["aion"]["real_trading"])
        self.assertEqual(cp["aion"]["cost_mode"], "ZERO_COST_DEFAULT")
        self.assertFalse(cp["aion"]["model_budget"]["allow_paid"])
        self.assertEqual(cp["aion"]["model_budget"]["monthly_limit_usd"],0.0)
        self.assertIn("approved_foundation", cp)
        self.assertTrue(checkpoint_digest(cp))

    def test_checkpoint_v7_has_operating_continuity_and_commercial_memory(self):
        cp=default_checkpoint()
        self.assertGreaterEqual(cp["checkpoint_version"],7)
        self.assertIn("operating",cp)
        self.assertEqual(cp["operating"]["tasks"],[])
        self.assertEqual(cp["operating"]["events"],[])
        self.assertFalse(cp["operating"]["dirty"])
        self.assertEqual(cp["studio"]["projects"],[])
        self.assertEqual(cp["business"]["products"],[])
        self.assertEqual(cp["promotions"]["campaigns"],[])
        self.assertEqual(cp["promotions"]["redemptions"],[])
        self.assertEqual(cp["entitlements"]["records"],[])
        self.assertEqual(cp["continuity"]["missions"],[])
        self.assertEqual(cp["continuity"]["handoffs"],[])
        self.assertTrue(cp["continuity"]["digest"])
        self.assertEqual(cp["learning"]["episodes"],[])
        self.assertEqual(cp["learning"]["experiments"],[])
        self.assertEqual(cp["learning"]["research_refs"],[])
        self.assertTrue(cp["learning"]["digest"])
        self.assertEqual(cp["wisdom"]["entries"],[])
        self.assertTrue(cp["wisdom"]["digest"])
        self.assertIn("portable_core",cp)
        self.assertTrue(cp["portable_core"]["digest"])
        self.assertIn("vault",cp)
        self.assertTrue(cp["vault"]["digest"])
        self.assertFalse(cp["vault"]["plaintext_secrets_present"])
        self.assertIn("tool_hub",cp)
        self.assertTrue(cp["tool_hub"]["digest"])
        self.assertIn("durable_tasks",cp)
        self.assertEqual(cp["durable_tasks"]["records"],[])
        self.assertTrue(cp["durable_tasks"]["digest"])
        self.assertIn("knowledge_graph",cp)
        self.assertTrue(cp["knowledge_graph"]["digest"])
        self.assertIn("evaluation_lab",cp)
        self.assertTrue(cp["evaluation_lab"]["digest"])
        self.assertFalse(cp["evaluation_lab"]["automatic_promotion"])
        self.assertEqual(cp["live_event_journal"]["events"],[])
        self.assertEqual(cp["live_event_journal"]["heartbeats"],[])
        self.assertTrue(cp["live_event_journal"]["digest"])
        self.assertIn("subscriptions",cp["areas"])

    def test_older_checkpoint_is_upgraded_without_claiming_persistence(self):
        old={"checkpoint_version":1,"project":"AtlasQuant"}
        upgraded=ensure_operating_checkpoint(old)
        self.assertEqual(upgraded["checkpoint_version"],12)
        self.assertIn("operating",upgraded)
        self.assertIn("studio",upgraded)
        self.assertIn("business",upgraded)
        self.assertIn("promotions",upgraded)
        self.assertIn("entitlements",upgraded)
        self.assertIn("continuity",upgraded)
        self.assertIn("learning",upgraded)
        self.assertIn("wisdom",upgraded)
        self.assertIn("portable_core",upgraded)
        self.assertIn("vault",upgraded)
        self.assertIn("tool_hub",upgraded)
        self.assertIn("durable_tasks",upgraded)
        self.assertIn("knowledge_graph",upgraded)
        self.assertIn("evaluation_lab",upgraded)
        self.assertIn("live_event_journal",upgraded)
        self.assertIn("subscriptions",upgraded["areas"])
        changed=update_operating_checkpoint(upgraded,tasks=[],events=[],dirty=True)
        self.assertTrue(changed["operating"]["dirty"])
        self.assertTrue(changed["operating"]["task_digest"])
        self.assertTrue(changed["operating"]["event_digest"])

    def test_checkpoint_v10_portable_core_and_vault_roundtrip(self):
        cp=default_checkpoint()
        portable=dict(cp["portable_core"])
        portable["connectors"]=[{
            "connector_id":"github-dev",
            "label":"GitHub Dev",
            "protocol":"MCP",
            "workspace_id":"development",
            "state":"DISABLED",
            "scopes":["read_repo"],
            "secret_refs":["GITHUB_TOKEN_HISTORICO"],
        }]
        cp=update_portable_core_checkpoint(cp,portable_core=portable,dirty=True)
        self.assertEqual(cp["portable_core"]["connectors"][0]["connector_id"],"github-dev")

        vault=dict(cp["vault"])
        vault["entries"]=[{
            "entry_id":"checkpoint-backup",
            "kind":"CHECKPOINT_BACKUP",
            "backend":"RUNTIME_DATA",
            "locator_ref":"dados/aion/checkpoint_master.json",
            "state":"ACTIVE",
            "content_digest":"abc123",
            "version":"v10",
            "metadata":{},
        }]
        cp=update_vault_checkpoint(cp,vault=vault,dirty=True)
        self.assertEqual(cp["vault"]["entries"][0]["entry_id"],"checkpoint-backup")
        self.assertEqual(checkpoint_integrity_report(cp)["state"],"CONFIRMED")

    def test_vault_checkpoint_rejects_plaintext_secret_like_top_level_field(self):
        cp=default_checkpoint()
        bad=dict(cp["vault"])
        bad["token"]="plaintext-is-forbidden"
        with self.assertRaises(ValueError):
            update_vault_checkpoint(cp,vault=bad,dirty=True)

    def test_checkpoint_v11_tool_hub_and_durable_tasks_roundtrip(self):
        cp=default_checkpoint()
        hub=dict(cp["tool_hub"])
        hub["tools"]=list(hub["tools"])+[{
            "tool_id":"dev.local.inspect",
            "label":"Inspect local",
            "workspace_id":"development",
            "connector_id":"",
            "kind":"READ",
            "guardian_action":"read",
            "state":"LOCAL_READY",
            "required_scopes":["repo:read"],
            "external_side_effects":False,
        }]
        cp=update_tool_hub_checkpoint(cp,tool_hub=hub,dirty=True)
        self.assertTrue(any(x["tool_id"]=="dev.local.inspect" for x in cp["tool_hub"]["tools"]))

        records=[{
            "durable_task_id":"DUR-TEST",
            "title":"Retomar bloco",
            "objective":"Preservar cursor.",
            "domain":"development",
            "state":"PAUSED",
            "steps":[{"step_id":"S001","title":"Validar","state":"PENDING"}],
            "cursor":0,
            "revision":1,
            "checkpoint_digest":"cp",
            "created_at":"2026-09-25T16:00:00+00:00",
        }]
        cp=update_durable_tasks_checkpoint(cp,records=records,dirty=True)
        self.assertEqual(cp["durable_tasks"]["records"][0]["durable_task_id"],"DUR-TEST")
        self.assertEqual(checkpoint_integrity_report(cp)["state"],"CONFIRMED")

    def test_learning_and_wisdom_writes_refresh_explicit_graph_links(self):
        cp=default_checkpoint()
        episode={
            "episode_id":"LEARN-GRAPH-1",
            "subject":"Payroll surprise",
            "state":"SETTLED",
            "domain":"trading",
            "forecast_type":"CATEGORICAL",
            "prediction":"USD_UP",
            "forecast_confidence_pct":70,
            "model_version":"AION",
            "evidence_refs":["calendar:payroll-1"],
            "created_at":"2026-09-25T12:00:00+00:00",
            "actual_outcome":"USD_UP",
            "evaluation":"MATCH",
            "correct":True,
            "error_cause":"UNKNOWN",
            "error_cause_truth":"UNKNOWN",
        }
        cp=update_learning_checkpoint(cp,episodes=[episode],dirty=True)
        self.assertTrue(any(
            x["node_id"]=="episode:learn-graph-1"
            for x in cp["knowledge_graph"]["nodes"]
        ))

        wisdom_entry={
            "wisdom_id":"WIS-GRAPH-1",
            "state":"ACTIVE",
            "topic":"Payroll reaction",
            "domain":"trading",
            "insight":"Resultado registrado com evidência.",
            "truth_state":"CONFIRMED",
            "confidence_pct":80,
            "evidence_refs":["calendar:payroll-1"],
            "applies_to":["USD"],
            "source_episode_ids":["LEARN-GRAPH-1"],
            "created_at":"2026-09-25T12:30:00+00:00",
            "created_by":"ADMIN",
        }
        cp=update_wisdom_checkpoint(cp,entries=[wisdom_entry],dirty=True)
        relations={x["relation"] for x in cp["knowledge_graph"]["edges"]}
        self.assertIn("DERIVED_FROM",relations)
        self.assertIn("SUPPORTED_BY",relations)

    def test_checkpoint_v12_graph_and_eval_lab_roundtrip(self):
        cp=default_checkpoint()
        graph={
            "nodes":[{
                "node_id":"component:guardian",
                "node_type":"COMPONENT",
                "label":"Guardian",
                "truth_state":"UNKNOWN",
            }],
            "edges":[],
        }
        cp=update_knowledge_graph_checkpoint(cp,graph=graph,dirty=True)
        self.assertTrue(any(x["node_id"]=="component:guardian" for x in cp["knowledge_graph"]["nodes"]))

        cp=synchronize_knowledge_graph_checkpoint(cp,dirty=True)
        self.assertTrue(cp["knowledge_graph"]["digest"])

        lab=dict(cp["evaluation_lab"])
        cp=update_evaluation_lab_checkpoint(cp,evaluation_lab=lab,dirty=True)
        self.assertFalse(cp["evaluation_lab"]["automatic_promotion"])
        self.assertEqual(checkpoint_integrity_report(cp)["state"],"CONFIRMED")

    def test_integrity_report_confirms_v7_and_detects_tampering(self):
        cp=default_checkpoint()
        report=checkpoint_integrity_report(cp)
        self.assertEqual(report["state"],"CONFIRMED")
        self.assertTrue(report["write_safe"])
        self.assertEqual(report["matched"],report["total"])

        tampered=default_checkpoint()
        tampered["studio"]["digest"]="deadbeef"
        report=checkpoint_integrity_report(tampered)
        self.assertEqual(report["state"],"MISMATCH")
        self.assertFalse(report["write_safe"])
        self.assertIn("studio",report["mismatches"])

    def test_integrity_report_marks_legacy_v6_checkpoint_for_safe_v7_migration(self):
        legacy=default_checkpoint()
        legacy["checkpoint_version"]=6
        legacy.pop("continuity",None)
        report=checkpoint_integrity_report(legacy)
        self.assertEqual(report["state"],"MIGRATION_REQUIRED")
        self.assertTrue(report["write_safe"])
        self.assertTrue(any("continuity" in x for x in report["migration_items"]))
        preflight=runtime_write_preflight({
            "status":"CONFIRMED",
            "sha":"legacysha",
            "checkpoint":legacy,
        })
        self.assertTrue(preflight["allowed"])
        self.assertEqual(preflight["mode"],"UPDATE_MIGRATION")
        self.assertIn("V12",preflight["reason"])

    def test_integrity_mismatch_blocks_runtime_write_preflight(self):
        tampered=default_checkpoint()
        tampered["business"]["digest"]="wrong"
        preflight=runtime_write_preflight({
            "status":"CONFIRMED",
            "sha":"abc123",
            "checkpoint":tampered,
        })
        self.assertFalse(preflight["allowed"])
        self.assertEqual(preflight["mode"],"BLOCKED")
        self.assertEqual(preflight["integrity_state"],"MISMATCH")

    def test_continuity_update_marks_checkpoint_dirty_and_is_integrity_checked(self):
        cp=default_checkpoint()
        changed=update_continuity_checkpoint(
            cp,
            missions=[{
                "title":"Missão teste",
                "domain":"development",
                "status":"PLANNED",
                "next_action":"Rodar testes",
                "created_at":"2026-09-24T20:00:00+00:00",
            }],
            handoffs=[],
            dirty=True,
        )
        self.assertEqual(len(changed["continuity"]["missions"]),1)
        self.assertTrue(changed["continuity"]["digest"])
        self.assertTrue(changed["operating"]["dirty"])
        self.assertEqual(checkpoint_integrity_report(changed)["state"],"CONFIRMED")

        tampered=default_checkpoint()
        tampered["continuity"]["digest"]="wrong"
        report=checkpoint_integrity_report(tampered)
        self.assertEqual(report["state"],"MISMATCH")
        self.assertIn("continuity",report["mismatches"])

    def test_learning_update_is_integrity_checked_and_marks_checkpoint_dirty(self):
        cp=default_checkpoint()
        changed=update_learning_checkpoint(
            cp,
            episodes=[{
                "subject":"Payroll reaction",
                "forecast_type":"DIRECTIONAL",
                "prediction":"USD_UP",
                "forecast_confidence_pct":70,
                "model_version":"aion-v1",
                "created_at":"2026-09-24T20:00:00+00:00",
            }],
            experiments=[],
            research_refs=[{
                "kind":"BACKTEST",
                "ref_id":"snapshot-1",
                "summary":"Research only",
                "created_at":"2026-09-24T20:01:00+00:00",
            }],
            dirty=True,
        )
        self.assertEqual(len(changed["learning"]["episodes"]),1)
        self.assertEqual(len(changed["learning"]["research_refs"]),1)
        self.assertTrue(changed["learning"]["digest"])
        self.assertTrue(changed["operating"]["dirty"])
        self.assertEqual(checkpoint_integrity_report(changed)["state"],"CONFIRMED")

        tampered=default_checkpoint()
        tampered["learning"]["digest"]="wrong"
        report=checkpoint_integrity_report(tampered)
        self.assertEqual(report["state"],"MISMATCH")
        self.assertIn("learning",report["mismatches"])

    def test_live_event_journal_update_is_integrity_checked(self):
        cp=default_checkpoint()
        changed=update_live_event_journal_checkpoint(
            cp,
            events=[{
                "event_id":"EVT-1",
                "headline":"Reported event",
                "kind":"NEWS_REPORT",
                "category":"GEOPOLITICAL_ESCALATION",
                "truth_state":"INFERENCE",
                "urgency_score":80,
                "alert_level":"URGENT_REVIEW",
            }],
            heartbeats=[{
                "observed_at":"2026-09-25T10:00:00+00:00",
                "source_state":"FRESH",
                "event_count":1,
                "alert_count":1,
            }],
            dirty=True,
        )
        self.assertEqual(len(changed["live_event_journal"]["events"]),1)
        self.assertEqual(len(changed["live_event_journal"]["heartbeats"]),1)
        self.assertTrue(changed["live_event_journal"]["digest"])
        self.assertTrue(changed["operating"]["dirty"])
        self.assertEqual(checkpoint_integrity_report(changed)["state"],"CONFIRMED")

        tampered=default_checkpoint()
        tampered["live_event_journal"]["digest"]="wrong"
        report=checkpoint_integrity_report(tampered)
        self.assertEqual(report["state"],"MISMATCH")
        self.assertIn("live_event_journal",report["mismatches"])

    def test_legacy_checkpoint_without_live_event_journal_requires_safe_migration(self):
        legacy=default_checkpoint()
        legacy.pop("live_event_journal",None)
        report=checkpoint_integrity_report(legacy)
        self.assertEqual(report["state"],"MIGRATION_REQUIRED")
        self.assertTrue(report["write_safe"])
        self.assertTrue(any("live_event_journal" in x for x in report["migration_items"]))

    def test_legacy_checkpoint_without_learning_requires_safe_migration(self):
        legacy=default_checkpoint()
        legacy.pop("learning",None)
        report=checkpoint_integrity_report(legacy)
        self.assertEqual(report["state"],"MIGRATION_REQUIRED")
        self.assertTrue(report["write_safe"])
        self.assertTrue(any("learning" in x for x in report["migration_items"]))

    def test_studio_and_business_updates_mark_checkpoint_dirty(self):
        cp=default_checkpoint()
        studio=update_studio_checkpoint(
            cp,
            projects=[{
                "title":"Vídeo teste",
                "platforms":["Instagram"],
                "created_at":"2026-09-23T20:00:00Z",
            }],
            dirty=True,
        )
        self.assertEqual(len(studio["studio"]["projects"]),1)
        self.assertTrue(studio["operating"]["dirty"])
        business=update_business_checkpoint(
            studio,
            products=[{
                "name":"Produto teste",
                "channel":"Mercado Livre",
                "created_at":"2026-09-23T20:01:00Z",
            }],
            dirty=True,
        )
        self.assertEqual(len(business["business"]["products"]),1)
        self.assertTrue(business["studio"]["digest"])
        self.assertTrue(business["business"]["digest"])

    def test_promotions_update_marks_checkpoint_dirty_without_plaintext_code(self):
        cp=default_checkpoint()
        changed=update_promotions_checkpoint(
            cp,
            campaigns=[{
                "name":"Semana grátis",
                "benefit":{"type":"TRIAL_DAYS","value":7},
                "code":{"sha256":"a"*64,"last4":"TEST"},
                "limits":{"max_uses":10,"confirmed_uses":0},
                "created_at":"2026-09-23T20:02:00Z",
            }],
            redemptions=[],
            dirty=True,
        )
        self.assertEqual(len(changed["promotions"]["campaigns"]),1)
        self.assertTrue(changed["operating"]["dirty"])
        stored=changed["promotions"]["campaigns"][0]
        self.assertFalse(stored["code"]["plaintext_stored"])
        self.assertEqual(stored["code"]["sha256"],"a"*64)
        self.assertNotIn("AQ-",str(stored))

    def test_entitlement_update_marks_checkpoint_dirty_and_keeps_registry_separate(self):
        cp=default_checkpoint()
        changed=update_entitlements_checkpoint(
            cp,
            records=[{
                "subject_ref":"cliente.01",
                "scope":"APP_ACCESS",
                "source":{"kind":"MANUAL_GRANT","ref":""},
                "status":"DRAFT",
                "created_at":"2026-09-24T12:00:00Z",
            }],
            dirty=True,
        )
        self.assertEqual(len(changed["entitlements"]["records"]),1)
        self.assertTrue(changed["entitlements"]["digest"])
        self.assertTrue(changed["operating"]["dirty"])
        row=changed["entitlements"]["records"][0]
        self.assertFalse(row["effects"]["account_registry_changed"])
        self.assertFalse(row["effects"]["role_changed"])
        self.assertFalse(row["effects"]["payment_executed"])
        self.assertFalse(row["effects"]["trading_permission_changed"])

    def test_source_digest_ignores_volatile_checkpoint_timestamps(self):
        a=default_checkpoint()
        b=default_checkpoint()
        a["created_at"]="2026-09-23T00:00:00+00:00"
        a["updated_at"]="2026-09-23T00:00:00+00:00"
        b["created_at"]="2026-09-24T00:00:00+00:00"
        b["updated_at"]="2026-09-24T00:00:00+00:00"
        b["operating"]["dirty"]=True
        self.assertEqual(checkpoint_source_digest(a),checkpoint_source_digest(b))

    def test_runtime_write_preflight_fails_closed_on_uncertain_state(self):
        for status in ("UNAVAILABLE","ERROR","BLOCKED","UNKNOWN"):
            result=runtime_write_preflight({"status":status})
            self.assertFalse(result["allowed"])
            self.assertEqual(result["mode"],"BLOCKED")
        missing_sha=runtime_write_preflight({"status":"CONFIRMED","sha":""})
        self.assertFalse(missing_sha["allowed"])
        create=runtime_write_preflight({"status":"NOT_FOUND"})
        self.assertTrue(create["allowed"])
        self.assertEqual(create["mode"],"CREATE")
        no_checkpoint=runtime_write_preflight({"status":"CONFIRMED","sha":"abc123"})
        self.assertFalse(no_checkpoint["allowed"])
        self.assertEqual(no_checkpoint["integrity_state"],"UNKNOWN")

        current=default_checkpoint()
        update=runtime_write_preflight({
            "status":"CONFIRMED",
            "sha":"abc123",
            "checkpoint":current,
        })
        self.assertTrue(update["allowed"])
        self.assertEqual(update["mode"],"UPDATE")
        self.assertEqual(update["expected_sha"],"abc123")

    def test_verified_save_persists_clean_checkpoint_and_requires_readback_match(self):
        cfg=RuntimeConfig(token="x",repo="owner/repo",branch="atlasquant-runtime")
        cp=default_checkpoint()
        cp["operating"]["dirty"]=True

        put=MagicMock()
        put.status_code=200
        put.raise_for_status.return_value=None
        put.json.return_value={"content":{"sha":"newsha"}}

        verified=ensure_operating_checkpoint(cp)
        verified["operating"]["dirty"]=False
        with patch("atlasquant_aion_memory.requests.put",return_value=put) as put_call, patch(
            "atlasquant_aion_memory.load_runtime_checkpoint",
            return_value={
                "status":"CONFIRMED",
                "sha":"newsha",
                "checkpoint":verified,
                "source":"GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json",
            },
        ):
            result=save_runtime_checkpoint(cp,cfg,approved=True,expected_sha="oldsha")

        self.assertTrue(result["saved"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"],"CONFIRMED")
        self.assertFalse(result["checkpoint"]["operating"]["dirty"])
        body=put_call.call_args.kwargs["json"]
        import base64, json
        written=json.loads(base64.b64decode(body["content"]).decode("utf-8"))
        self.assertFalse(written["operating"]["dirty"])
        self.assertEqual(body["sha"],"oldsha")

    def test_save_reports_conflict_when_conditional_write_is_rejected(self):
        cfg=RuntimeConfig(token="x",repo="owner/repo",branch="atlasquant-runtime")
        put=MagicMock()
        put.status_code=409
        with patch("atlasquant_aion_memory.requests.put",return_value=put):
            result=save_runtime_checkpoint(default_checkpoint(),cfg,approved=True,expected_sha="stale")
        self.assertEqual(result["status"],"CONFLICT")
        self.assertFalse(result["saved"])
        self.assertFalse(result["verified"])

    def test_save_never_claims_confirmed_when_readback_cannot_be_verified(self):
        cfg=RuntimeConfig(token="x",repo="owner/repo",branch="atlasquant-runtime")
        put=MagicMock()
        put.status_code=200
        put.raise_for_status.return_value=None
        put.json.return_value={"content":{"sha":"newsha"}}
        with patch("atlasquant_aion_memory.requests.put",return_value=put), patch(
            "atlasquant_aion_memory.load_runtime_checkpoint",
            return_value={"status":"ERROR","sha":"","checkpoint":None},
        ):
            result=save_runtime_checkpoint(default_checkpoint(),cfg,approved=True)
        self.assertEqual(result["status"],"UNVERIFIED")
        self.assertFalse(result["saved"])
        self.assertFalse(result["verified"])
        self.assertTrue(result["write_accepted"])

    def test_runtime_load_is_truthful_when_credentials_missing(self):
        cfg = RuntimeConfig(token="", repo="", branch="atlasquant-runtime")
        result = load_runtime_checkpoint(cfg)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIsNone(result["checkpoint"])

    def test_save_requires_explicit_approval_before_any_network_use(self):
        cfg = RuntimeConfig(token="x", repo="owner/repo", branch="atlasquant-runtime")
        result = save_runtime_checkpoint(default_checkpoint(), cfg, approved=False)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["saved"])

    def test_runtime_writes_refuse_code_branch(self):
        cfg = RuntimeConfig(token="x", repo="owner/repo", branch="main")
        load = load_runtime_checkpoint(cfg)
        save = save_runtime_checkpoint(default_checkpoint(), cfg, approved=True)
        self.assertEqual(load["status"], "BLOCKED")
        self.assertEqual(save["status"], "BLOCKED")

    def test_merged_checkpoint_labels_static_fallback(self):
        merged = merged_checkpoint({"status": "UNAVAILABLE"})
        self.assertFalse(merged["runtime_confirmed"])
        self.assertEqual(merged["provenance"], "static-seed")
        self.assertIn("checkpoint", merged)


if __name__ == "__main__":
    unittest.main()
