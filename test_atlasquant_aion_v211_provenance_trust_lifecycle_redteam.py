"""AION V2.11 red-team: provenance trust lifecycle READINESS (replay/rotation/revocation).

Pure, deterministic, fail-closed. No I/O, no network, no persistent storage,
no real key/signature/trust root. Global state BLOCKED until every dimension is
explicitly configured and verified; nothing auto-promotes to READY.
"""
from __future__ import annotations
import copy, json, socket, subprocess, unittest
import atlasquant_aion_provenance_trust_lifecycle as p

NOW = "2026-10-04T00:00:05Z"

def all_dims():
    return {d: True for d in p.DIMENSIONS}

def base_env(**over):
    e = {"nonce": "YWJjZA==", "timestamp": "2026-10-04T00:00:00Z",
         "key_version": 1, "key_id": "k1", "replay_window_configured": True}
    e.update(over)
    return e

class NoNetwork:
    def __enter__(self):
        self.calls = []
        self._rs, self._rp = socket.socket, subprocess.Popen
        socket.socket = lambda *a, **k: (self.calls.append("socket"), (_ for _ in ()).throw(AssertionError("real socket")))[1]
        subprocess.Popen = lambda *a, **k: (self.calls.append("popen"), (_ for _ in ()).throw(AssertionError("real popen")))[1]
        return self
    def __exit__(self, *a):
        socket.socket, subprocess.Popen = self._rs, self._rp
        return False

class ReplayTests(unittest.TestCase):
    def test_replay_same_evidence(self):
        ev = base_env(sequence=1)
        b = p.ReplayEvaluator().evaluate_batch([copy.deepcopy(ev), copy.deepcopy(ev)], now_ts=NOW, known_key_versions=[1])
        self.assertIn("EVENT_DUPLICATED", b["blockers"]); self.assertEqual(b["state"], "BLOCKED")
    def test_nonce_absent(self):
        r = p.evaluate_provenance_envelope(base_env(nonce=None), now_ts=NOW, known_key_versions=[1])
        self.assertIn("NONCE_ABSENT", r["blockers"])
    def test_nonce_duplicated(self):
        b = p.ReplayEvaluator().evaluate_batch([base_env(nonce="AAA=", sequence=1), base_env(nonce="AAA=", sequence=2)], now_ts=NOW, known_key_versions=[1])
        self.assertIn("NONCE_DUPLICATED", b["blockers"])
    def test_out_of_order(self):
        b = p.ReplayEvaluator().evaluate_batch([base_env(sequence=2), base_env(sequence=1)], now_ts=NOW, known_key_versions=[1])
        self.assertIn("SEQUENCE_OUT_OF_ORDER", b["blockers"])
    def test_event_duplication(self):
        b = p.ReplayEvaluator().evaluate_batch([base_env(sequence=1), copy.deepcopy(base_env(sequence=1))], now_ts=NOW, known_key_versions=[1])
        self.assertIn("EVENT_DUPLICATED", b["blockers"])

