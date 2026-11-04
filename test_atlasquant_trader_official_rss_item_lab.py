"""Fully synthetic RSS2.0 parser contracts. NOT actual BLS feed material."""
from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from atlasquant_trader_official_rss_item_lab import (
    STATE, DENIED, validate_official_bls_rss_item_lab as validate,
)

NOW = datetime(2026, 11, 12, 15, tzinfo=timezone.utc)
LINK = 'https://www.bls.gov/news.release/empsit.toc.htm'
CPI_LINK = 'https://www.bls.gov/news.release/cpi.toc.htm'
DATE = 'Fri, 06 Nov 2026 13:30:02 +0000'


def item(link=LINK, pubdate=DATE, title='SYNTHETIC BLS Employment Headline', extras=''):
    return (f'<item><title>{escape(title)}</title><link>{escape(link)}</link>'
            f'<pubDate>{escape(pubdate)}</pubDate>{extras}</item>')


def xml(items=None, *, root='<rss version="2.0">', channel='<channel>'):
    inner = item() if items is None else items
    return (root + channel + '<title>SYNTHETIC FEED</title>' + inner +
            '</channel></rss>').encode('utf-8')


def record(raw=None):
    raw = xml() if raw is None else raw
    return {
        'event_id': 'BLS_US_EMPLOYMENT_20261106',
        'source_id': 'BLS_EMPLOYMENT_RSS',
        'source_url': 'https://www.bls.gov/feed/empsit.rss',
        'item_url': LINK,
        'scheduled_release_at_utc': '2026-11-06T13:30:00Z',
        'feed_published_at_utc': '2026-11-06T13:30:02Z',
        'first_seen_at_utc': '2026-11-06T13:30:05Z',
        'captured_at_utc': '2026-11-06T13:30:08Z',
        'displayed_at_utc': '2026-11-06T13:30:12Z',
        'capture_mode': 'SYNTHETIC_CONTRACT_TEST',
        'http_status': 200,
        'content_type': 'application/rss+xml',
        'raw_payload_bytes': raw,
        'raw_payload_sha256': hashlib.sha256(raw).hexdigest(),
    }


def evaluated(raw=None):
    return validate(record(raw), evaluated_at=NOW)


