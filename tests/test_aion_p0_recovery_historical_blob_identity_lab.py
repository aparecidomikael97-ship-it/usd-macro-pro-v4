"""A131 RED-first: verify Git blob identity for historical recovery bytes.

Only synthetic responses and a mocked requests.get are used. No real network,
GitHub checkpoint writes, restore, Worker, or external supplier effects.
"""
from __future__ import annotations

import base64
import hashlib
import json
import unittest
from unittest.mock import MagicMock, patch

from atlasquant_aion_memory import RuntimeConfig, default_checkpoint
from atlasquant_aion_recovery import load_checkpoint_revision

REV = "a" * 40


def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw
    ).hexdigest()


class HistoricalBlobIdentityLab(unittest.TestCase):
    def setUp(self):
        self.cfg = RuntimeConfig(
            token="synthetic-unused", repo="example/repo",
            branch="atlasquant-runtime", path="dados/aion/checkpoint_master.json",
        )
        self.checkpoint = default_checkpoint()
        self.raw = json.dumps(
            self.checkpoint, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")

    def remote(self, *, payload=None, claimed_sha=None, **meta):
        raw = self.raw if payload is None else payload
        if claimed_sha is None:
            claimed_sha = blob_sha(raw)
        return {
            "content": base64.b64encode(raw).decode("ascii"),
            "encoding": "base64",
            "sha": claimed_sha,
            **meta,
        }

    def load(self, remote):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = remote
        with patch("requests.get", return_value=response) as get:
            out = load_checkpoint_revision(REV, self.cfg)
        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs.get("params"), {"ref": REV})
        return out

    def expect_denied(self, remote):
        result = self.load(remote)
        self.assertEqual(result["status"], "ERROR", result)
        self.assertIsNone(result["checkpoint"])
        self.assertIs(result["executes_action"], False)

    def test_01_exact_raw_blob_sha_accepted(self):
        result = self.load(self.remote())
        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(result["checkpoint"], self.checkpoint)
        self.assertIs(result["executes_action"], False)

    def test_02_case_insensitive_hex_blob_sha_accepted(self):
        result = self.load(self.remote(claimed_sha=blob_sha(self.raw).upper()))
        self.assertEqual(result["status"], "CONFIRMED")

    def test_03_valid_wrapped_base64_preserves_blob_identity(self):
        obj = self.remote()
        encoded = obj["content"]
        obj["content"] = "\n".join(encoded[i:i+64] for i in range(0, len(encoded), 64))
        result = self.load(obj)
        self.assertEqual(result["status"], "CONFIRMED")

    def test_04_missing_sha_denied(self):
        obj = self.remote()
        del obj["sha"]
        self.expect_denied(obj)

    def test_05_well_formed_but_wrong_sha_denied(self):
        self.expect_denied(self.remote(claimed_sha="f"*40))

    def test_06_boolean_sha_denied_without_string_coercion(self):
        self.expect_denied(self.remote(claimed_sha=True))

    def test_07_integer_sha_denied_without_string_coercion(self):
        self.expect_denied(self.remote(claimed_sha=1234))

    def test_08_short_sha_denied(self):
        self.expect_denied(self.remote(claimed_sha="a"*39))

    def test_09_overlong_sha_denied(self):
        self.expect_denied(self.remote(claimed_sha="a"*41))

    def test_10_sha_prefix_denied(self):
        self.expect_denied(self.remote(claimed_sha="sha1:"+blob_sha(self.raw)))

    def test_11_same_claimed_sha_different_checkpoint_bytes_denied(self):
        changed = dict(self.checkpoint)
        changed["project"] = "forged project"
        changed_raw = json.dumps(
            changed, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        self.expect_denied(
            self.remote(payload=changed_raw, claimed_sha=blob_sha(self.raw))
        )

    def test_12_sha_with_hidden_newline_denied(self):
        self.expect_denied(
            self.remote(claimed_sha=blob_sha(self.raw)+"\n")
        )


if __name__ == "__main__":
    unittest.main()
