"""P0 RED-first: checkpoint recovery review must not trust forged trace summaries.

The original local trace uses build_local_traceability, default_checkpoint,
and the real recovery_preflight. Mutations are local data only: no GitHub
restore, runtime save, Worker, external provider, HTTP or side effects.
This is only an administrative review gate, not an H0 independent witness.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from test_atlasquant_aion_recovery_traceability_gate import _current, _candidate, _trace
from atlasquant_aion_recovery_traceability_gate import recovery_traceability_readiness


class CheckpointRecoveryTraceShapeCoherenceLab(unittest.TestCase):
    def review(self, mutation=None):
        trace=_trace()
        if mutation is not None:
            mutation(trace)
        return recovery_traceability_readiness(_current(),_candidate(),trace)

    def denied(self, mutation, code):
        result=self.review(mutation)
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn(code,result["blockers"])
        for field in ("recovery_authorized","automatic_restore","automatic_retry",
                      "checkpoint_saved","external_action_executed","network_called"):
            self.assertIs(result[field],False)

    def test_01_genuine_local_trace_remains_review_only(self):
        result=self.review()
        self.assertEqual(result["state"],"READY_FOR_ADMIN_REVIEW")
        self.assertFalse(result["recovery_authorized"])
        self.assertFalse(result["automatic_retry"])
        self.assertFalse(result["automatic_restore"])

    def test_02_forged_count_with_empty_records_denied(self):
        self.denied(lambda d:d.update({"records":[],"record_count":1}),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_03_bool_record_count_not_an_integer_denied(self):
        self.denied(lambda d:d.__setitem__("record_count",True),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_04_large_string_record_count_does_not_throw(self):
        self.denied(lambda d:d.__setitem__("record_count","9"*10000),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_05_null_record_count_not_readiness(self):
        self.denied(lambda d:d.__setitem__("record_count",None),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_06_non_list_records_are_rejected(self):
        self.denied(lambda d:d.__setitem__("records",{"authority":False}),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_07_malformed_security_string_does_not_throw(self):
        self.denied(lambda d:d.__setitem__("security","SAFE_LOCAL"),"TRACEABILITY_SECURITY_BLOCK")

    def test_08_malformed_security_list_of_pairs_is_not_accepted(self):
        self.denied(lambda d:d.__setitem__("security",[("state","SAFE_LOCAL"),("external_side_effects",False)]),"TRACEABILITY_SECURITY_BLOCK")

    def test_09_network_called_true_blocks_although_state_claims_safe(self):
        self.denied(lambda d:d["security"].__setitem__("network_called",True),"TRACEABILITY_SECURITY_BLOCK")

    def test_10_connector_called_true_blocks(self):
        self.denied(lambda d:d["security"].__setitem__("connector_called",True),"TRACEABILITY_SECURITY_BLOCK")

    def test_11_security_issues_cannot_coexist_with_safe_label(self):
        self.denied(lambda d:d["security"].__setitem__("issues",["FORGED"]),"TRACEABILITY_SECURITY_BLOCK")

    def test_12_execution_refs_not_present_in_records_denied(self):
        self.denied(lambda d:d.__setitem__("execution_refs",["LCL-EV-FORGED99999"]),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_13_string_execution_refs_not_valid_sequence_denied(self):
        self.denied(lambda d:d.__setitem__("execution_refs","LCL-EV-FORGED"),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_14_source_keys_mismatch_actual_records_denied(self):
        self.denied(lambda d:d.__setitem__("source_keys",["checkpoint_master","operating_tasks"]),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_15_checkpoint_key_without_actual_checkpoint_tool_denied(self):
        self.denied(lambda d:d["records"][0].__setitem__("tool_id","aion.tasks.summary"),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_16_false_local_only_record_denied(self):
        self.denied(lambda d:d["records"][0].__setitem__("local_only",False),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_17_unconfirmed_execution_referenced_as_confirmed_denied(self):
        self.denied(lambda d:d["records"][0].__setitem__("execution_confirmed",False),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_18_record_claiming_security_block_with_safe_envelope_denied(self):
        self.denied(lambda d:d["records"][0].__setitem__("security_state","BLOCK"),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_19_record_authority_true_always_denied(self):
        self.denied(lambda d:d["records"][0].__setitem__("authority",True),"TRACEABILITY_AUTHORITY_FORBIDDEN")

    def test_20_conflict_in_record_with_cleared_top_level_refs_denied(self):
        self.denied(lambda d:d["records"][0].__setitem__("conflicts",["SPLIT_BRAIN"]),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_21_content_ref_forged_nonexistent_denied(self):
        self.denied(lambda d:d.__setitem__("confirmed_content_refs",["LCL-EV-NOTHERE000"]),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_22_raw_result_included_true_blocks_review(self):
        self.denied(lambda d:d.__setitem__("raw_result_included",True),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_23_trace_authority_claim_blocks_readiness(self):
        self.denied(lambda d:d.__setitem__("tool_output_is_authority",True),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_24_duplicated_execution_ref_in_projection_denied(self):
        self.denied(lambda d:d["execution_refs"].append(d["execution_refs"][0]),"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_25_forged_checkpoint_source_key_on_record_denied(self):
        def alter(trace):
            trace["records"][0]["source_key"]="operating_tasks"
            # The top-level caller can lie about source_keys too.
        self.denied(alter,"TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    def test_26_null_trace_is_never_a_ready_review(self):
        result=recovery_traceability_readiness(_current(),_candidate(),None)
        self.assertEqual(result["state"],"BLOCKED")
        self.assertFalse(result["recovery_authorized"])


if __name__=="__main__":
    unittest.main()
