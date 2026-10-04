"""Offline contracts for server-held selection; no database or external login."""
import inspect
import unittest
from unittest.mock import patch

import atlasquant_aion_library_server_selection as module
from aion_core.library_authorization import AuthorizationDenied
from atlasquant_aion_library_postgres_preview import LibraryPanelPreview


class FakeServerAssembly:
    def __init__(self):
        self.calls = []
        self.effect = None

    def read_preview(self, *, tenant_id, domain_id, entry_id):
        self.calls.append((tenant_id, domain_id, entry_id))
        if self.effect:
            return self.effect()
        return LibraryPanelPreview(entry_id, 1, "APPROVED_FOR_INDEXING", True)


class TrustedSelectionContracts(unittest.TestCase):
    def setUp(self):
        self.server = FakeServerAssembly()
        self.selected = [("T-A", "LIBRARY", "LIB-123")]
        patcher = patch.object(module, "SandboxLibraryServerReadAssembly", FakeServerAssembly)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.reader = module.SandboxServerSelectedRead(
            assembly=self.server, trusted_selection_provider=lambda: self.selected[0])

    def test_no_caller_scope_parameters(self):
        self.assertEqual(tuple(inspect.signature(self.reader.read_selected).parameters), ())

    def test_only_selected_metadata_returned(self):
        self.assertEqual(self.reader.read_selected(),
                         LibraryPanelPreview("LIB-123", 1, "APPROVED_FOR_INDEXING", True))
        self.assertEqual(self.server.calls, [("T-A", "LIBRARY", "LIB-123")])

    def test_review_state_stays_bounded_by_underlying_access_control(self):
        self.server.effect = lambda: LibraryPanelPreview("LIB-123", 1, "METADATA_REVIEW", True)
        self.assertEqual(self.reader.read_selected().state, "METADATA_REVIEW")

    def test_invalid_constructor_no_assembly(self):
        with self.assertRaises(AuthorizationDenied):
            module.SandboxServerSelectedRead(assembly=object(),
                trusted_selection_provider=lambda: ("T-A", "LIBRARY", "LIB-123"))

    def test_invalid_constructor_no_provider(self):
        with self.assertRaises(AuthorizationDenied):
            module.SandboxServerSelectedRead(assembly=self.server, trusted_selection_provider=None)

    def test_client_like_dictionary_not_selection(self):
        self.selected[0] = {"tenant_id": "T-A", "entry_id": "LIB-123"}
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()
        self.assertEqual(self.server.calls, [])

    def test_invalid_scope_and_type_fail_before_read(self):
        cases = [("T-A", "LIBRARY", "../secret"), ("", "LIBRARY", "LIB-123"),
                 ("T-A ", "LIBRARY", "LIB-123"), ("T-A", "LIBRARY", "x"*29),
                 ("T-A", "LIBRARY", True), ["T-A", "LIBRARY", "LIB-123"],
                 ("T-A", "LIBRARY"), ("T-A", "LIBRARY", "LIB-123", "OTHER")]
        for case in cases:
            with self.subTest(case=case):
                self.selected[0] = case
                with self.assertRaises(AuthorizationDenied): self.reader.read_selected()
        self.assertEqual(self.server.calls, [])

    def test_provider_failure_closed(self):
        r = module.SandboxServerSelectedRead(
            assembly=self.server, trusted_selection_provider=lambda: 1/0)
        with self.assertRaises(AuthorizationDenied) as ctx: r.read_selected()
        self.assertEqual(str(ctx.exception), "sandbox Library selection unavailable")

    def test_change_during_read_denied(self):
        def changed():
            self.selected[0] = ("T-B", "LIBRARY", "LIB-123")
            return LibraryPanelPreview("LIB-123", 1, "APPROVED_FOR_INDEXING", True)
        self.server.effect = changed
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()
        self.assertEqual(len(self.server.calls), 1)

    def test_inconsistent_entry_ref_denied(self):
        self.server.effect = lambda: LibraryPanelPreview("OTHER", 1, "APPROVED_FOR_INDEXING", True)
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()

    def test_no_success_without_integrity(self):
        self.server.effect = lambda: LibraryPanelPreview("LIB-123", 1, "APPROVED_FOR_INDEXING", False)
        with self.assertRaises(AuthorizationDenied): self.reader.read_selected()

    def test_invalid_backend_result_denied(self):
        for effect in (lambda: None, lambda: object(),
                       lambda: LibraryPanelPreview("LIB-123", True, "APPROVED_FOR_INDEXING", True),
                       lambda: LibraryPanelPreview("LIB-123", 1, "REVOKED", True)):
            with self.subTest(effect=repr(effect)):
                self.server.effect = effect
                with self.assertRaises(AuthorizationDenied): self.reader.read_selected()

    def test_underlying_denial_is_generic(self):
        def blocked():
            raise RuntimeError("secret database diagnostic")
        self.server.effect = blocked
        with self.assertRaises(AuthorizationDenied) as ctx: self.reader.read_selected()
        self.assertNotIn("secret database diagnostic", str(ctx.exception))


if __name__ == "__main__": unittest.main()
