"""A183 LAB-only Python socket guard with Windows asyncio self-pipe support.

External socket connect and connect_ex stay forbidden. Windows asyncio creates
a local loopback socketpair because its event loop uses a self-pipe. Allow only
the synchronous, IPv4 127.0.0.1 connection made inside the stdlib socketpair
function on the same ContextVar context. No arbitrary local connections are
permitted outside that narrow scope, and no remote address is permitted ever.

This is a process-level Python test harness, NOT an operating-system firewall;
subprocesses do not inherit these Python patches. Never use in production.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
import socket
import sys
from unittest.mock import Mock, patch


def _deny(*_args, **_kwargs):
    raise AssertionError("LAB network forbidden")


@contextmanager
def canonical_lab_socket_guard():
    """Block Python socket egress while preserving the OS-internal self-pipe."""
    original_connect = socket.socket.connect
    original_socketpair = socket.socketpair
    in_stdlib_pair = ContextVar("aion_lab_inside_stdlib_socketpair", default=False)

    def guarded_connect(sock, address):
        # Windows' stdlib socketpair fall-back creates its own transient local
        # listener, then a single synchronous loopback connect in this context.
        # The ContextVar is task/thread local; normal local/remote destinations
        # remain blocked, even if another thread is active simultaneously.
        if (
            sys.platform == "win32"
            and in_stdlib_pair.get()
            and sock.family == socket.AF_INET
            and sock.type == socket.SOCK_STREAM
            and isinstance(address, tuple)
            and len(address) == 2
            and address[0] == "127.0.0.1"
            and type(address[1]) is int
            and 0 < address[1] < 65536
        ):
            return original_connect(sock, address)
        return _deny()

    def scoped_socketpair(*args, **kwargs):
        token = in_stdlib_pair.set(True)
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            in_stdlib_pair.reset(token)

    with ExitStack() as stack:
        if sys.platform == "win32":
            stack.enter_context(patch.object(socket.socket, "connect", guarded_connect))
            stack.enter_context(patch.object(socket, "socketpair", scoped_socketpair))
        else:
            # Byte-for-byte semantic policy of the prior Unix A183 harness.
            stack.enter_context(patch.object(
                socket.socket, "connect",
                Mock(side_effect=AssertionError("LAB network forbidden")),
            ))
        stack.enter_context(patch.object(
            socket.socket, "connect_ex",
            Mock(side_effect=AssertionError("LAB network forbidden")),
        ))
        stack.enter_context(patch.object(
            socket, "create_connection",
            Mock(side_effect=AssertionError("LAB network forbidden")),
        ))
        yield
