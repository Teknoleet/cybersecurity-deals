"""Offline tests: real compact markup, deterministic clocks and no external I/O."""
from copy import deepcopy
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock, patch

from collector.adapters import trainsec, github_markdown, html_discovery, practical_devsecops, structured_offers
from collector.http import FetchError, Response, SafeFetcher, public_addresses, validate_url, PublicHTTPSConnection
from collector.import_evidence import corroborated, import_reviewed
from collector.policy import (acceptable, apply_overrides, deduplicate, eligibility,
                              identity, observe)
from collector.run import collect, source_record, valid_cache
from collector.state import atomic_json, load_json, validate_snapshot

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = (ROOT / 'tests/fixtures/trainsec.html').read_bytes()
REGISTRY = load_json(ROOT / 'config/sources.json')
TRAINSEC = {'id': 'trainsec-black-friday', 'name': 'TrainSec Black Friday', 'url': 'https://trainsec.net/cybersecurity-courses-black-friday-2026/',
            'type': 'official', 'adapter': 'trainsec', 'capability': 'supported', 'enabled': True, 'topics': ['offensive-security'],
            'note': 'Test-only registration of the removed TrainSec source; exercises official-adapter policy paths.'}
REGISTRY = {**REGISTRY, 'policy': {**REGISTRY['policy'], 'supported_official_domains': ['trainsec.net', *REGISTRY['policy']['supported_official_domains']]}, 'sources': [TRAINSEC, *REGISTRY['sources']]}
SOURCE = TRAINSEC
GITHUB = next(x for x in REGISTRY['sources'] if x['id'] == 'github-0x90n')
NOW = '2026-11-03T10:00:00Z'
LATER = '2026-11-03T11:00:00Z'


def offer():
    return deepcopy(trainsec.parse(FIXTURE, SOURCE)[0][0])


def registry(*sources):
    return {**REGISTRY, 'sources': list(sources or [SOURCE])}


def result(body=FIXTURE, status=200, url=None, headers=None):
    return Response(status, url or SOURCE['url'], body,
                    headers or {'content-type': 'text/html', 'etag': '"real-1"',
                                'last-modified': 'Tue, 03 Nov 2026 08:00:00 GMT'})


def collect_once(response=None, previous=None, cache=None, at=NOW, reg=None, **kwargs):
    f = Mock()
    if isinstance(response, Exception):
        f.fetch.side_effect = response
    else:
        f.fetch.return_value = response or result()
    snapshot, candidates, cache = collect(reg or registry(), previous, cache, f, now=at, **kwargs)
    return snapshot, candidates, cache, f


class TrainSecTests(unittest.TestCase):
    def test_real_scoped_card_prices(self):
        deals, candidates, status = trainsec.parse(FIXTURE, SOURCE)
        self.assertEqual(status, 'confirmed')
        edr = next(x for x in deals if x['product'].startswith('EDR'))
        malware = next(x for x in deals if x['product'].startswith('Malware Analysis'))
        windbg = next(x for x in deals if x['product'] == 'Mastering WinDbg')
        self.assertEqual((edr['sale_price'], edr['regular_price']), (1260, 2100))
        self.assertEqual((malware['sale_price'], malware['regular_price']), (534, 890))
        self.assertEqual((windbg['sale_price'], windbg['regular_price']), (105, 175))
        self.assertEqual(edr['discount_percent'], 40)
        self.assertIsNone(edr['currency'])
        self.assertEqual(edr['currency_symbol'], '$')
        self.assertIsNone(edr['ends_at'])
        self.assertEqual(edr['expiry_label'], 'November 2026 only')
        self.assertTrue(any(x['reason'] == 'no_course_specific_sale_price' for x in candidates))
        self.assertTrue(any(x['reason'] == 'price_campaign_conflict' for x in candidates))

    def test_hardware_course_is_training(self):
        deals, _, _ = trainsec.parse(FIXTURE, SOURCE)
        hardware = next(x for x in deals if 'UART Hacking' in x['product'])
        self.assertEqual(hardware['category'], 'training')
        self.assertIn('hardware-physical', hardware['topics'])
        self.assertIn('reverse-engineering', hardware['topics'])

    def test_no_broad_coupon_association(self):
        # Add an arbitrary unrelated course title outside any local price card.
        extra = b'<h3><a href="https://trainsec.net/courses/unrelated/">Unrelated course</a></h3>'
        deals, _, _ = trainsec.parse(FIXTURE.replace(b'</main>', extra + b'</main>'), SOURCE)
        self.assertNotIn('Unrelated course', [x['product'] for x in deals])

    def test_footer_2026_cannot_qualify_2025_campaign(self):
        old = FIXTURE.replace(b'2026', b'2025') + b'<footer>Copyright 2026</footer>'
        deals, _, status = trainsec.parse(old, SOURCE)
        self.assertEqual(deals, [])
        self.assertEqual(status, 'discovery')

    def test_missing_exclusions_blocks_campaign(self):
        altered = FIXTURE.replace(b'not included', b'included')
        deals, _, _ = trainsec.parse(altered, SOURCE)
        self.assertEqual(deals, [])

    def test_usd_requires_explicit_source_evidence(self):
        deals, _, _ = trainsec.parse(FIXTURE + b'<p>All prices are in USD</p>', SOURCE)
        self.assertTrue(all(x['currency'] == 'USD' for x in deals))

    def test_course_name_year_is_not_campaign(self):
        changed = FIXTURE.replace(b'November 2026', b'November 2025').replace(b'2026 Black Friday', b'2025 Black Friday').replace(b'BF2026', b'BF2025')
        self.assertEqual(trainsec.parse(changed, SOURCE)[0], [])


