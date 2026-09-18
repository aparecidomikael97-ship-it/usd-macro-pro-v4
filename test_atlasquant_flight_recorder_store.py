import base64
import unittest
from unittest.mock import patch

from atlasquant_flight_recorder_store import (
    merge_unique_records,
    parse_records,
    persist_records,
    serialize_records,
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


class AtlasQuantFlightRecorderStoreTests(unittest.TestCase):
    def row(self,fp="a",did="1"):
        return {"_fingerprint":fp,"decision_id":did,"asset":"EUR/USD"}

    def test_roundtrip_jsonl(self):
        rows=[self.row("a","1"),self.row("b","2")]
        self.assertEqual(parse_records(serialize_records(rows)),rows)

    def test_malformed_jsonl_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_records('{"ok":1}\nnot-json\n')

    def test_duplicate_fingerprint_is_not_added(self):
        rows,added=merge_unique_records([self.row("a","1")],[self.row("a","2")])
        self.assertEqual(added,0)
        self.assertEqual(len(rows),1)

    def test_decision_id_is_fallback_key(self):
        a={"decision_id":"x","asset":"EUR/USD"}
        b={"decision_id":"x","asset":"GBP/USD"}
        rows,added=merge_unique_records([a],[b])
        self.assertEqual(added,0)
        self.assertEqual(len(rows),1)

    def test_same_decision_id_deduplicates_without_fingerprint(self):
        a={"decision_id":"d1","asset":"EUR/USD","outcome":"BLOCKED"}
        b={"decision_id":"d1","asset":"EUR/USD","outcome":"BLOCKED"}
        rows,added=merge_unique_records([a],[b],max_records=10)
        self.assertEqual(len(rows),1)
        self.assertEqual(added,0)

    def test_different_decision_ids_are_preserved(self):
        a={"decision_id":"d1","asset":"EUR/USD","outcome":"BLOCKED"}
        b={"decision_id":"d2","asset":"EUR/USD","outcome":"BLOCKED"}
        rows,added=merge_unique_records([a],[b],max_records=10)
        self.assertEqual(len(rows),2)
        self.assertEqual(added,1)

    def test_fingerprint_has_priority_over_decision_id(self):
        a={"_fingerprint":"fp1","decision_id":"d1"}
        b={"_fingerprint":"fp1","decision_id":"d2"}
        rows,added=merge_unique_records([a],[b],max_records=10)
        self.assertEqual(len(rows),1)
        self.assertEqual(added,0)

    def test_max_records_keeps_newest(self):
        existing=[self.row(str(i),str(i)) for i in range(5)]
        rows,added=merge_unique_records(existing,[self.row("5","5")],max_records=3)
        self.assertEqual(added,1)
        self.assertEqual([x["decision_id"] for x in rows],["3","4","5"])

    def test_code_branch_fails_closed_before_io(self):
        with patch("atlasquant_flight_recorder_store.requests.get") as get:
            r=persist_records([self.row()],repo="o/r",branch="main",token="t")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"],"UNSAFE_BRANCH")
        get.assert_not_called()

    def test_404_creates_new_runtime_file(self):
        put=_Resp(201,{})
        with patch("atlasquant_flight_recorder_store.requests.get",return_value=_Resp(404,{})), \
             patch("atlasquant_flight_recorder_store.requests.put",return_value=put) as p:
            r=persist_records([self.row()],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertTrue(r["ok"])
        self.assertEqual(r["added"],1)
        payload=p.call_args.kwargs["json"]
        decoded=base64.b64decode(payload["content"]).decode("utf-8")
        self.assertEqual(parse_records(decoded)[0]["decision_id"],"1")

    def test_existing_duplicate_avoids_put(self):
        raw=serialize_records([self.row()]).encode("utf-8")
        get=_Resp(200,{"sha":"abc","content":base64.b64encode(raw).decode("ascii")})
        with patch("atlasquant_flight_recorder_store.requests.get",return_value=get), \
             patch("atlasquant_flight_recorder_store.requests.put") as p:
            r=persist_records([self.row()],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertTrue(r["ok"])
        self.assertEqual(r["reason"],"ALREADY_PRESENT")
        p.assert_not_called()

    def test_conflict_retries_once(self):
        empty=_Resp(404,{})
        responses=[_Resp(409,{}),_Resp(201,{})]
        with patch("atlasquant_flight_recorder_store.requests.get",side_effect=[empty,empty]), \
             patch("atlasquant_flight_recorder_store.requests.put",side_effect=responses) as p:
            r=persist_records([self.row()],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertTrue(r["ok"])
        self.assertEqual(p.call_count,2)


if __name__=="__main__":
    unittest.main()
