import unittest

from atlasquant_aion_studio import (
    approve_project,
    mark_published_from_evidence,
    new_content_project,
    publication_preflight,
    script_blueprint,
    studio_summary,
    upsert_project,
)


class AtlasQuantAionStudioTests(unittest.TestCase):
    def setUp(self):
        self.admin={"role":"ADMIN","username":"admin.test"}

    def test_new_project_does_not_publish(self):
        project=new_content_project(
            "Vídeo Radar",
            objective="Mostrar o Radar sem prometer lucro",
            platforms=["Instagram","TikTok"],
            duration_seconds=60,
        )
        self.assertEqual(project["status"],"IDEA")
        self.assertFalse(project["approval"]["approved"])
        self.assertFalse(project["publication"]["executed"])

    def test_script_blueprint_contains_truth_guard(self):
        project=new_content_project("Vídeo",duration_seconds=60)
        plan=script_blueprint(project)
        self.assertEqual(plan["total_seconds"],60)
        self.assertFalse(plan["executes_publish"])
        joined=" ".join(plan["truth_guard"]).lower()
        self.assertIn("rentabilidade",joined)
        self.assertIn("backtest",joined)

    def test_publication_requires_project_approval_flag_and_explicit_guardian_approval(self):
        project=new_content_project("Vídeo")
        blocked=publication_preflight(
            project,self.admin,
            feature_flags={"social_publish":True},
            approved=True,
        )
        self.assertFalse(blocked["allowed"])
        approved=approve_project(project,self.admin)
        no_click=publication_preflight(
            approved,self.admin,
            feature_flags={"social_publish":True},
            approved=False,
        )
        self.assertFalse(no_click["allowed"])
        ready=publication_preflight(
            approved,self.admin,
            feature_flags={"social_publish":True},
            approved=True,
        )
        self.assertTrue(ready["allowed"])
        self.assertFalse(ready["executes_publish"])

    def test_mark_published_requires_confirmed_connector_evidence(self):
        project=approve_project(new_content_project("Vídeo"),self.admin)
        with self.assertRaises(ValueError):
            mark_published_from_evidence(project,{"confirmed":True,"source":"instagram"})
        live=mark_published_from_evidence(
            project,
            {
                "confirmed":True,
                "source":"instagram_connector",
                "external_id":"post-123",
                "url":"https://example.invalid/post-123",
            },
        )
        self.assertEqual(live["status"],"PUBLISHED")
        self.assertTrue(live["publication"]["executed"])

    def test_summary_and_upsert(self):
        a=new_content_project("A",created_at="2026-09-23T20:00:00Z")
        b=approve_project(new_content_project("B",created_at="2026-09-23T20:01:00Z"),self.admin)
        rows=upsert_project([],a)
        rows=upsert_project(rows,b)
        summary=studio_summary(rows)
        self.assertEqual(summary["total"],2)
        self.assertEqual(summary["approved"],1)


if __name__=="__main__":
    unittest.main()