class EligibilityTests(unittest.TestCase):
    def test_scoped_campaign(self):
        self.assertEqual(eligibility({'campaign_text': '2026 Black Friday 40% sale'}), 'explicit_2026')

    def test_footer_course_title_and_updated_date_ignored(self):
        self.assertIsNone(eligibility({'page_text': 'Copyright 2026 Black Friday', 'course_title': 'Cybersecurity 2026', 'date_modified': '2026-10-15T00:00:00Z'}))

    def test_original_october_exception(self):
        evidence = {'original_published_at': '2026-10-31T20:00:00Z',
                    'original_date_verified': True, 'original_date_source': 'article:published_time'}
        self.assertEqual(eligibility(evidence), 'october_2026')
        evidence['original_published_at'] = '2026-11-01T00:00:00Z'
        self.assertIsNone(eligibility(evidence))

    def test_date_conflict_and_historical_block(self):
        for flag in ('date_conflict', 'historical'):
            self.assertIsNone(eligibility({'campaign_text': 'Black Friday sale 2026', flag: True}))

    def test_unverified_original_date_blocks(self):
        self.assertIsNone(eligibility({'original_published_at': '2026-10-10T00:00:00Z'}))

    def test_original_date_uses_publisher_calendar_not_utc_shift(self):
        evidence = {'original_published_at': '2026-11-01T00:30:00+02:00',
                    'original_date_verified': True, 'original_date_source': 'article:published_time'}
        self.assertIsNone(eligibility(evidence))
        evidence['original_published_at'] = '2026-10-31T23:30:00-05:00'
        self.assertEqual(eligibility(evidence), 'october_2026')

    def test_historical_coupon_not_relabelled_by_new_campaign(self):
        for coupon in ('BFCM25', 'BLACKFRIDAY2025', 'BF2025'):
            d = offer()
            d['coupon'] = coupon
            self.assertEqual(acceptable(d, NOW)[1], 'historical_coupon')

    def test_missing_expiry_stays_unknown(self):
        d = offer()
        d['expiry_label'] = None
        self.assertEqual(acceptable(d, '2027-02-01T00:00:00Z'), (True, None))

    def test_explicit_expiry_and_month_window(self):
        d = offer()
        d['ends_at'] = '2026-11-03T09:00:00Z'
        self.assertEqual(acceptable(d, NOW)[1], 'expired')
        d['ends_at'] = None
        self.assertEqual(acceptable(d, '2026-12-02T00:00:00Z')[1], 'expired_month_window')
        self.assertIsNone(d['ends_at'])

    def test_future_start_is_eligible_upcoming(self):
        d = offer()
        d['starts_at'] = '2026-11-20T00:00:00Z'
        self.assertTrue(acceptable(d, NOW)[0])

    def test_software_marketplace_authorization(self):
        d = offer()
        d.update({'marketplace': True, 'category': 'software', 'verification_status': 'marketplace_published'})
        self.assertEqual(acceptable(d, NOW)[1], 'unconfirmed_license_provenance')
        d['eligibility_evidence']['seller_authorized'] = True
        self.assertTrue(acceptable(d, NOW)[0])

    def test_missing_current_official_corroboration(self):
        d = offer()
        d['eligibility_evidence']['official_corroboration'] = False
        self.assertEqual(acceptable(d, NOW)[1], 'missing_current_official_corroboration')