class TimestampTests(unittest.TestCase):
    def test_absent(self):
        self.assertIn("TIMESTAMP_ABSENT", p.evaluate_provenance_envelope(base_env(timestamp=None), now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_malformed(self):
        self.assertIn("TIMESTAMP_MALFORMED", p.evaluate_provenance_envelope(base_env(timestamp="2026-13-99T99:99:99Z"), now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_future(self):
        self.assertIn("TIMESTAMP_FUTURE", p.evaluate_provenance_envelope(base_env(timestamp="2026-10-04T00:00:09Z"), now_ts=NOW, known_key_versions=[1])["blockers"])

class KeyVersionTests(unittest.TestCase):
    def test_absent(self):
        self.assertIn("KEY_VERSION_ABSENT", p.evaluate_provenance_envelope(base_env(key_version=None), now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_unknown(self):
        self.assertIn("KEY_VERSION_UNKNOWN", p.evaluate_provenance_envelope(base_env(key_version=99), now_ts=NOW, known_key_versions=[1])["blockers"])

class ClaimAuthorityTests(unittest.TestCase):
    def test_revocation_claim_untrusted(self):
        self.assertIn("KEY_REVOCATION_CLAIM_UNTRUSTED", p.evaluate_provenance_envelope(base_env(claims=[{"type": "key_revoked"}]), now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_revoked_by_registry(self):
        self.assertIn("KEY_REVOKED_BY_REGISTRY", p.evaluate_provenance_envelope(base_env(key_id="k1"), now_ts=NOW, known_key_versions=[1], revoked_key_ids=["k1"])["blockers"])
    def test_rotation_without_authority(self):
        self.assertIn("ROTATION_CLAIM_WITHOUT_AUTHORITY", p.evaluate_provenance_envelope(base_env(claims=[{"type": "rotation"}]), now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_revocation_claim_without_registry(self):
        self.assertIn("REVOCATION_CLAIM_WITHOUT_REGISTRY", p.evaluate_provenance_envelope(base_env(claims=[{"type": "revocation", "authority": "admin"}]), now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_compromise_without_policy(self):
        self.assertIn("COMPROMISE_RECOVERY_WITHOUT_POLICY", p.evaluate_provenance_envelope(base_env(claims=[{"type": "compromise_recovery", "authority": "admin"}]), now_ts=NOW, known_key_versions=[1])["blockers"])

class HostileObjectTests(unittest.TestCase):
    def test_not_mapping(self):
        self.assertIn("ENVELOPE_NOT_MAPPING", p.evaluate_provenance_envelope("str", now_ts=NOW)["blockers"])
    def test_list(self):
        self.assertIn("ENVELOPE_NOT_MAPPING", p.evaluate_provenance_envelope([1], now_ts=NOW)["blockers"])
    def test_none(self):
        self.assertIn("ENVELOPE_NOT_MAPPING", p.evaluate_provenance_envelope(None, now_ts=NOW)["blockers"])
    def test_keys_not_str(self):
        self.assertIn("ENVELOPE_KEYS_NOT_STR", p.evaluate_provenance_envelope({1: "x"}, now_ts=NOW)["blockers"])

class NonCanonicalTypeTests(unittest.TestCase):
    def test_kv_bool(self):
        self.assertIn("KEY_VERSION_NOT_CANONICAL", p.evaluate_provenance_envelope(base_env(key_version=True), now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_kv_float(self):
        self.assertIn("KEY_VERSION_NOT_CANONICAL", p.evaluate_provenance_envelope(base_env(key_version=1.0), now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_nonce_int(self):
        self.assertIn("NONCE_MALFORMED", p.evaluate_provenance_envelope(base_env(nonce=5), now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_claims_not_list(self):
        self.assertIn("CLAIMS_NOT_LIST", p.evaluate_provenance_envelope(base_env(claims={"a": 1}), now_ts=NOW, known_key_versions=[1])["blockers"])

class BoundsTests(unittest.TestCase):
    def test_oversized_evidence(self):
        big = base_env(); big["blob"] = "x" * 70000
        self.assertIn("EVIDENCE_OVERSIZED", p.evaluate_provenance_envelope(big, now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_nonce_oversized(self):
        self.assertIn("NONCE_MALFORMED", p.evaluate_provenance_envelope(base_env(nonce="A" * 200), now_ts=NOW, known_key_versions=[1])["blockers"])
    def test_claims_oversized(self):
        self.assertIn("CLAIMS_OVERSIZED", p.evaluate_provenance_envelope(base_env(claims=[{"type": "x"}] * 40), now_ts=NOW, known_key_versions=[1])["blockers"])

class DeterminismTests(unittest.TestCase):
    def test_byte_for_byte(self):
        e = base_env()
        r1 = p.evaluate_provenance_envelope(e, now_ts=NOW, known_key_versions=[1])
        r2 = p.evaluate_provenance_envelope(copy.deepcopy(e), now_ts=NOW, known_key_versions=[1])
        self.assertEqual(json.dumps(r1, sort_keys=True), json.dumps(r2, sort_keys=True))
    def test_thread_consistency(self):
        import threading
        e = base_env(); errs = []
        def worker():
            try:
                a = p.evaluate_provenance_envelope(e, now_ts=NOW, known_key_versions=[1])
                b = p.evaluate_provenance_envelope(copy.deepcopy(e), now_ts=NOW, known_key_versions=[1])
                if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True): errs.append("nondet")
            except Exception as ex: errs.append(repr(ex))
        ts = [threading.Thread(target=worker) for _ in range(8)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(errs, [])

class SideEffectGuardTests(unittest.TestCase):
    def test_no_real_network(self):
        with NoNetwork():
            r = p.evaluate_provenance_envelope(base_env(), now_ts=NOW, known_key_versions=[1])
            b = p.ReplayEvaluator().evaluate_batch([copy.deepcopy(base_env())], now_ts=NOW, known_key_versions=[1])
        self.assertFalse(r["reads_persistent_storage"]); self.assertFalse(b["persistent_store_used"])
    def test_no_key_material_created(self):
        r = p.evaluate_provenance_envelope(base_env(), now_ts=NOW, known_key_versions=[1])
        self.assertIs(r["creates_secret_or_key_material"], False)

class StateMachineTests(unittest.TestCase):
    def test_one_missing_dim_stays_blocked(self):
        e = base_env(); d = all_dims(); d.pop("revocation_registry_available"); e.update(d)
        r = p.evaluate_provenance_envelope(e, now_ts=NOW, known_key_versions=[1])
        self.assertEqual(r["state"], "BLOCKED")
        self.assertTrue(any(x.startswith("DIMENSION_NOT_CONFIGURED") for x in r["blockers"]))
    def test_all_dims_configured_valid_ready(self):
        e = base_env(); e.update(all_dims())
        r = p.evaluate_provenance_envelope(e, now_ts=NOW, known_key_versions=[1])
        self.assertEqual(r["state"], "READY"); self.assertEqual(r["blockers"], [])
    def test_approval_never_implied(self):
        e = base_env(); e.update(all_dims())
        r = p.evaluate_provenance_envelope(e, now_ts=NOW, known_key_versions=[1])
        self.assertIs(r["approval_implied"], False)
    def test_executes_action_always_false(self):
        e = base_env(); e.update(all_dims())
        r = p.evaluate_provenance_envelope(e, now_ts=NOW, known_key_versions=[1])
        self.assertIs(r["executes_action"], False)
    def test_execution_allowed_only_when_ready_and_dim(self):
        e = base_env(); e.update(all_dims())
        self.assertIs(p.evaluate_provenance_envelope(e, now_ts=NOW, known_key_versions=[1])["execution_allowed"], True)
        e2 = base_env(); e2.update(all_dims()); e2["nonce"] = None
        self.assertIs(p.evaluate_provenance_envelope(e2, now_ts=NOW, known_key_versions=[1])["execution_allowed"], False)

if __name__ == "__main__":
    unittest.main(verbosity=2)
