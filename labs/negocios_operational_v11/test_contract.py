"""Synthetic V1.1 acceptance tests. No network, CRM app, payments, real people or supplier."""
import unittest
from copy import deepcopy
try:
    from .contract import (review_record, advance_stage, render_proposal, privacy_summary,
                           request_external_action, ContractError, DISCLAIMER, CHECK_ITEMS)
except ImportError:
    from contract import (review_record, advance_stage, render_proposal, privacy_summary,
                          request_external_action, ContractError, DISCLAIMER, CHECK_ITEMS)

NOW = "2026-10-16T15:30:00-03:00"
CUTOFF = "2026-10-16T08:00:00-03:00"


def fixture():
    return {
        "tenant_id": "TENANT-FICTICIO-01", "case_id": "OF-TESTE-017", "stage": "CONSULTA",
        "state": "ABERTO", "updated_at": "2026-10-16T12:00:00-03:00",
        "owner_id": "FUNC-FICTICIO-A", "next_action": "Conferir fornecedor (simulado)",
        "next_due_at": "2026-10-17T09:00:00-03:00",
        "contact_preference": "RECUSOU", "purpose_ref": "SIM-FINALIDADE-001",
        "legal_basis_ref": "SIM-BASE-001", "retention_policy_ref": "SIM-RETENCAO-001",
        "qualification": {"need_identified": False, "can_serve": False,
                          "interest_to_proceed": False, "decision_path_documented": False},
        "stock": {"state": "NAO_VERIFICADO"}, "payment": {"state": "NAO_VERIFICADO"},
        "privacy_checklist": dict.fromkeys(CHECK_ITEMS, True),
    }


def codes(record):
    return set(review_record(record, now=NOW, review_cutoff=CUTOFF)["issues"])


def req_err(code, fn, *args, **kwargs):
    with unittest.TestCase().assertRaises(ContractError) as result:
        fn(*args, **kwargs)
    assert result.exception.code == code, (result.exception.code, code)