class DiscoveryTests(unittest.TestCase):
    def test_historical_readme_does_not_publish_codes_or_deals(self):
        markdown = (ROOT / 'tests/fixtures/infosec-readme.md').read_bytes()
        deals, candidates, status = github_markdown.parse(markdown, GITHUB)
        self.assertEqual(status, 'historical')
        self.assertEqual(deals, [])
        self.assertTrue(candidates)
        self.assertTrue(all(x['automatic_publication'] is False for x in candidates))
        self.assertNotIn('BLACKFRIDAY2025', str(candidates))
        self.assertTrue(all(x['campaign_year'] == 2025 for x in candidates))
        self.assertTrue(any(x['entry_status'] == 'unconfirmed' for x in candidates))

    def test_2026_list_is_still_discovery_only(self):
        deals, _, status = github_markdown.parse('# Black Friday 2026\nhttps://trainsec.net/cybersecurity-courses-black-friday/\n', GITHUB)
        self.assertEqual(deals, [])
        self.assertEqual(status, 'discovery')

    def test_safe_bounded_follow_known_canonical_only(self):
        github = GITHUB
        f = Mock()
        f.fetch.side_effect = [Response(200, github['fetch_url'], b'# 2026 deals\nhttps://trainsec.net/cybersecurity-courses-black-friday/\nhttps://unknown.example/\nhttps://trainsec.net/courses/arbitrary/\n', {'content-type': 'text/plain'}), result()]
        snap, _, _ = collect(registry(github, SOURCE), None, {}, f, now=NOW, max_sources=2)
        self.assertEqual(f.fetch.call_count, 2)
        self.assertEqual(snap['collection']['successful_sources'], 2)
        self.assertTrue(snap['deals'])

    def test_source_selection_never_follows_other_source(self):
        github = GITHUB
        f = Mock()
        f.fetch.return_value = Response(200, github['fetch_url'], b'# 2026\nhttps://trainsec.net/cybersecurity-courses-black-friday/\n', {})
        snap, _, _ = collect(registry(github, SOURCE), None, {}, f, now=NOW, selected=[github['id']])
        self.assertEqual(f.fetch.call_count, 1)
        self.assertEqual(snap['deals'], [])


class PracticalDevSecOpsTests(unittest.TestCase):
    FIXTURE = (ROOT / 'tests/fixtures/practical-devsecops-2026.html').read_bytes()
    SOURCE = next(x for x in REGISTRY['sources'] if x['id'] == 'practical-devsecops-2026')

    def test_singles_publish_bundles_and_coming_soon_do_not(self):
        deals, candidates, status = practical_devsecops.parse(self.FIXTURE, self.SOURCE)
        self.assertEqual(status, 'confirmed')
        by_name = {x['product']: x for x in deals}
        self.assertEqual(set(by_name), {'Certified DevSecOps Professional (CDP)', 'Certified AI Security Professional (CAISP)'})
        self.assertEqual({x['reason'] for x in candidates}, {'bundle_or_unlabelled_pricing_needs_review', 'course_not_yet_available'})
        cdp = by_name['Certified DevSecOps Professional (CDP)']
        self.assertEqual((cdp['sale_price'], cdp['regular_price'], cdp['discount_percent']), (764.15, 899.0, 15.0))
        self.assertEqual(cdp['offer_url'], 'https://www.practical-devsecops.com/pre-signup/?course=cdp')
        self.assertEqual(cdp['eligibility_basis'], 'explicit_2026')
        self.assertTrue(all(acceptable(x, NOW)[0] for x in deals))

    def test_usd_only_from_matching_vendor_banner_card(self):
        by_name = {x['product']: x for x in practical_devsecops.parse(self.FIXTURE, self.SOURCE)[0]}
        self.assertEqual(by_name['Certified AI Security Professional (CAISP)']['currency'], 'USD')
        self.assertIsNone(by_name['Certified DevSecOps Professional (CDP)']['currency'])

    def test_site_banner_and_footer_year_are_not_campaign_evidence(self):
        body = self.FIXTURE.replace(b'Best InfoSec Black Friday Deals 2026', b'Best InfoSec Deals')
        deals, candidates, status = practical_devsecops.parse(body, self.SOURCE)
        self.assertEqual((deals, status), ([], 'discovery'))
        self.assertEqual(candidates[0]['reason'], 'practical_devsecops_campaign_missing_or_changed')


