"""G100 safety regression: allow only stdlib Windows asyncio's local self-pipe.

Process-level Python guard, never a network firewall. These tests use only
synthetic sockets and loopback self-pipe; no endpoint/provider/real SEND.
"""
import asyncio
import socket
import sys
import unittest

from scripts.aion_a190_scoped_socketpair_guard import canonical_lab_socket_guard


class G100WindowsInternalSocketpairGuard(unittest.TestCase):
    def assert_denied(self, callback):
        with self.assertRaisesRegex(AssertionError, "LAB network forbidden"):
            callback()

    def test_01_external_ipv4_connect_is_forbidden(self):
        with canonical_lab_socket_guard():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                self.assert_denied(lambda: sock.connect(("8.8.8.8", 443)))
        print("G100_EXTERNAL_CONNECT=DENIED")

    def test_02_arbitrary_loopback_connect_is_also_forbidden(self):
        with canonical_lab_socket_guard():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                self.assert_denied(lambda: sock.connect(("127.0.0.1", 1)))
        print("G100_ARBITRARY_LOOPBACK=DENIED")

    def test_03_connect_ex_and_create_connection_are_always_denied(self):
        with canonical_lab_socket_guard():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                self.assert_denied(lambda: sock.connect_ex(("127.0.0.1", 1)))
            self.assert_denied(lambda: socket.create_connection(("8.8.8.8", 443)))
        print("G100_SECONDARY_CONNECT_METHODS=DENIED")

    def test_04_stdlib_self_pipe_round_trip_remains_functional(self):
        with canonical_lab_socket_guard():
            first, second = socket.socketpair()
            try:
                first.settimeout(2)
                second.settimeout(2)
                first.sendall(b"G100-internal")
                self.assertEqual(second.recv(32), b"G100-internal")
            finally:
                first.close()
                second.close()
        print("G100_STDLIB_SOCKETPAIR=INTERNAL_ONLY_PASS")

    def test_05_asyncio_event_loop_can_open_and_close_under_guard(self):
        with canonical_lab_socket_guard():
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(asyncio.sleep(0, result="G100"))
                self.assertEqual(result, "G100")
            finally:
                loop.close()
        print("G100_ASYNCIO_EVENT_LOOP=LOCAL_PASS")


if __name__ == "__main__":
    unittest.main()
