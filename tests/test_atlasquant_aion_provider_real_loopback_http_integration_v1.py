"""REAL Requests/urllib3 POST over TCP loopback: NO EXTERNAL NETWORK.

CI-only integration fixture. Server binds only 127.0.0.1:0 and uses a
synthetic, noncredential API key. Every socket.connect made by the tested
request is guarded: attempts outside the exact loopback host/port raise.
Never contact a vendor, test real credentials, or infer billing/owner trust.

Unlike the earlier Session.send mocks, these tests actually exercise:
Requests Session -> HTTPAdapter -> urllib3 -> TCP socket -> local HTTP server.
The inspected service is ephemeral test-only. No new production listener.
"""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread, Lock
from unittest.mock import patch
import json
import socket
import time
import unittest

import requests
import atlasquant_aion_provider as provider

_LOCAL_HOST="127.0.0.1"
_RESPONSE={"id":"resp_local_ci_only","output_text":"resposta local simulada"}


class _LoopbackFixture(ThreadingHTTPServer):
    allow_reuse_address=True
    daemon_threads=True
    def __init__(self,handler):
        super().__init__((_LOCAL_HOST,0),handler)
        self.history=[]
        self.lock=Lock()
        self.reply_status=200
        self.drop_after_receipt=False
        self.sleep_before_reply=0.0

    def append_request(self,item):
        with self.lock:
            self.history.append(item)

    def observed(self):
        with self.lock:
            return list(self.history)


