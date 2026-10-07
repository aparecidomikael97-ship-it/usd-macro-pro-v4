from __future__ import annotations
import unittest
import atlasquant_aion_chat_postgres_driver_binding_contract_v1 as contract

def ready_inputs():
    return {
        "driver_plan":{
            "driver":"PSYCOPG3_SYNC",
            "contract_imports_driver":False,
            "store_layer_driver_agnostic":True,
            "composition_root_owns_binding":True,
            "explicit_connection_factory":True,
        },
        "secret_boundary":{
            "credential_source":"PLATFORM_SECRET_INJECTION",
            "no_secret_read_at_import":True,
            "store_reads_environment":False,
            "dsn_in_source":False,
            "dsn_logged":False,
            "password_logged":False,
            "descriptor_contains_secret_reference_only":True,
            "rotation_without_code_change":True,
            "plaintext_dsn_returned_to_ui":False,
        },
        "connection_policy":{
            "endpoint_class":"INTERNAL_PRIVATE",
            "external_endpoint_allowed":False,
            "tls_mode":"REQUIRE",
            "autocommit":False,
            "connect_timeout_seconds":5,
            "statement_timeout_ms":10000,
            "application_name":"atlasquant-aion-chat",
            "least_privilege_role":True,
            "superuser":False,
            "auto_migrate_on_connect":False,
            "health_before_use":True,
            "schema_compatibility_before_use":True,
            "scope_policy_health_before_use":True,
            "fallback_to_external_endpoint":False,
            "fallback_to_sqlite":False,
        },
        "observability_policy":{
            "connection_state_logging":True,
            "latency_metrics":True,
            "error_class_metrics":True,
            "message_content_logged":False,
            "secret_material_logged":False,
            "safe_scope_identifier_policy":True,
        },
    }

class DriverBindingContractV1Tests(unittest.TestCase):
    def zero(self,out):
        for key in contract.FALSE_FIELDS:
            self.assertIs(out[key],False,key)

    def test_ready_is_review_only(self):
        out=contract.evaluate_driver_binding_contract(**ready_inputs())
        self.assertEqual(out["state"],contract.READY)
        self.assertEqual(out["planned_driver"],"PSYCOPG3_SYNC")
        self.assertEqual(out["endpoint_class"],"INTERNAL_PRIVATE")
        self.assertEqual(out["tls_mode"],"REQUIRE")
        self.zero(out)

    def test_external_endpoint_default_deny(self):
        d=ready_inputs()
        d["connection_policy"]["external_endpoint_allowed"]=True
        out=contract.evaluate_driver_binding_contract(**d)
        self.assertIn("EXTERNAL_ENDPOINT_DEFAULT_DENY_REQUIRED",out["blockers"])
        self.zero(out)

    def test_tls_required(self):
        d=ready_inputs()
        d["connection_policy"]["tls_mode"]="PREFER"
        out=contract.evaluate_driver_binding_contract(**d)
        self.assertIn("TLS_REQUIRED",out["blockers"])
        self.zero(out)

    def test_store_cannot_read_environment(self):
        d=ready_inputs()
        d["secret_boundary"]["store_reads_environment"]=True
        out=contract.evaluate_driver_binding_contract(**d)
        self.assertIn("NO_ENV_READ_IN_STORE_REQUIRED",out["blockers"])
        self.zero(out)

    def test_no_secret_logging(self):
        d=ready_inputs()
        d["secret_boundary"]["dsn_logged"]=True
        d["secret_boundary"]["password_logged"]=True
        out=contract.evaluate_driver_binding_contract(**d)
        self.assertIn("NO_DSN_IN_LOGS_REQUIRED",out["blockers"])
        self.assertIn("NO_PASSWORD_IN_LOGS_REQUIRED",out["blockers"])
        self.zero(out)

    def test_no_public_or_sqlite_fallback(self):
        d=ready_inputs()
        d["connection_policy"]["fallback_to_external_endpoint"]=True
        d["connection_policy"]["fallback_to_sqlite"]=True
        out=contract.evaluate_driver_binding_contract(**d)
        self.assertIn("AUTOMATIC_EXTERNAL_ENDPOINT_FALLBACK_FORBIDDEN",out["blockers"])
        self.assertIn("PRODUCTION_SQLITE_FALLBACK_FORBIDDEN",out["blockers"])
        self.zero(out)

    def test_timeouts_bounded(self):
        d=ready_inputs()
        d["connection_policy"]["connect_timeout_seconds"]=60
        d["connection_policy"]["statement_timeout_ms"]=120000
        out=contract.evaluate_driver_binding_contract(**d)
        self.assertIn("BOUNDED_CONNECT_TIMEOUT_REQUIRED",out["blockers"])
        self.assertIn("BOUNDED_STATEMENT_TIMEOUT_REQUIRED",out["blockers"])
        self.zero(out)

if __name__=="__main__":
    unittest.main()
