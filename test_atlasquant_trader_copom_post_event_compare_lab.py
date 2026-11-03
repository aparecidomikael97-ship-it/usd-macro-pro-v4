"""All post-Copom 'observations' here are SYNTHETIC future fixtures.

Never interpret passing tests as proof that the Nov 4 decision occurred, that
official BCB data were captured, or that Trader predicted market direction.
"""
from __future__ import annotations
import hashlib
import json
import unittest
from datetime import datetime,timezone
from pathlib import Path
from atlasquant_trader_copom_post_event_compare_lab import (
 PENDING,CANDIDATE,DENIED,PRE_EVENT_COMMIT,PRE_EVENT_BLOB,
 assess_copom_post_event_candidate_lab as assess,
)

ROOT=Path(__file__).resolve().parent
PRE=ROOT/"docs/continuidade/TRADER_COPOM_20261104_FROZEN_PRE_EVENT_20261103.json"
NOW=datetime(2026,11,5,0,1,tzinfo=timezone.utc)
RAW_TEXT="Comunicado sintético do Copom: o Copom decidiu manter a Selic em 13,75% ao ano. TESTE FICTÍCIO.".encode("utf-8")

def frozen():return PRE.read_bytes()
def candidate(text=RAW_TEXT,rate="13.75"):
 return {
  "source_type":"OFFICIAL_BCB_TEXT_EXTRACT_UNATTESTED",
  "source_name":"BANCO_CENTRAL_DO_BRASIL",
  "source_url":"https://www.bcb.gov.br/controleinflacao/comunicadoscopom/synthetic-test",
  "content_type":"text/plain; charset=utf-8",
  "http_status_claim":200,
  "declared_published_at_utc":"2026-11-04T21:35:00Z",
  "claimed_first_seen_at_utc":"2026-11-04T21:36:00Z",
  "policy_rate_claim_pct":rate,
  "raw_release_text":text,
  "raw_release_sha256":hashlib.sha256(text).hexdigest(),
 }
def run(result=None,raw=None,at=NOW):
 return assess(frozen() if raw is None else raw,result,evaluated_at=at)

