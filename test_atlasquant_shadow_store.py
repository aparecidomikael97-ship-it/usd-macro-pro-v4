import base64
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

    def test_code_branch_fails_closed_before_io(self):
        with patch("atlasquant_shadow_store.requests.get") as get:
            r=persist_shadow_samples([self.row()],repo="o/r",branch="main",token="t")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"],"UNSAFE_BRANCH")
        get.assert_not_called()

    def test_404_creates_new_runtime_file(self):
        with patch("atlasquant_shadow_store.requests.get",return_value=_Resp(404,{})), \
             patch("atlasquant_shadow_store.requests.put",return_value=_Resp(201,{})) as p:
            r=persist_shadow_samples([self.row()],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertTrue(r["ok"])
        self.assertEqual(r["added"],1)
        decoded=base64.b64decode(p.call_args.kwargs["json"]["content"]).decode("utf-8")
        self.assertEqual(parse_samples(decoded)[0]["sample_id"],"a")

    def test_existing_duplicate_avoids_put(self):
        raw=serialize_samples([self.row()]).encode("utf-8")
        get=_Resp(200,{"sha":"abc","content":base64.b64encode(raw).decode("ascii")})
        with patch("atlasquant_shadow_store.requests.get",return_value=get), \
             patch("atlasquant_shadow_store.requests.put") as p:
            r=persist_shadow_samples([self.row()],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertTrue(r["ok"])
        self.assertEqual(r["reason"],"ALREADY_PRESENT")
        p.assert_not_called()

    def test_conflict_retries_once(self):
        with patch("atlasquant_shadow_store.requests.get",side_effect=[_Resp(404,{}),_Resp(404,{})]), \
             patch("atlasquant_shadow_store.requests.put",side_effect=[_Resp(409,{}),_Resp(201,{})]) as p:
            r=persist_shadow_samples([self.row()],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertTrue(r["ok"])
        self.assertEqual(p.call_count,2)


if __name__=="__main__":
    unittest.main()
