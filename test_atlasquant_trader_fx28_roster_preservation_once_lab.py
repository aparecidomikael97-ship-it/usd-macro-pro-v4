"""All input forecasts are fabricated TEST claims; never trading evidence."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    prepare_window_witness_body_lab as prepare,
)
from atlasquant_trader_fx28_roster_preservation_once_lab import (
    SCHEMA, inspect_prepared_fx28_roster_lab as inspect,
    store_canonical_fx28_roster_once_lab as store,
)
from test_atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    make_claim,
)

class Fx28LocalRosterPreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.call = make_claim()
        self.prepared_at = self.call.github_witness.created_at
        self.now = self.prepared_at + timedelta(minutes=1)
        self.original = prepare(
            horizon=self.call.horizon,
            start_at=self.call.start_at,
            end_at=self.call.end_at,
            forecast_roster=self.call.forecast_roster,
            prepared_at=self.prepared_at,
        )
        assert self.original["state"] == "LAB_WITNESS_BODY_PREPARED_NOT_POSTED"

    def path(self, filename):
        return Path(self.tmp.name)/"AtlasQuant"/"LAB"/(
            "frozen_fx28_forecast_rosters")/filename

    def pure(self, prepared=None, *, at=None, issued=None):
        return inspect(prepared=self.original if prepared is None else prepared,
                       prepared_at_utc=self.prepared_at if issued is None else issued,
                       inspected_at_utc=self.now if at is None else at)

    def save(self, prepared=None, *, at=None, issued=None, allow=True, root=None):
        return store(
            prepared=self.original if prepared is None else prepared,
            prepared_at_utc=self.prepared_at if issued is None else issued,
            inspected_at_utc=self.now if at is None else at,
            local_appdata=self.tmp.name if root is None else root,
            allow_write=allow)

    def safe(self, r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for key in ("trade_authorized","publishable","live_alert_allowed",
                    "worker_enabled","scheduler_enabled",
                    "github_comment_posted","github_first_seen_independently_attested",
                    "publisher_time_independently_attested",
                    "model_and_macro_vintages_authenticated",
                    "independent_28_forecasts_authenticated",
                    "real_price_verification_completed",
                    "can_count_as_real_issued_forecasts"):
            self.assertFalse(r[key],key)
        self.assertIsNone(r["verified_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual(r["network_requests"],0)
        self.assertEqual(r["new_cost_brl"],0)
        self.assertIn(r["local_file_write_count"],(0,1))

    def test_01_pure_packet_has_28_exact_bytes_but_no_disk_custody(self):
        r=self.pure()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_CANONICAL_ROSTER_PREPARED_NOT_STORED_NO_GO")
        self.assertEqual(r["pairs_in_exact_recoverable_source"],28)
        self.assertEqual(r["canonical_roster_sha256"],
                         self.original["forecast_roster_sha256"])
        self.assertEqual(r["bytes_in_exact_recoverable_source"],
                         len(self.original["canonical_forecast_json"]))
        self.assertFalse(r["source_original_persisted_locally_claim_only"])
        self.assertFalse(r["source_bytes_replayed_and_hash_checked"])
        self.assertFalse((Path(self.tmp.name)/"AtlasQuant").exists())

    def test_02_default_store_has_no_implicit_file_write(self):
        r=self.save(allow=False)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "EXPLICIT_LOCAL_PRESERVATION_OPT_IN_REQUIRED")
        self.assertEqual(r["local_file_write_count"],0)
        self.assertFalse((Path(self.tmp.name)/"AtlasQuant").exists())

    def test_03_explicit_write_once_and_readback_exact_roster_bytes(self):
        r=self.save()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_LOCAL_CANONICAL_ROSTER_STORED_REPLAYED_NO_GO")
        self.assertEqual(r["local_file_write_count"],1)
        self.assertTrue(r["local_file_created_exclusively"])
        self.assertTrue(r["source_original_persisted_locally_claim_only"])
        self.assertTrue(r["source_bytes_replayed_and_hash_checked"])
        self.assertEqual(r["pairs_in_exact_recoverable_source"],28)
        raw=self.path(r["filename_in_lab_only"]).read_bytes()
        self.assertEqual(raw,
                         self.original["canonical_forecast_json"].encode("ascii"))
        self.assertEqual(sha256(raw).hexdigest(),r["canonical_roster_sha256"])
        self.assertEqual(len(json.loads(raw)["pairs"]),28)

    def test_04_same_window_refuses_second_write_even_if_identical(self):
        first=self.save()
        old=self.path(first["filename_in_lab_only"]).read_bytes()
        second=self.save()
        self.safe(second)
        self.assertEqual(second["state"],
                         "LAB_FX28_LOCAL_CANONICAL_ROSTER_BLOCKED")
        self.assertEqual(second["reason"],
                         "WINDOW_FILE_ALREADY_EXISTS_NEVER_OVERWRITE")
        self.assertEqual(second["local_file_write_count"],0)
        self.assertEqual(self.path(first["filename_in_lab_only"]).read_bytes(),old)

    def test_05_different_digest_same_window_cannot_erase_original(self):
        first=self.save()
        old=self.path(first["filename_in_lab_only"]).read_bytes()
        altered=self.change_one_pair_direction(self.original)
        rejected=self.save(altered)
        self.safe(rejected)
        self.assertEqual(rejected["reason"],
                         "WINDOW_FILE_ALREADY_EXISTS_NEVER_OVERWRITE")
        self.assertEqual(self.path(first["filename_in_lab_only"]).read_bytes(),old)

    def test_06_caller_changed_json_without_rehash_is_rejected(self):
        bad=deepcopy(self.original)
        bad["canonical_forecast_json"]=bad["canonical_forecast_json"].replace(
            '"direction_claim":"UP"','"direction_claim":"DOWN"',1)
        r=self.pure(bad)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_LOCAL_CANONICAL_ROSTER_BLOCKED")
        self.assertEqual(r["reason"],"CANONICAL_ROSTER_SHA_MISMATCH")

    def change_one_pair_direction(self, prepared):
        changed=deepcopy(prepared)
        obj=json.loads(changed["canonical_forecast_json"])
        first=obj["pairs"][0]
        first["direction_claim"]="DOWN" if first["direction_claim"]=="UP" else "UP"
        first["abstain_reason"]=None
        return self._repack(changed,obj)

    def _repack(self, original, payload):
        out=deepcopy(original)
        canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),
                             ensure_ascii=True)
        digest=sha256(canonical.encode("ascii")).hexdigest()
        old=out["forecast_roster_sha256"]
        out["canonical_forecast_json"]=canonical
        out["forecast_roster_sha256"]=digest
        out["body"]=out["body"].replace("roster_sha256="+old,
                                        "roster_sha256="+digest)
        return out

    def test_07_changed_direction_with_rehashed_canonical_bytes_is_structural_only(self):
        modified=self.change_one_pair_direction(self.original)
        r=self.pure(modified)
        self.safe(r)
        self.assertEqual(r["pairs_in_exact_recoverable_source"],28)
        self.assertNotEqual(r["canonical_roster_sha256"],
                            self.original["forecast_roster_sha256"])
        self.assertFalse(r["can_count_as_real_issued_forecasts"])

    def test_08_duplicate_or_unknown_pair_fails_even_with_rehashed_digest(self):
        for mutation in ("duplicate","unknown","missing"):
            with self.subTest(mutation=mutation):
                obj=json.loads(self.original["canonical_forecast_json"])
                if mutation=="duplicate":
                    obj["pairs"][1]["pair"]=obj["pairs"][0]["pair"]
                elif mutation=="unknown":
                    obj["pairs"][0]["pair"]="XAU/USD"
                else:
                    obj["pairs"].pop()
                bad=self._repack(self.original,obj)
                r=self.pure(bad)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_LOCAL_CANONICAL_ROSTER_BLOCKED")

    def test_09_future_or_post_window_forecast_always_rejected(self):
        for issue in (self.call.start_at,self.call.start_at+timedelta(minutes=1)):
            with self.subTest(issue=issue):
                obj=json.loads(self.original["canonical_forecast_json"])
                obj["pairs"][0]["forecast_issued_claim_utc"]=issue.strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                bad=self._repack(self.original,obj)
                self.safe(self.pure(bad))
                self.assertEqual(self.pure(bad)["state"],
                                 "LAB_FX28_LOCAL_CANONICAL_ROSTER_BLOCKED")

    def test_10_wrong_prepared_or_actual_clock_blocks(self):
        for t in (None,self.now.replace(tzinfo=None),
                  self.call.start_at,self.call.start_at+timedelta(seconds=1)):
            with self.subTest(t=t):
                r=self.pure(at=t) if t is not None else inspect(
                    prepared=self.original,
                    prepared_at_utc=self.prepared_at,inspected_at_utc=None)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_LOCAL_CANONICAL_ROSTER_BLOCKED")

    def test_11_wrong_flags_block_before_file_creation(self):
        for key in ("body_posted_on_github","external_precommit_verified",
                    "canonical_forecast_payload_retained_externally"):
            with self.subTest(key=key):
                tampered=deepcopy(self.original)
                tampered[key]=True
                r=self.save(tampered)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_LOCAL_CANONICAL_ROSTER_BLOCKED")
                self.assertFalse((Path(self.tmp.name)/"AtlasQuant").exists())

    def test_12_wrong_hash_only_body_or_noncanonical_json_blocks(self):
        for key,badval in (("body","## fake\n"+self.original["body"]),
                           ("canonical_forecast_json",
                            self.original["canonical_forecast_json"]+"\n")):
            with self.subTest(key=key):
                bad=deepcopy(self.original)
                bad[key]=badval
                self.assertEqual(self.pure(bad)["state"],
                                 "LAB_FX28_LOCAL_CANONICAL_ROSTER_BLOCKED")

    def test_13_invalid_root_relative_or_missing_refuses_disk_write(self):
        for root in ("","relative",True,"/does-not-exist-2026"):
            with self.subTest(root=root):
                r=self.save(root=root)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_LOCAL_CANONICAL_ROSTER_BLOCKED")
                self.assertFalse(r["local_file_created_exclusively"])

    def test_14_symlinked_atlasquant_root_never_written(self):
        base=Path(self.tmp.name)
        (base/"destination").mkdir()
        (base/"AtlasQuant").symlink_to(base/"destination",
                                     target_is_directory=True)
        r=self.save()
        self.safe(r)
        self.assertEqual(r["reason"],"LOCAL_STORAGE_ROOT_UNSAFE_OR_UNAVAILABLE")
        self.assertFalse(r["local_file_created_exclusively"])
        self.assertEqual(list((base/"destination").iterdir()),[])

    def test_15_existing_file_named_for_window_never_overwritten(self):
        path=self.path("20261115T220000Z_D1.json")
        path.parent.mkdir(parents=True)
        path.write_bytes(b"prior-window-data")
        r=self.save()
        self.safe(r)
        self.assertEqual(r["reason"],"WINDOW_FILE_ALREADY_EXISTS_NEVER_OVERWRITE")
        self.assertEqual(path.read_bytes(),b"prior-window-data")

    def test_16_partial_fsync_failure_keeps_immutable_file_for_manual_review(self):
        with patch(
            "atlasquant_trader_fx28_roster_preservation_once_lab.os.fsync",
            side_effect=OSError("simulated crash before durable flush"),
        ):
            r=self.save()
        self.safe(r)
        self.assertEqual(r["reason"],
                         "PARTIAL_LOCAL_FILE_REQUIRES_MANUAL_REVIEW")
        self.assertEqual(r["local_file_write_count"],1)
        self.assertTrue(r["local_file_created_exclusively"])
        self.assertTrue(self.path(r["filename_in_lab_only"]).exists())
        second=self.save()
        self.assertEqual(second["reason"],
                         "WINDOW_FILE_ALREADY_EXISTS_NEVER_OVERWRITE")

    def test_17_readback_mismatch_is_no_go_even_if_file_was_created(self):
        with patch("atlasquant_trader_fx28_roster_preservation_once_lab.Path.read_bytes",
                   return_value=b"tampered"):
            r=self.save()
        self.safe(r)
        self.assertEqual(r["reason"],"LOCAL_WRITE_READBACK_HASH_MISMATCH")
        self.assertFalse(r["source_bytes_replayed_and_hash_checked"])

    def test_18_weekly_window_separate_file_never_collides_daily(self):
        day=self.save()
        other=make_claim(horizon="W1",comment_id=999123)
        prep=prepare(
            horizon=other.horizon,start_at=other.start_at,end_at=other.end_at,
            forecast_roster=other.forecast_roster,
            prepared_at=other.github_witness.created_at)
        week=store(
            prepared=prep,
            prepared_at_utc=other.github_witness.created_at,
            inspected_at_utc=other.github_witness.created_at+
                             timedelta(minutes=1),
            local_appdata=self.tmp.name,allow_write=True)
        self.safe(week)
        self.assertEqual(week["state"],
                         "LAB_FX28_LOCAL_CANONICAL_ROSTER_STORED_REPLAYED_NO_GO")
        self.assertNotEqual(week["filename_in_lab_only"],
                            day["filename_in_lab_only"])
        self.assertTrue(self.path(week["filename_in_lab_only"]).exists())
        self.assertTrue(self.path(day["filename_in_lab_only"]).exists())

    def test_19_only_structure_not_macro_prices_or_predictions_verified(self):
        saved=self.save()
        self.safe(saved)
        self.assertFalse(saved["github_comment_posted"])
        self.assertFalse(saved["independent_28_forecasts_authenticated"])
        self.assertFalse(saved["model_and_macro_vintages_authenticated"])
        self.assertFalse(saved["can_count_as_real_issued_forecasts"])
        self.assertFalse(saved["real_price_verification_completed"])
        self.assertIsNone(saved["verified_accuracy"])
        self.assertTrue(saved["github_anchor_body"].startswith(
            "ATLASQUANT_FX28_NY17_WINDOW_PRE_EVENT_COMMITMENT_LAB_V1"))

    def test_20_pure_input_not_mutated(self):
        before=deepcopy(self.original)
        result=self.pure()
        self.safe(result)
        self.assertEqual(before,self.original)

if __name__=="__main__":
    unittest.main()
