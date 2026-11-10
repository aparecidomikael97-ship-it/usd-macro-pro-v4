"""Windows Time diagnostics, all synthetic/local and read-only."""
from __future__ import annotations

import unittest

from atlasquant_windows_time_diagnostic_lab import (
    QUERIES, diagnose_windows_time_readonly_lab as diagnose,
)
from test_atlasquant_mt5_xauusd_one_step_lab import ENGLISH_GOOD, PORTUGUESE_GOOD

SERVICE_GOOD = """SERVICE_NAME: w32time
        TYPE               : 20  WIN32_SHARE_PROCESS
        STATE              : 4  RUNNING
"""
SERVICE_STOPPED = SERVICE_GOOD.replace("4  RUNNING", "1  STOPPED")
PEERS_GOOD = "#Peers: 1\nPeer: time.windows.com,0x9\nState: Active"
PEERS_NONE = "#Peers: 0"
CONFIG_GOOD = "NtpServer: time.windows.com,0x9 (Local)\nType: NTP (Local)"
CONFIG_NONE = "NtpServer: (Local)\nType: NoSync (Local)"


def inputs(*, service=SERVICE_GOOD, status=ENGLISH_GOOD,
           source="time.windows.com,0x9", peers=PEERS_GOOD,
           config=CONFIG_GOOD):
    return {
        "service": (0, service), "status": (0, status),
        "source": (0, source), "peers": (0, peers),
        "configuration": (0, config),
    }


class WindowsTimeReadOnlyDiagnosticTests(unittest.TestCase):
    def no_trading_or_mutation(self, result):
        for key in ("independent_utc_attestation", "mt5_or_broker_accessed",
                    "settings_changed", "firewall_changed", "trade_authorized",
                    "ntp_udp123_or_dns_failure_proven"):
            self.assertIs(result[key], False, key)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual(result["new_cost_brl"], 0)

    def test_only_windows_service_queries_not_modifying_commands(self):
        self.assertEqual(set(QUERIES), {
            "service", "status", "source", "peers", "configuration"})
        for cmd in QUERIES.values():
            self.assertTrue(cmd[:2] in (("w32tm", "/query"),
                                         ("sc.exe", "query")))
        self.assertNotIn("/resync", str(QUERIES))
        self.assertNotIn("/config", str(QUERIES).replace("/configuration", ""))

    def test_synchronized_windows_status_still_not_utc_attestation(self):
        r = diagnose(inputs())
        self.assertEqual(r["state"], "LAB_W32TIME_OS_SYNC_CANDIDATE_UNATTESTED")
        self.assertTrue(r["os_sync_candidate"])
        self.assertTrue(r["service_running"])
        self.assertEqual(r["peers_reported"], 1)
        self.assertTrue(r["configured_ntp_peer_present"])
        self.no_trading_or_mutation(r)

    def test_ptbr_status_synced(self):
        r = diagnose(inputs(status=PORTUGUESE_GOOD, source="pool.ntp.org,0x9"))
        self.assertEqual(r["state"], "LAB_W32TIME_OS_SYNC_CANDIDATE_UNATTESTED")
        self.no_trading_or_mutation(r)

    def test_service_stopped_overrides_any_other_hint(self):
        r = diagnose(inputs(service=SERVICE_STOPPED))
        self.assertEqual(r["state"], "LAB_W32TIME_SERVICE_STOPPED_CANDIDATE")
        self.assertIs(r["service_running"], False)
        self.no_trading_or_mutation(r)

    def test_no_ntp_peers_and_local_clock_suggests_configuration_review(self):
        r = diagnose(inputs(status="Leap Indicator: 3\nSource: Local CMOS Clock",
                            source="Local CMOS Clock", peers=PEERS_NONE,
                            config=CONFIG_NONE))
        self.assertEqual(r["state"], "LAB_W32TIME_NO_PEER_CONFIGURATION_CANDIDATE")
        self.assertFalse(r["os_sync_candidate"])
        self.assertEqual(r["peers_reported"], 0)
        self.no_trading_or_mutation(r)

    def test_configured_peers_but_source_local_means_check_reachability(self):
        r = diagnose(inputs(status="Leap Indicator: 3\nSource: Local CMOS Clock",
                            source="Local CMOS Clock"))
        self.assertEqual(r["state"], "LAB_W32TIME_STUCK_ON_LOCAL_CLOCK_CANDIDATE")
        self.assertFalse(r["ntp_udp123_or_dns_failure_proven"])

    def test_peers_present_without_good_sync_suggests_network_or_remote(self):
        status = ENGLISH_GOOD.replace("Leap Indicator: 0", "Leap Indicator: 3")
        r = diagnose(inputs(status=status))
        self.assertEqual(r["state"], "LAB_W32TIME_PEERS_PRESENT_SYNC_FAILURE_CANDIDATE")
        self.assertIn("UDP123", r["reason"])
        self.no_trading_or_mutation(r)

    def test_missing_service_query_returns_inconclusive(self):
        raw = inputs()
        raw["service"] = (1, "")
        r = diagnose(raw)
        self.assertEqual(r["state"], "LAB_WINDOWS_TIME_DIAG_INCONCLUSIVE")
        self.assertEqual(r["reason"], "SERVICE_STATUS_NOT_READABLE")

    def test_one_missing_required_query_is_detected(self):
        raw = inputs()
        del raw["peers"]
        r = diagnose(raw)
        self.assertEqual(r["state"], "LAB_WINDOWS_TIME_DIAG_INCONCLUSIVE")
        self.assertEqual(r["queries_ok"], [])

    def test_query_nonzero_exit_does_not_parse_stale_text(self):
        raw = inputs()
        raw["status"] = (1, ENGLISH_GOOD)
        r = diagnose(raw)
        self.assertFalse(r["os_sync_candidate"])
        self.assertNotIn("status", r["queries_ok"])
        self.assertEqual(r["state"], "LAB_W32TIME_PEERS_PRESENT_SYNC_FAILURE_CANDIDATE")

    def test_unusable_peer_output_is_not_fabricated(self):
        raw = inputs(peers="unexpected")
        r = diagnose(raw)
        self.assertIsNone(r["peers_reported"])
        self.no_trading_or_mutation(r)

    def test_invalid_raw_output_length_is_rejected(self):
        raw = inputs()
        raw["peers"] = (0, "x" * 32769)
        r = diagnose(raw)
        self.assertEqual(r["state"], "LAB_WINDOWS_TIME_DIAG_INCONCLUSIVE")

    def test_ambiguous_local_source_not_published_in_summary(self):
        host = "private-time.internal.example"
        r = diagnose(inputs(source=host, peers=f"#Peers: 1\nPeer: {host}"))
        self.assertNotIn(host, str(r))
        self.no_trading_or_mutation(r)

    def test_ptbr_peer_count_can_be_parsed(self):
        r = diagnose(inputs(peers="Nº de pares: 2\nPar: pool.ntp.org"))
        self.assertEqual(r["peers_reported"], 2)

    def test_diagnostic_never_proves_udp123_blockage_on_text_alone(self):
        cases = [inputs(), inputs(status="not synced", source="Local CMOS Clock"),
                 inputs(status=ENGLISH_GOOD.replace("30.5s", "50000s"))]
        for case in cases:
            self.assertFalse(diagnose(case)["ntp_udp123_or_dns_failure_proven"])


if __name__ == "__main__":
    unittest.main()