class _Handler(BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"

    def log_message(self,fmt,*args):
        # Never log even fixture Authorization headers.
        return None

    def do_GET(self):
        self._serve()

    def do_POST(self):
        self._serve()

    def _serve(self):
        length=int(self.headers.get("Content-Length") or 0)
        body=self.rfile.read(length) if length else b""
        self.server.append_request({
            "method":self.command,
            "path":self.path,
            "body":body,
            "host":self.headers.get("Host"),
            "content_type":self.headers.get("Content-Type"),
            "has_authorization":bool(self.headers.get("Authorization")),
        })
        if self.server.drop_after_receipt:
            try:self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            self.connection.close()
            return
        if self.server.sleep_before_reply:
            time.sleep(self.server.sleep_before_reply)
        status=self.server.reply_status
        body=json.dumps(
            _RESPONSE,separators=(",",":")
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        if 300<=status<400:
            self.send_header(
                "Location",
                f"http://{_LOCAL_HOST}:{self.server.server_port}/redirect-trap",
            )
        if status in (429,503):
            self.send_header("Retry-After","0")
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError,OSError):
            # A timed-out client must not cause a noisy test-server crash.
            pass


class RealLoopbackNoRetryTests(unittest.TestCase):
    def setUp(self):
        self.server=_LoopbackFixture(_Handler)
        self.thread=Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.target=f"http://{_LOCAL_HOST}:{self.server.server_port}/v1/responses"
        self.example={
            "AION_MODEL_PROVIDER":"openai",
            "OPENAI_API_KEY":"fixture-key-NOT-valid-for-any-vendor",
            "AION_OPENAI_FAST_MODEL":"local-test-model",
            "AION_OPENAI_REASONING_MODEL":"local-reasoning-model",
            "AION_OPENAI_INPUT_USD_PER_MTOK":"1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK":"2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS":"500",
            # provider_config enforces minimum 5-second network timeout
            "AION_OPENAI_TIMEOUT_SECONDS":"5",
        }
        self.connected=[]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    @contextmanager
    def _loopback_only_connect(self):
        original=socket.socket.connect
        port=self.server.server_port
        captured=self.connected

        def restricted(sock,address):
            if (not isinstance(address,tuple)
                or len(address)<2
                or address[0]!=_LOCAL_HOST
                or address[1]!=port):
                raise AssertionError("external socket connection forbidden by CI")
            captured.append(address)
            return original(sock,address)

        with patch.object(socket.socket,"connect",restricted):
            yield

    def invoke(self,*,approved=True,budget_allowed=True,
               expected_sha=None,session=None,
               endpoint=None,external=True):
        """Patches only static endpoint constant to exact locally bound URL."""
        with patch.object(provider,"OPENAI_RESPONSES_URL",
                          self.target if endpoint is None else endpoint):
            review=provider.preview_openai_request_binding(
                "Solicitação sintética ao loopback",
                lane="EXTERNAL_FAST",values=self.example,
            )
            self.assertEqual(
                review["state"],"BOUND_REQUEST_PREVIEW_UNTRUSTED",
            )
            sha=review["request_sha256"] if expected_sha is None else expected_sha
            with self._loopback_only_connect(), \
                 patch.object(provider,"_PAID_MODEL_DISPATCH_HARD_DENY",False):
                result=provider.execute_openai_answer(
                    "Solicitação sintética ao loopback",
                    lane="EXTERNAL_FAST",
                    budget={"allow_paid":budget_allowed,"monthly_limit_usd":10},
                    external_feature_enabled=external,
                    request_approved=approved,
                    values=self.example,
                    expected_request_sha256=sha,
                    session=session,
                )
        return result

    def expected_single_wire_request(self):
        r=self.server.observed()
        self.assertEqual(len(r),1,r)
        self.assertEqual(r[0]["method"],"POST")
        self.assertEqual(r[0]["path"],"/v1/responses")
        self.assertEqual(r[0]["content_type"],"application/json")
        self.assertEqual(r[0]["host"],f"{_LOCAL_HOST}:{self.server.server_port}")
        self.assertTrue(r[0]["has_authorization"])
        self.assertEqual(json.loads(r[0]["body"]),{
            "model":"local-test-model",
            "input":"Solicitação sintética ao loopback",
            "max_output_tokens":500,
        })
        self.assertEqual(self.connected,[(_LOCAL_HOST,self.server.server_port)])

    def test_success_real_tcp_requests_no_mock_send_one_post_only(self):
        result=self.invoke()
        self.assertEqual(result["state"],"ANSWER_READY")
        self.assertEqual(result["response_id"],"resp_local_ci_only")
        self.expected_single_wire_request()

    def test_redirect_301_302_303_307_308_not_followed_on_real_tcp(self):
        for status in (301,302,303,307,308):
            with self.subTest(status=status):
                self.server.reply_status=status
                self.connected.clear()
                with self.server.lock:self.server.history.clear()
                o=self.invoke()
                self.assertEqual(o["state"],"PROVIDER_REDIRECT_BLOCKED")
                self.assertEqual(o["http_status"],status)
                self.expected_single_wire_request()
                self.assertFalse(any(
                    x["path"]=="/redirect-trap" for x in self.server.observed()
                ))

    def test_error_408_429_503_504_still_one_post_despite_retry_after(self):
        for status in (408,429,503,504):
            with self.subTest(status=status):
                self.server.reply_status=status
                self.connected.clear()
                with self.server.lock:self.server.history.clear()
                o=self.invoke()
                self.assertEqual(o["state"],"PROVIDER_HTTP_ERROR")
                self.assertEqual(o["http_status"],status)
                self.expected_single_wire_request()

    def test_disconnect_after_server_read_is_unknown_not_retried(self):
        self.server.drop_after_receipt=True
        result=self.invoke()
        self.assertEqual(result["state"],"PROVIDER_NETWORK_ERROR")
        self.assertTrue(result["called"])
        self.expected_single_wire_request()
        # No valid HTTP reply; provider side *could* already have processed.
        self.assertNotIn("ANSWER_READY",repr(result))
        self.assertNotIn("fixture-key",repr(result))

    def test_timeout_after_server_read_is_not_retried(self):
        # Minimum 5 sec timeout is enforced by provider config.
        self.server.sleep_before_reply=5.5
        result=self.invoke()
        self.assertEqual(result["state"],"PROVIDER_NETWORK_ERROR")
        self.assertTrue(result["called"])
        self.expected_single_wire_request()

    def test_all_preflight_blocks_before_any_tcp_connect(self):
        cases=(
            {"approved":False},
            {"budget_allowed":False},
            {"external":False},
            {"expected_sha":"0"*64},
            {"session":requests.Session()},
        )
        try:
            for case in cases:
                with self.subTest(case=str(list(case))):
                    self.connected.clear()
                    with self.server.lock:self.server.history.clear()
                    result=self.invoke(**case)
                    self.assertFalse(result["called"])
                    self.assertEqual(self.connected,[])
                    self.assertEqual(self.server.observed(),[])
        finally:
            cases[-1]["session"].close()

    def test_endpoint_changed_after_preflight_blocks_before_wire(self):
        with patch.object(provider,"OPENAI_RESPONSES_URL",self.target):
            sha=provider.preview_openai_request_binding(
                "Solicitação sintética ao loopback",lane="EXTERNAL_FAST",
                values=self.example,
            )["request_sha256"]
        result=self.invoke(
            expected_sha=sha,
            endpoint=self.target.replace("/v1/responses","/v1/other"),
        )
        self.assertEqual(result["state"],"BLOCKED_REQUEST_BINDING")
        self.assertEqual(self.server.observed(),[])
        self.assertEqual(self.connected,[])

    def test_no_default_external_provider_endpoint_ever_contacted(self):
        # Even valid-looking approvals lack owner/witness legitimacy;
        # the local test deliberately substitutes an exact 127.0.0.1 origin.
        self.assertNotIn("api.openai.com",self.target)
        self.assertEqual(self.server.server_address[0],_LOCAL_HOST)
        self.assertIn("127.0.0.1",self.target)


if __name__=="__main__":
    unittest.main()
