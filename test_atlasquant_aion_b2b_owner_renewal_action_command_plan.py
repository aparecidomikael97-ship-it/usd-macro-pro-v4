from __future__ import annotations

import unittest

from atlasquant_aion_b2b_owner_renewal_action_command_plan import (
    ACTION_OPERATION_KIND,
    build_owner_renewal_action_command_plan,
)
from atlasquant_aion_b2b_owner_renewal_action_execution_persistence_attestation import (
    SCHEMA as PERSISTENCE_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_action_execution_preflight import (
    SCHEMA as PREFLIGHT_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_action_execution_writer_attestation import (
    RESULT_SCHEMA as WRITER_SCHEMA,
)

SCOPE={"owner_id":"owner-a","tenant_id":"tenant-a","workspace_id":"workspace-a"}


def h(c): return "sha256:"+c*64


AUTHORITY_FIELDS=(
    "business_action_authorized","renewal_authorized","expansion_authorized",
    "non_renewal_authorized","remediation_authorized","pause_authorized",
    "termination_authorized","billing_authorized","pricing_change_authorized",
    "quota_change_authorized","package_change_authorized","role_change_authorized",
    "integration_change_authorized","customer_contact_authorized",
    "provisioning_authorized","deploy_authorized","provider_called",
    "crm_write_authorized","production_mutation_authorized",
    "external_action_executed","network_called","executes_action",
)


def persisted(**overrides):
    row={
        "schema":PERSISTENCE_SCHEMA,
        "state":"OWNER_RENEWAL_ACTION_EXECUTION_RECORD_PERSISTENCE_ATTESTED",
        "blockers":[],"execution_decision":"AUTHORIZE_BUSINESS_ACTION_EXECUTION",
        "requested_choice":"RENEW_AS_IS_REVIEW","action_family":"RENEWAL",
        "scope":dict(SCOPE),**SCOPE,
        "customer_id":"customer-a","pilot_id":"pilot-a",
        "package":"PROFISSIONAL","review_type":"RENEWAL_REVIEW",
        "action_record_digest":h("1"),"action_persistence_receipt_digest":h("2"),
        "action_checkpoint_digest":h("3"),"action_writer_request_digest":h("4"),
        "authorization_preflight_digest":h("5"),"action_parameters_digest":h("6"),
        "execution_environment_digest":h("7"),"execution_preflight_digest":h("8"),
        "execution_request_digest":h("9"),"execution_record_digest":h("a"),
        "checkpoint_revision":5,"checkpoint_state_digest":h("b"),
        "before_checkpoint_digest":h("c"),"after_checkpoint_digest":h("d"),
        "receipt_digest":h("e"),"execution_record_persisted":True,
        "persistence_attested":True,"receipt_consistency_verified":True,
        "writer_identity_verified":False,"eligible_for_command_planning":True,
        "storage_write_performed":False,
        "execution_command_generated":False,"execution_command_executed":False,
        **{key:False for key in AUTHORITY_FIELDS},
    }
    row.update(overrides);return row


def writer(**overrides):
    row={
        "schema":WRITER_SCHEMA,
        "state":"EXECUTION_INTENT_CHECKPOINT_WRITER_AUTHORITY_ATTESTED",
        "blockers":[],"customer_id":"customer-a","pilot_id":"pilot-a",
        "requested_choice":"RENEW_AS_IS_REVIEW","action_family":"RENEWAL",
        "execution_decision":"AUTHORIZE_BUSINESS_ACTION_EXECUTION",
        "receipt_digest":h("e"),"after_checkpoint_digest":h("d"),
        "execution_record_digest":h("a"),"event_id":"event-001",
        "writer_ref":"checkpoint-writer:execution-intent",
        "writer_key_id":"execution-writer-key","writer_key_version":1,
        "writer_public_key_fingerprint":h("f"),"writer_request_digest":h("0"),
        "writer_identity_verified":True,"writer_authority_verified":True,
        "receipt_binding_verified":True,"nonce_registered":True,
        "checkpoint_write_performed":False,"eligible_for_command_planning":True,
        "execution_command_generated":False,"execution_command_executed":False,
        **{key:False for key in AUTHORITY_FIELDS},
    }
    row.update(overrides);return row


def preflight(**overrides):
    row={
        "schema":PREFLIGHT_SCHEMA,
        "state":"READY_FOR_BUSINESS_ACTION_EXECUTION_CEREMONY",
        "blockers":[],"scope":dict(SCOPE),**SCOPE,
        "customer_id":"customer-a","pilot_id":"pilot-a",
        "package":"PROFISSIONAL","review_type":"RENEWAL_REVIEW",
        "requested_choice":"RENEW_AS_IS_REVIEW","action_family":"RENEWAL",
        "action_record_digest":h("1"),"action_persistence_receipt_digest":h("2"),
        "action_checkpoint_digest":h("3"),"action_writer_request_digest":h("4"),
        "authorization_preflight_digest":h("5"),"action_parameters_digest":h("6"),
        "execution_environment_digest":h("7"),"execution_preflight_digest":h("8"),
        "business_action_execution_ceremony_eligible":True,
        "human_execution_confirmation_required":True,
        "execution_request_issued":False,"owner_execution_signature_verified":False,
        "execution_command_generated":False,"execution_command_executed":False,
        "customer_visible":False,
        **{key:False for key in AUTHORITY_FIELDS},
    }
    row.update(overrides);return row


def run(**overrides):
    args={
        "trusted_scope":SCOPE,
        "execution_persistence_attestation":persisted(),
        "execution_writer_attestation":writer(),
        "execution_preflight":preflight(),
    }
    args.update(overrides)
    return build_owner_renewal_action_command_plan(**args)


class OwnerRenewalActionCommandPlanTests(unittest.TestCase):
    def test_valid_chain_builds_abstract_non_executable_plan(self):
        out=run()
        self.assertEqual(out["state"],"READY_FOR_BUSINESS_ACTION_COMMAND_ADAPTER_REVIEW")
        self.assertEqual(out["operation_kind"],"CONTRACT_CONTINUITY")
        self.assertEqual(out["command_plan"]["action_parameters_digest"],h("6"))
        self.assertTrue(out["command_plan_digest"].startswith("sha256:"))
        self.assertTrue(out["command_adapter_review_required"])
        self.assertTrue(out["requires_separate_adapter_binding"])
        self.assertFalse(out["execution_command_generated"])
        self.assertFalse(out["provider_called"])
        self.assertFalse(out["executes_action"])

    def test_denied_execution_cannot_create_plan(self):
        p=persisted(
            execution_decision="DENY_BUSINESS_ACTION_EXECUTION",
            eligible_for_command_planning=False,
        )
        w=writer(
            execution_decision="DENY_BUSINESS_ACTION_EXECUTION",
            eligible_for_command_planning=False,
        )
        out=run(execution_persistence_attestation=p,execution_writer_attestation=w)
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn("EXECUTION_DECISION_NOT_AUTHORIZE",out["blockers"])

    def test_writer_must_bind_exact_receipt_and_record(self):
        for key,value,blocker in (
            ("receipt_digest",h("9"),"EXECUTION_WRITER_BINDING_MISMATCH:receipt_digest"),
            ("after_checkpoint_digest",h("9"),"EXECUTION_WRITER_BINDING_MISMATCH:after_checkpoint_digest"),
            ("execution_record_digest",h("9"),"EXECUTION_WRITER_BINDING_MISMATCH:execution_record_digest"),
        ):
            with self.subTest(key=key):
                out=run(execution_writer_attestation=writer(**{key:value}))
                self.assertEqual(out["state"],"BLOCKED")
                self.assertIn(blocker,out["blockers"])

    def test_preflight_lineage_digest_mismatch_blocks(self):
        out=run(execution_preflight=preflight(action_parameters_digest=h("9")))
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn(
            "EXECUTION_LINEAGE_DIGEST_MISMATCH:action_parameters_digest",
            out["blockers"],
        )

    def test_cross_customer_or_scope_blocks(self):
        out=run(execution_writer_attestation=writer(customer_id="other-customer"))
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn(
            "EXECUTION_WRITER_BINDING_MISMATCH:customer_id",
            out["blockers"],
        )
        bad_scope=dict(SCOPE);bad_scope["tenant_id"]="tenant-other"
        out=run(trusted_scope=bad_scope)
        self.assertEqual(out["state"],"BLOCKED")

    def test_each_action_family_maps_to_abstract_operation_only(self):
        cases={
            "RENEWAL":"CONTRACT_CONTINUITY",
            "RENEWAL_WITH_CHANGES":"CONTRACT_CHANGE",
            "NON_RENEWAL":"SERVICE_OFFBOARDING",
            "REMEDIATION":"SERVICE_REMEDIATION",
            "CAPACITY_RESCOPE":"CAPACITY_CHANGE",
            "REPRICING":"COMMERCIAL_PRICING_CHANGE",
            "INCIDENT_REMEDIATION":"INCIDENT_REMEDIATION",
            "SERVICE_PAUSE":"SERVICE_PAUSE",
            "SERVICE_TERMINATION":"SERVICE_TERMINATION",
        }
        self.assertEqual(cases,ACTION_OPERATION_KIND)

    def test_command_plan_contains_no_executable_provider_material(self):
        out=run()
        plan=out["command_plan"]
        banned_keys={
            "endpoint","url","method","headers","authorization","token","password",
            "credentials","body","payload","command","curl","powershell","script",
        }
        def walk(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    self.assertNotIn(str(key).lower(),banned_keys)
                    walk(item)
            elif isinstance(value,(list,tuple)):
                for item in value: walk(item)
        walk(plan)
        self.assertFalse(out["provider_operation_materialized"])
        self.assertFalse(out["provider_adapter_selected"])
        self.assertFalse(out["provider_endpoint_included"])
        self.assertFalse(out["http_method_included"])
        self.assertFalse(out["headers_included"])
        self.assertFalse(out["executable_payload_included"])
        self.assertFalse(out["credential_material_included"])
        self.assertFalse(out["secret_material_included"])
        self.assertFalse(out["execution_token_issued"])
        self.assertFalse(out["shell_command_generated"])

    def test_any_authority_flip_blocks(self):
        out=run(
            execution_persistence_attestation=persisted(
                billing_authorized=True
            )
        )
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn(
            "EXECUTION_PERSISTENCE_UNSAFE_FIELD:billing_authorized",
            out["blockers"],
        )

    def test_output_grants_no_execution_authority(self):
        out=run()
        for key in (
            "provider_operation_materialized","provider_adapter_selected",
            "provider_endpoint_included","http_method_included","headers_included",
            "executable_payload_included","credential_material_included",
            "secret_material_included","execution_token_issued",
            "shell_command_generated","execution_command_generated",
            "execution_command_executed",*AUTHORITY_FIELDS,
        ):
            self.assertFalse(out[key],key)

    def test_command_plan_digest_is_deterministic(self):
        self.assertEqual(run()["command_plan_digest"],run()["command_plan_digest"])


if __name__=="__main__":
    unittest.main()
