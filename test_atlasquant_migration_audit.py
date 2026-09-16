import unittest
from unittest.mock import patch
from atlasquant_migration_audit import inspect_payload, compare_payloads, audit_repository


class MigrationAuditTests(unittest.TestCase):
    def test_missing_target_requires_review(self):
        r = compare_payloads({'dados/a.json': b'{}'}, {})
        self.assertEqual(r['review_items'], 1)
        self.assertFalse(r['automatic_migration_allowed'])

    def test_target_only_preserved(self):
        r = compare_payloads({}, {'dados/a.json': b'{}'})
        self.assertEqual(r['files'][0]['proposal'], 'preserve_target')

    def test_bad_identical_data_not_accepted(self):
        for raw in (b'{', b'{"a":1,"a":2}', b'{"a":NaN}', b'null', b'\xff'):
            r = compare_payloads({'dados/a.json': raw}, {'dados/a.json': raw})
            self.assertEqual(r['review_items'], 1)

    def test_jsonl_conflicting_and_duplicate_ids(self):
        for raw, issue in [(b'{"id":1}\n{"id":1}', 'duplicate_id'),
                           (b'{"id":1,"x":1}\n{"id":1,"x":2}', 'conflicting_id')]:
            self.assertIn(issue, inspect_payload('a.jsonl', raw)['issues'])

    def test_csv_shape_and_duplicates(self):
        self.assertFalse(inspect_payload('a.csv', b'a,b\n1')['syntax_valid'])
        self.assertFalse(inspect_payload('a.csv', b'a,a\n1,2')['syntax_valid'])
        self.assertIn('duplicate_row', inspect_payload('a.csv', b'a\n1\n1')['issues'])

    def test_budget_never_cleared_by_identical_payload(self):
        r = compare_payloads({'dados/budget.json': b'{}'}, {'dados/budget.json': b'{}'})
        self.assertEqual(r['review_items'], 1)
        self.assertFalse(r['promotion_allowed'])

    def test_valid_identical_does_not_claim_schema_or_freshness(self):
        r = compare_payloads({'dados/a.json': b'{}'}, {'dados/a.json': b'{}'})
        self.assertEqual(r['review_items'], 0)
        self.assertFalse(r['files'][0]['source']['schema_validated'])
        self.assertFalse(r['files'][0]['source']['freshness_validated'])

    def test_concurrent_ref_change_blocks(self):
        with patch('atlasquant_migration_audit.resolve_ref', side_effect=['a','b','c','b']), \
             patch('atlasquant_migration_audit.inventory', return_value={'dados/a.json':b'{}'}):
            r = audit_repository('.', 'source', 'target')
        self.assertTrue(r['blocked'])
        self.assertFalse(r['refs_stable'])

    def test_empty_inventory_blocks(self):
        with patch('atlasquant_migration_audit.resolve_ref', return_value='a'), \
             patch('atlasquant_migration_audit.inventory', return_value={}):
            self.assertTrue(audit_repository('.', 'a', 'b')['blocked'])


if __name__ == '__main__':
    unittest.main()
