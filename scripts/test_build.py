"""Static generation safety checks, independent of network or deployment."""
import unittest
from datetime import datetime, timedelta, timezone
from jinja2 import Environment, FileSystemLoader
from scripts.build import DEFAULT_TAXONOMY, ROOT, json_for_html, llms_text, money, prepare_deals, safe_url, structured_data


class StaticBuildTests(unittest.TestCase):
    def offer(self, **changes):
        now = datetime.now(timezone.utc).isoformat()
        result = {'id': 'real-example', 'vendor': 'Vendor', 'product': 'Security course', 'description': 'Testing the renderer only', 'category': 'training', 'topics': ['appsec'], 'campaign_year': 2026, 'campaign_type': 'general_promotion', 'verification_status': 'vendor_published', 'eligibility_basis': 'explicit_2026', 'eligibility_evidence': '2026 promotion', 'source_id': 'vendor', 'offer_url': 'https://example.com/offer', 'source_url': 'https://example.com/evidence', 'last_offer_confirmed_at': now, 'first_seen_at': now, 'sale_price': 60, 'regular_price': 100, 'discount_percent': 40, 'currency': None, 'currency_symbol': '$'}
        result.update(changes)
        return result

    def test_original_currency_is_not_invented(self):
        self.assertEqual(money(60, None, '$'), '$60')
        self.assertEqual(money(60, 'USD'), 'USD 60')
        result = prepare_deals({'deals': [self.offer()]}, DEFAULT_TAXONOMY)[0]
        self.assertIsNone(result['currency'])

    def test_public_output_rejects_unsafe_urls(self):
        self.assertFalse(safe_url('javascript:alert(1)'))
        self.assertFalse(safe_url('https://user:password@example.com'))
        self.assertFalse(safe_url('https://example.com/\nscript'))
        with self.assertRaises(ValueError):
            prepare_deals({'deals': [self.offer(source_url='javascript:alert(1)')]}, DEFAULT_TAXONOMY)

    def test_public_output_withholds_expired(self):
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.assertEqual(prepare_deals({'deals': [self.offer(ends_at=yesterday)]}, DEFAULT_TAXONOMY), [])

    def test_public_output_withholds_passed_expiry_cutoff(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self.assertEqual(prepare_deals({'deals': [self.offer(expiry_cutoff_at=past)]}, DEFAULT_TAXONOMY), [])
        self.assertEqual(len(prepare_deals({'deals': [self.offer(expiry_cutoff_at=future)]}, DEFAULT_TAXONOMY)), 1)
        with self.assertRaises(ValueError):
            prepare_deals({'deals': [self.offer(expiry_cutoff_at='2026-12-01')]}, DEFAULT_TAXONOMY)

    def test_confirmation_is_not_replaced_by_build_time(self):
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        result = prepare_deals({'deals': [self.offer(last_offer_confirmed_at=yesterday)]}, DEFAULT_TAXONOMY)[0]
        self.assertTrue(result['is_stale'])
        self.assertEqual(result['last_offer_confirmed_at'], yesterday)

    def test_duplicate_identity_fails_closed(self):
        with self.assertRaises(ValueError):
            prepare_deals({'deals': [self.offer(), self.offer()]}, DEFAULT_TAXONOMY)

    def test_historical_status_fails_closed(self):
        with self.assertRaises(ValueError):
            prepare_deals({'deals': [self.offer(campaign_year=2025)]}, DEFAULT_TAXONOMY)

    def test_nan_price_fails_closed(self):
        with self.assertRaises(ValueError):
            money(float('nan'), 'USD')

    def test_stale_upcoming_label_is_outside_closed_details(self):
        now = datetime.now(timezone.utc)
        future = (now + timedelta(days=1)).isoformat()
        old = (now - timedelta(hours=4)).isoformat()
        deal = prepare_deals({'deals': [self.offer(starts_at=future, last_offer_confirmed_at=old)]}, DEFAULT_TAXONOMY)[0]
        env = Environment(loader=FileSystemLoader(ROOT / 'web/templates'), autoescape=True)
        render_card = getattr(env.get_template('card.html').module, 'offer_card')
        html = str(render_card(deal, {'training': 'Training & Labs'}, {'appsec': 'AppSec'}))
        visible = html.split('<details', 1)[0]
        self.assertIn('Upcoming · Recheck pending', visible)

    def test_structured_data_never_invents_currency_and_is_script_safe(self):
        deals = prepare_deals({'deals': [self.offer(), self.offer(id='eur', currency='EUR', product='</script><b>x', offer_url='https://example.com/eur')]}, DEFAULT_TAXONOMY)
        context = {'deals': deals, 'collection': {'last_completed_at': None}, 'category_labels': {'training': 'Training & Labs'}}
        offers = {item['item']['url']: item['item'] for item in structured_data('/', 'T', 'D', context)['@graph'][2]['itemListElement']}
        self.assertNotIn('price', offers['https://example.com/offer'])
        self.assertEqual((offers['https://example.com/eur']['price'], offers['https://example.com/eur']['priceCurrency']), (60, 'EUR'))
        self.assertNotIn('</script>', json_for_html(offers))
        self.assertEqual(structured_data('/methodology/', 'T', 'D', dict(context, page_type='methodology'))['@graph'][2]['@type'], 'FAQPage')

    def test_llms_text_lists_offer_with_evidence(self):
        text = llms_text(prepare_deals({'deals': [self.offer(coupon='BF2026')]}, DEFAULT_TAXONOMY), {'training': 'Training & Labs'}, {'last_completed_at': None})
        self.assertIn('- [Vendor: Security course](https://example.com/offer): $60 (was $100) Training & Labs, code BF2026. Evidence: https://example.com/evidence', text)


if __name__ == '__main__':
    unittest.main()
