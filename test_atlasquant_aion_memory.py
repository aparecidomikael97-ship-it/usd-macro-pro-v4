import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from atlasquant_aion_memory import (
    APPROVED_AION_FOUNDATION,
    RuntimeConfig,
    canonical_documents,
    canonical_memory_summary,
    checkpoint_digest,
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

    def test_canonical_loader_reads_project_files_and_foundation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CONTEXTO_DO_PROJETO.md").write_text("AtlasQuant checkpoint mestre", encoding="utf-8")
            (root / "HISTORICO_DE_ALTERACOES.md").write_text("Histórico AtlasQuant", encoding="utf-8")
            docs = canonical_documents(root)
            paths = {d["path"] for d in docs}
            self.assertIn("CONTEXTO_DO_PROJETO.md", paths)
            self.assertIn("HISTORICO_DE_ALTERACOES.md", paths)
            self.assertIn("AION_APPROVED_FOUNDATION_2026-09-23", paths)
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

    def test_default_checkpoint_is_safe_and_has_no_real_trading(self):
        cp = default_checkpoint()
        self.assertFalse(cp["aion"]["real_trading"])
        self.assertEqual(cp["aion"]["cost_mode"], "ZERO_COST_DEFAULT")
        self.assertFalse(cp["aion"]["model_budget"]["allow_paid"])
        self.assertEqual(cp["aion"]["model_budget"]["monthly_limit_usd"],0.0)
        self.assertIn("approved_foundation", cp)
        self.assertTrue(checkpoint_digest(cp))

    def test_checkpoint_v5_has_operating_studio_business_promotions_and_entitlements_memory(self):
        cp=default_checkpoint()
        self.assertGreaterEqual(cp["checkpoint_version"],5)
        self.assertIn("operating",cp)
        self.assertEqual(cp["operating"]["tasks"],[])
        self.assertEqual(cp["operating"]["events"],[])
        self.assertFalse(cp["operating"]["dirty"])
        self.assertEqual(cp["studio"]["projects"],[])
        self.assertEqual(cp["business"]["products"],[])
        self.assertEqual(cp["promotions"]["campaigns"],[])
        self.assertEqual(cp["promotions"]["redemptions"],[])
        self.assertEqual(cp["entitlements"]["records"],[])

    def test_older_checkpoint_is_upgraded_without_claiming_persistence(self):
        old={"checkpoint_version":1,"project":"AtlasQuant"}
        upgraded=ensure_operating_checkpoint(old)
        self.assertEqual(upgraded["checkpoint_version"],5)
        self.assertIn("operating",upgraded)
        self.assertIn("studio",upgraded)
        self.assertIn("business",upgraded)
        self.assertIn("promotions",upgraded)
        self.assertIn("entitlements",upgraded)
        changed=update_operating_checkpoint(upgraded,tasks=[],events=[],dirty=True)
        self.assertTrue(changed["operating"]["dirty"])
        self.assertTrue(changed["operating"]["task_digest"])
        self.assertTrue(changed["operating"]["event_digest"])

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
        update=runtime_write_preflight({"status":"CONFIRMED","sha":"abc123"})
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