class TestNegociosV11(unittest.TestCase):
    def test_01_unverified_stock_is_not_available(self):
        self.assertIn("STOCK_NOT_VERIFIED", codes(fixture()))
    def test_02_unverified_payment_is_not_paid(self):
        self.assertIn("PAYMENT_NOT_VERIFIED", codes(fixture()))
    def test_03_sale_status_does_not_change_payment(self):
        x = fixture(); x["state"] = "GANHO"
        self.assertIn("PAYMENT_NOT_VERIFIED", codes(x))
    def test_04_stock_confirm_without_provenance_warns(self):
        x = fixture(); x["stock"] = {"state": "DISPONIVEL"}
        self.assertIn("STOCK_EVIDENCE_MISSING", codes(x))
    def test_05_stock_fake_provenance_tracks_but_proves_nothing_external(self):
        x = fixture(); x["stock"] = {"state": "RESERVADO", "checked_by": "FUNC-FICTICIO-A",
            "checked_at": NOW, "source_ref": "SIM-ESTOQUE-A"}
        output=review_record(x,now=NOW,review_cutoff=CUTOFF)
        self.assertNotIn("STOCK_EVIDENCE_MISSING", output["issues"])
        self.assertFalse(output["stock_availability_proven"])
    def test_06_invalid_source_is_rejected(self):
        x=fixture(); x["stock"]={"state":"DISPONIVEL", "checked_by":"A", "checked_at":NOW,"source_ref":"PROVIDER-REAL"}
        self.assertIn("STOCK_EVIDENCE_MISSING", codes(x))
    def test_07_future_stock_proof_warns(self):
        x=fixture(); x["stock"]={"state":"DISPONIVEL", "checked_by":"A", "checked_at":"2027-01-01T00:00:00-03:00","source_ref":"SIM-A"}
        self.assertIn("STOCK_EVIDENCE_MISSING", codes(x))
    def test_08_payment_confirm_without_source_warns(self):
        x=fixture(); x["payment"]={"state":"CONFIRMADO"}
        self.assertIn("PAYMENT_EVIDENCE_MISSING", codes(x))
    def test_09_synthetic_payment_confirmation_is_not_external_bank_proof(self):
        x=fixture(); x["payment"]={"state":"CONFIRMADO","checked_by":"TESOURARIA-FICTICIA","checked_at":NOW,"source_ref":"SIM-BANCO-01"}
        out=review_record(x,now=NOW,review_cutoff=CUTOFF)
        self.assertFalse(out["bank_receipt_proven"])
        self.assertIn("FINANCIAL_RECONCILIATION_NOT_VERIFIED_EXTERNALLY",out["issues"])
    def test_10_unrecognized_stock_state_denied(self):
        x=fixture();x["stock"]={"state":"PRODUTO_GRATIS"};req_err("STOCK_STATE_INVALID",codes,x)
    def test_11_without_owner_flag(self):
        x=fixture();x["owner_id"]="";self.assertIn("OWNER_MISSING",codes(x))
    def test_12_without_next_step_or_reason_flag(self):
        x=fixture();x["next_action"]="";self.assertIn("NEXT_ACTION_OR_PAUSE_MISSING",codes(x))
    def test_13_paused_reason_is_valid_alternative(self):
        x=fixture();x["state"]="PAUSADO";x["next_action"]="";x["pause_reason"]="SIM-PARADO-A-PEDIDO"
        self.assertNotIn("NEXT_ACTION_OR_PAUSE_MISSING",codes(x))
    def test_14_missing_due_date_flag(self):
        x=fixture();x.pop("next_due_at");self.assertIn("NEXT_DUE_MISSING",codes(x))
    def test_15_overdue_is_warning_not_send(self):
        x=fixture();x["next_due_at"]="2026-10-15T09:00:00-03:00"
        out=review_record(x,now=NOW,review_cutoff=CUTOFF)
        self.assertIn("FOLLOW_UP_OVERDUE",out["issues"]);self.assertFalse(out["send_approved"])
    def test_16_stale_record_flagged(self):
        x=fixture();x["updated_at"]="2026-10-15T09:00:00-03:00";self.assertIn("DAILY_REVIEW_REQUIRED",codes(x))
    def test_17_no_timezone_denied(self):
        x=fixture();x["updated_at"]="2026-10-16T09:00:00";req_err("TIMESTAMP_TIMEZONE_REQUIRED",codes,x)
    def test_18_future_update_denied(self):
        x=fixture();x["updated_at"]="2027-10-16T12:00:00-03:00";req_err("UPDATED_IN_FUTURE",codes,x)
    def test_19_cross_tenant_stage_denied(self):
        req_err("TENANT_ACCESS_DENIED",advance_stage,fixture(),target="LEAD_NAO_QUALIFICADO",actor_tenant="TENANT-FICTICIO-02")
    def test_20_cannot_skip_stages(self):
        req_err("STAGE_SKIP_REVIEW_REQUIRED",advance_stage,fixture(),target="OPORTUNIDADE",actor_tenant="TENANT-FICTICIO-01")
    def test_21_qualification_not_automatic(self):
        x=fixture();x["stage"]="LEAD_NAO_QUALIFICADO"
        req_err("QUALIFICATION_UNVERIFIED",advance_stage,x,target="LEAD_QUALIFICADO",actor_tenant=x["tenant_id"])
    def test_22_qualified_with_evidence_shape(self):
        x=fixture();x["stage"]="LEAD_NAO_QUALIFICADO";x["qualification"].update(need_identified=True,can_serve=True,interest_to_proceed=True)
        self.assertEqual("LEAD_QUALIFICADO",advance_stage(x,target="LEAD_QUALIFICADO",actor_tenant=x["tenant_id"]))
    def test_23_opportunity_needs_decision_path(self):
        x=fixture();x["stage"]="LEAD_QUALIFICADO";x["qualification"].update(need_identified=True,can_serve=True,interest_to_proceed=True)
        req_err("OPPORTUNITY_REQUIRED_DATA_MISSING",advance_stage,x,target="OPORTUNIDADE",actor_tenant=x["tenant_id"])
    def test_24_no_silent_stage_regression(self):
        x=fixture();x["stage"]="OPORTUNIDADE"
        req_err("STAGE_REGRESSION_REVIEW_REQUIRED",advance_stage,x,target="CONSULTA",actor_tenant=x["tenant_id"])
    def test_25_qualified_state_unverified_warn(self):
        x=fixture();x["stage"]="LEAD_QUALIFICADO";self.assertIn("QUALIFICATION_UNVERIFIED",codes(x))
    def test_26_proposal_mandatory_disclaimer(self):
        text=render_proposal(scope="Diagnostico ficticio",price_label="R$ 0 (simulacao)")
        self.assertIn(DISCLAIMER,text);self.assertIn("NAO ENVIADO",text)
    def test_27_blank_proposal_refused(self):
        req_err("PROPOSAL_SCOPE_OR_PRICE_REQUIRED",render_proposal,scope="",price_label="R$ 9")
    def test_28_optout_never_approves_send(self):
        x=fixture(); self.assertIn("OUTBOUND_CONTACT_NOT_AUTHORIZED",codes(x));self.assertFalse(review_record(x,now=NOW,review_cutoff=CUTOFF)["send_approved"])
    def test_29_missing_privacy_purpose_warn(self):
        x=fixture();x.pop("purpose_ref");self.assertIn("PRIVACY_PURPOSE_REF_MISSING",codes(x))
    def test_30_missing_legal_basis_warn(self):
        x=fixture();x.pop("legal_basis_ref");self.assertIn("PRIVACY_LEGAL_BASIS_REF_MISSING",codes(x))
    def test_31_retention_missing_warn(self):
        x=fixture();x.pop("retention_policy_ref");self.assertIn("PRIVACY_RETENTION_POLICY_REF_MISSING",codes(x))
    def test_32_checklist_does_not_certify_lgpd(self):
        x=fixture();out=review_record(x,now=NOW,review_cutoff=CUTOFF)
        self.assertFalse(out["lgpd_compliance_certified"])
        self.assertEqual("REVISAO_HUMANA_NECESSARIA",privacy_summary(x["privacy_checklist"]))
    def test_33_missing_check_item_warn(self):
        x=fixture();x["privacy_checklist"]["incidentes_escalados"]=False
        self.assertIn("PRIVACY_CHECKLIST_PENDING",codes(x))
    def test_34_no_external_actions(self):
        for item in ("SEND","PAY","CHARGE","RESERVE_STOCK","IMPORT_PII","ENABLE_WORKER","DEPLOY"):
            with self.subTest(item=item):req_err("HARD_NO_GO_EXTERNAL_ACTION",request_external_action,item)
    def test_35_unknown_actions_also_denied(self):
        req_err("OFFLINE_SPEC_ONLY",request_external_action,"X-NOVO")
    def test_36_review_is_pure(self):
        x=fixture();prior=deepcopy(x);review_record(x,now=NOW,review_cutoff=CUTOFF);self.assertEqual(prior,x)
    def test_37_closed_case_not_auto_reopened(self):
        x=fixture();x["state"]="CONCLUIDO";x.pop("owner_id");x.pop("next_action")
        self.assertNotIn("OWNER_MISSING",codes(x))
    def test_39_four_requested_two_seen_is_insufficient(self):
        x=fixture();x["requested_qty"]=4
        x["stock"]={"state":"DISPONIVEL", "checked_by":"FUNC-FICTICIO-A", "checked_at":NOW,
                    "source_ref":"SIM-ESTOQUE-A", "observed_qty":2}
        self.assertIn("STOCK_INSUFFICIENT_FOR_REQUEST",codes(x))
    def test_40_available_without_quantities_is_not_sufficient(self):
        x=fixture();x["stock"]={"state":"DISPONIVEL","checked_by":"A","checked_at":NOW,"source_ref":"SIM-A"}
        self.assertIn("STOCK_REQUESTED_QUANTITY_MISSING",codes(x))
        self.assertIn("STOCK_OBSERVED_QUANTITY_MISSING",codes(x))
    def test_41_reservation_needs_separate_provenance(self):
        x=fixture();x["requested_qty"]=4
        x["stock"]={"state":"RESERVADO","checked_by":"A","checked_at":NOW,"source_ref":"SIM-A","observed_qty":4}
        self.assertIn("STOCK_RESERVATION_NOT_DOCUMENTED",codes(x))
    def test_42_stock_na_not_allowed_for_product_with_stock_required(self):
        x=fixture();x["requires_stock"]=True;x["stock"]={"state":"NAO_APLICAVEL"}
        self.assertIn("STOCK_APPLICABILITY_CONFLICT",codes(x))
    def test_43_partial_amount_below_total_does_not_become_paid(self):
        x=fixture();x["payment"]={"state":"PARCIAL","checked_by":"A","checked_at":NOW,"source_ref":"SIM-A",
                                 "amount_due_cents":100000, "amount_received_cents":50000}
        self.assertIn("FINANCIAL_RECONCILIATION_NOT_VERIFIED_EXTERNALLY",codes(x))
        self.assertNotIn("PAYMENT_PARTIAL_BUT_AMOUNT_FULL",codes(x))
    def test_44_confirmed_but_partial_value_warns(self):
        x=fixture();x["payment"]={"state":"CONFIRMADO","checked_by":"A","checked_at":NOW,"source_ref":"SIM-A",
                                 "amount_due_cents":100000, "amount_received_cents":50000}
        self.assertIn("PAYMENT_CONFIRMED_BUT_AMOUNT_SHORT",codes(x))
    def test_45_no_amount_no_paid_proof(self):
        x=fixture();x["payment"]={"state":"CONFIRMADO","checked_by":"A","checked_at":NOW,"source_ref":"SIM-A"}
        self.assertIn("PAYMENT_AMOUNT_UNVERIFIED",codes(x))
    def test_38_no_timestamp_cutoff_future(self):
        req_err("CUTOFF_IN_FUTURE",review_record,fixture(),now=NOW,review_cutoff="2027-01-01T00:00:00-03:00")


if __name__ == "__main__":
    unittest.main()