class CopomPostEventAuditLabTests(unittest.TestCase):
 def test_pending_before_event_without_future_news(self):
  r=run(at=datetime(2026,11,3,18,tzinfo=timezone.utc))
  self.assertEqual(r["state"],PENDING)
  self.assertTrue(r["original_pre_event_snapshot_matched"])
  self.assertFalse(r["actual_policy_decision_verified"])
  self.assertIsNone(r["candidate_rate_pct"])
 def test_pending_after_event_if_no_real_result_was_provided(self):
  r=run(at=NOW)
  self.assertEqual(r["state"],PENDING)
  self.assertFalse(r["actual_policy_decision_verified"])
  self.assertEqual(r["official_earliest_release_utc"],"2026-11-04T21:30:00+00:00")
 def test_pre_event_json_is_bound_to_existing_actual_git_blob(self):
  r=run()
  self.assertEqual(r["frozen_checkpoint_commit"],PRE_EVENT_COMMIT)
  self.assertEqual(r["frozen_checkpoint_blob"],PRE_EVENT_BLOB)
  self.assertEqual(len(PRE_EVENT_BLOB),40)
  self.assertTrue(r["original_pre_event_snapshot_matched"])
 def test_synthetic_hold_classification_not_confirmed_policy(self):
  r=run(candidate())
  self.assertEqual(r["state"],CANDIDATE)
  self.assertEqual(r["result_scenario"],"HOLD_13_75")
  self.assertEqual(r["candidate_rate_pct"],"13.75")
  self.assertTrue(r["economist_poll_modal_matched"])
  self.assertFalse(r["actual_policy_decision_verified"])
  self.assertIsNone(r["trader_accuracy"])
 def test_synthetic_cut_is_alternative_not_focus_prediction(self):
  t="TESTE FICTÍCIO Copom: comunicado simulado; a Selic seria 13,50% ao ano.".encode()
  r=run(candidate(t,"13.50"))
  self.assertEqual(r["state"],CANDIDATE)
  self.assertEqual(r["result_scenario"],"CUT_25BP_13_50")
  self.assertFalse(r["economist_poll_modal_matched"])
  self.assertFalse(r["pre_event_focus_is_next_meeting_probability"])
 def test_synthetic_other_decision_is_supported_but_unverified(self):
  t="Comunicado FICTÍCIO do Copom: a Selic teria chegado a 14,00% ao ano.".encode()
  r=run(candidate(t,"14.00"))
  self.assertEqual(r["state"],CANDIDATE)
  self.assertEqual(r["result_scenario"],"OTHER")
  self.assertFalse(r["actual_policy_decision_verified"])
 def test_result_can_never_be_injected_before_earliest_release(self):
  r=run(candidate(),at=datetime(2026,11,4,21,29,tzinfo=timezone.utc))
  self.assertEqual(r["state"],DENIED)
  self.assertFalse(r["actual_policy_decision_verified"])
 def test_candidate_pubdate_cannot_precede_21_30_utc(self):
  r=candidate();r["declared_published_at_utc"]="2026-11-04T21:29:59Z"
  self.assertEqual(run(r)["state"],DENIED)
 def test_future_clocks_and_receipt_before_publication_refused(self):
  for published,seen in [
   ("2026-11-04T21:35:00Z","2026-11-04T21:34:00Z"),
   ("2026-11-05T00:03:00Z","2026-11-05T00:04:00Z"),
   ("2026-11-04T21:35:00Z","2026-11-05T00:04:00Z"),
  ]:
   r=candidate()
   r["declared_published_at_utc"]=published
   r["claimed_first_seen_at_utc"]=seen
   self.assertEqual(run(r)["state"],DENIED)
 def test_timezone_in_clocks_must_be_explicit_z(self):
  for bad in ("2026-11-04T21:35:00","2026-11-04T17:35:00-04:00",None,"bad"):
   r=candidate();r["declared_published_at_utc"]=bad
   self.assertEqual(run(r)["state"],DENIED)
 def test_changed_frozen_pre_event_document_never_accepted(self):
  d=json.loads(frozen());d["reuters_poll_hold_responses"]=48
  raw=(json.dumps(d,ensure_ascii=False)+"\n").encode()
  r=run(raw=raw)
  self.assertEqual(r["state"],DENIED)
  self.assertFalse(r["original_pre_event_snapshot_matched"])
 def test_reformatted_same_content_is_not_original_git_blob(self):
  d=json.loads(frozen())
  raw=json.dumps(d,sort_keys=True,indent=4).encode()
  self.assertEqual(run(raw=raw)["state"],DENIED)
 def test_missing_or_corrupt_frozen_source_denied(self):
  for data in (b"",b"{}",b"garbage","str",{},None):
   if data is None:
    self.assertEqual(assess(data,evaluated_at=NOW)["state"],DENIED)
   else:
    self.assertEqual(run(raw=data)["state"],DENIED)
 def test_no_other_actor_can_add_claimed_external_validation(self):
  for field,value in (("independently_verified",True),("actual_confirmed",True),
                      ("market_probability",0.99),("trade_authorized",True)):
   x=candidate();x[field]=value
   self.assertEqual(run(x)["state"],DENIED)
 def test_identity_and_disallowed_provider_url_rejected(self):
  for url in ("http://www.bcb.gov.br/controleinflacao/comunicadoscopom/a",
              "https://www.bcb.gov.br.evil.example/controleinflacao/comunicadoscopom/a",
              "https://www.bcb.gov.br@evil.example/controleinflacao/comunicadoscopom/a",
              "https://www.bcb.gov.br:443/controleinflacao/comunicadoscopom/a",
              "https://www.bcb.gov.br/controleinflacao/comunicadoscopom/a?foo=1",
              "https://www.bcb.gov.br/controleinflacao/comunicadoscopom/a#archive"):
   with self.subTest(url=url):
    x=candidate();x["source_url"]=url
    self.assertEqual(run(x)["state"],DENIED)
 def test_wrong_source_or_type_denied(self):
  for field,v in (("source_name","REUTERS"),("source_type","SPOT_BROKER"),
                  ("content_type","application/octet-stream"),
                  ("http_status_claim",True),("http_status_claim",404)):
   x=candidate();x[field]=v
   self.assertEqual(run(x)["state"],DENIED)
 def test_modified_content_fails_local_checksum(self):
  x=candidate();x["raw_release_text"]+=b" changed"
  self.assertEqual(run(x)["state"],DENIED)
 def test_recomputed_checksum_still_does_not_authenticate_source(self):
  text=b"TESTE FICTICIO: Copom e Selic em 13,75% ao ano, texto nao oficial."
  x=candidate(text)
  r=run(x)
  self.assertEqual(r["state"],CANDIDATE)
  self.assertTrue(r["release_text_local_sha256_matches"])
  self.assertFalse(r["release_independently_authenticated"])
  self.assertFalse(r["publication_clock_independently_attested"])
  self.assertFalse(r["receipt_clock_independently_attested"])
 def test_wrong_text_token_but_valid_checksum_refused(self):
  text=b"TESTE FICTICIO sobre o Copom: a Selic em 12,50% ao ano."
  self.assertEqual(run(candidate(text,"13.75"))["state"],DENIED)
 def test_unrelated_text_and_markup_refused(self):
  for text in (
   b"TESTE FICTICIO generic: Selic em 13,75% a.a. (sem comite)",
   b"TESTE FICTICIO Copom decide algo, 13,75% mas sem indicador",
   b"<!DOCTYPE html><html><p>Copom Selic 13,75%</p></html>",
   b"<script>Copom Selic 13,75%</script>",
  ):
   self.assertEqual(run(candidate(text))["state"],DENIED)
 def test_finite_bounded_decimal_policy_rate_required(self):
  for level in (None,13.75,True,"13,75","NaN","0.00","-1.00","40.00","13.7"):
   x=candidate();x["policy_rate_claim_pct"]=level
   self.assertEqual(run(x)["state"],DENIED)
 def test_bad_bytes_boolean_hash_and_size_refused(self):
  for payload in (b"",b"\x00"*50,b"x"*100001,None,"string"):
   x=candidate()
   x["raw_release_text"]=payload
   x["raw_release_sha256"]=hashlib.sha256(payload).hexdigest() if isinstance(payload,bytes) else "0"*64
   self.assertEqual(run(x)["state"],DENIED)
 def test_caller_evaluation_without_timezone_refused(self):
  with self.assertRaises(ValueError):
   run(at=datetime(2026,11,5,0))
 def test_market_bias_probability_accuracy_worker_render_payment_always_off(self):
  for r in (run(),run(candidate())):
   self.assertEqual(r["market_direction"],"AGUARDAR")
   self.assertIsNone(r["market_implied_probability"])
   self.assertFalse(r["economist_share_is_market_probability"])
   self.assertIsNone(r["trader_accuracy"])
   for flag in ("real_oos_eligible","can_feed_live_radar","trade_authorized",
                "worker_enabled","scheduler_enabled","paid_provider_approved",
                "render_configuration_changed","actual_policy_decision_verified"):
    self.assertFalse(r[flag],flag)

if __name__=="__main__":unittest.main()