class StructuredOffersTests(unittest.TestCase):
    FIXTURE = (ROOT / 'tests/fixtures/structured-offers-2026.html').read_bytes()
    SOURCE = {'id': 'vendor-structured', 'name': 'Vendor Example Black Friday 2026',
              'url': 'https://www.vendor.example/black-friday-2026/', 'type': 'official',
              'adapter': 'structured_offers', 'capability': 'supported', 'enabled': True,
              'topics': ['offensive-security'], 'note': 'Test-only structured-data source.',
              'structured': {'vendor': 'Vendor Example', 'category': 'training', 'topics': ['offensive-security']}}

    def parse(self, body=None, **changes):
        return structured_offers.parse(body or self.FIXTURE, {**self.SOURCE, **changes})

    def reg(self, *domains):
        return {**REGISTRY, 'policy': {**REGISTRY['policy'], 'supported_official_domains': list(domains)},
                'sources': [self.SOURCE]}

    def test_only_priced_vendor_offers_publish(self):
        deals, candidates, status = self.parse()
        self.assertEqual(status, 'confirmed')
        by_name = {x['product']: x for x in deals}
        self.assertEqual(set(by_name), {'Red Team Operator', 'Lab Subscription — Annual'})
        rto = by_name['Red Team Operator']
        self.assertEqual((rto['sale_price'], rto['regular_price'], rto['discount_percent'], rto['currency']), (150.0, 300.0, 50.0, 'USD'))
        self.assertEqual(rto['offer_url'], 'https://www.vendor.example/courses/rto')
        self.assertEqual(rto['description'], 'Hands-on adversary emulation labs.')
        self.assertEqual((rto['category'], rto['topics'], rto['vendor']), ('training', ['offensive-security'], 'Vendor Example'))
        labs = by_name['Lab Subscription — Annual']
        self.assertEqual(labs['offer_url'], 'https://checkout.vendor.example/labs/annual')
        self.assertEqual(labs['starts_at'], '2026-11-20T00:00:00Z')
        self.assertEqual({x['product']: x['reason'] for x in candidates if 'product' in x}, {
            'Lab Subscription': 'structured_offer_missing_reference_price',
            'Range Bundle': 'aggregate_offer_needs_review',
            'Partner Course': 'offer_link_left_vendor_domain',
            'Badge Kit': 'structured_offer_not_available',
            'Exam Voucher': 'invalid_price_pair',
            'Mystery Box': 'structured_offer_missing_currency'})
        self.assertIn('malformed_structured_data', {x['reason'] for x in candidates})
        self.assertTrue(all(x['coupon'] is None for x in deals))
        self.assertNotIn('SAVE2026', str(deals))
        self.assertTrue(all(acceptable(x, NOW)[0] for x in deals))

    def test_structured_data_alone_is_not_campaign_evidence(self):
        body = self.FIXTURE.replace(b'<h1>Black Friday 2026 Sale</h1>', b'<h1>Pricing</h1>')
        deals, candidates, status = self.parse(body)
        self.assertEqual((deals, status), ([], 'discovery'))
        self.assertEqual(candidates[0]['reason'], 'structured_campaign_missing_or_changed')
        body = self.FIXTURE.replace(b'Black Friday 2026 Sale', b'Black Friday 2025 Sale')
        self.assertEqual(self.parse(body)[0], [])

    def test_campaign_without_publishable_offers_is_discovery(self):
        body = self.FIXTURE.replace(b'ListPrice', b'SalePrice').replace(b'StrikethroughPrice', b'SalePrice')
        deals, candidates, status = self.parse(body)
        self.assertEqual((deals, status), ([], 'discovery'))
        self.assertIn('structured_campaign_without_publishable_offers', {x['reason'] for x in candidates})

    def test_registry_configuration_fails_closed(self):
        config = self.SOURCE['structured']
        for bad in ({'type': 'roundup'}, {'structured': None},
                    {'structured': {**config, 'category': 'gadgets'}},
                    {'structured': {**config, 'topics': ['video']}},
                    {'structured': {**config, 'topics': []}},
                    {'structured': {**config, 'vendor': ' '}},
                    {'structured': {**config, 'item_types': ['Event']}},
                    {'structured': {**config, 'sale_price': 1}}):
            with self.assertRaises(ValueError):
                self.parse(**bad)

    def test_date_only_expiry_is_enforced_once_passed_everywhere(self):
        rto = next(x for x in self.parse()[0] if x['product'] == 'Red Team Operator')
        self.assertIsNone(rto['ends_at'])
        self.assertEqual(rto['expiry_label'], 'Until 2026-12-01 (vendor date; time zone not stated)')
        self.assertEqual(rto['expiry_cutoff_at'], '2026-12-02T12:00:00Z')
        self.assertTrue(acceptable(rto, '2026-12-02T11:59:59Z')[0])
        self.assertEqual(acceptable(rto, '2026-12-02T12:00:00Z'), (False, 'expired'))

    def test_publication_requires_supported_official_domain(self):
        response = result(self.FIXTURE, url=self.SOURCE['url'])
        snap, candidates, _, _ = collect_once(response, reg=self.reg('www.practical-devsecops.com'))
        self.assertEqual(snap['deals'], [])
        self.assertEqual(snap['sources'][0]['status'], 'unavailable')
        snap, _, _, _ = collect_once(response, reg=self.reg('www.vendor.example'))
        self.assertEqual(len(snap['deals']), 2)
        self.assertEqual(snap['sources'][0]['status'], 'confirmed')
        self.assertTrue(validate_snapshot(snap))
        upcoming = next(x for x in snap['deals'] if x['product'] == 'Lab Subscription — Annual')
        self.assertEqual(upcoming['offer_timing'], 'upcoming')
        later, _, _, _ = collect_once(FetchError('blocked'), snap, at='2026-12-02T12:00:00Z', reg=self.reg('www.vendor.example'))
        self.assertEqual([x['product'] for x in later['deals']], ['Lab Subscription — Annual'])


