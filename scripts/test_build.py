"""Static generation safety checks, independent of network or deployment."""
import unittest
from datetime import datetime, timedelta, timezone
from jinja2 import Environment, FileSystemLoader
from scripts.build import DEFAULT_TAXONOMY, ROOT, money, prepare_deals, safe_url


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


if __name__ == '__main__':
    unittest.main()