class OfficialRSSItemGateTests(unittest.TestCase):
    def test_plain_rss_2_item_can_match_metadata_but_not_authenticate(self):
        r = evaluated()
        self.assertEqual(r['state'], STATE)
        self.assertEqual(r['event_id'], 'BLS_US_EMPLOYMENT_20261106')
        self.assertEqual(r['rss_item_count'], 1)
        self.assertTrue(r['rss_pubdate_matches_declared_clock'])
        self.assertTrue(r['raw_sha256_internally_matched'])
        self.assertFalse(r['source_origin_independently_attested'])
        self.assertFalse(r['delivery_latency_independently_attested'])

    def test_more_than_one_item_selects_exact_official_link(self):
        raw = xml(item(CPI_LINK, 'Tue, 10 Nov 2026 13:30:02 +0000')+item())
        r = evaluated(raw)
        self.assertEqual(r['state'], STATE)
        self.assertEqual(r['rss_item_count'], 2)
        self.assertEqual(r['item_url'], LINK)

    def test_rfc822_offset_is_normalized_to_utc(self):
        r = evaluated(xml(item(pubdate='Fri, 06 Nov 2026 08:30:02 -0500')))
        self.assertEqual(r['state'], STATE)
        self.assertEqual(r['rss_item_pubdate_claimed_utc'], '2026-11-06T13:30:02+00:00')

    def test_matching_bls_link_required_in_actual_item_content(self):
        self.assertEqual(evaluated(xml(item(CPI_LINK)))['state'], DENIED)

    def test_not_accept_xml_claiming_wrong_pubdate(self):
        r = evaluated(xml(item(pubdate='Fri, 06 Nov 2026 13:31:02 +0000')))
        self.assertEqual(r['state'], DENIED)

    def test_no_pubdate_falls_closed_even_if_external_clock_claimed(self):
        raw = xml('<item><title>SYNTHETIC</title><link>'+LINK+'</link></item>')
        self.assertEqual(evaluated(raw)['state'], DENIED)

    def test_no_title_falls_closed(self):
        raw = xml('<item><link>'+LINK+'</link><pubDate>'+DATE+'</pubDate></item>')
        self.assertEqual(evaluated(raw)['state'], DENIED)

    def test_unzoned_pubdate_is_not_treated_as_utc(self):
        self.assertEqual(evaluated(xml(item(pubdate='Fri, 06 Nov 2026 13:30:02')))['state'],DENIED)

    def test_date_only_pubdate_does_not_get_imaginary_release_minute(self):
        self.assertEqual(evaluated(xml(item(pubdate='06 Nov 2026')))['state'],DENIED)

    def test_malformed_xml_never_becomes_news(self):
        self.assertEqual(evaluated(b'<rss><channel><item>')['state'],DENIED)

    def test_html_atom_and_other_roots_are_rejected_in_rss2_pilot(self):
        for raw in (b'<html></html>', b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>',
                    xml(root='<rss version="1.0">')):
            with self.subTest(raw=raw[:20]):
                self.assertEqual(evaluated(raw)['state'], DENIED)

    def test_external_dtd_and_entity_declarations_denied(self):
        raw = (b'<!DOCTYPE rss [<!ENTITY attacker SYSTEM "file:///etc/passwd">]>' + xml())
        self.assertEqual(evaluated(raw)['state'], DENIED)
        raw = (b'<!DOCTYPE rss SYSTEM "https://evil.example/rss.dtd">' + xml())
        self.assertEqual(evaluated(raw)['state'], DENIED)

    def test_two_channels_are_ambiguous(self):
        raw = b'<rss version="2.0"><channel>'+item().encode()+b'</channel><channel>'+item().encode()+b'</channel></rss>'
        self.assertEqual(evaluated(raw)['state'], DENIED)

    def test_duplicate_matching_items_denied(self):
        self.assertEqual(evaluated(xml(item()+item()))['state'], DENIED)

    def test_duplicate_irrelevant_links_cannot_hide_one_fast_item(self):
        self.assertEqual(evaluated(xml(item()+item(CPI_LINK)+item(CPI_LINK)))['state'],DENIED)

    def test_oversized_item_list_rejected(self):
        many=''.join(item(f'https://www.bls.gov/news.release/other{i}.htm') for i in range(105))
        self.assertEqual(evaluated(xml(many))['state'],DENIED)

    def test_nested_markup_in_critical_title_is_refused(self):
        raw=xml('<item><title><script>alert(1)</script></title><link>'+LINK+'</link><pubDate>'+DATE+'</pubDate></item>')
        self.assertEqual(evaluated(raw)['state'],DENIED)

    def test_nested_link_is_not_usable(self):
        raw=xml('<item><title>test</title><link><a>'+LINK+'</a></link><pubDate>'+DATE+'</pubDate></item>')
        self.assertEqual(evaluated(raw)['state'],DENIED)

    def test_no_fake_price_consensus_or_direction(self):
        r=evaluated()
        self.assertFalse(r['feed_actual_economic_value_extracted'])
        self.assertFalse(r['market_consensus_verified'])
        self.assertEqual(r['directional_bias'],'AGUARDAR')
        self.assertIsNone(r['probability_calibrated'])
        self.assertFalse(r['can_feed_live_radar'])
        self.assertFalse(r['can_feed_real_oos'])

    def test_never_enables_render_trading_news_worker_or_payment(self):
        r=evaluated()
        for key in ('trade_authorized','worker_enabled','scheduler_enabled',
                    'realtime_news_enabled','render_configuration_changed',
                    'paid_provider_approved'):
            self.assertFalse(r[key], key)

    def test_underlying_sha256_mismatch_fails_closed(self):
        x=record()
        x['raw_payload_sha256']='0'*64
        self.assertEqual(validate(x,evaluated_at=NOW)['state'],DENIED)

    def test_underlying_future_claim_fails_closed(self):
        x=record()
        self.assertEqual(validate(x,evaluated_at=datetime(2026,11,3,14,tzinfo=timezone.utc))['state'],DENIED)

    def test_wrong_input_shape_refused(self):
        self.assertEqual(validate(None,evaluated_at=NOW)['state'],DENIED)

    def test_source_payload_never_echoed_or_executed(self):
        r=evaluated()
        self.assertNotIn('raw_payload_bytes', r)
        self.assertNotIn('actual', r)
        self.assertIn('UNATTESTED',r['note'])


if __name__=='__main__':
    unittest.main()