class HtmlDiscoveryTests(unittest.TestCase):
    def test_historical_roundup_yields_external_candidates_only(self):
        source = {'id': 'roundup', 'url': 'https://roundup.example/deals/'}
        deals, candidates, status = html_discovery.parse((ROOT / 'tests/fixtures/roundup-2025.html').read_bytes(), source)
        self.assertEqual((deals, status), ([], 'historical'))
        self.assertEqual([x['offer_url'] for x in candidates], ['https://vendor.example/sale'])
        self.assertEqual(candidates[0]['published_at'], '2025-11-20T09:00:00+00:00')
        self.assertEqual(candidates[0]['section'], 'Training')
        self.assertFalse(candidates[0]['automatic_publication'])
        self.assertNotIn('BF2025', str(candidates))


class LifecycleTests(unittest.TestCase):
    def test_failure_retains_original_offer_confirmation(self):
        first, _, cache, _ = collect_once()
        later, _, _, _ = collect_once(FetchError('blocked'), first, cache, at=LATER)
        self.assertEqual(later['deals'], first['deals'])
        source = later['sources'][0]
        self.assertEqual(source['last_attempt_at'], LATER)
        self.assertEqual(source['last_successful_fetch_at'], NOW)
        self.assertEqual(source['last_offer_confirmed_at'], NOW)
        self.assertEqual(source['status'], 'unavailable')

    def test_successful_changed_page_withdraws_unmatched_offer(self):
        first, _, cache, _ = collect_once()
        changed = FIXTURE.replace(b'$1,260 Instead of $2,100', b'No longer offered')
        later, candidates, _, _ = collect_once(result(changed), first, cache, at=LATER)
        self.assertFalse(any(x['product'].startswith('EDR') for x in later['deals']))
        self.assertTrue(any(x['reason'] == 'withdrawn_or_no_longer_matched' for x in candidates['candidates']))

    def test_successfully_changed_campaign_does_not_retain_current(self):
        first, _, cache, _ = collect_once()
        changed = FIXTURE.replace(b'BF2026', b'OLD-CODE')
        later, _, _, _ = collect_once(result(changed), first, cache, at=LATER)
        self.assertEqual(later['deals'], [])
        self.assertEqual(later['sources'][0]['last_offer_confirmed_at'], NOW)
        self.assertEqual(later['sources'][0]['last_successful_fetch_at'], LATER)

    def test_confirmed_304_requires_matching_representation(self):
        first, _, cache, _ = collect_once()
        later, _, _, f = collect_once(result(status=304, body=b''), first, cache, at=LATER)
        self.assertEqual(later['sources'][0]['last_offer_confirmed_at'], LATER)
        self.assertTrue(all(x['last_offer_confirmed_at'] == LATER for x in later['deals']))
        self.assertEqual(f.fetch.call_args.kwargs['headers']['If-None-Match'], '"real-1"')
        self.assertTrue(all(x['first_seen_at'] == NOW for x in later['deals']))
        self.assertTrue(all(len(x['price_history']) == 1 for x in later['deals']))

    def test_bare_304_does_not_create_or_confirm_offers(self):
        snap, _, _, _ = collect_once(result(status=304))
        self.assertEqual(snap['deals'], [])
        self.assertEqual(snap['sources'][0]['status'], 'unavailable')
        self.assertIsNone(snap['sources'][0]['last_successful_fetch_at'])

    def test_tampered_cache_304_does_not_freshen_previous(self):
        first, _, cache, _ = collect_once()
        cache[SOURCE['id']]['deals'][0]['sale_price'] = 1
        self.assertFalse(valid_cache(cache[SOURCE['id']], SOURCE))
        later, _, _, _ = collect_once(result(status=304), first, cache, at=LATER)
        self.assertEqual(later['deals'], first['deals'])
        self.assertEqual(later['sources'][0]['status'], 'unavailable')

    def test_304_conflicting_entity_tag_is_not_confirmation(self):
        first, _, cache, _ = collect_once()
        response = result(status=304, headers={'etag': '"different-representation"'})
        later, _, _, _ = collect_once(response, first, cache, at=LATER)
        self.assertEqual(later['deals'], first['deals'])
        self.assertEqual(later['sources'][0]['status'], 'unavailable')

    def test_expiry_still_applies_on_fetch_failure(self):
        first, _, cache, _ = collect_once()
        later, _, _, _ = collect_once(FetchError('blocked'), first, cache, at='2026-12-02T00:00:00Z')
        self.assertEqual(later['deals'], [])

    def test_cross_origin_official_redirect_cannot_publish(self):
        snap, _, _, _ = collect_once(result(url='https://unrelated.example/'))
        self.assertEqual(snap['deals'], [])
        self.assertEqual(snap['sources'][0]['status'], 'unavailable')

    def test_fetch_count_bounded(self):
        github = GITHUB
        snap, _, _, f = collect_once(reg=registry(SOURCE, github), max_sources=1)
        self.assertEqual(f.fetch.call_count, 1)
        self.assertEqual(snap['collection']['successful_sources'], 1)

    def test_invalid_override_cannot_destroy_existing_output(self):
        with self.assertRaises(ValueError):
            collect_once(overrides={'corrections': {'fake': {'sale_price': 1}}})

    def test_full_snapshot_invariants(self):
        snap, _, _, _ = collect_once()
        self.assertTrue(validate_snapshot(snap))
        snap['deals'][0]['last_offer_confirmed_at'] = '2026-11-04T00:00:00Z'
        with self.assertRaises(ValueError):
            validate_snapshot(snap)


