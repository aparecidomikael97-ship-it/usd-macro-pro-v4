"""Negative contracts for caller-scope guardrails in the offline Library V1.

These do not constitute authenticating an untrusted caller. Runtime RBAC and
signed decisions remain separately blocked by issue #477.
"""
import unittest
from aion_core.library_foundation import LibraryCatalog, LibraryFoundationError


def doc(catalog, *, tenant='T-A', domain='TRADER', docid='DOC-1', **kwargs):
    options = dict(tenant_id=tenant, domain_id=domain, document_id=docid,
                   version=1, sha256='a'*64, source_type='BOOK',
                   source_reference='isbn:123', license_kind='CC0',
                   rights_holder='rights', usage_scope='INTERNAL',
                   human_approved_by='mikael')
    options.update(kwargs)
    return catalog.register_document(**options)


class LibraryGuardContractTests(unittest.TestCase):
    def test_transition_rejects_other_tenant(self):
        cat = LibraryCatalog()
        e = doc(cat)
        with self.assertRaises(LibraryFoundationError):
            cat.transition(tenant_id='T-B', domain_id='TRADER', entry_id=e.entry_id,
                           to_state='METADATA_REVIEW', actor='mikael')
        self.assertEqual(cat.get(tenant_id='T-A', domain_id='TRADER', document_id='DOC-1', version=1).state,
                         'RECEIVED')

    def test_transition_rejects_other_domain(self):
        cat = LibraryCatalog()
        e = doc(cat)
        with self.assertRaises(LibraryFoundationError):
            cat.transition(tenant_id='T-A', domain_id='BUSINESS', entry_id=e.entry_id,
                           to_state='REVOKED', actor='mikael')

    def test_transition_requires_explicit_scope(self):
        cat = LibraryCatalog()
        e = doc(cat)
        with self.assertRaises(TypeError):
            cat.transition(entry_id=e.entry_id, to_state='REVOKED', actor='mikael')

    def test_lookup_requires_scope(self):
        cat = LibraryCatalog()
        e = doc(cat)
        with self.assertRaises(TypeError):
            cat.find_by_entry_id(entry_id=e.entry_id)
        self.assertIsNone(cat.find_by_entry_id(tenant_id='T-B', domain_id='TRADER', entry_id=e.entry_id))
        self.assertIsNone(cat.find_by_entry_id(tenant_id='T-A', domain_id='BUSINESS', entry_id=e.entry_id))
        self.assertEqual(e, cat.find_by_entry_id(tenant_id='T-A', domain_id='TRADER', entry_id=e.entry_id))

    def test_approval_declared_actor_must_match(self):
        cat = LibraryCatalog()
        e = doc(cat)
        cat.transition(tenant_id='T-A', domain_id='TRADER', entry_id=e.entry_id,
                       to_state='METADATA_REVIEW', actor='analyst')
        with self.assertRaises(LibraryFoundationError):
            cat.transition(tenant_id='T-A', domain_id='TRADER', entry_id=e.entry_id,
                           to_state='APPROVED_FOR_INDEXING', actor='outsider')
        self.assertEqual(cat.find_by_entry_id(tenant_id='T-A', domain_id='TRADER', entry_id=e.entry_id).state,
                         'METADATA_REVIEW')

    def test_rights_reserved_cannot_be_approved_on_metadata_only(self):
        cat = LibraryCatalog()
        e = doc(cat, license_kind='ALL_RIGHTS_RESERVED', rights_holder='', usage_scope='PUBLISHED')
        cat.transition(tenant_id='T-A', domain_id='TRADER', entry_id=e.entry_id,
                       to_state='METADATA_REVIEW', actor='mikael')
        with self.assertRaises(LibraryFoundationError):
            cat.transition(tenant_id='T-A', domain_id='TRADER', entry_id=e.entry_id,
                           to_state='APPROVED_FOR_INDEXING', actor='mikael')
        self.assertEqual(cat.indexable(tenant_id='T-A', domain_id='TRADER'), [])

    def test_rights_reserved_even_if_rightsholder_declared_is_blocked(self):
        cat = LibraryCatalog()
        e = doc(cat, license_kind='ALL_RIGHTS_RESERVED', rights_holder='rights owner')
        cat.transition(tenant_id='T-A', domain_id='TRADER', entry_id=e.entry_id,
                       to_state='METADATA_REVIEW', actor='mikael')
        with self.assertRaises(LibraryFoundationError):
            cat.transition(tenant_id='T-A', domain_id='TRADER', entry_id=e.entry_id,
                           to_state='APPROVED_FOR_INDEXING', actor='mikael')

    def test_cc0_happy_path_remains(self):
        cat = LibraryCatalog()
        e = doc(cat)
        cat.transition(tenant_id='T-A', domain_id='TRADER', entry_id=e.entry_id,
                       to_state='METADATA_REVIEW', actor='analyst')
        result = cat.transition(tenant_id='T-A', domain_id='TRADER', entry_id=e.entry_id,
                                to_state='APPROVED_FOR_INDEXING', actor='mikael')
        self.assertEqual(result.state, 'APPROVED_FOR_INDEXING')

    def test_invalid_tenant_characters_rejected(self):
        cat = LibraryCatalog()
        with self.assertRaises(LibraryFoundationError):
            doc(cat, tenant='T A')

    def test_invalid_domain_characters_rejected(self):
        cat = LibraryCatalog()
        with self.assertRaises(LibraryFoundationError):
            doc(cat, domain='TRA/DER')


if __name__ == '__main__':
    unittest.main()
