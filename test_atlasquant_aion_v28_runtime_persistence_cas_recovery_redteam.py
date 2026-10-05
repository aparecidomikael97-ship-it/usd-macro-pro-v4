from __future__ import annotations

import base64
import json
from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

from atlasquant_aion_memory import (
    MAX_RUNTIME_BYTES,
    RuntimeConfig,
    _runtime_write_receipt,
    checkpoint_integrity_report,
    checkpoint_source_digest,
    default_checkpoint,
    ensure_operating_checkpoint,
    load_runtime_checkpoint,
    reconcile_runtime_write,
)
from atlasquant_aion_recovery import restore_checkpoint_revision


def cfg(*, token="") -> RuntimeConfig:
    return RuntimeConfig(token=token, repo="owner/repo", branch="atlasquant-runtime")


def github_response(*, content, encoding="base64", sha="runtime-sha", include_encoding=True):
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    payload = {"content": content, "sha": sha}
    if include_encoding:
        payload["encoding"] = encoding
    response.json.return_value = payload
    return response


def encoded_checkpoint(checkpoint=None) -> str:
    raw = json.dumps(checkpoint or default_checkpoint(), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def load_with_response(response):
    with patch("requests.get", return_value=response):
        return load_runtime_checkpoint(cfg())


class TestLoadTransportHardening:
    def test_load_runtime_duplicate_json_keys_rejected(self):
        raw = '{"operating":{"tasks":[]},"operating":{"tasks":[{"id":"X"}]}}'.encode("utf-8")
        response = github_response(content=base64.b64encode(raw).decode("ascii"))
        result = load_with_response(response)
        assert result["status"] == "ERROR"
        assert result["checkpoint"] is None
        assert result["reason"] == "ValueError"

    @pytest.mark.parametrize("where", ["middle", "prefix"])
    def test_load_runtime_base64_invalid_chars_rejected(self, where):
        encoded = encoded_checkpoint()
        attacked = "@@@" + encoded if where == "prefix" else encoded[:10] + "@@@" + encoded[10:]
        result = load_with_response(github_response(content=attacked))
        assert result["status"] == "ERROR"
        assert result["checkpoint"] is None

    @pytest.mark.parametrize("encoding", ["utf-8", "", "gzip", "none"])
    def test_load_runtime_encoding_incompatible_rejected(self, encoding):
        result = load_with_response(
            github_response(content=encoded_checkpoint(), encoding=encoding)
        )
        assert result["status"] == "ERROR"
        assert result["checkpoint"] is None

    def test_load_runtime_missing_encoding_keeps_documented_base64_default(self):
        result = load_with_response(
            github_response(content=encoded_checkpoint(), include_encoding=False)
        )
        assert result["status"] == "CONFIRMED"
        assert isinstance(result["checkpoint"], dict)

    def test_load_runtime_encoded_size_is_bounded_before_decode(self):
        max_encoded_chars = 4 * ((MAX_RUNTIME_BYTES + 2) // 3)
        response = github_response(content="A" * (max_encoded_chars + 1))
        with patch("requests.get", return_value=response), patch(
            "atlasquant_aion_memory.base64.b64decode"
        ) as decoder:
            result = load_runtime_checkpoint(cfg())
        assert result["status"] == "ERROR"
        assert result["reason"] == "ValueError"
        decoder.assert_not_called()

    def test_load_runtime_accepts_whitespace_wrapped_valid_base64(self):
        encoded = encoded_checkpoint()
        wrapped = "\n".join(encoded[i:i + 64] for i in range(0, len(encoded), 64))
        result = load_with_response(github_response(content=wrapped))
        assert result["status"] == "CONFIRMED"


class TestReceiptReconcile:
    def _state(self):
        checkpoint = ensure_operating_checkpoint(default_checkpoint())
        digest = checkpoint_source_digest(checkpoint)
        receipt = _runtime_write_receipt(
            cfg(token="x"),
            expected_sha="old-sha",
            expected_digest=digest,
        )
        runtime = {
            "status": "CONFIRMED",
            "sha": "current-sha",
            "checkpoint": checkpoint,
            "source": "GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json",
        }
        return checkpoint, digest, receipt, runtime

    @pytest.mark.parametrize("field", ["repo", "branch", "path"])
    def test_receipt_target_tampering_is_blocked(self, field):
        _, _, receipt, runtime = self._state()
        attacked = deepcopy(receipt)
        attacked["target"][field] = "tampered"
        result = reconcile_runtime_write(attacked, runtime)
        assert result["status"] == "BLOCKED"
        assert result["verified"] is False
        assert result["write_attributed"] is False

    @pytest.mark.parametrize("field,value", [
        ("expected_sha", "tampered"),
        ("expected_digest", "0" * 16),
        ("intent_id", "0" * 64),
    ])
    def test_receipt_intent_tampering_is_blocked(self, field, value):
        _, _, receipt, runtime = self._state()
        attacked = deepcopy(receipt)
        attacked[field] = value
        result = reconcile_runtime_write(attacked, runtime)
        assert result["status"] == "BLOCKED"
        assert result["verified"] is False

    def test_lost_response_matching_content_is_not_blindly_attributed(self):
        _, _, receipt, runtime = self._state()
        result = reconcile_runtime_write(receipt, runtime)
        assert result["status"] == "CONTENT_CONFIRMED"
        assert result["verified"] is True
        assert result["write_attributed"] is False
        assert result["automatic_retry"] is False

    def test_lost_response_different_runtime_is_conflict(self):
        checkpoint, _, receipt, runtime = self._state()
        changed = deepcopy(checkpoint)
        changed["aion"]["priority"] = "different"
        runtime["checkpoint"] = ensure_operating_checkpoint(changed)
        result = reconcile_runtime_write(receipt, runtime)
        assert result["status"] == "CONFLICT"
        assert result["verified"] is False
        assert result.get("automatic_retry") is not True

    def test_lost_response_unavailable_runtime_waits_without_retry(self):
        _, _, receipt, runtime = self._state()
        runtime.update(status="ERROR", checkpoint=None, sha="")
        result = reconcile_runtime_write(receipt, runtime)
        assert result["status"] == "WAITING"
        assert result["verified"] is False
        assert result.get("automatic_retry") is not True


class TestCasConflict:
    def test_write_sha_mismatch_is_conflict_not_retry(self):
        _, digest, _, runtime = TestReceiptReconcile()._state()
        receipt = _runtime_write_receipt(
            cfg(token="x"),
            expected_sha="old-sha",
            expected_digest=digest,
            write_sha="accepted-sha",
            write_accepted=True,
        )
        runtime["sha"] = "different-current-sha"
        result = reconcile_runtime_write(receipt, runtime)
        assert result["status"] == "CONFLICT"
        assert result["write_attributed"] is False
        assert result.get("automatic_retry") is not True


class TestRecoveryRevalidation:
    def test_candidate_changed_after_preflight_is_blocked_before_save(self):
        current_cp = default_checkpoint()
        current = {
            "status": "CONFIRMED",
            "sha": "0" * 40,
            "checkpoint": current_cp,
            "integrity": checkpoint_integrity_report(current_cp),
        }

        selected_cp = default_checkpoint()
        selected_cp["aion"]["priority"] = "selected candidate"
        selected = {
            "status": "CONFIRMED",
            "revision": "a" * 40,
            "checkpoint": selected_cp,
            "integrity": checkpoint_integrity_report(selected_cp),
            "digest": checkpoint_source_digest(selected_cp),
        }

        rebound_cp = default_checkpoint()
        rebound_cp["aion"]["priority"] = "different historical content"
        rebound = {
            "status": "CONFIRMED",
            "revision": "a" * 40,
            "checkpoint": rebound_cp,
            "integrity": checkpoint_integrity_report(rebound_cp),
            "digest": checkpoint_source_digest(rebound_cp),
        }

        with patch(
            "atlasquant_aion_recovery.load_checkpoint_revision",
            return_value=rebound,
        ), patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint"
        ) as save:
            result = restore_checkpoint_revision(
                selected,
                current,
                cfg(token="x"),
                approved=True,
            )

        assert result["status"] == "BLOCKED"
        assert result["restore_confirmed"] is False
        assert result["restored_revision"] == ""
        save.assert_not_called()
