"""Never call real RBNZ or AM12 in tests of manual October archive."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError
import json
import unittest

from atlasquant_trader_nzd_rbnz_oct_article_local_capture_lab import (
    URL, USER_AGENT,
    collect_october_rbnz_release_once_lab as collect,
    save_october_rbnz_release_local_lab as save,
    main,
)
from test_atlasquant_trader_nzd_rbnz_ocr_decision_article_lab import (
    page, receipt as article_receipt,
)
from atlasquant_trader_nzd_rbnz_policy_source_variant_lab import (
    OCTOBER_ARTICLE_URL,
)

UTC=timezone.utc
AT=datetime(2026,11,14,11,50,tzinfo=UTC)


class FakeHTTP:
    def __init__(self, data, url=URL, status=200):
        self.data=BytesIO(data)
        self.url=url
        self.status=status
        self.headers={"Content-Type":"text/html; charset=utf-8"}
    def __enter__(self):return self
    def __exit__(self,*a):self.data.close()
    def read(self,n=-1):return self.data.read(n)
    def geturl(self):return self.url


class RbnzOctManualArchiveTests(unittest.TestCase):
    def test_01_requires_explicit_flag_no_network(self):
        calls=[]
        def fake(*a,**kw):
            calls.append(True)
            raise AssertionError("should not GET")
        with self.assertRaises(PermissionError):
            collect(explicit_capture=False,request_open=fake)
        self.assertEqual(calls,[])

    def test_02_exact_single_http_get_compliant_useragent(self):
        raw=page("2026-10")
        calls=[]
        times=iter(("2026-11-14T11:49:59Z","2026-11-14T11:50:00Z"))
        def opener(req,*,timeout):
            calls.append((req.full_url,req.get_method(),
                          req.get_header("User-agent"),timeout))
            return FakeHTTP(raw)
        got,receipt=collect(explicit_capture=True,request_open=opener,
                            stamp_clock=lambda:next(times))
        self.assertEqual(got,raw)
        self.assertEqual(receipt["source_url"],OCTOBER_ARTICLE_URL)
        self.assertEqual(receipt["body_sha256"],sha256(raw).hexdigest())
        self.assertEqual(calls,[(URL,"GET",USER_AGENT,12)])

    def test_03_default_cli_does_not_attempt_http_or_save(self):
        with patch(
            "atlasquant_trader_nzd_rbnz_oct_article_local_capture_lab."
            "collect_october_rbnz_release_once_lab"
        ) as collector:
            self.assertEqual(main([]),2)
            collector.assert_not_called()

    def test_04_forged_403_no_retry(self):
        calls=[]
        def denied(req,*,timeout):
            calls.append(req.full_url)
            raise HTTPError(req.full_url,403,"Denied",None,None)
        with self.assertRaises(HTTPError):
            collect(explicit_capture=True,request_open=denied,
                    stamp_clock=lambda:"2026-11-14T11:50:00Z")
        self.assertEqual(calls,[URL])

    def test_05_capture_refused_at_dec9_before_any_get(self):
        calls=[]
        def fake(req,*,timeout):
            calls.append(req.full_url)
            raise AssertionError("after event GET not allowed")
        with self.assertRaisesRegex(ValueError,"SUPERSEDED"):
            collect(explicit_capture=True,request_open=fake,
                    stamp_clock=lambda:"2026-12-09T01:00:00Z")
        self.assertEqual(calls,[])

    def test_06_wrong_final_url_is_not_archived(self):
        raw=page("2026-10")
        def redirect(req,*,timeout):
            return FakeHTTP(raw,url="https://www.rbnz.govt.nz/other")
        times=iter(("2026-11-14T11:49:59Z","2026-11-14T11:50:00Z"))
        with self.assertRaisesRegex(ValueError,"REJECTED"):
            collect(explicit_capture=True,request_open=redirect,
                    stamp_clock=lambda:next(times))

    def test_07_saver_writes_exactly_two_archive_files_no_overwrite(self):
        raw=page("2026-10")
        receipt=article_receipt("2026-10",raw)
        with TemporaryDirectory() as td:
            names=save(original_html=raw,receipt=receipt,
                       local_appdata=td,as_of_utc=AT)
            folder=Path(td)/"AtlasQuant"/"LAB"/"official_macro_receipts"
            self.assertEqual(len(list(folder.iterdir())),2)
            self.assertTrue(names[0].startswith("NZD_RBNZ_OCR_20261114T115000Z_"))
            self.assertEqual((folder/names[0]).read_bytes(),raw)
            self.assertEqual(json.loads((folder/names[1]).read_text()),receipt)
            with self.assertRaises(FileExistsError):
                save(original_html=raw,receipt=receipt,
                     local_appdata=td,as_of_utc=AT)

    def test_08_no_source_save_if_corrupt_hash_or_wrong_url(self):
        raw=page("2026-10")
        good=article_receipt("2026-10",raw)
        for receipt in (
            dict(good,body_sha256="f"*64),
            dict(good,source_url="https://fake.example/news"),
            dict(good,http_status=403),
        ):
            with self.subTest(receipt=receipt):
                with TemporaryDirectory() as td:
                    with self.assertRaises(ValueError):
                        save(original_html=raw,receipt=receipt,
                             local_appdata=td,as_of_utc=AT)
                    self.assertFalse(
                        (Path(td)/"AtlasQuant"/"LAB").exists())

    def test_09_save_never_after_next_policy_event_or_fake_clock(self):
        raw=page("2026-10")
        rec=article_receipt("2026-10",raw)
        for when in (
            datetime(2026,12,9,1,tzinfo=UTC),
            datetime(2026,12,10,1,tzinfo=UTC),
            AT.replace(tzinfo=None),
        ):
            with self.subTest(when=when):
                with TemporaryDirectory() as td:
                    with self.assertRaises(ValueError):
                        save(original_html=raw,receipt=rec,
                             local_appdata=td,as_of_utc=when)

    def test_10_save_requires_absolute_root_and_blocks_symlinked_subfolder(self):
        raw=page("2026-10")
        rec=article_receipt("2026-10",raw)
        with self.assertRaises(ValueError):
            save(original_html=raw,receipt=rec,
                 local_appdata="relative/root",as_of_utc=AT)
        with TemporaryDirectory() as td:
            atlas=Path(td)/"AtlasQuant"
            target=Path(td)/"external"
            target.mkdir()
            try:
                atlas.symlink_to(target,target_is_directory=True)
            except (NotImplementedError,OSError):
                self.skipTest("symlinks unsupported")
            with self.assertRaisesRegex(ValueError,"SYMLINK"):
                save(original_html=raw,receipt=rec,
                     local_appdata=td,as_of_utc=AT)

    def test_11_synthetic_consent_flag_is_not_live_source_evidence(self):
        raw=page("2026-10")
        rec=article_receipt("2026-10",raw)
        with TemporaryDirectory() as td:
            names=save(original_html=raw,receipt=rec,
                       local_appdata=td,as_of_utc=AT)
            self.assertEqual(len(names),2)
            self.assertNotIn("AM12",names[0])
            self.assertEqual(rec["source_url"],URL)


if __name__=="__main__":
    unittest.main()
