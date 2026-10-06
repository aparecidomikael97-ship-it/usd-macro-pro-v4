"""Focal regression proof for G1/G2/G3/G5; no real executor is exercised."""
from copy import deepcopy
from contextlib import ExitStack
import unittest
from unittest.mock import patch

import atlasquant_aion_b2b_owner_renewal_action_adapter_plan as legacy
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter
import atlasquant_aion_b2b_owner_renewal_action_adapter_dry_run_v2 as dry
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipt
import atlasquant_aion_b2b_owner_renewal_action_command_plan_v2 as command
from test_atlasquant_aion_b2b_owner_renewal_action_adapter_v2 import args_v2, dry_args_v2, receipt_args_v2, NOW
from test_atlasquant_aion_b2b_owner_renewal_action_adapter import args as args_v1, dry_args as dry_args_v1, receipt_args as receipt_args_v1

DANGEROUS = ('api_base', 'webhook', 'callback', 'invoke', 'transport', 'provider_config', 'connection', 'secret_ref')


class FinalHardeningTests(unittest.TestCase):
    def test_g1_v2_finops_does_not_depend_on_legacy_validator_or_cap(self):
        data = args_v2()
        with patch.object(legacy, 'FINOPS_CAP_CENTS', 1), patch.object(legacy, 'environment_blockers', side_effect=AssertionError('V1 environment used')):
            out = adapter.build_owner_renewal_action_adapter_plan_v2(**data)
            self.assertEqual(out['state'], adapter.READY)
            di = dry_args_v2(out)
            simulation = dry.build_owner_renewal_action_adapter_dry_run_v2(**di)
            self.assertEqual(simulation['state'], 'DRY_RUN_READY')
            self.assertEqual(simulation['simulation']['finops_cap_cents'], 20000)
        with patch.object(legacy, 'FINOPS_CAP_CENTS', 999999):
            data['adapter_environment']['finops_monthly_cents'] = 20001
            self.assertEqual(adapter.build_owner_renewal_action_adapter_plan_v2(**data)['state'], 'BLOCKED')

    def test_g5_future_contract_explicitly_requires_every_v2_schema(self):
        out = receipt.owner_renewal_action_receipt_contract_v2()
        self.assertEqual(out['required_command_plan_schema'], command.SCHEMA)
        self.assertEqual(out['required_adapter_plan_schema'], adapter.SCHEMA)
        self.assertEqual(out['required_dry_run_schema'], dry.SCHEMA)
        self.assertEqual(out['required_receipt_schema'], receipt.SYNTHETIC_RECEIPT_SCHEMA)
        self.assertIs(out['legacy_v1_allowed'], False)

    def test_g5_legacy_modules_are_explicitly_archival(self):
        import atlasquant_aion_b2b_owner_renewal_action_command_plan as old_command
        import atlasquant_aion_b2b_owner_renewal_action_adapter_dry_run as old_dry
        import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt as old_receipt
        for module in (old_command, legacy, old_dry, old_receipt):
            self.assertIn('LEGACY / NON-EXECUTABLE', module.__doc__)

    def test_g3_closed_schema_rejects_innocuous_unknown_fields(self):
        data = args_v2(); data['adapter_environment']['innocuous_extension'] = 'opaque'
        self.assertEqual(adapter.build_owner_renewal_action_adapter_plan_v2(**data)['state'], 'BLOCKED')
        data = dry_args_v2(); data['synthetic_provider_snapshot']['innocuous_extension'] = 'opaque'
        self.assertEqual(dry.build_owner_renewal_action_adapter_dry_run_v2(**data)['state'], 'DRY_RUN_BLOCKED')
        data = receipt_args_v2(); data['receipt']['innocuous_extension'] = 'opaque'
        self.assertEqual(receipt.validate_synthetic_owner_renewal_action_receipt_v2(**data)['state'], 'BLOCKED')

    def test_g5_v1_artifacts_cannot_enter_v2_boundaries(self):
        old = legacy.build_owner_renewal_action_adapter_plan(**args_v1())
        with self.assertRaises(ValueError): adapter.validate_adapter_plan_v2(old, NOW)
        data = dry_args_v2(); data['adapter_plan'] = old
        self.assertEqual(dry.build_owner_renewal_action_adapter_dry_run_v2(**data)['state'], 'DRY_RUN_BLOCKED')
        old_receipt = receipt_args_v1()
        for field, artifact in (('adapter_plan', old), ('dry_run', old_receipt['dry_run']), ('receipt', old_receipt['receipt'])):
            with self.subTest(field=field):
                data = receipt_args_v2(); data[field] = artifact
                self.assertEqual(receipt.validate_synthetic_owner_renewal_action_receipt_v2(**data)['state'], 'BLOCKED')

    def test_receipt_stays_synthetic_and_request_digest_is_bound(self):
        data = receipt_args_v2()
        self.assertIn('execution_request_digest', data['receipt']['binding'])
        result = receipt.validate_synthetic_owner_renewal_action_receipt_v2(**data)
        self.assertEqual(result['state'], 'SYNTHETIC_RECEIPT_VALIDATED')
        data['receipt']['binding']['execution_request_digest'] = 'sha256:' + 'f' * 64
        data['receipt']['receipt_digest'] = legacy.digest({k:v for k,v in data['receipt'].items() if k != 'receipt_digest'})
        blocked = receipt.validate_synthetic_owner_renewal_action_receipt_v2(**data)
        self.assertEqual(blocked['state'], 'BLOCKED')
        for out in (result, blocked, receipt.owner_renewal_action_receipt_contract_v2()):
            for key in ('actual_receipt_generated', 'execution_verified', 'provider_identity_authenticated', 'writer_identity_authenticated', *adapter.FALSE_FIELDS):
                self.assertIs(out[key], False, key)

    def test_zero_external_io_and_persistence_for_full_v2_chain(self):
        a, d, r = args_v2(), dry_args_v2(), receipt_args_v2()
        from atlasquant_aion_unified_journal_store import UnifiedJournalStore
        from atlasquant_aion_nonce_registry import PersistentNonceRegistry
        targets = ('builtins.open', 'io.open', 'os.open', 'pathlib.Path.open', 'pathlib.Path.read_text',
            'pathlib.Path.read_bytes', 'pathlib.Path.write_text', 'pathlib.Path.write_bytes',
            'pathlib.Path.rename', 'pathlib.Path.replace', 'pathlib.Path.unlink', 'os.rename',
            'os.replace', 'os.remove', 'os.system', 'socket.socket', 'socket.create_connection',
            'subprocess.Popen', 'subprocess.run', 'atlasquant_aion_checkpoint_master.append_checkpoint_patch')
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch(t, side_effect=AssertionError('external I/O'))) for t in targets]
            mocks += [stack.enter_context(patch.object(c, '__init__', side_effect=AssertionError('persistence'))) for c in (UnifiedJournalStore, PersistentNonceRegistry)]
            self.assertEqual(adapter.build_owner_renewal_action_adapter_plan_v2(**a)['state'], adapter.READY)
            self.assertEqual(dry.build_owner_renewal_action_adapter_dry_run_v2(**d)['state'], 'DRY_RUN_READY')
            self.assertEqual(receipt.validate_synthetic_owner_renewal_action_receipt_v2(**r)['state'], 'SYNTHETIC_RECEIPT_VALIDATED')
            for mock in mocks: mock.assert_not_called()


