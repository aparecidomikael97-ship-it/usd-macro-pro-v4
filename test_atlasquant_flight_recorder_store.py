"""Historical Flight Recorder transport protocol tests -- synthetic only.

The actual production writer is HARD_DENIED. Legacy CAS/HTTP behavior below is
reconstructed from reviewed unreachable source only inside this network-blocked
test case. No runtime gate or environment knob is changed.
"""
import ast
from contextlib import ExitStack
from pathlib import Path
import atlasquant_flight_recorder_store as _flight_store
import base64
import hashlib
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


def _blob_sha(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()


def _contents(raw):
    return _Resp(200,{"sha":_blob_sha(raw),"encoding":"base64",
                      "content":base64.b64encode(raw).decode("ascii")})


class AtlasQuantFlightRecorderStoreTests(unittest.TestCase):
    def setUp(self):
        # Isolate the historical protocol from the production HARD_DENIED
        # writer. All unmocked real sockets/HTTP are blocked.
        stack=ExitStack()
        self.addCleanup(stack.close)
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "requests.sessions.Session.request"):
            stack.enter_context(patch(target,side_effect=AssertionError("REAL_NETWORK_FORBIDDEN")))
        stack.enter_context(patch("atlasquant_private_read_gate_v1.require_private_read",return_value=None))
        stack.enter_context(patch("atlasquant_legacy_private_resource_gate_v1.require_legacy_private_remote_resource",return_value=None))
        source=Path(_flight_store.__file__).read_text("utf-8")
        module=ast.parse(source)
        functions=[n for n in module.body if isinstance(n,ast.FunctionDef)
                   and n.name=="persist_records"]
        if len(functions)!=1:
            raise AssertionError("Legacy Flight Recorder writer source changed")
        fn=functions[0]
        if len(fn.body)<2 or not isinstance(fn.body[0],ast.Return):
            raise AssertionError("Production HARD_DENIED guard missing")
        if "HARD_DENIED" not in (ast.get_source_segment(source,fn.body[0]) or ""):
            raise AssertionError("Writer no longer hard denied")
        if not isinstance(fn.body[1],ast.Try):
            raise AssertionError("Historic CAS protocol changed; manual review required")
        fn.body=fn.body[1:]
        ns=dict(vars(_flight_store))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),
                     str(_flight_store.__file__),"exec"),ns)
        global persist_records
        original=persist_records
        persist_records=ns["persist_records"]
        self.addCleanup(lambda: globals().__setitem__("persist_records",original))

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
        raw=serialize_records([self.row()]).encode("utf-8")
        put=_Resp(201,{"content":{"sha":_blob_sha(raw)}})
        with patch("atlasquant_flight_recorder_store.requests.get",side_effect=[_Resp(404,{}),_contents(raw)]), \
             patch("atlasquant_flight_recorder_store.requests.put",return_value=put) as p:
            r=persist_records([self.row()],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertTrue(r["ok"])
        self.assertEqual(r["added"],1)
        payload=p.call_args.kwargs["json"]
        decoded=base64.b64decode(payload["content"]).decode("utf-8")
        self.assertEqual(parse_records(decoded)[0]["decision_id"],"1")

    def test_existing_duplicate_avoids_put(self):
        raw=serialize_records([self.row()]).encode("utf-8")
        get=_contents(raw)
        with patch("atlasquant_flight_recorder_store.requests.get",return_value=get), \
             patch("atlasquant_flight_recorder_store.requests.put") as p:
            r=persist_records([self.row()],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertTrue(r["ok"])
        self.assertEqual(r["reason"],"ALREADY_PRESENT")
        p.assert_not_called()

    def test_missing_configuration_avoids_remote_io(self):
        with patch("atlasquant_flight_recorder_store.requests.get") as get, patch("atlasquant_flight_recorder_store.requests.put") as put:
            r=persist_records([self.row()],repo="",branch="atlasquant-runtime",token="")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"],"NOT_CONFIGURED")
        get.assert_not_called()
        put.assert_not_called()

    def test_corrupt_remote_fails_closed_without_overwrite(self):
        corrupt=b'{"ok":1}\nnot-json\n'
        get=_contents(corrupt)
        with patch("atlasquant_flight_recorder_store.requests.get",return_value=get), patch("atlasquant_flight_recorder_store.requests.put") as put:
            r=persist_records([self.row()],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"],"CORRUPT_REMOTE")
        put.assert_not_called()

    def test_conflict_never_retries(self):
        empty=_Resp(404,{})
        responses=[_Resp(409,{}),_Resp(201,{})]
        with patch("atlasquant_flight_recorder_store.requests.get",side_effect=[empty,empty]), \
             patch("atlasquant_flight_recorder_store.requests.put",side_effect=responses) as p:
            r=persist_records([self.row()],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"],"CONFLICT")
        self.assertFalse(r["safe_to_retry"])
        self.assertTrue(r["reconciliation_required"])
        self.assertEqual(p.call_count,1)


if __name__=="__main__":
    unittest.main()
