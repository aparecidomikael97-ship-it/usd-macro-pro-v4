"""Offline boundary contracts. No DB or app/UI is started here."""
import unittest
from unittest.mock import patch

from aion_core.library_authorization import AuthorizationDenied
from atlasquant_aion_library_internal_entry import (
    LibrarySelectionStatus, TrustedLibraryAppSelection,
)
from atlasquant_aion_library_postgres_preview import LibraryPanelPreview
from atlasquant_aion_library_server_assembly import SandboxLibraryServerReadAssembly


class HostSelectionTests(unittest.TestCase):
    def setUp(self):
        self.target = {"study": ("TENANT-1", "LIBRARY", "ENTRY-1")}
        self.assembly = object.__new__(SandboxLibraryServerReadAssembly)
        self.output = LibraryPanelPreview("ENTRY-1", 2, "APPROVED_FOR_INDEXING", True)
        self.called = []
        self.reader = patch.object(SandboxLibraryServerReadAssembly, 'read_preview',
                                   autospec=True, side_effect=self.read)
        self.reader.start()
        self.addCleanup(self.reader.stop)
        self.svc = TrustedLibraryAppSelection(
            assembly=self.assembly, resolve_selection=self.resolve)

    def resolve(self, alias):
        return self.target[alias]

    def read(self, _assembly, **kwargs):
        self.called.append(kwargs)
        return self.output

    def test_minimal_status_no_entry_id_or_hash(self):
        out=self.svc.preview_for_host(selection='study')
        self.assertEqual(out, LibrarySelectionStatus('study','APPROVED_FOR_INDEXING',2,True))
        self.assertNotIn('entry_id', out.__dict__)
        self.assertNotIn('sha256', out.__dict__)
        self.assertEqual(self.called,[dict(tenant_id='TENANT-1',domain_id='LIBRARY',entry_id='ENTRY-1')])

    def test_resolver_called_fresh_each_request_and_after_read(self):
        x=[]
        def resolve(alias):
            x.append(alias)
            return self.target[alias]
        svc=TrustedLibraryAppSelection(assembly=self.assembly,resolve_selection=resolve)
        svc.preview_for_host(selection='study')
        svc.preview_for_host(selection='study')
        self.assertEqual(x,['study']*4)

    def test_unavailable_or_unknown_selection_denied(self):
        for alias in ('../secrets','', 'x'*49, 1, None, 'other'):
            with self.subTest(alias=alias):
                with self.assertRaises(AuthorizationDenied):self.svc.preview_for_host(selection=alias)

    def test_bad_resolution_shapes_and_injection_denied(self):
        for target in (['TENANT-1','LIBRARY','ENTRY-1'],('TENANT-1','LIBRARY'),
                       ('TENANT-1','LIBRARY','../ENTRY'),('TENANT-1','LIBRARY',True),
                       ('TENANT-1','LIBRARY', 'E'*129)):
            with self.subTest(target=target):
                self.target['study']=target
                with self.assertRaises(AuthorizationDenied):self.svc.preview_for_host(selection='study')

    def test_server_retargets_during_read_fails_closed(self):
        def flip(_,**kw):
            self.target['study']=('TENANT-2','LIBRARY','ENTRY-2')
            return self.output
        with patch.object(SandboxLibraryServerReadAssembly,'read_preview',autospec=True,side_effect=flip):
            with self.assertRaises(AuthorizationDenied):self.svc.preview_for_host(selection='study')

    def test_server_removes_selection_during_read_fails_closed(self):
        def remove(_,**kw):
            self.target.clear()
            return self.output
        with patch.object(SandboxLibraryServerReadAssembly,'read_preview',autospec=True,side_effect=remove):
            with self.assertRaises(AuthorizationDenied):self.svc.preview_for_host(selection='study')

    def test_mismatched_or_unverified_result_denied(self):
        for result in (LibraryPanelPreview('ENTRY-2',1,'APPROVED_FOR_INDEXING',True),
                       LibraryPanelPreview('ENTRY-1',1,'REVOKED',True),
                       LibraryPanelPreview('ENTRY-1',1,'APPROVED_FOR_INDEXING',False),
                       {'entry_id':'ENTRY-1'}, None):
            with self.subTest(result=result):
                self.output=result
                with self.assertRaises(AuthorizationDenied):self.svc.preview_for_host(selection='study')

    def test_backend_exception_not_exposed(self):
        with patch.object(SandboxLibraryServerReadAssembly,'read_preview',
                          side_effect=RuntimeError('synthetic-internal-db-details')):
            with self.assertRaises(AuthorizationDenied) as cm:
                self.svc.preview_for_host(selection='study')
        self.assertEqual(str(cm.exception),'library selection unavailable')

    def test_constructor_does_not_accept_untrusted_assembly(self):
        with self.assertRaises(AuthorizationDenied):
            TrustedLibraryAppSelection(assembly=object(),resolve_selection=self.resolve)
        with self.assertRaises(AuthorizationDenied):
            TrustedLibraryAppSelection(assembly=self.assembly,resolve_selection=None)

    def test_review_status_delivered_only_after_underlying_read(self):
        self.output=LibraryPanelPreview('ENTRY-1',1,'METADATA_REVIEW',True)
        self.assertEqual(self.svc.preview_for_host(selection='study').state,'METADATA_REVIEW')
        # Underlying assembly, not this wrapper, owns role/scope authorization.


if __name__ == '__main__': unittest.main()
