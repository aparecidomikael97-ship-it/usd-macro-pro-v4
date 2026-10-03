"""Standalone loopback preview. No production shell imports or authentication changes.

python atlasquant_aion_chat_ui.py --data-dir /private/local/path
Identity is fixed by the trusted host; production requires an authenticated Scope.
"""
import argparse
import base64
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import parse_qs, urlparse

from aion_chat.attachments import AttachmentPolicy
from aion_chat.context import build_conversation_context, compact_conversation
from aion_chat.models import Scope
from aion_chat.service import ChatService
from aion_chat.store import SQLiteChatStore

ASSETS = Path(__file__).parent / "aion_chat" / "web"
MAX_BODY = 28 * 1024 * 1024


def render_chat_html(token=""):
    return (ASSETS / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", token)


def make_handler(service, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _reply(self, value, status=200, mime="application/json"):
            data = json.dumps(value, ensure_ascii=False).encode() if mime == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def _guard(self, api=False):
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected:
                raise PermissionError("loopback host required")
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + expected:
                raise PermissionError("origin rejected")
            if api and not secrets.compare_digest(self.headers.get("X-Aion-Token", ""), token):
                raise PermissionError("session token required")

        def do_GET(self):
            try:
                self._guard()
                path = urlparse(self.path).path
                if path == "/":
                    return self._reply(render_chat_html(token).encode(), mime="text/html")
                if path in {"/chat.css", "/chat.js"}:
                    mime = "text/css" if path.endswith(".css") else "application/javascript"
                    return self._reply((ASSETS / path[1:]).read_bytes(), mime=mime)
                self._guard(api=True)
                q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                if path == "/api/conversations":
                    return self._reply(asdict(service.store.list_conversations(service.scope, cursor=q.get("cursor"),
                        query=q.get("query", ""), archived=q.get("archived") == "true")))
                if path == "/api/messages":
                    return self._reply(asdict(service.store.list_messages(service.scope, q["cid"], cursor=q.get("cursor"), newest_first=True)))
                if path == "/api/context":
                    return self._reply(build_conversation_context(service.store, service.scope, q["cid"], query=q.get("query", "")))
                self._reply({"error": "not found"}, 404)
            except PermissionError:
                self._reply({"error": "access denied"}, 403)
            except (LookupError, ValueError, KeyError, TypeError):
                self._reply({"error": "invalid or unavailable request"}, 400)
            except (sqlite3.Error, OSError):
                self._reply({"error": "local storage unavailable"}, 503)

        def do_POST(self):
            try:
                self._guard(api=True)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    return self._reply({"error": "request exceeds technical byte budget"}, 413)
                body = json.loads(self.rfile.read(length))
                path, cid = urlparse(self.path).path, body.get("cid")
                if path == "/api/create":
                    value = service.store.create_conversation(service.scope, body.get("title") or "Nova conversa")
                elif path == "/api/send":
                    value = service.send(cid, body.get("content", ""), body.get("attachments"), action=body.get("action"))
                elif path == "/api/attach":
                    value = service.attach(cid, body["name"], base64.b64decode(body["data"], validate=True), body.get("mime", ""))
                elif path == "/api/archive":
                    value = service.store.archive_conversation(service.scope, cid)
                elif path == "/api/cancel":
                    value = service.cancel(cid, body["message_id"])
                elif path == "/api/feedback":
                    value = service.feedback(cid, body["message_id"], body["value"])
                elif path == "/api/compact":
                    cp, summary = compact_conversation(service.store, service.scope, cid)
                    return self._reply({"checkpoint": asdict(cp), "summary": asdict(summary)})
                else:
                    return self._reply({"error": "not found"}, 404)
                self._reply(asdict(value))
            except PermissionError:
                self._reply({"error": "access denied"}, 403)
            except (LookupError, ValueError, KeyError, TypeError):
                self._reply({"error": "invalid or unavailable request"}, 400)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--attachment-max-bytes", type=int, default=20 * 1024 * 1024)
    args = parser.parse_args()
    store = SQLiteChatStore(args.data_dir / "chat.sqlite3")
    service = ChatService(store, Scope("local-preview", "local-preview", "default"), args.data_dir / "attachments",
                          AttachmentPolicy(max_bytes=args.attachment_max_bytes))
    server = HTTPServer(("127.0.0.1", args.port), make_handler(service, secrets.token_urlsafe(32)))
    print(f"AION local preview: http://127.0.0.1:{server.server_port} — model NOT_CONNECTED", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        store.close()


if __name__ == "__main__":
    main()
