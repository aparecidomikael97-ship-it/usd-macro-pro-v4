"""A136b RED-first: four remaining generic GitHub writers deny Checkpoint Mestre.

Function bodies are AST-isolated and executed only against mocked config and
requests. No Streamlit app, runner, network, GitHub PUT or provider is executed.
"""
from __future__ import annotations

import ast
import base64
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

ROOT=Path(__file__).resolve().parents[1]
CHECKPOINT="dados/aion/checkpoint_master.json"


def isolate_function(file_name, func_name, variables):
    file=ROOT/file_name
    tree=ast.parse(file.read_text(encoding="utf-8"),filename=str(file))
    nodes=[x for x in tree.body
           if isinstance(x,ast.FunctionDef) and x.name==func_name]
    assert len(nodes)==1,(file_name,func_name)
    ns=dict(variables)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(file),"exec"),ns)
    return ns[func_name]


class OtherGenericWritersDestinationLAB(unittest.TestCase):
    def news_writer(self,filename):
        getcfg=MagicMock(return_value=("synthetic-unused","example/repo","atlasquant-runtime"))
        requests=MagicMock()
        requests.get.return_value.status_code=404
        requests.put.return_value.status_code=200
        variables={
            "pd": SimpleNamespace(DataFrame=object),
            "_gh_cfg_v1061":getcfg,
            "_gh_headers_v1061":lambda token:{"Authorization":"synthetic"},
            "requests":requests,
            "base64":base64,
            "_NEWS_VALIDATION_PATH":"dados/currency_news_validation_v1061.csv",
        }
        return (isolate_function(filename,"_gh_write_csv_v1061",variables),
                getcfg,requests)

    def autopilot_writer(self):
        requests=MagicMock()
        requests.get.return_value.status_code=404
        requests.put.return_value.status_code=200
        variables={
            "TOKEN":"synthetic-unused","REPO":"example/repo",
            "BRANCH":"atlasquant-runtime",
            "gh_headers":lambda : {"Authorization":"synthetic"},
            "requests":requests,"base64":base64,
        }
        return isolate_function("autopilot_v107.py","gh_put_bytes",variables),requests

    def check_news_blocked(self,filename,path):
        call,cfg,requests=self.news_writer(filename)
        df=MagicMock()
        ok,_=call(path,df,"synthetic")
        self.assertFalse(ok)
        cfg.assert_not_called()
        requests.get.assert_not_called()
        requests.put.assert_not_called()

    def check_autopilot_blocked(self,path):
        fn,requests=self.autopilot_writer()
        ok,_=fn(path,b"synthetic","synthetic")
        self.assertFalse(ok)
        requests.get.assert_not_called()
        requests.put.assert_not_called()

    def test_01_v1061_news_cannot_point_at_checkpoint(self):
        self.check_news_blocked("currency_news_v1061.py",CHECKPOINT)

    def test_02_v1062_news_cannot_point_at_checkpoint(self):
        self.check_news_blocked("currency_news_v1062.py",CHECKPOINT)

    def test_03_v107_news_cannot_point_at_checkpoint(self):
        self.check_news_blocked("currency_news_v107.py",CHECKPOINT)

    def test_04_news_encoded_slashes_cannot_override_target(self):
        self.check_news_blocked("currency_news_v107.py",
                                "dados%2Faion%2Fcheckpoint_master.json")

    def test_05_news_relative_traversal_cannot_override_target(self):
        self.check_news_blocked("currency_news_v1062.py",
                                "dados/x/../aion/checkpoint_master.json")

    def test_06_news_approved_csv_path_retained(self):
        call,cfg,requests=self.news_writer("currency_news_v107.py")
        df=MagicMock()
        df.to_csv.return_value="col\nvalue\n"
        ok,msg=call("dados/currency_news_validation_v1061.csv",df,"synthetic")
        self.assertTrue(ok,msg)
        cfg.assert_called_once()
        requests.put.assert_called_once()

    def test_07_autopilot_cannot_write_checkpoint(self):
        self.check_autopilot_blocked(CHECKPOINT)

    def test_08_autopilot_cannot_write_url_encoded_checkpoint(self):
        self.check_autopilot_blocked("dados%2Faion%2Fcheckpoint_master.json")

    def test_09_autopilot_cannot_write_dotdot_checkpoint(self):
        self.check_autopilot_blocked("dados/tmp/../aion/checkpoint_master.json")

    def test_10_autopilot_cannot_write_backslash_checkpoint(self):
        self.check_autopilot_blocked("dados\\aion\\checkpoint_master.json")

    def test_11_autopilot_cannot_write_query_injection(self):
        self.check_autopilot_blocked("dados/autopilot_status_v107.json?ref=main")

    def test_12_autopilot_cannot_write_nonstring_target(self):
        self.check_autopilot_blocked(None)

    def test_13_autopilot_can_still_write_known_status_path(self):
        call,requests=self.autopilot_writer()
        ok,msg=call("dados/autopilot_status_v107.json",b"{}", "synthetic")
        self.assertTrue(ok,msg)
        requests.put.assert_called_once()


if __name__=="__main__":
    unittest.main()
