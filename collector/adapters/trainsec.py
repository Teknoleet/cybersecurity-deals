"""TrainSec's Elementor Black Friday landing page (not a general HTML scraper).

Only one linked course title per price container is accepted. This intentionally
omits catalog cards without a specific sale/reference pair, and quarantines
contradictory prices instead of attaching a page-wide coupon to arbitrary links.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

from collector.policy import clean, eligibility, identity

PRICE = re.compile(r'\$\s*([\d,]+(?:\.\d{1,2})?)\s+Instead\s+of\s+\$\s*([\d,]+(?:\.\d{1,2})?)', re.I)
URL = 'https://trainsec.net/cybersecurity-courses-black-friday-2026/'


def parse(body, source):
    soup = BeautifulSoup(body, 'html.parser')
    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
        element.decompose()
    # Campaign evidence comes only from the lead-in before the first course
    # category, not footer copyright, course names or linked advertisements.
    preamble = []
    for element in soup.find_all(['h1', 'h2', 'h3', 'p']):
        if element.name == 'h2':
            break
        text = clean(element.get_text(' ', strip=True))
        if text:
            preamble.append(text)
    campaign = ' '.join(preamble)
    evidence = {'campaign_text': campaign[:3000], 'official_corroboration': True,
                'scope': 'Individual course cards with their own advertised sale prices',
                'checkout_tested': False}
    basis = eligibility(evidence)
    if (basis != 'explicit_2026' or not re.search(r'November\s+2026\s+only', campaign, re.I)
            or not re.search(r'40\s*%\s*Discount', campaign, re.I)
            or not re.search(r'code\s+BF2026\b', campaign, re.I)
            or not re.search(r'Live events.*learning paths.*bundles.*subscriptions.*not included', campaign, re.I)):
        return [], [{'source_id': source['id'], 'source_url': source['url'],
                     'reason': 'trainsec_campaign_missing_or_changed',
                     'evidence_excerpt': campaign[:600]}], 'discovery'
    # A dollar sign is not USD evidence. US corporate address is not either.
    currency = 'USD' if re.search(r'\b(?:All (?:prices|amounts) (?:are )?(?:in )?USD|Prices (?:are )?in US dollars)\b', soup.get_text(' ', strip=True), re.I) else None
    deals, candidates = [], []
    category_heading = ''
    for heading in soup.find_all(['h2', 'h3']):
        if heading.name == 'h2':
            category_heading = clean(heading.get_text(' ', strip=True))
            continue
        anchor = heading.find('a', href=True)
        if not anchor:
            continue
        url = str(anchor['href'])
        p = urlsplit(url)
        if p.scheme != 'https' or p.hostname != 'trainsec.net' or not p.path.startswith('/courses/'):
            continue
        title = clean(heading.get_text(' ', strip=True))
        block = None
        # Choose the smallest enclosing container containing exactly this course
        # heading and a local price pair. Never ascend into a multi-course page.
        for parent in heading.parents:
            if parent.name in {'body', 'html'}:
                break
            linked_titles = [h for h in parent.find_all('h3') if h.find('a', href=True)]
            if len(linked_titles) > 1:
                break
            if len(linked_titles) == 1 and PRICE.search(parent.get_text(' ', strip=True)):
                block = parent
                break
        if block is None:
            candidates.append({'source_id': source['id'], 'source_url': source['url'],
                               'offer_url': url, 'product': title,
                               'reason': 'no_course_specific_sale_price'})
            continue
        text = clean(block.get_text(' ', strip=True))
        matches = set(PRICE.findall(text))
        if len(matches) != 1:
            candidates.append({'source_id': source['id'], 'source_url': source['url'],
                               'offer_url': url, 'product': title, 'reason': 'conflicting_course_prices'})
            continue
        sale_text, regular_text = next(iter(matches))
        sale, regular = (Decimal(x.replace(',', '')) for x in (sale_text, regular_text))
        if regular <= 0 or sale < 0 or sale >= regular:
            candidates.append({'source_id': source['id'], 'product': title, 'reason': 'invalid_price_pair'})
            continue
        discount = ((1 - sale / regular) * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if abs(discount - Decimal(40)) > Decimal('0.15'):
            candidates.append({'source_id': source['id'], 'product': title,
                               'reason': 'price_campaign_conflict', 'evidence_excerpt': text[-500:]})
            continue
        section = category_heading.casefold()
        if 'hardware' in section:
            topics = ['hardware-physical', 'reverse-engineering', 'offensive-security']
        elif 'defense' in section:
            topics = ['blue-team-dfir']
        elif 'malware' in section:
            topics = ['reverse-engineering', 'offensive-security', 'blue-team-dfir']
        else:
            topics = ['reverse-engineering']
        description = ''
        for div in block.select('.elementor-widget-text-editor'):
            candidate = clean(div.get_text(' ', strip=True))
            if len(candidate) > 90 and not PRICE.search(candidate):
                description = candidate[:900]
                break
        deal = {
            'id': '', 'vendor': 'TrainSec', 'product': title,
            'description': description or f'Individual course in {category_heading}.',
            'category': 'training', 'topics': topics,
            'campaign_type': 'black_friday', 'campaign_year': 2026,
            'eligibility_basis': basis, 'eligibility_evidence': dict(evidence),
            'source_id': source['id'], 'source_url': URL, 'discovery_urls': [],
            'offer_url': url, 'coupon': 'BF2026', 'currency': currency,
            'currency_symbol': '$', 'sale_price': float(sale), 'regular_price': float(regular),
            'discount_percent': float(discount), 'billing_period': None,
            'conditions': [
                'Individual courses only; live events, learning paths, bundles and subscriptions excluded.',
                'Apply BF2026 at checkout. Vendor-published; checkout not tested.',
                'Reference prices are vendor-advertised, not independently verified historical baselines.',
                'Tax/VAT inclusion, access terms and regional eligibility not established by this campaign page.',
            ],
            'scope': ['Individual course; non-subscription; regional eligibility unspecified'],
            'starts_at': None, 'ends_at': None, 'expiry_label': 'November 2026 only',
            'verification_status': 'vendor_published', 'last_offer_confirmed_at': None,
            'first_seen_at': None, 'price_history': [],
            'evidence_excerpt': f'{title}: ${sale_text} Instead of ${regular_text}. For November 2026 only; 40% Discount; code BF2026.',
            'marketplace': False,
            'reference_price_basis': 'vendor_advertised',
            'offer_timing': 'month_window_unknown_timezone',
        }
        deal['id'] = identity(deal)
        deals.append(deal)
    if not deals:
        raise ValueError('TrainSec parser found campaign but no validated course cards; selector review required')
    return deals, candidates, 'confirmed'
