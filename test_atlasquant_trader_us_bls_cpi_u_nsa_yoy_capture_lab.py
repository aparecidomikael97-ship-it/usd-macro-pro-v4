"""Fully offline mocked transport tests; BLS CPI values are SYNTHETIC.

Exercises real JSON parser, local bytes archive, checksum & replay. No
requests to public BLS API in CI, no brokerage or FX directional forecast.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from contextlib import redirect_stdout
import unittest

from atlasquant_trader_us_bls_cpi_u_nsa_yoy_capture_lab import (
    SCHEMA, SERIES, URL, MAX_BYTES, _parse_original,
    capture_bls_cpi_u_nsa_original_once_lab as capture,
    replay_bls_cpi_u_nsa_original_lab as replay,
    main,
)

UTC=timezone.utc
START=datetime(2026,11,13,15,0,tzinfo=UTC)
END=START+timedelta(seconds=2)
PRE=datetime(2026,10,31,22,0,tzinfo=UTC)


def body(v2026="324.000",v2025="314.000",*,id=SERIES,with_base=True):
    data=[
        {"year":"2026","period":"M10","periodName":"October",
         "value":v2026,"footnotes":[]},
        {"year":"2026","period":"M09","periodName":"September",
         "value":"323.000","footnotes":[]},
    ]
    if with_base:
        data.append({"year":"2025","period":"M10","periodName":"October",
                     "value":v2025,"footnotes":[]})
    packet={"status":"REQUEST_SUCCEEDED","responseTime":123,"message":[],
            "Results":{"series":[{"seriesID":id,"data":data}]}}
    return json.dumps(packet,sort_keys=True,separators=(",",":")).encode("utf-8")


class Response:
    def __init__(self, content=None,status=200,url=URL,mime="application/json",
                 encoding="identity"):
        self.raw=body() if content is None else content
        self.status=status
        self.url=url
        self.headers={"Content-Type":mime,"Content-Encoding":encoding}
    def __enter__(self):
        return self
    def __exit__(self,*exc):
        return False
    def geturl(self):
        return self.url
    def read(self,n):
        assert n==MAX_BYTES+1
        return self.raw


class BLSCpiUNSAOriginalArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.get=Mock(return_value=Response())
        self.clock=Mock(side_effect=[START,END])

    def call(self,allow=True,root=None,get=None,clock=None):
        return capture(allow_one_get=allow,
                       local_appdata=self.tmp.name if root is None else root,
                       open_url=self.get if get is None else get,
                       clock=self.clock if clock is None else clock)

    def read(self,result,at=END):
        return replay(local_appdata=self.tmp.name,
                      archive_basename=result["archive_directory_basename"],
                      observed_at_utc=at)

    def directory(self,result):
        return (Path(self.tmp.name)/"AtlasQuant"/"LAB"/
                "official_macro_receipts"/result["archive_directory_basename"])

    def safe(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["series_id"],SERIES)
        self.assertEqual(r["seasonal_adjustment"],"NSA")
        self.assertEqual(r["index_unit"],"INDEX_LEVEL")
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertEqual(r["comparison"],
                         "YEAR_OVER_YEAR_FROM_TWO_MONTHLY_INDEX_LEVELS")
        self.assertIsNone(r["cpi_surprise_percentage_points"])
        self.assertIsNone(r["usd_directional_impact"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["fx28_direction_authorized"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["source_first_seen_independently_attested"])
        self.assertFalse(r["published_release_timestamp_independently_attested"])
        self.assertFalse(r["asof_historical_vintage_authenticated"])
        self.assertFalse(r["independent_pre_release_consensus_authenticated"])
        self.assertTrue(r["calculation_is_not_official_blspublished_yoy"])
        self.assertEqual(r["new_cost_brl"],0)

    def test_01_default_explicit_optin_required_no_net_no_files(self):
        r=self.call(allow=False)
        self.safe(r)
        self.assertEqual(r["http_get_attempts"],0)
        self.assertEqual(r["file_writes_attempted"],0)
        self.get.assert_not_called()
        self.assertFalse((Path(self.tmp.name)/"AtlasQuant").exists())

    def test_02_official_single_get_preserves_raw_bytes_and_receipt(self):
        r=self.call()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_US_BLS_CPI_U_NSA_YOY_LOCAL_DOCUMENT_REPLAY_NO_GO")
        self.assertTrue(r["raw_original_bytes_retained_and_replayed_local_only"])
        self.assertEqual(r["http_get_attempts"],1)
        self.assertEqual(r["file_writes_attempted"],2)
        self.assertEqual(r["index_target_level_documentary"],"324.000")
        self.assertEqual(r["index_base_level_documentary"],"314.000")
        self.assertEqual(r["calculated_yoy_pct_documentary"],"3.185")
        self.assertEqual(r["raw_body_sha256"],sha256(body()).hexdigest())
        d=self.directory(r)
        self.assertEqual((d/"original.json").read_bytes(),body())
        meta=json.loads((d/"receipt.json").read_text())
        self.assertEqual(meta["raw_sha256"],sha256(body()).hexdigest())
        self.assertEqual(meta["body_bytes"],len(body()))
        self.assertEqual(meta["url"],URL)
        self.assertEqual(meta["http_status"],200)
        req=self.get.call_args.args[0]
        self.assertEqual(req.get_method(),"GET")
        self.assertEqual(req.full_url,URL)
        self.assertEqual(self.get.call_count,1)
        self.assertEqual(self.get.call_args.kwargs["timeout"],15)

    def test_03_readonly_replay_same_numbers_and_sha_without_http(self):
        original=self.call()
        later=self.read(original,at=END+timedelta(days=1))
        self.safe(later)
        for key in ("calculated_yoy_pct_documentary",
                    "index_target_level_documentary",
                    "index_base_level_documentary",
                    "raw_body_sha256"):
            self.assertEqual(original[key],later[key])
        self.assertEqual(later["http_get_attempts"],0)
        self.assertEqual(later["file_writes_attempted"],0)
        self.get.assert_called_once()

    def test_04_unsupported_or_wrong_series_id_never_accepted(self):
        invalid=body(id="CUSR0000SA0")
        self.assertIsNone(_parse_original(invalid,END))
        r=self.call(get=Mock(return_value=Response(content=invalid)))
        self.safe(r)
        self.assertEqual(r["http_get_attempts"],1)
        self.assertEqual(r["file_writes_attempted"],0)
        self.assertFalse(r["raw_original_bytes_retained_and_replayed_local_only"])

    def test_05_missing_year_ago_no_fake_cpi_yoy(self):
        self.assertIsNone(_parse_original(body(with_base=False),END))
        r=self.call(get=Mock(return_value=Response(content=body(with_base=False))))
        self.safe(r)
        self.assertEqual(r["file_writes_attempted"],0)

    def test_06_invalid_value_or_zero_denominator_rejects(self):
        for old,new in (("324.000","NaN"),("314.000","0"),
                        ("314.000","-0.3"),("324.000","1e3"),
                        ("324.000","0"),("314.000","9999")):
            with self.subTest(old=old,new=new):
                invalid=body().replace(old.encode(),new.encode())
                self.assertIsNone(_parse_original(invalid,END))

    def test_07_duplicate_month_row_and_duplicate_json_key_rejected(self):
        raw=json.loads(body())
        rows=raw["Results"]["series"][0]["data"]
        rows.append(dict(rows[0]))
        self.assertIsNone(_parse_original(json.dumps(raw).encode(),END))
        duplicated=body().replace(
            b'"status":"REQUEST_SUCCEEDED"',
            b'"status":"REQUEST_SUCCEEDED","status":"REQUEST_SUCCEEDED"')
        self.assertIsNone(_parse_original(duplicated,END))

    def test_08_future_target_month_or_pre_release_observation_cannot_pass(self):
        self.assertIsNone(_parse_original(body(),PRE))
        bad=self.call(clock=Mock(side_effect=[PRE,END]))
        self.safe(bad)
        self.assertEqual(bad["http_get_attempts"],0)
        self.get.assert_not_called()

    def test_09_http_403_redirect_html_gzip_and_wrong_url_block(self):
        opts=[
            {"status":403}, {"status":302},
            {"url":"https://evil.invalid/CUUR0000SA0"},
            {"mime":"text/html"}, {"encoding":"gzip"},
        ]
        for kw in opts:
            with self.subTest(kw=kw):
                ret=self.call(
                    get=Mock(return_value=Response(**kw)),
                    clock=Mock(side_effect=[START,END]))
                self.safe(ret)
                self.assertEqual(ret["http_get_attempts"],1)
                self.assertEqual(ret["file_writes_attempted"],0)

    def test_10_oversized_truncated_or_api_error_never_save(self):
        for data in (
            b"x"*(MAX_BYTES+1), b"x", b"",
            body().replace(b"REQUEST_SUCCEEDED",b"REQUEST_FAILED"),
            body().replace(b'"message":[]',
                           b'"message":["some BLS warning"]'),
        ):
            with self.subTest(length=len(data)):
                r=self.call(get=Mock(return_value=Response(content=data)),
                            clock=Mock(side_effect=[START,END]))
                self.safe(r)
                self.assertEqual(r["file_writes_attempted"],0)

    def test_11_source_byte_tamper_detected_and_levels_hidden(self):
        r=self.call()
        path=self.directory(r)/"original.json"
        path.write_bytes(path.read_bytes()+b" ")
        checked=self.read(r)
        self.safe(checked)
        self.assertFalse(checked["raw_original_bytes_retained_and_replayed_local_only"])
        self.assertIsNone(checked["calculated_yoy_pct_documentary"])

    def test_12_receipt_sha_tamper_detected(self):
        r=self.call()
        path=self.directory(r)/"receipt.json"
        meta=json.loads(path.read_text())
        meta["raw_sha256"]="f"*64
        path.write_text(json.dumps(meta))
        checked=self.read(r)
        self.safe(checked)
        self.assertIsNone(checked["index_target_level_documentary"])

    def test_13_duplicate_receipt_key_rejected(self):
        r=self.call()
        path=self.directory(r)/"receipt.json"
        value=path.read_text()
        path.write_text(value[:-2]+',"http_status":200}\n')
        checked=self.read(r)
        self.safe(checked)
        self.assertFalse(checked["raw_original_bytes_retained_and_replayed_local_only"])

    def test_14_existing_archive_same_timestamp_same_sha_never_overwritten(self):
        one=self.call()
        original=(self.directory(one)/"original.json").read_bytes()
        second=self.call(clock=Mock(side_effect=[START,END]))
        self.safe(second)
        self.assertEqual(second["http_get_attempts"],1)
        self.assertEqual(second["file_writes_attempted"],0)
        self.assertEqual((self.directory(one)/"original.json").read_bytes(),original)

    def test_15_one_network_failure_never_retries(self):
        other=Mock(side_effect=OSError("simulated server failure"))
        r=self.call(get=other)
        self.safe(r)
        other.assert_called_once()
        self.assertEqual(r["http_get_attempts"],1)
        self.assertEqual(r["file_writes_attempted"],0)

    def test_16_symlink_to_outside_denies_before_network(self):
        base=Path(self.tmp.name)
        real=base/"outside"
        real.mkdir()
        (base/"AtlasQuant").symlink_to(real,target_is_directory=True)
        r=self.call()
        self.safe(r)
        self.assertEqual(r["http_get_attempts"],0)
        self.get.assert_not_called()
        self.assertEqual(list(real.iterdir()),[])

    def test_17_partial_file_write_no_auto_repair_or_backfill(self):
        with patch(
            "atlasquant_trader_us_bls_cpi_u_nsa_yoy_capture_lab.os.fsync",
            side_effect=OSError("simulated write error")
        ):
            first=self.call()
        self.safe(first)
        self.assertEqual(first["file_writes_attempted"],1)
        self.assertFalse(first["raw_original_bytes_retained_and_replayed_local_only"])
        later=self.call(clock=Mock(side_effect=[START,END]))
        self.safe(later)
        self.assertEqual(later["file_writes_attempted"],0)

    def test_18_replay_wrong_folder_name_timestamp_and_clock_denies(self):
        r=self.call()
        for bad in ("../outside","US_BLS_CPIU_NSA_X",
                    r["archive_directory_basename"]+"_suffix",""):
            with self.subTest(bad=bad):
                out=replay(local_appdata=self.tmp.name,
                           archive_basename=bad,observed_at_utc=END)
                self.safe(out)
                self.assertFalse(out["raw_original_bytes_retained_and_replayed_local_only"])
        before=self.read(r,at=START)
        self.safe(before)
        self.assertFalse(before["raw_original_bytes_retained_and_replayed_local_only"])

    def test_19_default_cli_no_hidden_get(self):
        with patch(
            "atlasquant_trader_us_bls_cpi_u_nsa_yoy_capture_lab.capture_bls_cpi_u_nsa_original_once_lab"
        ) as called:
            output=io.StringIO()
            with redirect_stdout(output):
                rc=main([])
        self.assertEqual(rc,2)
        called.assert_not_called()
        packet=json.loads(output.getvalue())
        self.safe(packet)
        self.assertEqual(packet["http_get_attempts"],0)

    def test_20_even_valid_oct_index_levels_no_forex_trade_or_cpi_surprise(self):
        r=self.call()
        self.safe(r)
        self.assertTrue(r["raw_original_bytes_retained_and_replayed_local_only"])
        self.assertEqual(r["target_month"],"2026-10")
        self.assertEqual(r["base_month"],"2025-10")
        self.assertIsNone(r["cpi_surprise_percentage_points"])
        self.assertIsNone(r["usd_directional_impact"])
        self.assertFalse(r["fx28_direction_authorized"])
        self.assertFalse(r["source_first_seen_independently_attested"])

if __name__=="__main__":
    unittest.main()
