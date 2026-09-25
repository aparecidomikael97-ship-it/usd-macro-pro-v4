import unittest

from atlasquant_aion_incident_center import (
    collect_incidents,
    incident_center_rows,
    incident_response_plan,
)
from atlasquant_aion_memory import default_checkpoint
from atlasquant_aion_observability import append_event, new_event


class AtlasQuantAionIncidentCenterTests(unittest.TestCase):
    def test_clean_unknown_external_state_does_not_invent_incident(self):
        cp=default_checkpoint()
        out=collect_incidents(
            checkpoint=cp,
            runtime_result={
                "status":"CONFIRMED",
                "integrity":{"state":"CONFIRMED","matched":6,"total":6},
            },
            system_context={"source_build":"abc"},
            account_audit={},
        )
        self.assertEqual(out["total"],0)
        self.assertFalse(out["has_critical"])
        self.assertFalse(out["rollback_review_recommended"])
        self.assertFalse(out["automatic_containment"])
        self.assertFalse(out["automatic_rollback"])
        self.assertFalse(out["real_orders_enabled"])
        self.assertFalse(out["executes_action"])

    def test_checkpoint_digest_mismatch_is_critical_incident(self):
        out=collect_incidents(
            checkpoint=default_checkpoint(),
            runtime_result={
                "status":"CONFIRMED",
                "integrity":{
                    "state":"MISMATCH",
                    "mismatches":["studio","business"],
                },
            },
        )
        self.assertTrue(out["has_critical"])
        row=next(x for x in out["incidents"] if x["kind"]=="CHECKPOINT_INTEGRITY")
        self.assertEqual(row["severity"],"CRITICAL")
        self.assertIn("studio",row["detail"])
        self.assertFalse(row["automatic_rollback"])

    def test_migration_required_is_medium_not_corruption_claim(self):
        out=collect_incidents(
            checkpoint=default_checkpoint(),
            runtime_result={
                "status":"CONFIRMED",
                "integrity":{"state":"MIGRATION_REQUIRED"},
            },
        )
        row=next(x for x in out["incidents"] if x["kind"]=="CHECKPOINT_INTEGRITY")
        self.assertEqual(row["severity"],"MEDIUM")
        self.assertIn("migração",row["title"].lower())

    def test_confirmed_secret_exposure_is_critical_without_secret_value(self):
        out=collect_incidents(
            checkpoint=default_checkpoint(),
            system_context={
                "secret_exposure_confirmed":True,
                "secret_value":"should-never-appear",
            },
        )
        row=next(x for x in out["incidents"] if x["kind"]=="SECRET_EXPOSURE")
        self.assertEqual(row["severity"],"CRITICAL")
        self.assertNotIn("should-never-appear",str(row))
        plan=incident_response_plan(row)
        joined=" ".join(plan["steps"])
        self.assertIn("Revogar/rotacionar",joined)
        self.assertIn("Nunca reutilizar",joined)
        self.assertFalse(plan["automatic_secret_rotation"])

    def test_health_failure_recommends_human_rollback_review_only(self):
        out=collect_incidents(
            checkpoint=default_checkpoint(),
            system_context={
                "app_boot_ok":True,
                "health_check_ok":False,
                "critical_engine_error":False,
                "data_integrity_breach":False,
                "error_rate_pct":0.0,
                "max_error_rate_pct":5.0,
            },
        )
        self.assertTrue(out["rollback_review_recommended"])
        self.assertTrue(any("Health check" in x for x in out["rollback_reasons"]))
        self.assertFalse(out["automatic_rollback"])
        row=next(x for x in out["incidents"] if x["kind"]=="APPLICATION_HEALTH")
        plan=incident_response_plan(row)
        self.assertTrue(plan["requires_human_review"])
        self.assertFalse(plan["automatic_rollback"])

    def test_partial_or_unknown_health_inputs_never_claim_rollback_signal(self):
        out=collect_incidents(
            checkpoint=default_checkpoint(),
            system_context={
                "health_check_ok":False,
            },
        )
        self.assertFalse(out["rollback_review_recommended"])
        self.assertTrue(any(x["kind"]=="APPLICATION_HEALTH" for x in out["incidents"]))

    def test_production_identity_mismatch_is_high_and_build_identity_oriented(self):
        out=collect_incidents(
            checkpoint=default_checkpoint(),
            system_context={"production_identity_state":"MISMATCH"},
        )
        row=next(x for x in out["incidents"] if x["kind"]=="PRODUCTION_IDENTITY")
        self.assertEqual(row["severity"],"HIGH")
        plan=incident_response_plan(row)
        joined=" ".join(plan["steps"])
        self.assertIn("HTTP 200",joined)
        self.assertIn("fingerprint/build identity",joined)

    def test_account_entitlement_divergence_is_high_without_auto_mutation(self):
        out=collect_incidents(
            checkpoint=default_checkpoint(),
            account_audit={
                "user_accounts_without_effective_entitlement":1,
                "duplicate_effective_user_accounts":2,
                "orphan_effective_entitlements":1,
            },
        )
        row=next(x for x in out["incidents"] if x["kind"]=="ACCOUNT_ACCESS")
        self.assertEqual(row["severity"],"HIGH")
        self.assertIn("4 divergência",row["detail"])
        self.assertFalse(row["automatic_account_mutation"])

    def test_observability_warning_error_and_critical_become_incidents(self):
        cp=default_checkpoint()
        events=[]
        events=append_event(events,new_event(
            "data_warning","Atenção de dados",severity="WARNING",
            created_at="2026-09-24T10:00:00+00:00",
        ))
        events=append_event(events,new_event(
            "engine_fault","Erro do motor",severity="ERROR",
            created_at="2026-09-24T10:01:00+00:00",
        ))
        events=append_event(events,new_event(
            "secret_exposure","credential was exposed",severity="CRITICAL",
            created_at="2026-09-24T10:02:00+00:00",
        ))
        cp["operating"]["events"]=events
        out=collect_incidents(checkpoint=cp)
        sevs={x["severity"] for x in out["incidents"]}
        self.assertIn("MEDIUM",sevs)
        self.assertIn("HIGH",sevs)
        self.assertIn("CRITICAL",sevs)
        self.assertTrue(any(x["kind"]=="SECRET_EXPOSURE" for x in out["incidents"]))

    def test_rows_are_presentation_only(self):
        out=collect_incidents(
            checkpoint=default_checkpoint(),
            system_context={"production_identity_state":"STALE"},
        )
        rows=incident_center_rows(out)
        self.assertTrue(rows)
        self.assertIn("Severidade",rows[0])
        self.assertIn("Origem",rows[0])
        self.assertFalse(out["automatic_containment"])


if __name__=="__main__":
    unittest.main()
