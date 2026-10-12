"""Fail-closed Windows IANA time zone regression for the AION greeting.

Run in an environment provisioned from requirements.txt. The test deliberately
fails when a Windows interpreter lacks tzdata; it never silently falls back to
UTC, a fixed offset or a simulated timezone database.
"""
from datetime import datetime, timedelta
from importlib import metadata
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from packaging.requirements import Requirement


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT = 'tzdata==2026.3; sys_platform == "win32"'


class AionWindowsTimezoneRequirementTests(unittest.TestCase):
    def test_tzdata_is_pinned_and_only_requested_on_windows(self):
        lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        entries = [line.strip() for line in lines if line.strip().split(";", 1)[0].strip().startswith("tzdata")]
        self.assertEqual(entries, [REQUIREMENT])
        requirement = Requirement(entries[0])
        self.assertEqual(requirement.name, "tzdata")
        self.assertEqual(str(requirement.specifier), "==2026.3")
        self.assertTrue(requirement.marker.evaluate({"sys_platform": "win32"}))
        self.assertFalse(requirement.marker.evaluate({"sys_platform": "linux"}))

    def test_cuiaba_and_utc_resolve_with_real_iana_data(self):
        if sys.platform == "win32":
            self.assertEqual(metadata.version("tzdata"), "2026.3")
        cuiaba = datetime(2026, 10, 11, 22, tzinfo=ZoneInfo("America/Cuiaba"))
        utc = datetime(2026, 10, 11, 22, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(cuiaba.utcoffset(), timedelta(hours=-4))
        self.assertEqual(utc.utcoffset(), timedelta(0))

    def test_nonexistent_zone_is_not_silently_replaced(self):
        with self.assertRaises(ZoneInfoNotFoundError):
            ZoneInfo("AION/Definitely_Not_A_Zone")


if __name__ == "__main__":
    unittest.main()
