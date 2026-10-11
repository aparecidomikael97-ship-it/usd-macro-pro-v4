import base64
import hashlib
import unittest
from unittest.mock import patch

from atlasquant_shadow_store import (
    merge_unique_samples,
    parse_samples,
    persist_shadow_samples,
    serialize_samples,
)


class _Resp:
    def __init__(self,status=200,payload=None):
        self.status_code=status
        self._payload=payload or {}
    def json(self):
        return self._payload
    def raise_for_status(self):
        if self.status_code>=400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _blob_sha(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()


def _contents(raw):
    return _Resp(200,{"sha":_blob_sha(raw),"encoding":"base64",
                      "content":base64.b64encode(raw).decode("ascii")})


class AtlasQuantShadowStoreTests(unittest.TestCase):
    def row(self,sid="a",pair="EUR/USD"):
        return {"sample_id":sid,"champion":{"pair":pair},"challenger":{"pair":pair}}

    def test_roundtrip_jsonl(self):
        rows=[self.row("a"),self.row("b","GBP/USD")]
        self.assertEqual(parse_samples(serialize_samples(rows)),rows)

    def test_malformed_jsonl_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_samples('{"ok":1}\nnot-json\n')

    def test_duplicate_sample_id_is_not_added(self):
        rows,added=merge_unique_samples([self.row("a")],[self.row("a","GBP/USD")])
        self.assertEqual(added,0)
        self.assertEqual(len(rows),1)

    def test_max_samples_keeps_newest(self):
        existing=[self.row(str(i)) for i in range(5)]
        rows,added=merge_unique_samples(existing,[self.row("5")],max_samples=3)
        self.assertEqual(added,1)
        self.assertEqual([x["sample_id"] for x in rows],["3","4","5"])

    def test_remote_shadow_writer_hard_denies_every_legacy_scenario_without_io(self):
        # No caller-controlled arguments or synthetic HTTP fixture may enable
        # this legacy remote writer before an independent durable claim/CAS.
        scenarios=[
            ("code_branch", "main", "o/r", "t"),
            ("runtime_branch", "atlasquant-runtime", "o/r", "t"),
            ("missing_config", "atlasquant-runtime", "", ""),
            ("missing_token", "atlasquant-runtime", "o/r", ""),
        ]
        for name,branch,repo,token in scenarios:
            with self.subTest(name=name), \
                 patch("atlasquant_shadow_store.requests.get") as get, \
                 patch("atlasquant_shadow_store.requests.put") as put:
                result=persist_shadow_samples(
                    [self.row()],repo=repo,branch=branch,token=token,
                    retry_conflict_once=True,
                )
                self.assertFalse(result["ok"])
                self.assertEqual(result["reason"],"HARD_DENIED")
                self.assertEqual(result["added"],0)
                self.assertFalse(result["safe_to_retry"])
                self.assertTrue(result["reconciliation_required"])
                get.assert_not_called()
                put.assert_not_called()

    def test_remote_shadow_writer_never_executes_mocked_404_409_or_corrupt_payload(self):
        # A 404 create, 409 retry or corrupt remote read is unreachable:
        # fail closed before either GET or PUT, not a mocked pseudo-success.
        for status in (404,409,500):
            with self.subTest(status=status), \
                 patch("atlasquant_shadow_store.requests.get",return_value=_Resp(status)) as get, \
                 patch("atlasquant_shadow_store.requests.put",return_value=_Resp(201)) as put:
                result=persist_shadow_samples(
                    [self.row()],repo="o/r",branch="atlasquant-runtime",token="t",
                )
                self.assertEqual(result["reason"],"HARD_DENIED")
                self.assertFalse(result["safe_to_retry"])
                get.assert_not_called()
                put.assert_not_called()

if __name__=="__main__":
    unittest.main()
