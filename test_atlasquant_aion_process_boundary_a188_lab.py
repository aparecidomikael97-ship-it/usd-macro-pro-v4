"""A188 LAB: IPC boundary positive cases and deliberate trust-limit counterexamples."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from labs.a188.sqlite_process_boundary_lab import BrokerLab


class A188ProcessBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="a188-process-boundary-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "lab.sqlite"
        self.broker = BrokerLab(self.path)
        self.addCleanup(self.broker.close)

    def test_real_broker_owns_db_and_exposes_no_sql_execution(self) -> None:
        self.assertNotEqual(self.broker.process.pid, None)
        self.assertFalse(hasattr(self.broker, "db"))
        resp = self.broker.request("execute_sql", sql="DROP TABLE lab_reservations")
        self.assertEqual(resp["status"], "DENIED_UNSUPPORTED_OPERATION")
        self.assertEqual(self.broker.request("count_local")["count"], 0)
        print("A188_ARBITRARY_SQL_OVER_BROKER=DENIED")

    def test_incorrect_token_is_denied_before_local_reservation(self) -> None:
        resp = self.broker.request("reserve", token="bad-token", request_id="id1", event_id="event1", payload="intent")
        self.assertEqual(resp["status"], "DENIED_UNAUTHENTICATED_LOCAL_TOKEN")
        self.assertEqual(self.broker.request("count_local")["count"], 0)
        print("A188_INVALID_LOCAL_TOKEN=DENIED")

    def test_request_id_deduplicates_only_matching_claims(self) -> None:
        args = {"request_id": "id1", "event_id": "claimed-event", "payload": "synthetic"}
        self.assertEqual(self.broker.request("reserve", **args)["status"], "RESERVED_LOCAL_ONLY")
        self.assertEqual(self.broker.request("reserve", **args)["status"], "ALREADY_RESERVED")
        self.assertEqual(self.broker.request("reserve", request_id="id1", event_id="changed", payload="synthetic")["status"], "DENIED_REQUEST_CONFLICT")
        self.assertEqual(self.broker.request("count_local")["count"], 1)
        print("A188_REQUEST_ID_CONFLICT=DENIED_LOCAL_ONLY")

    def test_ack_loss_after_durable_local_write_remains_uncertain(self) -> None:
        res = self.broker.request("reserve", request_id="id1", event_id="event1", payload="synthetic", simulate_ack_loss=True)
        self.assertEqual(res, {"status": "UNCERTAIN", "auto_resend": False})
        self.broker.close()
        with BrokerLab(self.path) as reopened:
            obs = reopened.request("lookup_local", request_id="id1")
            self.assertEqual(obs, {"status": "OBSERVED_LOCAL_UNTRUSTED", "found": True})
        print("A188_POST_COMMIT_ACK_LOSS=UNCERTAIN_ZERO_AUTO_RESEND")

    def test_second_claimed_event_id_allows_duplicate_semantic_reservation(self) -> None:
        for key in ("one", "two"):
            self.assertEqual(
                self.broker.request("reserve", request_id=key, event_id="same-claimed-event", payload="effect")["status"],
                "RESERVED_LOCAL_ONLY",
            )
        self.assertEqual(self.broker.request("count_local")["count"], 2)
        print("A188_EVENT_ID_NOT_EXTERNALLY_ATTESTED_DUPLICATE=REPRODUCED")

    def test_same_host_direct_sqlite_bypasses_ipc_guard(self) -> None:
        # The service is alive, but the file remains available to raw sqlite3.
        raw = sqlite3.connect(self.path)
        try:
            raw.execute("INSERT INTO lab_reservations VALUES(?,?,?,'RESERVED')", ("raw", "fake", "0" * 64))
            raw.commit()
        finally:
            raw.close()
        self.assertEqual(self.broker.request("count_local")["count"], 1)
        print("A188_SAME_HOST_RAW_FILE_BYPASS=REPRODUCED")

    def test_local_rollback_restores_old_history_without_external_witness(self) -> None:
        self.assertEqual(self.broker.request("reserve", request_id="first", event_id="e1", payload="intent")["status"], "RESERVED_LOCAL_ONLY")
        self.broker.close()
        before = Path(self.tmp.name) / "offline_snapshot.sqlite"
        shutil.copyfile(self.path, before)
        with BrokerLab(self.path) as second:
            self.assertEqual(second.request("reserve", request_id="second", event_id="e2", payload="intent")["status"], "RESERVED_LOCAL_ONLY")
            self.assertEqual(second.request("count_local")["count"], 2)
        # Explicit adversarial host-level restore while db is OFFLINE.
        shutil.copyfile(before, self.path)
        with BrokerLab(self.path) as restored:
            self.assertEqual(restored.request("count_local")["count"], 1)
            self.assertEqual(restored.request("lookup_local", request_id="second"),
                             {"status": "OBSERVED_LOCAL_UNTRUSTED", "found": False})
        print("A188_FULL_DB_ROLLBACK_WITHOUT_EXTERNAL_WITNESS=REPRODUCED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
