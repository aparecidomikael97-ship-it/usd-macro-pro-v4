import base64
import unittest
from unittest.mock import patch

from atlasquant_challenger_v1 import build_challenger_snapshot, champion_snapshot
from atlasquant_shadow_store import parse_samples,serialize_samples,merge_unique_samples,persist_shadow_samples
from atlasquant_shadow_capture import ensure_shadow_hydrated, build_shadow_batch,hydrate_shadow_samples


class _Resp:
    def __init__(self,status=200,payload=None):
        self.status_code=status; self._payload=payload or {}
    def json(self): return self._payload
    def raise_for_status(self):
        if self.status_code>=400: raise RuntimeError(f"HTTP {self.status_code}")


class AtlasQuantShadowPersistenceTests(unittest.TestCase):
    def pack(self,executable=True):
        return {
            "pair":"EUR/USD","side":"BUY","state":"EXECUTABLE","score":82,"quality":88,
            "macro_diff":12,"h4":"🟢 CONFIRMA","h1":"🟢 CONFIRMA","m15":"🟢 GATILHO",
            "executable":executable,"hard_blocks":[],"updated_at":"2026-09-16T01:00:00Z",
            "data_ready":{"sufficient":True,"score":91},
        }

    def test_strict_challenger_can_execute_only_when_champion_executes(self):
        a=build_challenger_snapshot(self.pack(True))
        b=build_challenger_snapshot(self.pack(False))
        self.assertTrue(a["executable"])
        self.assertFalse(b["executable"])

    def test_challenger_never_flips_side(self):
        p=self.pack(); p["side"]="SELL"
        r=build_challenger_snapshot(p)
        self.assertEqual(r["side"],"SELL")

    def test_champion_and_challenger_share_timestamp(self):
        p=self.pack()
        self.assertEqual(
            champion_snapshot(p,version="v")["timestamp"],
            build_challenger_snapshot(p)["timestamp"],
        )

    def test_batch_is_deterministic(self):
        a=build_shadow_batch([self.pack()],champion_version="v")
        b=build_shadow_batch([self.pack()],champion_version="v")
        self.assertEqual(a[0]["sample_id"],b[0]["sample_id"])

    def test_hydrate_deduplicates(self):
        sample=build_shadow_batch([self.pack()],champion_version="v")[0]
        rows=hydrate_shadow_samples([sample],[sample])
        self.assertEqual(len(rows),1)

    def test_store_roundtrip(self):
        sample=build_shadow_batch([self.pack()],champion_version="v")[0]
        self.assertEqual(parse_samples(serialize_samples([sample]))[0]["sample_id"],sample["sample_id"])

    def test_merge_deduplicates(self):
        sample=build_shadow_batch([self.pack()],champion_version="v")[0]
        rows,added=merge_unique_samples([sample],[sample])
        self.assertEqual(added,0); self.assertEqual(len(rows),1)

    def test_main_branch_fails_closed(self):
        sample=build_shadow_batch([self.pack()],champion_version="v")[0]
        with patch("atlasquant_shadow_store.requests.get") as g:
            r=persist_shadow_samples([sample],repo="o/r",branch="main",token="t")
        self.assertFalse(r["ok"]); self.assertEqual(r["reason"],"UNSAFE_BRANCH"); g.assert_not_called()

    def test_create_remote_file(self):
        sample=build_shadow_batch([self.pack()],champion_version="v")[0]
        with patch("atlasquant_shadow_store.requests.get",return_value=_Resp(404,{})), \
             patch("atlasquant_shadow_store.requests.put",return_value=_Resp(201,{})) as p:
            r=persist_shadow_samples([sample],repo="o/r",branch="atlasquant-runtime",token="t")
        self.assertTrue(r["ok"]); self.assertEqual(r["added"],1)
        raw=base64.b64decode(p.call_args.kwargs["json"]["content"]).decode("utf-8")
        self.assertEqual(parse_samples(raw)[0]["sample_id

    def test_shadow_hydration_source_metadata_is_safe_and_explicit(self):
        import inspect
        source=inspect.getsource(ensure_shadow_hydrated)
        self.assertIn('"source":"runtime_persistent"',source)
        self.assertIn('"source":"session_fallback"',source)
        self.assertIn('"branch":cfg["branch"]',source)
        self.assertNotIn('"token":cfg["token"]',source)
"],sample["sample_id"])


if __name__=="__main__":
    unittest.main()
