"""AION V2 real HTTPS/TLS Requests integration with ephemeral local-only CA.

No real provider, cloud, tokens, FIDO2 credentials, or owner machine. Tests
bind 127.0.0.1:0 on GitHub-hosted Windows/Linux runners, create disposable
certificate keys within a TemporaryDirectory, and prohibit all external
socket.connect addresses for tested outbound operations.

Only the CI-only sealed-transport factory is patched to provide a temporary
trusted CA path; the adapter's production transport remains TLS-verifying.
Plaintext #1141 tests continue unchanged as regressions.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import tempfile
from threading import Lock, Thread
from unittest.mock import patch
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

import atlasquant_aion_provider as provider

LOCAL_IP="127.0.0.1"
TEST_RESPONSE=b'{"id":"resp_ci_tls_only","output_text":"TLS local"}'


def _pem_cert(root:Path,*,hostname:str,kind:str)->dict[str,Path]:
    """Generate short-lived private CA and signed server leaf, CI only."""
    now=datetime.now(timezone.utc)
    ca_key=ec.generate_private_key(ec.SECP256R1())
    ca_subject=x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME,"AION temporary local TLS test CA")
    ])
    ca_cert=(
        x509.CertificateBuilder()
        .subject_name(ca_subject).issuer_name(ca_subject)
        .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(days=1))
        .not_valid_after(now+timedelta(days=3))
        .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True,content_commitment=False,
            key_encipherment=False,data_encipherment=False,
            key_agreement=False,key_cert_sign=True,crl_sign=True,
            encipher_only=False,decipher_only=False
        ),critical=True)
        .sign(ca_key,hashes.SHA256())
    )
    server_key=ec.generate_private_key(ec.SECP256R1())
    subject=x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME,hostname),
    ])
    if kind=="wrong_san":
        san=x509.SubjectAlternativeName([x509.DNSName("different-host.invalid")])
    else:
        san=x509.SubjectAlternativeName([
            x509.IPAddress(ipaddress.ip_address(LOCAL_IP))
        ])
    if kind=="expired":
        start,end=now-timedelta(days=4),now-timedelta(days=2)
    else:
        start,end=now-timedelta(minutes=3),now+timedelta(days=2)
    leaf=(
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start).not_valid_after(end)
        .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
        .add_extension(san,critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                       critical=False)
        .add_extension(x509.KeyUsage(
            digital_signature=True,content_commitment=False,
            key_encipherment=False,data_encipherment=False,
            key_agreement=False,key_cert_sign=False,crl_sign=False,
            encipher_only=False,decipher_only=False
        ),critical=True)
        .sign(ca_key,hashes.SHA256())
    )
    path_ca=root/"ephemeral_ca.crt"
    path_cert=root/"ephemeral_server.crt"
    path_key=root/"ephemeral_server.key"
    path_ca.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    path_cert.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    path_key.write_bytes(server_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    return {"ca":path_ca,"cert":path_cert,"key":path_key}


class _TLSOnlyServer(ThreadingHTTPServer):
    allow_reuse_address=True
    daemon_threads=True
    def __init__(self,ssl_context:ssl.SSLContext):
        super().__init__((LOCAL_IP,0),_TLSHandler)
        self.lock=Lock()
        self.received=[]
        self.reply_status=200
        self.drop_after_receipt=False
        self.socket=ssl_context.wrap_socket(self.socket,server_side=True)

    def observe(self,method:str,path:str,body:bytes):
        with self.lock:self.received.append((method,path,body))

    def snapshot(self):
        with self.lock:return list(self.received)


class _TLSHandler(BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def log_message(self,fmt,*args):
        return None  # never echo synthetic Authorization
    def do_POST(self):
        amount=int(self.headers.get("Content-Length") or 0)
        data=self.rfile.read(amount)
        self.server.observe("POST",self.path,data)
        if self.server.drop_after_receipt:
            try:self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            self.connection.close()
            return
        status=self.server.reply_status
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(TEST_RESPONSE)))
        if 300<=status<400:
            self.send_header("Location","https://different-host.invalid/evil")
        if status==503:self.send_header("Retry-After","0")
        self.end_headers()
        try:
            self.wfile.write(TEST_RESPONSE)
            self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError,OSError):
            pass


class LocalRealTLSTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.tmp=Path(self.temporary.name)
        self.pem=_pem_cert(self.tmp,hostname="127.0.0.1",kind="valid")
        self.server=None
        self.thread=None
        self.connections=[]
        self.values={
            "AION_MODEL_PROVIDER":"openai",
            "OPENAI_API_KEY":"fake-local-only-NOT-a-real-API-token",
            "AION_OPENAI_FAST_MODEL":"tls-fixture-fast",
            "AION_OPENAI_REASONING_MODEL":"tls-fixture-reasoning",
            "AION_OPENAI_INPUT_USD_PER_MTOK":"1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK":"2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS":"100",
            "AION_OPENAI_TIMEOUT_SECONDS":"5",
        }
        self.start_server()

    def start_server(self):
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(
            certfile=str(self.pem["cert"]),keyfile=str(self.pem["key"])
        )
        self.server=_TLSOnlyServer(context)
        self.thread=Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.endpoint=f"https://{LOCAL_IP}:{self.server.server_port}/v1/responses"

    def tearDown(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=3)
        self.temporary.cleanup()

    def change_certificate(self,kind):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.pem=_pem_cert(self.tmp,hostname="127.0.0.1",kind=kind)
        self.start_server()

    @contextmanager
    def guarded_socket(self):
        original=socket.socket.connect
        port=self.server.server_port
        expected=(LOCAL_IP,port)
        def only_loopback(s,address):
            if (type(address) is not tuple or len(address)<2
                or address[:2]!=expected):
                raise AssertionError("NON_LOOPBACK_NETWORK_FORBIDDEN")
            self.connections.append(tuple(address[:2]))
            return original(s,address)
        with patch.object(socket.socket,"connect",only_loopback):
            yield

    def invoke(self,*,trust_local_ca=True,expected_hash=None,approved=True):
        original_factory=provider._sealed_provider_transport
        def local_cert_authority():
            sess=original_factory()
            # The test-only CA becomes the *explicit* trust root. This does
            # not disable certificate validation, nor alter production code.
            self.assertIs(sess.trust_env,False)
            self.assertIs(sess.verify,True)
            sess.verify=str(self.pem["ca"])
            return sess

        with patch.object(provider,"OPENAI_RESPONSES_URL",self.endpoint):
            preview=provider.preview_openai_request_binding(
                "Pedido sintético TLS sem provedor",
                lane="EXTERNAL_FAST",values=self.values,
            )
            self.assertEqual(preview["state"],"BOUND_REQUEST_PREVIEW_UNTRUSTED")
            with self.guarded_socket(), \
                 patch.object(provider,"_PAID_MODEL_DISPATCH_HARD_DENY",False):
                if trust_local_ca:
                    with patch.object(
                        provider,"_sealed_provider_transport",
                        local_cert_authority,
                    ):
                        return provider.execute_openai_answer(
                            "Pedido sintético TLS sem provedor",
                            lane="EXTERNAL_FAST",
                            budget={"allow_paid":True,"monthly_limit_usd":10},
                            external_feature_enabled=True,
                            request_approved=approved,
                            values=self.values,
                            expected_request_sha256=(
                                preview["request_sha256"]
                                if expected_hash is None else expected_hash
                            ),
                        )
                return provider.execute_openai_answer(
                    "Pedido sintético TLS sem provedor",
                    lane="EXTERNAL_FAST",
                    budget={"allow_paid":True,"monthly_limit_usd":10},
                    external_feature_enabled=True,
                    request_approved=approved,
                    values=self.values,
                    expected_request_sha256=(
                        preview["request_sha256"]
                        if expected_hash is None else expected_hash
                    ),
                )

    def assert_one_wire_post(self):
        requests_seen=self.server.snapshot()
        self.assertEqual(len(requests_seen),1,requests_seen)
        meth,path,body=requests_seen[0]
        self.assertEqual((meth,path),("POST","/v1/responses"))
        self.assertEqual(json.loads(body),{
            "model":"tls-fixture-fast",
            "input":"Pedido sintético TLS sem provedor",
            "max_output_tokens":100,
        })
        self.assertEqual(self.connections,[(LOCAL_IP,self.server.server_port)])

    def test_real_https_valid_temporary_ca_and_ip_san_one_post(self):
        r=self.invoke()
        self.assertEqual(r["state"],"ANSWER_READY")
        self.assertEqual(r["response_id"],"resp_ci_tls_only")
        self.assert_one_wire_post()

    def test_untrusted_self_signed_ca_rejected_without_http_body(self):
        r=self.invoke(trust_local_ca=False)
        self.assertEqual(r["state"],"PROVIDER_NETWORK_ERROR")
        self.assertTrue(r["called"])
        self.assertEqual(r["reason"],"SSLError")
        self.assertEqual(self.server.snapshot(),[])
        self.assertEqual(len(self.connections),1)

    def test_wrong_ip_san_even_when_ca_trusted_fails_closed(self):
        self.change_certificate("wrong_san")
        r=self.invoke()
        self.assertEqual(r["state"],"PROVIDER_NETWORK_ERROR")
        self.assertEqual(r["reason"],"SSLError")
        self.assertEqual(self.server.snapshot(),[])
        self.assertEqual(len(self.connections),1)

    def test_expired_certificate_even_when_ca_trusted_fails_closed(self):
        self.change_certificate("expired")
        r=self.invoke()
        self.assertEqual(r["state"],"PROVIDER_NETWORK_ERROR")
        self.assertEqual(r["reason"],"SSLError")
        self.assertEqual(self.server.snapshot(),[])
        self.assertEqual(len(self.connections),1)

    def test_https_307_and_308_with_cross_origin_location_are_not_followed(self):
        for status in (307,308):
            with self.subTest(status=status):
                self.server.reply_status=status
                self.connections.clear()
                with self.server.lock:self.server.received.clear()
                r=self.invoke()
                self.assertEqual(r["state"],"PROVIDER_REDIRECT_BLOCKED")
                self.assertEqual(r["http_status"],status)
                self.assert_one_wire_post()

    def test_https_503_with_retry_after_not_replayed(self):
        self.server.reply_status=503
        r=self.invoke()
        self.assertEqual(r["state"],"PROVIDER_HTTP_ERROR")
        self.assertEqual(r["http_status"],503)
        self.assert_one_wire_post()

    def test_https_disconnect_after_receipt_remains_unknown_no_second_post(self):
        self.server.drop_after_receipt=True
        r=self.invoke()
        self.assertEqual(r["state"],"PROVIDER_NETWORK_ERROR")
        self.assertTrue(r["called"])
        self.assert_one_wire_post()

    def test_https_mismatched_hash_and_missing_approval_zero_connections(self):
        for kw in ({"approved":False},{"expected_hash":"0"*64}):
            with self.subTest(kw=kw):
                self.connections.clear()
                r=self.invoke(**kw)
                self.assertFalse(r["called"])
                self.assertEqual(self.connections,[])
                self.assertEqual(self.server.snapshot(),[])

    def test_temporary_certificates_are_not_production_credentials(self):
        self.assertEqual(self.server.server_address[0],LOCAL_IP)
        self.assertNotIn("api.openai.com",self.endpoint)
        self.assertTrue(self.pem["ca"].exists())
        self.assertTrue(self.pem["key"].exists())
        self.assertTrue(self.endpoint.startswith("https://127.0.0.1:"))


if __name__=="__main__":
    unittest.main()
