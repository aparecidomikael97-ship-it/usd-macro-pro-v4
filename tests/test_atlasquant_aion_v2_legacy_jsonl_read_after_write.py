"""Offline verification tests for actual Flight/Research/Shadow GitHub JSONL writes.

No live GitHub API or paid provider traffic. All network methods patched.
"""
from __future__ import annotations
import ast
import base64
import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests
from legacy_protocol_reference_v1 import install_historical_write_protocol_fixture

import atlasquant_flight_recorder_store as flight
import atlasquant_research_evidence_store as research
import atlasquant_shadow_store as shadow
from atlasquant_aion_v2_legacy_github_contents_readback import (
    GitHubReadAfterWriteUnconfirmedError, verify_legacy_jsonl_readback,
)

ROOT=Path(__file__).resolve().parents[1]
TEST_TOKEN="SYNTHETIC_NON_REAL"
ARGS={"repo":"example/repository","branch":"atlasquant-runtime",
      "token":TEST_TOKEN,"retry_conflict_once":True}
CASES=(
    (flight,"persist_records","_fetch_remote",
     [{"decision_id":"synthetic-flight-1","signal":"long"}],
     "serialize_records","records"),
    (research,"persist_research_evidence","_fetch",
     [{"record_id":"synthetic-research-1","strategy":"reference"}],
     "serialize_evidence_records","records"),
    (shadow,"persist_shadow_samples","_fetch",
     [{"sample_id":"synthetic-shadow-1","score":4}],
     "serialize_samples","samples"),
)

def git_blob_sha(text:str)->str:
    raw=text.encode("utf-8")
    return hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\x00"+raw).hexdigest()

def response(status:int,sha:str):
    return SimpleNamespace(status_code=status,
                           json=lambda:{"content":{"sha":sha}},
                           raise_for_status=lambda:None)

