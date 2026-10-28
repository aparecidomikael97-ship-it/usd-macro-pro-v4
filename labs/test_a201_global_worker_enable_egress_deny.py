"""A201: Global Worker ENABLE is denied at the actual low-level HTTP writer.

Synthetic runtime/token, fake requests transport. Never activate a real worker.
Safety DISABLE is intentionally preserved; these tests simulate its HTTP calls.
A local role/approval/feature state is not independent owner custody or P0.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from atlasquant_aion_global_worker_activation import (
    CONFIRMATION_PHRASE, DEACTIVATION_PHRASE,
    activate_global_worker_feature_flag,
    deactivate_global_worker_feature_flag,
    force_disable_repository_feature_flag,
    write_repository_feature_flag_enabled,
)
from test_atlasquant_aion_global_worker_activation import (
    GlobalWorkerActivationCeremonyTests,
    NOW, _config, _safe_flag,
)


class A201WorkerEnableContainmentTests(unittest.TestCase):
    def block_network(self):
        return (
            patch(
                "atlasquant_aion_global_worker_activation.requests.post",
                side_effect=AssertionError("ENABLE_POST_FORBIDDEN"),
            ),
            patch(
                "atlasquant_aion_global_worker_activation.requests.patch",
                side_effect=AssertionError("ENABLE_PATCH_FORBIDDEN"),
            ),
        )

    def test_01_both_valid_prior_states_deny_any_enable_transport(self):
        post, change = self.block_network()
        with post as p, change as q:
            for previous in ("UNSET", "DISABLED"):
                outcome = write_repository_feature_flag_enabled(
                    _config(), previous,
                )
                self.assertEqual(outcome["status"], "BLOCKED")
                self.assertEqual(
                    outcome["reason"],
                    "EXTERNAL_ENABLE_CUSTODY_NOT_HOMOLOGATED",
                )
                self.assertEqual(outcome["previous_state"], previous)
                self.assertEqual(outcome["target_state"], "ENABLED")
                self.assertIs(outcome["modified"], False)
                self.assertIs(outcome["raw_value_exposed"], False)
        p.assert_not_called()
        q.assert_not_called()

    def test_02_caller_can_not_override_with_flags_or_prior_state_spelling(self):
        post, change = self.block_network()
        with post as p, change as q:
            for previous in ("unset", "disabled", "UnSeT", " DISABLED "):
                outcome = write_repository_feature_flag_enabled(
                    _config(), previous,
                )
                self.assertNotEqual(outcome["status"], "WRITE_ACCEPTED")
                self.assertFalse(outcome["modified"])
        p.assert_not_called()
        q.assert_not_called()

    def test_03_unsafe_state_denied_before_transport(self):
        post, change = self.block_network()
        with post as p, change as q:
            for previous in ("ENABLED", "ERROR", "UNKNOWN", ""):
                outcome = write_repository_feature_flag_enabled(_config(), previous)
                self.assertEqual(outcome["status"], "BLOCKED")
                self.assertIs(outcome["modified"], False)
        p.assert_not_called()
        q.assert_not_called()

    def test_04_concurrent_enable_attempts_cannot_enter_http(self):
        post, change = self.block_network()
        with post as p, change as q:
            with ThreadPoolExecutor(max_workers=8) as pool:
                outputs = list(pool.map(
                    lambda i: write_repository_feature_flag_enabled(
                        _config(), ("UNSET" if i % 2 else "DISABLED"),
                    ),
                    range(64),
                ))
        self.assertEqual(len(outputs), 64)
        self.assertTrue(all(x["status"] == "BLOCKED" for x in outputs))
        p.assert_not_called()
        q.assert_not_called()

    def test_05_lack_of_token_cannot_enable_worker(self):
        from atlasquant_aion_memory import RuntimeConfig
        config=RuntimeConfig(token="",repo="owner/repo",branch="runtime")
        post, change = self.block_network()
        with post as p, change as q:
            got = write_repository_feature_flag_enabled(config,"UNSET")
        self.assertEqual(got["status"],"UNAVAILABLE")
        self.assertIs(got["modified"],False)
        p.assert_not_called()
        q.assert_not_called()

    def test_06_ceremony_using_default_real_writer_blocks_when_ticket_valid(self):
        # Creates an otherwise valid synthetic ADMIN plan + approval using
        # existing fixture. This is a self-attested local approval, not owner
        # custody; it MUST NOT trigger an actual GitHub enable HTTP request.
        fixture=GlobalWorkerActivationCeremonyTests(
            "test_plan_is_read_only_and_bound_to_persisted_armed_runtime",
        )
        fixture.setUp()
        ticket=fixture.approval()
        pre_reads=[]
        def fake_flag_read(*args,**kwargs):
            pre_reads.append(1)
            return _safe_flag("UNSET")
        post, change = self.block_network()
        with post as p, change as q:
            result=activate_global_worker_feature_flag(
                fixture.access, fixture.runtime, ticket, _config(),
                confirmation=True,
                runtime_reader=lambda *a,**k: deepcopy(fixture.runtime),
                flag_reader=fake_flag_read,
                now=NOW,
            )
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(
            result["reason"],
            "EXTERNAL_ENABLE_CUSTODY_NOT_HOMOLOGATED",
        )
        self.assertIs(result["feature_flag_modified"],False)
        self.assertIs(result["global_worker_executed"],False)
        self.assertIs(result["real_trading_enabled"],False)
        self.assertEqual(len(pre_reads),1)
        p.assert_not_called()
        q.assert_not_called()

    def test_07_no_confirmation_blocks_before_read_or_mutation(self):
        post, change = self.block_network()
        with post as p, change as q:
            result=activate_global_worker_feature_flag(
                None, {}, None, _config(),
                confirmation=False,
                runtime_reader=lambda *a,**k: self.fail("runtime read forbidden"),
                flag_reader=lambda *a,**k: self.fail("flag read forbidden"),
            )
        self.assertEqual(result["status"],"BLOCKED")
        self.assertFalse(result["feature_flag_modified"])
        p.assert_not_called()
        q.assert_not_called()

    def test_08_safety_disable_is_not_blocked_and_writes_only_zero(self):
        reply=Mock(status_code=204)
        reply.raise_for_status.return_value=None
        with patch(
            "atlasquant_aion_global_worker_activation.requests.patch",
            return_value=reply,
        ) as patch_call, patch(
            "atlasquant_aion_global_worker_activation.requests.post",
            side_effect=AssertionError("ENABLE_POST_FORBIDDEN"),
        ) as post:
            outcome=force_disable_repository_feature_flag(_config())
        self.assertEqual(outcome["status"],"DISABLED")
        self.assertTrue(outcome["modified"])
        self.assertEqual(patch_call.call_args.kwargs["json"]["value"],"0")
        post.assert_not_called()

    def test_09_safety_disable_create_on_404_also_writes_only_zero(self):
        missing=Mock(status_code=404)
        created=Mock(status_code=201)
        created.raise_for_status.return_value=None
        with patch(
            "atlasquant_aion_global_worker_activation.requests.patch",
            return_value=missing,
        ) as change, patch(
            "atlasquant_aion_global_worker_activation.requests.post",
            return_value=created,
        ) as post:
            outcome=force_disable_repository_feature_flag(_config())
        self.assertEqual(outcome["status"],"DISABLED")
        self.assertTrue(outcome["modified"])
        self.assertEqual(change.call_args.kwargs["json"]["value"],"0")
        self.assertEqual(post.call_args.kwargs["json"]["value"],"0")

    def test_10_explicit_deactivation_is_still_possible_with_admin(self):
        # ADMIN stop is a safety-reducing mutation. No real network: reader
        # and disabler are fake here; real disable behavior tested separately.
        fixture=GlobalWorkerActivationCeremonyTests(
            "test_plan_is_read_only_and_bound_to_persisted_armed_runtime",
        )
        fixture.setUp()
        read=list([
            {"status":"CONFIRMED","state":"ENABLED"},
            _safe_flag("DISABLED"),
        ])
        got=deactivate_global_worker_feature_flag(
            fixture.access,_config(),
            confirmation=True,
            confirmation_phrase=DEACTIVATION_PHRASE,
            flag_reader=lambda *a,**k: read.pop(0),
            flag_disabler=lambda *a,**k: {"status":"DISABLED","modified":True},
        )
        self.assertEqual(got["status"],"DISABLED")
        self.assertEqual(got["feature_flag_state"],"DISABLED")
        self.assertIs(got["global_worker_executed"],False)

    def test_11_caller_claim_of_custody_does_not_authenticate_external_root(self):
        # These are claims in an untrusted caller context, not external
        # independent witnesses. The writer has NO bypass argument by design.
        post, change = self.block_network()
        with post as p, change as q:
            outcome=write_repository_feature_flag_enabled(
                _config(),"UNSET",timeout=1,
            )
        self.assertEqual(outcome["reason"],"EXTERNAL_ENABLE_CUSTODY_NOT_HOMOLOGATED")
        p.assert_not_called()
        q.assert_not_called()
        print("A201_CALLER_REPORTED_ADMIN_NOT_INDEPENDENT_OWNER_ROOT_RED",flush=True)


if __name__=="__main__":
    unittest.main()
