import unittest
from unittest.mock import patch

import requests
from streamlit.testing.v1 import AppTest


class _OfflineResponse:
    status_code=503
    content=b""
    text="offline smoke test"
    headers={}

    def json(self):
        return {}

    def raise_for_status(self):
        raise requests.HTTPError("offline smoke test")


class AtlasQuantRuntimeSmokeTests(unittest.TestCase):
    def test_app_boots_offline_without_twelve_or_remote_writes(self):
        calls=[]

        def fake_get(url,*args,**kwargs):
            calls.append(("GET",str(url)))
            return _OfflineResponse()

        def forbidden_write(url,*args,**kwargs):
            calls.append(("WRITE",str(url)))
            raise AssertionError(f"remote write attempted during UI boot: {url}")

        at=AppTest.from_file("usd_macro_pro_v4_cloud.py",default_timeout=180)
        at.secrets["CHAVE_FRED"]=""
        at.secrets["CHAVE_TWELVE_DATA"]=""
        at.secrets["CHAVE_NEWSAPI"]=""
        at.secrets["CHAVE_EODHD"]=""
        at.secrets["GITHUB_TOKEN_HISTORICO"]=""
        at.secrets["GITHUB_REPO_HISTORICO"]=""
        at.secrets["GITHUB_DATA_BRANCH"]="atlasquant-runtime"
        at.secrets["GITHUB_BRANCH_HISTORICO"]="atlasquant-runtime"

        with patch("requests.get",side_effect=fake_get), \
             patch("requests.post",side_effect=forbidden_write), \
             patch("requests.put",side_effect=forbidden_write), \
             patch("requests.patch",side_effect=forbidden_write), \
             patch("requests.delete",side_effect=forbidden_write):
            at.run(timeout=180)

        exceptions=[]
        for exc in at.exception:
            try:
                exceptions.append(str(exc.value))
            except Exception:
                exceptions.append(str(exc))
        self.assertEqual(exceptions,[])

        twelve=[url for method,url in calls if "api.twelvedata.com" in url.lower()]
        writes=[(method,url) for method,url in calls if method=="WRITE"]
        self.assertEqual(twelve,[],"UI boot must not consume Twelve Data")
        self.assertEqual(writes,[],"UI boot must not perform remote writes")

        rendered=" ".join(
            [str(x.value) for x in list(at.title)+list(at.caption)+list(at.info)]
        )
        self.assertIn("USD Macro Pro",rendered)
        self.assertIn("RUNTIME",rendered)

    def test_app_source_has_no_hardcoded_dev_badge(self):
        src=__import__("pathlib").Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertNotIn("Market Intelligence Platform · DEV",src)
        self.assertNotIn('environment="DEV"',src)
        self.assertIn("ATLASQUANT_ENVIRONMENT",src)


if __name__=="__main__":
    unittest.main()
