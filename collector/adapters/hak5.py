"""Hak5's own seasonal sale page on its Shopify store (not a general scraper).

Listing on the vendor's own seasonal sale page inside the 2026 window is the
eligibility criterion. Each product card publishes from its dedicated current
and crossed-out price fields; a "from" price is a variant range and stays a
candidate, and a card without a crossed-out price is not an offer. Currency is
recorded only from the store's own active-currency declaration on the page.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup

from collector.policy import clean, eligibility, identity

ORIGIN = 'https://shop.hak5.org'
MONEY = re.compile(r'^\$\s*([\d,]+(?:\.\d{1,2})?)$')
CURRENCY = re.compile(r'Shopify\.currency\s*=\s*\{"active":"([A-Z]{3})"')
CODE = re.compile(r'discount code\s+([A-Z0-9]{6,20})\b', re.I)


def money(text):
    found = MONEY.match(clean(text or ''))
    return Decimal(found.group(1).replace(',', '')) if found else None


def parse(body, source):
    raw = body if isinstance(body, str) else body.decode('utf-8', 'replace')
    currency_match = CURRENCY.search(raw)
    currency = currency_match.group(1) if currency_match else None
    soup = BeautifulSoup(body, 'html.parser')
    for element in soup(['script', 'style', 'noscript', 'nav', 'footer']):
        element.decompose()
    title = clean(soup.title.get_text(' ', strip=True) if soup.title else '')
    banner = soup.find(class_='pxu-sales-banner__heading')
    banner_text = clean(banner.find_parent().get_text(' ', strip=True)) if banner and banner.find_parent() else ''
    campaign = ' '.join(x for x in (title, banner_text) if x)[:1500]
    evidence = {'campaign_text': campaign, 'official_corroboration': True, 'vendor_page': True,
                'scope': 'Product cards with their own current and crossed-out prices on the vendor sale page',
                'checkout_tested': False}
    basis = eligibility(evidence)
    if basis is None:
        return [], [{'source_id': source['id'], 'source_url': source['url'],
                     'reason': 'hak5_campaign_missing_or_changed', 'evidence_excerpt': campaign[:600]}], 'discovery'
    code = CODE.search(banner_text)
    conditions = [
        'Vendor-published store listing; checkout not tested.',
        'Expiry is not published. Tax, shipping and regional eligibility not established.',
    ]
    if code:
        conditions.append(f'The vendor advertises a stackable code ({code.group(1)}) for selected gear; it is not applied to the listed price.')
    deals, candidates = [], []
    for card in soup.find_all('div', class_='product-details'):
        name = card.find('span', class_='title')
        product = clean(re.sub(r'[\U0001F300-\U0001FAFF☀-➿]', '', name.get_text(' ', strip=True))) if name else ''
        price = card.find('span', class_='price')
        current = card.find('span', class_='current_price')
        was = card.find('span', class_='was_price')
        if not product or price is None or current is None:
            continue
        if 'sale' not in (price.get('class') or []) or was is None:
            continue  # Regular-price listing, not an offer.
        sale = money(current.get_text(' ', strip=True))
        if sale is None:
            candidates.append({'source_id': source['id'], 'product': product, 'reason': 'variant_price_range_needs_review',
                               'evidence_excerpt': clean(card.get_text(' ', strip=True))[:300]})
            continue
        regular = money(was.get_text(' ', strip=True))
        if regular is not None and (regular <= 0 or sale >= regular):
            regular = None
        anchor = card.find_parent('a', href=True)
        if anchor is None:
            candidates.append({'source_id': source['id'], 'product': product, 'reason': 'offer_link_missing'})
            continue
        url = urljoin(ORIGIN + '/', str(anchor['href']))
        if urlsplit(url).hostname != urlsplit(ORIGIN).hostname:
            candidates.append({'source_id': source['id'], 'product': product, 'reason': 'offer_link_left_vendor_domain'})
            continue
        discount = ((1 - sale / regular) * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if regular else None
        deal = {
            'id': '', 'vendor': 'Hak5', 'product': product,
            'description': f'{product} listed on the Hak5 store sale page.',
            'category': 'hardware', 'topics': list(source.get('topics') or ['hardware-physical']),
            'campaign_type': 'general_promotion', 'campaign_year': 2026,
            'eligibility_basis': basis, 'eligibility_evidence': dict(evidence),
            'source_id': source['id'], 'source_url': source['url'], 'discovery_urls': [],
            'offer_url': url, 'coupon': None, 'currency': currency, 'currency_symbol': '$',
            'sale_price': float(sale), 'regular_price': float(regular) if regular else None,
            'discount_percent': float(discount) if discount is not None else None,
            'billing_period': None, 'conditions': list(conditions),
            'scope': ['Hak5 store listing; variants and regional eligibility unspecified'],
            'starts_at': None, 'ends_at': None, 'expiry_label': None,
            'verification_status': 'vendor_published', 'last_offer_confirmed_at': None,
            'first_seen_at': None, 'price_history': [],
            'evidence_excerpt': (f'{product}: ${sale} instead of ${regular} ({discount}% off) on "{title}".'
                                 if regular else f'{product}: ${sale} on "{title}".'),
            'marketplace': False, 'reference_price_basis': 'vendor_advertised',
        }
        deal['id'] = identity(deal)
        deals.append(deal)
    if not deals:
        candidates.append({'source_id': source['id'], 'source_url': source['url'],
                           'reason': 'hak5_campaign_without_publishable_offers', 'evidence_excerpt': campaign[:600]})
        return [], candidates, 'discovery'
    return deals, candidates, 'confirmed'
