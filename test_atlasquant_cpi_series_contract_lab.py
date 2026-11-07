"""Synthetic policy tests, not market accuracy, nor authenticated official data."""
import copy
import unittest
from datetime import datetime, timezone
from atlasquant_cpi_series_contract_lab import SCHEMA, audit_cpi_series_lab

NOW = datetime(2027, 5, 10, tzinfo=timezone.utc)

def obs(currency, kind, period="2027-03", pub="2027-04-22T12:00:00Z", cap="2027-04-22T12:01:00Z"):
    return dict(currency=currency, atlasquant_series_key=f"{currency}_{kind}_CPI_YOY",
                frequency=kind, observation_period=period, value="3.7",
                published_at_utc=pub, captured_at_utc=cap,
                source_sha256="a"*64,
                source_url=("https://www.abs.gov.au/statistics/" if currency=="AUD"
                            else "https://www.stats.govt.nz/indicators/consumers-price-index-cpi/"))

def sample(aud_kind="QUARTERLY", nzd_kind="QUARTERLY"):
    return dict(schema=SCHEMA, pair="AUD/NZD", decision_at_utc="2027-05-09T12:00:00Z",
                records=[obs("AUD",aud_kind),obs("NZD",nzd_kind)])

def audit(d): return audit_cpi_series_lab(d,as_of_utc=NOW)

class PilotTests(unittest.TestCase):
    def no_signal(self,x):
        self.assertEqual(x["operational_bias"],"AGUARDAR")
        self.assertFalse(x["trade_authorized"])
        self.assertFalse(x["can_feed_live_radar"])
        self.assertFalse(x["source_independently_verified"])
        self.assertFalse(x["vintage_independently_verified"])
        self.assertIsNone(x["score_0_to_10"])
    def test_quarterly_2027_pair_metadata_only(self):
        x=audit(sample()); self.assertEqual(x["state"],"LAB_CPI_SAME_FREQUENCY_UNATTESTED");self.no_signal(x)
    def test_monthly_2027_pair_metadata_only(self):
        d=sample("MONTHLY","MONTHLY")
        for row in d["records"]: row["observation_period"]="2027-04"
        x=audit(d);self.assertEqual(x["state"],"LAB_CPI_SAME_FREQUENCY_UNATTESTED");self.no_signal(x)
    def test_mixed_frequency_not_comparable(self):
        d=sample("MONTHLY","QUARTERLY")
        d["records"][0]["observation_period"]="2027-04"
        x=audit(d); self.assertEqual(x["state"],"LAB_CPI_FREQUENCY_MISMATCH");self.no_signal(x)
    def test_series_and_currency_swap_rejected(self):
        d=sample();d["records"][0]["currency"]="NZD"
        x=audit(d);self.assertEqual(x["reason"],"SERIES_ID_FREQUENCY_CURRENCY_MISMATCH");self.no_signal(x)
    def test_period_must_end_quarter(self):
        d=sample();d["records"][1]["observation_period"]="2027-02"
        x=audit(d);self.assertEqual(x["reason"],"QUARTER_END_REQUIRED");self.no_signal(x)
    def test_nzd_monthly_before_2027_rejected(self):
        d=sample("MONTHLY","MONTHLY")
        d["records"][1]["observation_period"]="2026-12"
        x=audit(d);self.assertEqual(x["reason"],"REFERENCE_PERIOD_INVALID_FOR_SERIES");self.no_signal(x)
    def test_old_quarter_republished_today_rejected(self):
        d=sample();d["records"][1]["observation_period"]="2026-09"
        x=audit(d);self.assertEqual(x["reason"],"CPI_PERIOD_OR_RELEASE_STALE");self.no_signal(x)
    def test_future_capture_rejected(self):
        d=sample();d["records"][0]["captured_at_utc"]="2027-05-09T12:00:01Z"
        x=audit(d);self.assertEqual(x["reason"],"LOOKAHEAD_OR_CHRONOLOGY");self.no_signal(x)
    def test_future_release_rejected(self):
        d=sample();d["records"][0]["published_at_utc"]="2027-05-10T12:00:00Z"
        x=audit(d);self.assertEqual(x["reason"],"LOOKAHEAD_OR_CHRONOLOGY");self.no_signal(x)
    def test_unexpected_fields_rejected(self):
        d=sample();d["records"][0]["probability"]="90%"
        x=audit(d);self.assertEqual(x["reason"],"RECORD_FIELDS_INVALID");self.no_signal(x)
    def test_unknown_key_rejected(self):
        d=sample();d["records"][1]["atlasquant_series_key"]="NZD_CPI_ANYTHING"
        x=audit(d);self.assertEqual(x["reason"],"UNKNOWN_SERIES_KEY");self.no_signal(x)
    def test_bad_url_rejected(self):
        d=sample();d["records"][0]["source_url"]="https://evil.test/?abs.gov.au"
        x=audit(d);self.assertEqual(x["reason"],"SOURCE_URL_FORMAT_INVALID");self.no_signal(x)
    def test_bad_sha_rejected(self):
        d=sample();d["records"][0]["source_sha256"]="a"*63
        x=audit(d);self.assertEqual(x["reason"],"SOURCE_HASH_FORMAT_INVALID");self.no_signal(x)
    def test_duplicate_currency_rejected(self):
        d=sample();d["records"][1]=copy.deepcopy(d["records"][0])
        x=audit(d);self.assertEqual(x["reason"],"DUPLICATE_CURRENCY");self.no_signal(x)
    def test_bad_numeric_not_exposed(self):
        d=sample();d["records"][1]["value"]="NaN"
        x=audit(d);self.assertEqual(x["reason"],"VALUE_FORMAT_INVALID");self.no_signal(x)
    def test_invalid_pair_not_fx_scanner(self):
        d=sample();d["pair"]="EUR/USD"
        x=audit(d);self.assertEqual(x["reason"],"UNSUPPORTED_SCHEMA_OR_PAIR");self.no_signal(x)
    def test_clock_naive_invalid(self):
        x=audit_cpi_series_lab(sample(),as_of_utc=datetime(2027,5,10));self.assertEqual(x["reason"],"DECISION_CLOCK_INVALID");self.no_signal(x)
    def test_missing_two_currencies(self):
        d=sample();d["records"].pop()
        x=audit(d);self.assertEqual(x["reason"],"TWO_SOURCES_REQUIRED");self.no_signal(x)
    def test_value_not_a_score(self):
        x=audit(sample());self.assertNotIn("value",str(x["coverage"]));self.no_signal(x)

if __name__=="__main__": unittest.main(verbosity=2)