class IdentityHistoryOverrideTests(unittest.TestCase):
    def test_dedupe_unions_provenance(self):
        a, b = offer(), offer()
        b['source_url'] = 'https://trainsec.net/another-official-evidence/'
        a['discovery_urls'] = ['https://github.com/example/list']
        b['discovery_urls'] = ['https://example.org/roundup']
        deals, conflicts = deduplicate([a, b])
        self.assertEqual(len(deals), 1)
        self.assertEqual(conflicts, [])
        self.assertEqual(len(deals[0]['discovery_urls']), 2)
        self.assertEqual(len(deals[0]['provenance']), 2)

    def test_conflicting_prices_are_quarantined_not_stale(self):
        a, b = offer(), offer()
        b['sale_price'] = 900
        deals, conflicts = deduplicate([a, b])
        self.assertEqual(deals, [])
        self.assertEqual(conflicts[0]['reason'], 'conflicting_prices')

    def test_fresh_identical_evidence_wins_over_stale_source(self):
        stale = observe(offer(), None, NOW)
        fresh = observe(offer(), None, LATER)
        deals, _ = deduplicate([stale, fresh])
        self.assertEqual(deals[0]['last_offer_confirmed_at'], LATER)
        self.assertEqual(deals[0]['first_seen_at'], NOW)

    def test_plans_billing_coupon_scope_are_distinct(self):
        d = offer()
        for key, value in [('product', 'Different plan'), ('billing_period', 'annual'),
                           ('coupon', 'OTHER2026'), ('scope', ['Netherlands only'])]:
            other = deepcopy(d)
            other[key] = value
            self.assertNotEqual(identity(d), identity(other))

    def test_price_change_only_history_max_90(self):
        d = offer()
        previous = None
        for i in range(100):
            d['sale_price'] = 100 + i
            previous = observe(d, previous, NOW)
        assert previous is not None
        self.assertEqual(len(previous['price_history']), 90)
        unchanged = observe(d, previous, LATER)
        self.assertEqual(unchanged['price_history'], previous['price_history'])
        self.assertEqual(unchanged['first_seen_at'], NOW)

    def test_currency_change_resets_comparability(self):
        d = offer()
        previous = observe(d, None, NOW)
        d['currency'] = 'USD'
        current = observe(d, previous, LATER)
        self.assertEqual(len(current['price_history']), 1)
        self.assertEqual(current['price_history'][0]['at'], LATER)

    def test_safe_overrides_and_exclusions(self):
        d = offer()
        self.assertEqual(apply_overrides([d], {'exclude': [d['id']]}), [])
        new = apply_overrides([d], {'corrections': {d['id']: {'description': 'Clear plain-text correction'}}})
        self.assertEqual(new[0]['description'], 'Clear plain-text correction')
        for key in ('sale_price', 'eligibility_basis', 'offer_url', 'last_offer_confirmed_at'):
            with self.assertRaises(ValueError):
                apply_overrides([d], {'corrections': {d['id']: {key: 'bad'}}})
        with self.assertRaises(ValueError):
            apply_overrides([d], {'corrections': {d['id']: {'description': '<script>alert(1)</script>'}}})


