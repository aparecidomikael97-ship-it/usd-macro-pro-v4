import unittest

from atlasquant_aion_status_board import build_master_status_board, status_rows


class AtlasQuantAionMasterStatusBoardTests(unittest.TestCase):
    def base(self, **kwargs):
        payload={
            "checkpoint":{
                "operating":{"tasks":[]},
                "entitlements":{"records":[]},
            },
            "runtime_result":{"status":"CONFIRMED"},
            "provider":{"state":"ZERO_COST_LOCAL"},
            "feature_flags":{},
            "system_context":{
                "truth_state":"CONFIRMED",
                "source_build":"abc123",
            },
            "market_context":{"fresh_confirmed":False,"summary":""},
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

    def test_status_rows_are_presentation_only(self):
        board=self.base()
        rows=status_rows(board)
        self.assertTrue(rows)
        self.assertIn("Estado",rows[0])
        self.assertFalse(board["automatic_external_actions"])


if __name__=="__main__":
    unittest.main()