class LegacyJSONLReadAfterWriteTests(unittest.TestCase):
    def setUp(self):
        install_historical_write_protocol_fixture(self)

    def test_each_real_writer_requires_two_reads_and_matching_blob_before_saved(self):
        for module,writer,reader,data,serializer,field in CASES:
            with self.subTest(store=module.__name__):
                text=getattr(module,serializer)(data)
                sha=git_blob_sha(text)
                with patch.object(module,reader,side_effect=[([], ""), (data,sha)]) as get, \
                     patch.object(module.requests,"put",return_value=response(201,sha)) as put:
                    outcome=getattr(module,writer)(data,**ARGS)
                self.assertTrue(outcome["ok"],outcome)
                self.assertEqual(outcome["reason"],"SAVED")
                self.assertEqual(outcome[field],1)
                self.assertIs(outcome["verified"],True)
                self.assertFalse(outcome["remote_durability_certified"])
                self.assertFalse(outcome["independent_response_origin_verified"])
                self.assertEqual(outcome["blob_sha"],sha)
                self.assertEqual(outcome["content_sha256"],hashlib.sha256(text.encode("utf-8")).hexdigest())
                self.assertIs(outcome["safe_to_retry"],False)
                self.assertEqual(get.call_count,2)
                self.assertEqual(put.call_count,1)
                self.assertIs(put.call_args.kwargs["allow_redirects"],False)
                self.assertEqual(base64.b64decode(put.call_args.kwargs["json"]["content"]).decode("utf-8"),text)
                self.assertEqual(put.call_args.args[0].split("/contents/")[0],"https://api.github.com/repos/example/repository")

    def test_forged_success_sha_is_unknown_and_never_read_as_verified(self):
        for module,writer,reader,data,serializer,_ in CASES:
            with self.subTest(store=module.__name__):
                with patch.object(module,reader,return_value=([],"")) as get, \
                     patch.object(module.requests,"put",return_value=response(200,"b"*40)) as put:
                    outcome=getattr(module,writer)(data,**ARGS)
                self.assertEqual(outcome["reason"],"UNKNOWN_OUTCOME",outcome)
                self.assertIs(outcome["reconciliation_required"],True)
                self.assertIs(outcome["safe_to_retry"],False)
                self.assertEqual(outcome["error"],"GitHubReadAfterWriteUnconfirmedError")
                self.assertEqual(get.call_count,1)
                self.assertEqual(put.call_count,1)
                self.assertNotIn(TEST_TOKEN,str(outcome))

    def test_post_write_readback_mismatch_is_unknown_no_second_put(self):
        for module,writer,reader,data,serializer,_ in CASES:
            with self.subTest(store=module.__name__):
                text=getattr(module,serializer)(data)
                sha=git_blob_sha(text)
                with patch.object(module,reader,side_effect=[([],""),(data,"c"*40)]) as get, \
                     patch.object(module.requests,"put",return_value=response(201,sha)) as put:
                    outcome=getattr(module,writer)(data,**ARGS)
                self.assertFalse(outcome["ok"])
                self.assertEqual(outcome["reason"],"UNKNOWN_OUTCOME")
                self.assertEqual(outcome["write_outcome"],"UNKNOWN")
                self.assertTrue(outcome["reconciliation_required"])
                self.assertEqual((get.call_count,put.call_count),(2,1))

    def test_post_write_readback_data_different_same_claimed_sha_is_unknown(self):
        for module,writer,reader,data,serializer,_ in CASES:
            with self.subTest(store=module.__name__):
                sha=git_blob_sha(getattr(module,serializer)(data))
                changed=[dict(data[0])]
                changed[0]["EXTRA_TAMPER"]=True
                with patch.object(module,reader,side_effect=[([], ""),(changed,sha)]) as get, \
                     patch.object(module.requests,"put",return_value=response(200,sha)) as put:
                    outcome=getattr(module,writer)(data,**ARGS)
                self.assertEqual(outcome["reason"],"UNKNOWN_OUTCOME")
                self.assertEqual((get.call_count,put.call_count),(2,1))

    def test_post_write_readback_timeout_is_unknown_not_authorized_to_retry(self):
        for module,writer,reader,data,serializer,_ in CASES:
            with self.subTest(store=module.__name__):
                sha=git_blob_sha(getattr(module,serializer)(data))
                with patch.object(module,reader,side_effect=[([], ""),requests.Timeout("secret "+TEST_TOKEN)]) as get, \
                     patch.object(module.requests,"put",return_value=response(200,sha)) as put:
                    outcome=getattr(module,writer)(data,**ARGS)
                self.assertEqual(outcome["reason"],"UNKNOWN_OUTCOME")
                self.assertTrue(outcome["reconciliation_required"])
                self.assertIs(outcome["safe_to_retry"],False)
                self.assertNotIn(TEST_TOKEN,str(outcome))
                self.assertEqual((get.call_count,put.call_count),(2,1))

    def test_malformed_put_body_cannot_become_saved_even_if_http_201(self):
        for module,writer,reader,data,serializer,_ in CASES:
            with self.subTest(store=module.__name__):
                forged=SimpleNamespace(status_code=201,json=lambda:{"content":{}})
                with patch.object(module,reader,return_value=([],"")) as get, \
                     patch.object(module.requests,"put",return_value=forged) as put:
                    outcome=getattr(module,writer)(data,**ARGS)
                self.assertEqual(outcome["reason"],"UNKNOWN_OUTCOME")
                self.assertEqual((get.call_count,put.call_count),(1,1))

    def test_helper_blocks_bad_input_no_remote_read(self):
        callback=lambda: self.fail("must not call network reader")
        for status in (199,204,302,409,422):
            with self.subTest(status=status):
                with self.assertRaises(GitHubReadAfterWriteUnconfirmedError):
                    verify_legacy_jsonl_readback(response=response(status,"a"*40),
                        expected_text='{"x":1}\n',readback=callback,serialize=lambda rows:"")
        with self.assertRaises(GitHubReadAfterWriteUnconfirmedError):
            verify_legacy_jsonl_readback(response=response(201,"a"*40),
                expected_text="",readback=callback,serialize=lambda rows:"")

    def test_real_source_each_saved_path_invokes_readback_verifier(self):
        for module,writer,reader,data,serializer,_ in CASES:
            path=ROOT/(module.__name__+".py")
            tree=ast.parse(path.read_text("utf-8"))
            funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==writer]
            self.assertEqual(len(funcs),1)
            calls=[n for n in ast.walk(funcs[0]) if isinstance(n,ast.Call)
                   and isinstance(n.func,ast.Name)
                   and n.func.id=="verify_legacy_jsonl_readback"]
            self.assertEqual(len(calls),1)
            self.assertEqual({k.arg for k in calls[0].keywords},
                {"response","expected_text","readback","serialize"})
            serializers=[x.value.id for x in calls[0].keywords if x.arg=="serialize"
                         and isinstance(x.value,ast.Name)]
            self.assertEqual(serializers,[serializer])
            imports=[n for n in tree.body if isinstance(n,ast.ImportFrom)
                     and n.module=="atlasquant_aion_v2_legacy_github_contents_readback"]
            self.assertEqual(len(imports),1)
if __name__=="__main__":
    unittest.main()