def add_case(name, fn):
    fn.__name__ = 'test_' + name
    setattr(FinalHardeningTests, fn.__name__, fn)


for index, value in enumerate((0, 20000, 20001, True, False, -1, 1.0, '20000', None)):
    def case(self, value=value):
        data = args_v2(); data['adapter_environment']['finops_monthly_cents'] = value
        out = adapter.build_owner_renewal_action_adapter_plan_v2(**data)
        self.assertEqual(out['state'], adapter.READY if type(value) is int and 0 <= value <= 20000 else 'BLOCKED')
    add_case(f'g1_finops_{index}', case)

    def environment_case(self, value=value):
        data = args_v2(); env = data['adapter_environment']; env['finops_monthly_cents'] = value
        with patch.object(legacy, 'FINOPS_CAP_CENTS', 999999):
            blockers = adapter.environment_blockers_v2(env, env['binding'], NOW)
        self.assertEqual('FINOPS_CAP_VIOLATION' in blockers, not (type(value) is int and 0 <= value <= 20000))
    add_case(f'g1_environment_exact_type_{index}', environment_case)


for field in ('customer_id', 'pilot_id', 'package', 'review_type', 'requested_choice', 'action_family', 'action_parameters_digest', 'execution_request_digest'):
    for index, value in enumerate((True, False, 1, 0, [], {}, None)):
        def case(self, field=field, value=value):
            data = args_v2(); data['execution_persistence_attestation'][field] = value
            with patch.object(adapter, 'build_owner_renewal_action_command_plan_v2', side_effect=AssertionError('semantic processing too early')) as producer:
                self.assertEqual(adapter.build_owner_renewal_action_adapter_plan_v2(**data)['state'], 'BLOCKED')
                producer.assert_not_called()
        add_case(f'g2_before_producer_{field}_{index}', case)


for field in ('command_plan_v1_digest', 'red_team_hardening_digest'):
    for index, value in enumerate((True, False, 1, 0, [], {}, None)):
        def case(self, field=field, value=value):
            data = dry_args_v2(); data['adapter_plan']['adapter_plan'][field] = value
            self.assertEqual(dry.build_owner_renewal_action_adapter_dry_run_v2(**data)['state'], 'DRY_RUN_BLOCKED')
        add_case(f'g2_digest_body_{field}_{index}', case)


for key in DANGEROUS:
    for layer in ('adapter', 'dry', 'receipt'):
        def case(self, key=key, layer=layer):
            if layer == 'adapter':
                data = args_v2(); data['command_plan']['command_plan']['scope'][key] = 'CANARY'
                with patch.object(adapter, 'build_owner_renewal_action_command_plan_v2', side_effect=AssertionError('unsafe material processed')):
                    out = adapter.build_owner_renewal_action_adapter_plan_v2(**data)
                self.assertEqual(out['state'], 'BLOCKED')
            elif layer == 'dry':
                data = dry_args_v2(); data['synthetic_provider_snapshot']['binding'][key] = 'CANARY'
                out = dry.build_owner_renewal_action_adapter_dry_run_v2(**data)
                self.assertEqual(out['state'], 'DRY_RUN_BLOCKED')
            else:
                data = receipt_args_v2(); data['receipt']['binding'][key] = 'CANARY'
                out = receipt.validate_synthetic_owner_renewal_action_receipt_v2(**data)
                self.assertEqual(out['state'], 'BLOCKED')
            self.assertNotIn('CANARY', repr(out))
        add_case(f'g3_{layer}_{key}', case)


if __name__ == '__main__': unittest.main()
