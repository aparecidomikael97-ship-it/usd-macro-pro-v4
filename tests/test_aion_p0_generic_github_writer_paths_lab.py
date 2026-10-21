"""A136 RED-first: generic GitHub stores must never address Checkpoint Mestre.

No imported Streamlit app, credentials, network I/O or real requests. We compile
one isolated function AST to avoid executing UI top-level side effects.
"""
from __future__ import annotations

import ast
import base64
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


def isolated_budget_module():
    path=ROOT/"twelve_budget_v1108.py"
    tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
    cls=[n for n in tree.body
         if isinstance(n,ast.ClassDef) and n.name=="GitHubStore"]
    val=[n for n in tree.body
         if isinstance(n,ast.Assign)
         and any(isinstance(t,ast.Name) and t.id=="BUDGET_PATH" for t in n.targets)]
    assert len(cls)==1 and len(val)==1
    budget_path=ast.literal_eval(val[0].value)
    budget_error=type("BudgetUnavailable",(RuntimeError,),{})
    ns={"BUDGET_PATH":budget_path,"BudgetUnavailable":budget_error,
        "requests":MagicMock(),"base64":base64,"json":json}
    exec(compile(ast.Module(body=cls,type_ignores=[]),str(path),"exec"),ns)
    return ns["GitHubStore"],budget_path,budget_error,ns["requests"]

ROOT=Path(__file__).resolve().parents[1]
CHECKPOINT="dados/aion/checkpoint_master.json"


def isolated_feedback_helper():
    path=ROOT/"usd_macro_pro_v4_cloud.py"
    tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
    fn=[n for n in tree.body
        if isinstance(n,ast.FunctionDef) and n.name=="_github_put_bytes_v104"]
    assert len(fn)==1
    mod=ast.Module(body=fn,type_ignores=[])
    config=MagicMock(return_value=("synthetic-no-network","example/repo","atlasquant-runtime"))
    requests=MagicMock()
    requests.get.return_value.status_code=404
    requests.put.return_value.status_code=200
    namespace={"_github_cfg_v84":config,"requests":requests}
    exec(compile(mod,str(path),"exec"),namespace)
    return namespace["_github_put_bytes_v104"],config,requests


class GenericGitHubFilePathFenceLAB(unittest.TestCase):
    def setUp(self):
        self.helper,self.config,self.requests=isolated_feedback_helper()
        self.Store,self.budget_path,self.BudgetUnavailable,self.budget_requests=isolated_budget_module()

    def blocked_feedback(self,path):
        result=self.helper(path,b"synthetic","synthetic")
        self.assertEqual(result[0],False,result)
        self.config.assert_not_called()
        self.requests.get.assert_not_called()
        self.requests.put.assert_not_called()

    def test_01_feedback_helper_rejects_exact_checkpoint(self):
        self.blocked_feedback(CHECKPOINT)

    def test_02_feedback_helper_rejects_checkpoint_leading_slash(self):
        self.blocked_feedback("/"+CHECKPOINT)

    def test_03_feedback_helper_rejects_encoded_checkpoint_slashes(self):
        self.blocked_feedback("dados%2Faion%2Fcheckpoint_master.json")

    def test_04_feedback_helper_rejects_dot_dot_namespace_escape(self):
        self.blocked_feedback("dados/feedback_anexos/../aion/checkpoint_master.json")

    def test_05_feedback_helper_rejects_arbitrary_runtime_path(self):
        self.blocked_feedback("dados/aion/unexpected.json")

    def test_06_feedback_helper_rejects_url_query_or_fragment(self):
        self.blocked_feedback("dados/feedback_anexos/fake.png?ref=main")

    def test_07_feedback_helper_rejects_non_string_path(self):
        self.blocked_feedback(123)

    def test_08_feedback_helper_permits_only_genuine_attachment_shape(self):
        ok,msg=self.helper(
            "dados/feedback_anexos/20261021T200000Z_abcdef12.png",
            b"synthetic","synthetic",
        )
        self.assertTrue(ok,msg)
        self.requests.get.assert_called_once()
        self.requests.put.assert_called_once()

    def test_09_budget_constructor_cannot_use_checkpoint(self):
        with patch.object(self.budget_requests,"put") as put:
            with self.assertRaises(self.BudgetUnavailable):
                self.Store("unused","example/repo","atlasquant-runtime",path=CHECKPOINT)
        put.assert_not_called()

    def test_10_budget_path_is_not_mutable_into_checkpoint_target(self):
        store=self.Store("unused","example/repo","atlasquant-runtime")
        store.path=CHECKPOINT
        with patch.object(self.budget_requests,"put") as put:
            with self.assertRaises(self.BudgetUnavailable):
                store.save({"synthetic":True},None)
        put.assert_not_called()

    def test_11_budget_normal_path_retained(self):
        store=self.Store("unused","example/repo","atlasquant-runtime")
        self.assertEqual(store.path,self.budget_path)

    def test_12_budget_dotdot_escape_cannot_be_injected(self):
        with self.assertRaises(self.BudgetUnavailable):
            self.Store("unused","example/repo","atlasquant-runtime",
                           path="dados/x/../aion/checkpoint_master.json")

    def test_13_budget_encoded_path_cannot_be_injected(self):
        with self.assertRaises(self.BudgetUnavailable):
            self.Store("unused","example/repo","atlasquant-runtime",
                           path="dados%2Faion%2Fcheckpoint_master.json")


if __name__=="__main__":
    unittest.main()
