import json
import unittest

from atlasquant_render_deploy_hook import deploy_hook_status


HOOK="https://example.invalid/deploy-hook"


class AtlasQuantRenderDeployHookTests(unittest.TestCase):
    def test_missing_variable_is_not_configured_and_does_not_dispatch(self):
        status=deploy_hook_status({}, human_approved=True)
        self.assertEqual(status["state"],"NOT_CONFIGURED")
        self.assertFalse(status["configured"])
        self.assertFalse(status["authorized"])
        self.assertFalse(status["executes_request"])
        self.assertFalse(status["dispatches_hook"])

    def test_presence_without_exact_approval_does_not_authorize(self):
        for flag in ("true","yes",1,None,"false"):
            status=deploy_hook_status(
                {"RENDER_DEPLOY_HOOK_URL":HOOK},
                human_approved=flag,
            )
            self.assertEqual(status["state"],"APPROVAL_REQUIRED", flag)
            self.assertTrue(status["configured"])
            self.assertFalse(status["authorized"])
            self.assertFalse(status["dispatches_hook"])

    def test_explicit_approval_still_does_not_send(self):
        status=deploy_hook_status(
            {"RENDER_DEPLOY_HOOK_URL":HOOK},
            human_approved=True,
        )
        self.assertEqual(status["state"],"APPROVED_NOT_SENT")
        self.assertTrue(status["authorized"])
        self.assertFalse(status["executes_request"])
        self.assertFalse(status["dispatches_hook"])
        rendered=json.dumps(status)
        self.assertNotIn(HOOK, rendered)
        self.assertNotIn("example.invalid", rendered)
        self.assertFalse(status["hook_url_included"])

    def test_non_https_url_is_not_configured(self):
        status=deploy_hook_status(
            {"RENDER_DEPLOY_HOOK_URL":"http://example.invalid/hook"},
            human_approved=True,
        )
        self.assertEqual(status["state"],"NOT_CONFIGURED")
        self.assertFalse(status["authorized"])


if __name__=="__main__":
    unittest.main()
