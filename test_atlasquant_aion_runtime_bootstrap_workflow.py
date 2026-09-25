from __future__ import annotations

import unittest
from unittest.mock import patch

import scripts.aion_runtime_bootstrap as bootstrap


class AtlasQuantAionRuntimeBootstrapWorkflowTests(unittest.TestCase):
    @patch.object(bootstrap, "runtime_configuration_status")
    @patch.object(bootstrap, "load_runtime_checkpoint")
    @patch.object(bootstrap, "save_runtime_checkpoint")
    @patch.object(bootstrap, "runtime_write_preflight")
    def test_creates_only_when_not_found_and_verifies(
        self, preflight, save, load, config
    ):
        config.return_value={"read_ready":True,"write_ready":True}
        load.side_effect=[
            {"status":"NOT_FOUND","source":"runtime","sha":""},
            {
                "status":"CONFIRMED",
                "source":"GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json",
                "sha":"sha-1",
                "integrity":{"state":"CONFIRMED"},
                "checkpoint":{
                    "checkpoint_version":14,
                    "aion":{"foundation_revision":"2026-09-25-complete-v2"},
                },
            },
        ]
        preflight.return_value={"allowed":True,"mode":"CREATE","expected_sha":""}
        save.return_value={
            "status":"CONFIRMED","saved":True,"verified":True,
            "sha":"sha-1","digest":"digest-1",
            "integrity":{"state":"CONFIRMED"},
        }
        self.assertEqual(bootstrap.main(),0)
        save.assert_called_once()

    @patch.object(bootstrap, "runtime_configuration_status")
    @patch.object(bootstrap, "load_runtime_checkpoint")
    @patch.object(bootstrap, "save_runtime_checkpoint")
    def test_existing_confirmed_checkpoint_is_never_overwritten(self, save, load, config):
        config.return_value={"read_ready":True,"write_ready":True}
        confirmed={
            "status":"CONFIRMED",
            "source":"GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json",
            "sha":"sha-1",
            "integrity":{"state":"CONFIRMED"},
            "checkpoint":{
                "checkpoint_version":14,
                "aion":{"foundation_revision":"2026-09-25-complete-v2"},
            },
        }
        load.side_effect=[confirmed,confirmed]
        self.assertEqual(bootstrap.main(),0)
        save.assert_not_called()

    @patch.object(bootstrap, "runtime_configuration_status")
    @patch.object(bootstrap, "load_runtime_checkpoint")
    @patch.object(bootstrap, "save_runtime_checkpoint")
    def test_existing_mismatch_fails_closed(self, save, load, config):
        config.return_value={"read_ready":True,"write_ready":True}
        load.return_value={
            "status":"CONFIRMED",
            "source":"runtime",
            "sha":"sha-1",
            "integrity":{"state":"MISMATCH"},
            "checkpoint":{"checkpoint_version":14},
        }
        self.assertNotEqual(bootstrap.main(),0)
        save.assert_not_called()

    @patch.object(bootstrap, "runtime_configuration_status")
    @patch.object(bootstrap, "load_runtime_checkpoint")
    @patch.object(bootstrap, "save_runtime_checkpoint")
    def test_missing_write_credential_blocks_initial_creation(self, save, load, config):
        config.return_value={"read_ready":True,"write_ready":False}
        load.return_value={"status":"NOT_FOUND","source":"runtime","sha":""}
        self.assertNotEqual(bootstrap.main(),0)
        save.assert_not_called()


if __name__=="__main__":
    unittest.main()
