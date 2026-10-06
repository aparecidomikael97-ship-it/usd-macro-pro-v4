from __future__ import annotations

import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from atlasquant_aion_b2b_terminal_certificate_panel_component_offline_v1 import (
    FALSE_FIELDS,
    FORBIDDEN_HTML_TOKENS,
    REQUIRED_UI_SECTIONS,
    render_terminal_certificate_panel_offline,
)
from atlasquant_aion_b2b_terminal_certificate_read_model_runtime_projection_offline_v1 import (
    project_terminal_certificate_read_model_offline,
)
from atlasquant_aion_b2b_terminal_certificate_read_model_store_projection_offline_v1 import (
    DurableTerminalCertificateReadModelSource,
)
from atlasquant_aion_b2b_terminal_certificate_read_model_ui_runtime_binding_offline_v1 import (
    build_terminal_certificate_panel_view_model_offline,
)
from atlasquant_aion_b2b_terminal_certificate_runtime_reader_offline_v1 import (
    read_terminal_certificate_offline,
)
from atlasquant_aion_durable_execution_kernel import DurableExecutionStore
from test_atlasquant_aion_b2b_execution_terminal_certificate_durable_store_extension_offline_v1 import (
    build_full_chain,
)


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.sections = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        data = dict(attrs)
        if tag == "section" and data.get("data-section"):
            self.sections.append(data["data-section"])


class TerminalCertificatePanelComponentOfflineV1Tests(unittest.TestCase):
    def make_view_model(self, *, observed_at="2026-10-06T13:33:00Z", max_age=120):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = DurableExecutionStore(Path(tmp.name) / "execution.sqlite3")
        execution_id = build_full_chain(store)
        source = DurableTerminalCertificateReadModelSource(store)
        runtime = read_terminal_certificate_offline(
            read_model_source=source,
            execution_id=execution_id,
            owner_id="owner-1",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            observed_at=observed_at,
            max_age_seconds=max_age,
        )
        projection = project_terminal_certificate_read_model_offline(
            runtime_reader_result=runtime,
            owner_id="owner-1",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
        )
        return build_terminal_certificate_panel_view_model_offline(
            read_model_projection=projection,
        )

    def assert_no_authority(self, out):
        for key in FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_verified_component_renders_static_html_only(self):
        out = render_terminal_certificate_panel_offline(
            panel_view_model=self.make_view_model(),
        )
        self.assertEqual(out["state"], "VERIFIED")
        self.assertTrue(out["html_rendered"])
        self.assertTrue(out["static_only"])
        self.assertEqual(out["section_count"], 10)
        self.assertIn("Evidência verificada", out["html"])
        self.assertIn("Não autoriza execução", out["html"])
        parser = Tags()
        parser.feed(out["html"])
        self.assertEqual(tuple(parser.sections), REQUIRED_UI_SECTIONS)
        for tag in ("button", "form", "input", "select", "textarea", "script", "iframe", "a"):
            self.assertNotIn(tag, parser.tags)
        self.assert_no_authority(out)

    def test_all_forbidden_interactive_tokens_are_absent(self):
        out = render_terminal_certificate_panel_offline(
            panel_view_model=self.make_view_model(),
        )
        lower = out["html"].lower()
        for token in FORBIDDEN_HTML_TOKENS:
            self.assertNotIn(token, lower)
        self.assert_no_authority(out)

    def test_html_escapes_untrusted_text(self):
        model = self.make_view_model()
        model["title"] = '<img src=x onerror="alert(1)">'
        model["sections"]["scope_boundary"]["tenant_id"] = '<script>alert(1)</script>'
        out = render_terminal_certificate_panel_offline(panel_view_model=model)
        self.assertEqual(out["state"], "VERIFIED")
        self.assertNotIn("<script>", out["html"])
        self.assertNotIn("<img ", out["html"])
        self.assertIn("&lt;script&gt;", out["html"])
        self.assertIn("&lt;img", out["html"])
        self.assert_no_authority(out)

    def test_stale_component_is_refresh_required(self):
        out = render_terminal_certificate_panel_offline(
            panel_view_model=self.make_view_model(
                observed_at="2026-10-06T13:40:00Z",
                max_age=120,
            ),
        )
        self.assertEqual(out["state"], "STALE")
        self.assertIn("Evidência desatualizada", out["html"])
        self.assertIn("Atualização da evidência é necessária", out["html"])
        self.assertNotIn("Evidência verificada</strong>", out["html"])
        self.assert_no_authority(out)

    def test_unknown_state_does_not_render_html(self):
        model = self.make_view_model()
        model["state"] = "MAYBE"
        out = render_terminal_certificate_panel_offline(panel_view_model=model)
        self.assertEqual(out["state"], "MISMATCH")
        self.assertFalse(out["html_rendered"])
        self.assertEqual(out["html"], "")
        self.assertEqual(out["error_code"], "PANEL_VIEW_MODEL_STATE_UNKNOWN")
        self.assert_no_authority(out)

    def test_action_controls_flip_blocks_render(self):
        model = self.make_view_model()
        model["action_controls_present"] = True
        out = render_terminal_certificate_panel_offline(panel_view_model=model)
        self.assertFalse(out["html_rendered"])
        self.assertEqual(
            out["error_code"],
            "PANEL_VIEW_MODEL_ACTION_CONTROLS_FORBIDDEN",
        )
        self.assert_no_authority(out)

    def test_nonempty_controls_block_render(self):
        model = self.make_view_model()
        model["controls"] = ("retry",)
        out = render_terminal_certificate_panel_offline(panel_view_model=model)
        self.assertFalse(out["html_rendered"])
        self.assertEqual(out["error_code"], "PANEL_VIEW_MODEL_CONTROLS_MUST_BE_EMPTY")
        self.assert_no_authority(out)

    def test_authority_flip_blocks_render(self):
        model = self.make_view_model()
        model["retry_authorized"] = True
        out = render_terminal_certificate_panel_offline(panel_view_model=model)
        self.assertFalse(out["html_rendered"])
        self.assertTrue(
            out["error_code"].startswith("PANEL_VIEW_MODEL_UNSAFE_AUTHORITY_FIELD:")
        )
        self.assert_no_authority(out)

    def test_section_order_must_match_contract_exactly(self):
        model = self.make_view_model()
        model["sections"] = dict(reversed(list(model["sections"].items())))
        out = render_terminal_certificate_panel_offline(panel_view_model=model)
        self.assertFalse(out["html_rendered"])
        self.assertEqual(out["error_code"], "PANEL_SECTION_ORDER_MISMATCH")
        self.assert_no_authority(out)

    def test_badge_cannot_claim_verified_for_stale_state(self):
        model = self.make_view_model(
            observed_at="2026-10-06T13:40:00Z",
            max_age=120,
        )
        model["badge"]["state"] = "VERIFIED"
        out = render_terminal_certificate_panel_offline(panel_view_model=model)
        self.assertFalse(out["html_rendered"])
        self.assertEqual(out["error_code"], "PANEL_BADGE_STATE_MISMATCH")
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
