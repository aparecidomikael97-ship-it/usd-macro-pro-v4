"""A132 RED-first: runtime branch checkpoint SHA must identify the observed bytes.

All requests.get calls are mocked; no real GitHub runtime restore, PUT, Worker
or supplier operation is attempted. This is Git blob consistency, not an
independent monotonic-head attestation.
"""
from __future__ import annotations

import base64
import hashlib
import json
import unittest
from unittest.mock import MagicMock, patch

from atlasquant_aion_memory import RuntimeConfig, default_checkpoint, load_runtime_checkpoint
from atlasquant_aion_recovery import restore_checkpoint_revision
from test_atlasquant_aion_recovery_traceability_gate import _current, _candidate


def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw
    ).hexdigest()


class RuntimeCurrentGitBlobIdentityLab(unittest.TestCase):
    def setUp(self):
        self.config = RuntimeConfig(
            token="unused-synthetic", repo="example/repo",
            branch="atlasquant-runtime", path="dados/aion/checkpoint_master.json",
        )
        self.checkpoint = default_checkpoint()
        self.raw = json.dumps(self.checkpoint, sort_keys=True).encode("utf-8")

    def envelope(self, *, raw=None, claimed_sha=None):
        payload = self.raw if raw is None else raw
        if claimed_sha is None:
            claimed_sha = blob_sha(payload)
        return {
            "content":base64.b64encode(payload).decode("ascii"),
            "encoding":"base64",
            "sha":claimed_sha,
        }

    def read(self, envelope):
        response=MagicMock()
        response.status_code=200
        response.raise_for_status.return_value=None
        response.json.return_value=envelope
        with patch("requests.get", return_value=response) as get:
            result=load_runtime_checkpoint(self.config)
        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs["params"], {"ref":self.config.branch})
        return result

    def denied(self, envelope):
        result=self.read(envelope)
        self.assertEqual(result["status"], "ERROR", result)
        self.assertIsNone(result["checkpoint"])
        self.assertEqual(result["sha"], "")
        return result

    def test_01_valid_blob_bytes_confirmed(self):
        result=self.read(self.envelope())
        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(result["sha"],blob_sha(self.raw))
        self.assertEqual(result["checkpoint"],self.checkpoint)

    def test_02_uppercase_hex_sha_confirmed(self):
        result=self.read(self.envelope(claimed_sha=blob_sha(self.raw).upper()))
        self.assertEqual(result["status"],"CONFIRMED")

    def test_03_wrapped_base64_confirmed(self):
        envelope=self.envelope()
        enc=envelope["content"]
        envelope["content"]="\n".join(enc[i:i+76] for i in range(0,len(enc),76))
        result=self.read(envelope)
        self.assertEqual(result["status"],"CONFIRMED")

    def test_04_missing_sha_does_not_confirm(self):
        envelope=self.envelope()
        del envelope["sha"]
        self.denied(envelope)

    def test_05_well_formed_forged_sha_does_not_confirm(self):
        self.denied(self.envelope(claimed_sha="a"*40))

    def test_06_numeric_sha_does_not_confirm(self):
        self.denied(self.envelope(claimed_sha=1234))

    def test_07_boolean_sha_does_not_confirm(self):
        self.denied(self.envelope(claimed_sha=True))

    def test_08_39_character_sha_does_not_confirm(self):
        self.denied(self.envelope(claimed_sha="a"*39))

    def test_09_41_character_sha_does_not_confirm(self):
        self.denied(self.envelope(claimed_sha="a"*41))

    def test_10_sha_with_prefix_does_not_confirm(self):
        self.denied(self.envelope(claimed_sha="sha1:"+blob_sha(self.raw)))

    def test_11_sha_with_newline_does_not_confirm(self):
        self.denied(self.envelope(claimed_sha=blob_sha(self.raw)+"\n"))

    def test_12_valid_sha_of_previous_bytes_cannot_confirm_modified_body(self):
        changed=dict(self.checkpoint)
        changed["aion"]=dict(changed["aion"])
        changed["aion"]["priority"]="different current checkpoint"
        raw=json.dumps(changed,sort_keys=True).encode("utf-8")
        self.denied(self.envelope(raw=raw,claimed_sha=blob_sha(self.raw)))

    def test_13_invalid_current_blob_never_reaches_historical_readback_or_save(self):
        current=_current()
        current["sha"]="f"*40
        remote=self.envelope(
            raw=json.dumps(current["checkpoint"],sort_keys=True).encode("utf-8"),
            claimed_sha=current["sha"],
        )
        response=MagicMock()
        response.status_code=200
        response.raise_for_status.return_value=None
        response.json.return_value=remote
        with patch("requests.get",return_value=response) as live_get, patch(
            "atlasquant_aion_recovery._verify_runtime_revision_ancestry",
            return_value={"allowed":True},
        ) as compare, patch(
            "atlasquant_aion_recovery.load_checkpoint_revision",
            return_value=_candidate(),
        ) as historical_read, patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint",
            return_value={"status":"CONFLICT","saved":False,"verified":False},
        ) as save:
            result=restore_checkpoint_revision(
                _candidate(),current,self.config,approved=True
            )
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertIs(result["saved"],False)
        self.assertIs(result["verified"],False)
        self.assertIs(result["automatic_retry_allowed"],False)
        live_get.assert_called_once()
        compare.assert_not_called()
        historical_read.assert_not_called()
        save.assert_not_called()


if __name__=="__main__":
    unittest.main()