class NetworkSafetyTests(unittest.TestCase):
    def setUp(self):
        self.public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]

    def test_unsafe_schemes_ports_credentials_and_control_chars(self):
        for url in ('file:///etc/passwd', 'http://user:password@example.com/', 'gopher://example.com/',
                    'http://example.com:8080/', 'https://example.com/\r\nX:yes', 'http://example.com\\@localhost/'):
            with self.subTest(url=url), self.assertRaises(FetchError):
                validate_url(url)

    def test_private_local_metadata_reserved_dns_blocked(self):
        for ip in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '192.168.1.1', '100.64.0.1',
                   '0.0.0.0', '224.0.0.1', '192.0.2.1', '::1', 'fd00::1', 'fe80::1', '::ffff:127.0.0.1'):
            family = socket.AF_INET6 if ':' in ip else socket.AF_INET
            with self.subTest(ip=ip), patch('collector.http.socket.getaddrinfo', return_value=[(family, socket.SOCK_STREAM, 6, '', (ip, 443))]):
                with self.assertRaises(FetchError):
                    public_addresses('looks-public.example', 443)

    def test_any_private_answer_blocks_mixed_dns(self):
        mixed = self.public_dns + [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
        with patch('collector.http.socket.getaddrinfo', return_value=mixed), self.assertRaises(FetchError):
            validate_url('https://example.com/')

    def test_public_url_and_no_environment_proxy(self):
        with patch('collector.http.socket.getaddrinfo', return_value=self.public_dns):
            self.assertEqual(validate_url('https://example.com/').hostname, 'example.com')
        f = SafeFetcher()
        self.assertFalse(f.session.trust_env)
        f.close()

    def test_socket_connects_validated_numeric_address(self):
        conn = PublicHTTPSConnection('example.com', timeout=1)
        fake_socket = Mock()
        with patch('collector.http.socket.getaddrinfo', return_value=self.public_dns), patch('collector.http.socket.socket', return_value=fake_socket):
            self.assertIs(conn._new_conn(), fake_socket)
            fake_socket.connect.assert_called_once_with(('93.184.216.34', 443))

    def test_redirect_private_target_blocked(self):
        f = SafeFetcher()
        def dns(host, *args, **kwargs):
            return self.public_dns if host == 'example.com' else [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 80))]
        with patch('collector.http.socket.getaddrinfo', side_effect=dns), patch.object(f, '_obey_robots'), patch.object(f, '_request', return_value=Response(302, 'https://example.com/', b'', {'location': 'http://127.0.0.1/'})):
            with self.assertRaises(FetchError):
                f.fetch('https://example.com/')
        f.close()

    def test_robots_unavailable_fails_closed(self):
        for status in (403, 500, 302):
            f = SafeFetcher()
            with patch.object(f, '_request', return_value=Response(status, 'https://example.com/robots.txt', b'', {})):
                with self.assertRaises(FetchError):
                    f._obey_robots('https://example.com/page')
            f.close()

    def test_robots_disallows_and_caches(self):
        f = SafeFetcher()
        body = b'User-agent: *\nDisallow: /private\n'
        with patch.object(f, '_request', return_value=Response(200, 'https://example.com/robots.txt', body, {})) as req:
            f._obey_robots('https://example.com/public')
            with self.assertRaises(FetchError):
                f._obey_robots('https://example.com/private')
            self.assertEqual(req.call_count, 1)
        f.close()

    def test_oversized_stream_is_rejected(self):
        f = SafeFetcher(max_bytes=100)
        response = Mock()
        response.status_code = 200
        response.headers = {'Content-Length': '101'}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('collector.http.socket.getaddrinfo', return_value=self.public_dns), patch.object(f.session, 'get', return_value=response):
            with self.assertRaises(FetchError):
                f._request('https://example.com/')
        f.close()

    def test_domain_and_total_budget(self):
        f = SafeFetcher(max_requests=0)
        with patch('collector.http.socket.getaddrinfo', return_value=self.public_dns), self.assertRaises(FetchError):
            f._request('https://example.com/')
        f.close()


