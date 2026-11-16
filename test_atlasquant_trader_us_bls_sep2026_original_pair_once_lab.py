"""All HTTP mocked. Fictional BLS-style HTML never counts as real history."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
import json
import unittest

from atlasquant_trader_us_bls_sep2026_original_pair_once_lab import (
    SCHEMA, SPECS, _pair_digest, capture_sep2026_bls_original_pair_once_lab as capture,
    inspect_sep2026_bls_release_body_lab as parser,
    replay_sep2026_bls_original_pair_lab as replay,
)

UTC=timezone.utc
BEGIN=datetime(2026,11,15,22,0,tzinfo=UTC)


def body(kind: str, *, headline: str | None = None):
    s=SPECS[kind]
    if kind=="CPI":
        statement=(
            "The Consumer Price Index for All Urban Consumers (CPI-U) "
            "increased "+(headline or "0.6")+" percent on a seasonally adjusted basis in "
            "September after rising 0.4 percent in August"
        )
    else:
        statement=(
            "The Producer Price Index for final demand increased "+
            (headline or "1.3")+" percent in September, seasonally adjusted, "
            "the U.S. Bureau of Labor Statistics reported today"
        )
    html=("<html><body><h1>Bureau of Labor Statistics</h1>"
          +s["edition"]+" "+s["title"]+" <p>"+statement+"</p>"
          +"<section>"+s["table"]+"</section>"
          +("</body></html>"))
    return html.encode("utf-8")+b" "*110_000


class Response:
    def __init__(self, payload,*,url,mime="text/html; charset=utf-8",
                 status=200,encoding="identity",length=None):
        self.payload=payload
        self.url=url
        self.status=status
        self.headers={
            "Content-Type":mime, "Content-Encoding":encoding,
            "Content-Length":str(len(payload) if length is None else length),
            "Date":"Sun, 15 Nov 2026 22:00:00 GMT",
        }
    def geturl(self):
        return self.url
    def read(self, max_bytes):
        return self.payload[:max_bytes]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class MockOpen:
    def __init__(self, cpi=None,ppi=None, fail_at=None, bad_cpi=None, bad_ppi=None):
        self.items={"CPI":cpi if cpi is not None else body("CPI"),
                    "PPI":ppi if ppi is not None else body("PPI")}
        self.fail_at=fail_at
        self.bad={"CPI":bad_cpi or {}, "PPI":bad_ppi or {}}
        self.calls=[]
    def __call__(self, request,*,timeout):
        k="CPI" if len(self.calls)==0 else "PPI"
        self.calls.append(k)
        assert len(self.calls)<=2, "NETWORK_RETRY_FORBIDDEN"
        assert request.get_method()=="GET"
        assert request.full_url==SPECS[k]["url"]
        assert request.get_header("Accept-encoding")=="identity"
        assert timeout==15
        if k==self.fail_at:
            raise HTTPError(request.full_url,403,"Forbidden",{},None)
        return Response(self.items[k],url=SPECS[k]["url"],**self.bad[k])


def times():
    values=iter(BEGIN+timedelta(seconds=i) for i in range(4))
    return lambda:next(values)


class SeptemberOriginalPairLabTests(unittest.TestCase):
    def safety(self,report):
        self.assertEqual(report["schema"],SCHEMA)
        self.assertFalse(report["consensus_pre_event_authenticated"])
        self.assertFalse(report["first_print_original_independently_authenticated"])
        self.assertFalse(report["market_reaction_causally_identified"])
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["publishable"])
        self.assertFalse(report["original_fx28_672_slots_modified"])
        self.assertEqual(report["operational_bias"],"AGUARDAR")
        self.assertEqual(report["independent_fx_forecast_trials"],0)
        self.assertIsNone(report["out_of_sample_accuracy"])
        self.assertIsNone(report["forex_bias"])

    def collect(self, directory, **kwargs):
        http=kwargs.pop("http",MockOpen())
        result=capture(output_root=directory,allow_two_official_gets=kwargs.pop("allow",True),
                       opener=http,clock=kwargs.pop("clock",times()))
        self.safety(result)
        return result,http

    def test_01_requires_explicit_opt_in_zero_get(self):
        with TemporaryDirectory() as td:
            r,http=self.collect(td,allow=False)
            self.assertEqual(http.calls,[])
            self.assertEqual(r["documentary_original_count"],0)
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_02_both_synthetic_original_style_documents_replay(self):
        with TemporaryDirectory() as td:
            r,http=self.collect(td)
            self.assertEqual(http.calls,["CPI","PPI"])
            self.assertEqual(r["http_get_attempts"],2)
            self.assertEqual(r["documentary_original_count"],2)
            self.assertEqual(r["paired_headline_sa_mom_pct"],{"CPI":"0.6","PPI":"1.3"})
            folder=Path(td)/r["archive_basename"]
            for k in ("CPI","PPI"):
                original=(folder/(k.lower()+"_original.html")).read_bytes()
                self.assertEqual(original,body(k))
                self.assertEqual(r["paired_original_source_sha256"][k],
                                 sha256(original).hexdigest())
            later=replay(output_root=td,archive_basename=r["archive_basename"],
                         as_of_utc=BEGIN+timedelta(seconds=3))
            self.assertEqual(later["documentary_original_count"],2)
            self.assertEqual(later["paired_headline_sa_mom_pct"],{"CPI":"0.6","PPI":"1.3"})

    def test_03_cpi_parser_extracts_its_own_numeric_value(self):
        v=parser(kind="CPI",raw_html=body("CPI"))
        self.assertEqual(v["sa_mom_pct_body_claim"],"0.6")
        self.assertEqual(v["metric"],"HEADLINE_MOM_SA_PCT")

    def test_04_ppi_parser_extracts_its_own_numeric_value(self):
        v=parser(kind="PPI",raw_html=body("PPI"))
        self.assertEqual(v["sa_mom_pct_body_claim"],"1.3")

    def test_05_wrong_value_cpi_rejected(self):
        self.assertIsNone(parser(kind="CPI",raw_html=body("CPI",headline="0.5")))
    def test_06_wrong_value_ppi_rejected(self):
        self.assertIsNone(parser(kind="PPI",raw_html=body("PPI",headline="0.3")))
    def test_07_october_doc_falsely_labeled_as_september_rejected(self):
        self.assertIsNone(parser(kind="CPI",raw_html=body("CPI").replace(
            b"CONSUMER PRICE INDEX - SEPTEMBER 2026",
            b"CONSUMER PRICE INDEX - OCTOBER 2026")))
    def test_08_wrong_document_edition_rejected(self):
        self.assertIsNone(parser(kind="PPI",raw_html=body("PPI").replace(
            b"USDL 26-1576",b"USDL 26-1687")))
    def test_09_table_missing_rejected(self):
        self.assertIsNone(parser(kind="CPI",raw_html=body("CPI").replace(
            b"Table 1. Consumer Price Index for All Urban Consumers",
            b"Table 4. Fake")))
    def test_10_duplicate_headline_rejected(self):
        raw=body("PPI").replace(b"</body></html>",b"</body></html>"
                             +b"The Producer Price Index for final demand increased "
                             +b"1.3 percent in September, seasonally adjusted")
        self.assertIsNone(parser(kind="PPI",raw_html=raw))

    def test_11_oversize_html_rejected(self):
        from atlasquant_trader_us_bls_sep2026_original_pair_once_lab import MAX_BYTES
        self.assertIsNone(parser(kind="PPI",raw_html=body("PPI")+b" " * MAX_BYTES))
    def test_12_short_fake_html_rejected(self):
        self.assertIsNone(parser(kind="CPI",raw_html=b"<html>CPI September 0.6</html>"))
    def test_13_wrong_kind_rejected(self):
        self.assertIsNone(parser(kind="ADP",raw_html=body("CPI")))

    def test_14_second_http403_means_no_false_pair(self):
        with TemporaryDirectory() as td:
            r,http=self.collect(td,http=MockOpen(fail_at="PPI"))
            self.assertEqual(http.calls,["CPI","PPI"])
            self.assertEqual(r["documentary_original_count"],0)
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_15_first_http403_does_not_retry(self):
        with TemporaryDirectory() as td:
            r,http=self.collect(td,http=MockOpen(fail_at="CPI"))
            self.assertEqual(http.calls,["CPI"])
            self.assertEqual(list(Path(td).iterdir()),[])
    def test_16_mime_mismatch_no_files(self):
        with TemporaryDirectory() as td:
            r,http=self.collect(td,http=MockOpen(bad_ppi={"mime":"application/json"}))
            self.assertEqual(http.calls,["CPI","PPI"])
            self.assertEqual(list(Path(td).iterdir()),[])
    def test_17_wrong_final_url_no_files(self):
        with TemporaryDirectory() as td:
            r,http=self.collect(td,http=MockOpen(bad_cpi={"url":"https://example.org/" }))
            self.assertEqual(http.calls,["CPI"])
            self.assertEqual(list(Path(td).iterdir()),[])
    def test_18_gzip_not_identity_refused(self):
        with TemporaryDirectory() as td:
            r,http=self.collect(td,http=MockOpen(bad_ppi={"encoding":"gzip"}))
            self.assertEqual(r["documentary_original_count"],0)
    def test_19_content_length_mismatch_refused(self):
        with TemporaryDirectory() as td:
            r,http=self.collect(td,http=MockOpen(bad_cpi={"length":"500"}))
            self.assertEqual(r["documentary_original_count"],0)

    def test_20_before_releases_no_http(self):
        with TemporaryDirectory() as td:
            r,http=self.collect(td,clock=lambda:datetime(2026,10,10,tzinfo=UTC))
            self.assertEqual(http.calls,[])
            self.assertEqual(r["documentary_original_count"],0)

    def test_21_replay_cutoff_one_second_early_hides_both(self):
        with TemporaryDirectory() as td:
            r,_=self.collect(td)
            cut=replay(output_root=td,archive_basename=r["archive_basename"],
                       as_of_utc=BEGIN+timedelta(seconds=2))
            self.safety(cut)
            self.assertEqual(cut["documentary_original_count"],0)

    def test_22_replay_cpi_bytes_tampered_blocks_whole_pair(self):
        with TemporaryDirectory() as td:
            r,_=self.collect(td)
            f=Path(td)/r["archive_basename"]/"cpi_original.html"
            f.write_bytes(f.read_bytes()+b"X")
            cut=replay(output_root=td,archive_basename=r["archive_basename"],
                       as_of_utc=BEGIN+timedelta(seconds=3))
            self.safety(cut)
            self.assertEqual(cut["documentary_original_count"],0)

    def test_23_replay_receipt_sha_tampered_blocks(self):
        with TemporaryDirectory() as td:
            r,_=self.collect(td)
            f=Path(td)/r["archive_basename"]/"receipt.json"
            m=json.loads(f.read_text())
            m["sources"]["PPI"]["raw_sha256"]="f"*64
            f.write_text(json.dumps(m),encoding="utf-8")
            cut=replay(output_root=td,archive_basename=r["archive_basename"],
                       as_of_utc=BEGIN+timedelta(seconds=3))
            self.safety(cut)
            self.assertEqual(cut["documentary_original_count"],0)

    def test_24_replay_wrong_headline_claim_blocks(self):
        with TemporaryDirectory() as td:
            r,_=self.collect(td)
            f=Path(td)/r["archive_basename"]/"receipt.json"
            m=json.loads(f.read_text())
            m["sources"]["CPI"]["sa_mom_pct_body_claim"]="9.9"
            f.write_text(json.dumps(m),encoding="utf-8")
            cut=replay(output_root=td,archive_basename=r["archive_basename"],
                       as_of_utc=BEGIN+timedelta(seconds=3))
            self.assertEqual(cut["documentary_original_count"],0)

    def test_25_duplicate_manifest_json_key_rejected(self):
        with TemporaryDirectory() as td:
            r,_=self.collect(td)
            f=Path(td)/r["archive_basename"]/"receipt.json"
            text=f.read_text()
            f.write_text(text.replace('"schema":','"schema":"FAKE","schema":'),encoding="utf-8")
            cut=replay(output_root=td,archive_basename=r["archive_basename"],
                       as_of_utc=BEGIN+timedelta(seconds=3))
            self.assertEqual(cut["documentary_original_count"],0)

    def test_26_archive_traversal_rejected(self):
        with TemporaryDirectory() as td:
            cut=replay(output_root=td,archive_basename="../etc",as_of_utc=BEGIN)
            self.assertEqual(cut["documentary_original_count"],0)

    def test_27_nonexistent_output_root_cannot_trigger_http(self):
        http=MockOpen()
        r=capture(allow_two_official_gets=True,output_root="/unlikely-atlasquant-path-2026-zz",
                  opener=http,clock=times())
        self.safety(r)
        self.assertEqual(http.calls,[])

    def test_28_no_new_accuracy_from_two_public_headlines(self):
        with TemporaryDirectory() as td:
            r,_=self.collect(td)
            self.assertEqual(r["required_event_roots"],["US_CPI_SEP2026","US_PPI_SEP2026"])
            self.assertEqual(r["independent_fx_forecast_trials"],0)
            self.assertIsNone(r["forex_bias"])

    def test_29_different_body_hash_changes_pair_digest(self):
        a={"CPI":body("CPI"),"PPI":body("PPI")}
        b={**a,"PPI":a["PPI"]+b" "}
        self.assertNotEqual(_pair_digest(a),_pair_digest(b))


if __name__ == "__main__":
    unittest.main()
