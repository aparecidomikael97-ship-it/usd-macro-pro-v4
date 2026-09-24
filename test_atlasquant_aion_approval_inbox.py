import unittest

from atlasquant_aion_approval_inbox import collect_approval_inbox, approval_rows
from atlasquant_aion_operations import new_task
from atlasquant_aion_studio import new_content_project
from atlasquant_aion_business import new_product_candidate
from atlasquant_aion_promotions import new_campaign
from atlasquant_aion_entitlements import new_entitlement_request


class AtlasQuantAionApprovalInboxTests(unittest.TestCase):
    def checkpoint(self):
        task=new_task(
            "Publicar conteúdo",
            domain="studio",
            priority="P0",
            action="publish_social",
            created_at="2026-09-24T12:00:00Z",
        )
        task["status"]="WAITING_APPROVAL"
        task["approval"]["required"]=True

        studio=new_content_project(
            "Vídeo AION",
            created_at="2026-09-24T12:01:00Z",
        )
        studio["status"]="REVIEW"

        business=new_product_candidate(
            "Produto teste",
            created_at="2026-09-24T12:02:00Z",
        )
        business["status"]="VALIDATE"

        promo,_=new_campaign(
            "Semana teste",
            created_at="2026-09-24T12:03:00Z",
        )

        entitlement=new_entitlement_request(
            "cliente.01",
            created_at="2026-09-24T12:04:00Z",
        )

        return {
            "operating":{"tasks":[task]},
            "studio":{"projects":[studio]},
            "business":{"products":[business]},
            "promotions":{"campaigns":[promo],"redemptions":[]},
            "entitlements":{"records":[entitlement]},
        }

    def test_collects_only_records_that_genuinely_need_admin_review(self):
        inbox=collect_approval_inbox(self.checkpoint())
        self.assertEqual(inbox["total"],5)
        self.assertEqual(inbox["by_kind"]["TASK"],1)
        self.assertEqual(inbox["by_kind"]["STUDIO"],1)
        self.assertEqual(inbox["by_kind"]["BUSINESS"],1)
        self.assertEqual(inbox["by_kind"]["PROMOTION"],1)
        self.assertEqual(inbox["by_kind"]["ENTITLEMENT"],1)
        self.assertTrue(inbox["has_pending"])
        self.assertFalse(inbox["automatic_approval"])
        self.assertFalse(inbox["executes_action"])
        self.assertFalse(inbox["real_orders_enabled"])

    def test_priority_sort_puts_p0_task_first(self):
        inbox=collect_approval_inbox(self.checkpoint())
        self.assertEqual(inbox["items"][0]["kind"],"TASK")
        self.assertEqual(inbox["items"][0]["priority"],"P0")

    def test_ideas_research_and_approved_records_are_not_fake_pending_approvals(self):
        cp=self.checkpoint()
        cp["studio"]["projects"][0]["status"]="IDEA"
        cp["business"]["products"][0]["status"]="RESEARCH"
        cp["promotions"]["campaigns"][0]["status"]="APPROVED"
        cp["promotions"]["campaigns"][0]["approval"]["approved"]=True
        cp["entitlements"]["records"][0]["status"]="APPROVED"
        cp["entitlements"]["records"][0]["approval"]["approved"]=True
        cp["operating"]["tasks"][0]["status"]="TODO"
        cp["operating"]["tasks"][0]["approval"]["required"]=False
        inbox=collect_approval_inbox(cp)
        self.assertEqual(inbox["total"],0)
        self.assertFalse(inbox["has_pending"])

    def test_entitlement_reason_never_claims_access_was_granted(self):
        inbox=collect_approval_inbox(self.checkpoint())
        item=next(x for x in inbox["items"] if x["kind"]=="ENTITLEMENT")
        self.assertIn("não altera conta nem concede acesso automaticamente",item["reason"].lower())
        self.assertFalse(item["approved"])

    def test_presentation_rows_do_not_add_actions(self):
        inbox=collect_approval_inbox(self.checkpoint())
        rows=approval_rows(inbox)
        self.assertEqual(len(rows),5)
        self.assertIn("Motivo",rows[0])
        self.assertNotIn("Aprovar",rows[0])


if __name__=="__main__":
    unittest.main()