class ReviewedImportTests(unittest.TestCase):
    def test_corroboration_requires_own_course_price_pair(self):
        d = offer()
        markdown = f'### [{d["product"]}]({d["offer_url"]})\n$1,260 Instead of $2,100\n'
        self.assertTrue(corroborated(d, markdown))
        self.assertFalse(corroborated(d, markdown.replace('$1,260', '$999')))
        self.assertFalse(corroborated(d, markdown.replace(d['offer_url'], 'https://trainsec.net/courses/other/')))

    def test_import_rejects_future_and_old_evidence(self):
        for date in ('2027-01-01T00:00:00Z', '2025-11-01T00:00:00Z'):
            with self.assertRaises(ValueError):
                import_reviewed(REGISTRY, FIXTURE, '', date, 'first_party_tool_extraction', trainsec.URL, now=NOW)

    def test_reviewed_import_does_not_claim_automatic_fetch(self):
        d = offer()
        preamble = 'November 2026 only BF2026 40% Discount Live events, learning paths, bundles and subscriptions are not included\n## Malware Analysis\n'
        markdown = preamble + f'### [{d["product"]}]({d["offer_url"]})\n$1,260 Instead of $2,100\n'
        snap, _, receipt = import_reviewed(REGISTRY, FIXTURE, markdown, NOW, 'first_party_tool_extraction', trainsec.URL, now=LATER)
        self.assertEqual(len(snap['deals']), 1)
        self.assertEqual(snap['deals'][0]['last_offer_confirmed_at'], NOW)
        source = snap['sources'][0]
        self.assertIsNone(source['last_successful_fetch_at'])
        self.assertIsNone(source['last_attempt_at'])
        self.assertEqual(receipt['observed_at'], NOW)

    def test_atomic_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            atomic_json(path, {'hello': 'world'})
            self.assertEqual(load_json(path), {'hello': 'world'})
            self.assertEqual(list(Path(folder).glob('.*')), [])


if __name__ == '__main__':
    unittest.main()
