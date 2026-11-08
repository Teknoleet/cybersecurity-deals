"""Practical DevSecOps' own 2026 Black Friday article (not a general HTML scraper).

Individual certification cards publish from their local reference/sale price pair.
Bundle cards publish from their dedicated original/discount price fields only when
the vendor's own "You're saving" amount equals the difference. "Coming Soon" courses,
and bundles that include one, stay candidates. USD is recorded only when the
vendor's own banner card states "USD" for the same product and price.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup

from collector.policy import clean, eligibility, identity

ORIGIN = 'https://www.practical-devsecops.com'
PRICE = re.compile(r'\$\s*([\d,]+(?:\.\d{1,2})?)\s+\$\s*([\d,]+(?:\.\d{1,2})?)')
BADGES = re.compile(r'\b(Best Seller|New Course|Coming Soon|Best Value)\b', re.I)
MONEY = re.compile(r'\$\s*([\d,]+(?:\.\d{1,2})?)')
CODES = re.compile(r'\(([A-Z]{2,8}(?:\s*\+\s*[A-Z]{2,8})*)\)\s*$')


def money(text):
    """Exactly one dollar amount in a dedicated price field, else None."""
    found = MONEY.findall(text or '')
    return Decimal(found[0].replace(',', '')) if len(found) == 1 else None


def bundle(container, source, coming_soon):
    """Return (fields, None) for a verifiable bundle card or (None, candidate)."""
    def reject(reason, product=None):
        return None, {'source_id': source['id'], 'product': product, 'reason': reason,
                      'evidence_excerpt': clean(container.get_text(' ', strip=True))[:300]}
    title_node = container.find('p')
    title = clean(BADGES.sub('', title_node.get_text(' ', strip=True))) if title_node else ''
    codes = CODES.search(title)
    if not title or not codes or '+' not in codes.group(1):
        return reject('bundle_or_unlabelled_pricing_needs_review', title or None)
    included = {x.strip() for x in codes.group(1).split('+')}
    original = container.select('.pdso_bundle_original_price')
    discount = container.select('.pdso_bundle_discount_price')
    saving = container.select_one('.bfcm_pricing_save_text')
    if len(original) != 1 or len(discount) != 1 or saving is None:
        return reject('bundle_or_unlabelled_pricing_needs_review', title)
    regular, sale = money(original[0].get_text(' ', strip=True)), money(discount[0].get_text(' ', strip=True))
    stated = re.search(r'saving\s*\$\s*([\d,]+(?:\.\d{1,2})?)', saving.get_text(' ', strip=True), re.I)
    if regular is None or sale is None or not stated or regular <= 0 or sale < 0 or sale >= regular:
        return reject('invalid_price_pair', title)
    # The vendor's own stated saving must agree with the two prices it shows.
    if regular - sale != Decimal(stated.group(1).replace(',', '')):
        return reject('bundle_saving_does_not_match_prices', title)
    if included & coming_soon:
        return reject('bundle_includes_unavailable_course', title)
    anchor = container.select_one('.pdso_menu_pricing a[href]')
    if anchor is None:
        return reject('bundle_or_unlabelled_pricing_needs_review', title)
    return {'title': title, 'regular': regular, 'sale': sale, 'href': str(anchor['href']),
            'included': sorted(included)}, None


def topics_for(title):
    lowered = title.casefold()
    topics = []
    if re.search(r'\bai\b|agentic|mcp|llm', lowered):
        topics.append('ai-security')
        if 'mcp' in lowered:
            topics.append('mcp-security')
        if 'agentic' in lowered:
            topics.append('agent-security')
    if re.search(r'devsecops|container|cloud native|kubernetes', lowered):
        topics.append('cloud-devsecops')
    if re.search(r'threat modeling|api security|supply chain|security champion', lowered):
        topics.append('appsec')
    return topics or ['appsec']


def parse(body, source):
    soup = BeautifulSoup(body, 'html.parser')
    for element in soup(['script', 'style', 'noscript', 'nav', 'footer']):
        element.decompose()
    h1 = soup.find('h1')
    heading = clean(h1.get_text(' ', strip=True)) if h1 else ''
    intro = []
    for element in (h1.find_all_next(['p', 'h2']) if h1 else []):
        if element.name == 'h2':
            break
        text = clean(element.get_text(' ', strip=True))
        if text:
            intro.append(text)
    campaign = ' '.join([heading, *intro])[:1500]
    evidence = {'campaign_text': campaign, 'official_corroboration': True,
                'scope': 'Individual certification cards with their own advertised sale prices in the vendor 2026 article',
                'checkout_tested': False}
    basis = eligibility(evidence)
    # The article heading itself must name the 2026 Black Friday campaign; a site-wide
    # sale banner, footer year or related-article link is not campaign evidence.
    if basis != 'explicit_2026' or not re.search(r'black\s*friday.*\b2026\b', heading, re.I):
        return [], [{'source_id': source['id'], 'source_url': source['url'],
                     'reason': 'practical_devsecops_campaign_missing_or_changed',
                     'evidence_excerpt': campaign[:600]}], 'discovery'
    site_label = 'CSA Month Sale' if re.search(r'CSA\s+Month\s+Sale', soup.get_text(' ', strip=True), re.I) else None
    usd_cards = {}
    for card in soup.select('.pdso-bn'):
        title, now = card.select_one('.pdso-bn__title'), card.select_one('.pdso-bn__now')
        if title and now:
            amount = re.search(r'USD\s*([\d,]+(?:\.\d{1,2})?)', now.get_text(' ', strip=True))
            if amount:
                usd_cards[clean(title.get_text()).casefold()] = Decimal(amount.group(1).replace(',', ''))
    deals, candidates = [], []
    coming_soon = set()
    for container in soup.select('.pdso_single_cards'):
        blurb = container.find_parent(class_='et_pb_blurb')
        header = blurb.find(class_='et_pb_module_header') if blurb else None
        text = clean(header.get_text(' ', strip=True)) if header else ''
        code = re.search(r'\(([A-Z]{2,8})\)', text)
        if code and re.search(r'coming soon', text, re.I):
            coming_soon.add(code.group(1))
    for container in soup.select('.pdso_course_card_container'):
        if 'pdso_bundle_cards' in container.get('class', []):
            fields, rejected = bundle(container, source, coming_soon)
            if rejected:
                candidates.append(rejected)
                continue
            url = urljoin(ORIGIN + '/', fields['href'])
            if urlsplit(url).hostname != urlsplit(ORIGIN).hostname:
                candidates.append({'source_id': source['id'], 'product': fields['title'], 'reason': 'offer_link_left_vendor_domain'})
                continue
            regular, sale, title = fields['regular'], fields['sale'], fields['title']
            discount = ((1 - sale / regular) * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            conditions = [
                f'Certification bundle ({" + ".join(fields["included"])}); the vendor prices the included certifications together.',
                'Vendor-published pre-signup link; checkout not tested.',
                'Reference prices are vendor-advertised, not independently verified historical baselines. The vendor\'s stated saving matches the two prices shown.',
                'Expiry is shown by the vendor only as a countdown; no end date is established. Tax/VAT and regional eligibility not established.',
            ]
            if site_label:
                conditions.append(f'The vendor site currently labels the same discount "{site_label}"; the 2026 Black Friday article lists these prices.')
            deal = {
                'id': '', 'vendor': 'Practical DevSecOps', 'product': title,
                'description': f'Certification bundle: {title}.',
                'category': 'certifications', 'topics': topics_for(title),
                'campaign_type': 'black_friday', 'campaign_year': 2026,
                'eligibility_basis': basis, 'eligibility_evidence': dict(evidence, scope='Certification bundle cards with their own advertised original and discount prices in the vendor 2026 article'),
                'source_id': source['id'], 'source_url': source['url'], 'discovery_urls': [],
                'offer_url': url, 'coupon': None, 'currency': None, 'currency_symbol': '$',
                'sale_price': float(sale), 'regular_price': float(regular), 'discount_percent': float(discount),
                'billing_period': None, 'conditions': conditions,
                'scope': ['Certification bundle; regional eligibility unspecified'],
                'starts_at': None, 'ends_at': None, 'expiry_label': None,
                'verification_status': 'vendor_published', 'last_offer_confirmed_at': None,
                'first_seen_at': None, 'price_history': [],
                'evidence_excerpt': f'{title}: ${sale} instead of ${regular} ({discount}% off) in "{heading}".',
                'marketplace': False, 'reference_price_basis': 'vendor_advertised',
            }
            deal['id'] = identity(deal)
            deals.append(deal)
            continue
        blurb = container.find_parent(class_='et_pb_blurb')
        header = blurb.find(class_='et_pb_module_header') if blurb else None
        anchor = container.find('a', href=True)
        text = clean(container.get_text(' ', strip=True))
        if not header or not anchor:
            candidates.append({'source_id': source['id'], 'source_url': source['url'],
                               'reason': 'bundle_or_unlabelled_pricing_needs_review', 'evidence_excerpt': text[:300]})
            continue
        raw_title = clean(header.get_text(' ', strip=True))
        title = clean(BADGES.sub('', raw_title))
        if re.search(r'coming soon', raw_title, re.I):
            candidates.append({'source_id': source['id'], 'product': title, 'reason': 'course_not_yet_available'})
            continue
        matches = set(PRICE.findall(text))
        if len(matches) != 1:
            candidates.append({'source_id': source['id'], 'product': title, 'reason': 'conflicting_or_missing_prices'})
            continue
        regular_text, sale_text = next(iter(matches))
        regular, sale = (Decimal(x.replace(',', '')) for x in (regular_text, sale_text))
        if regular <= 0 or sale < 0 or sale >= regular:
            candidates.append({'source_id': source['id'], 'product': title, 'reason': 'invalid_price_pair'})
            continue
        discount = ((1 - sale / regular) * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        url = urljoin(ORIGIN + '/', str(anchor['href']))
        if urlsplit(url).hostname != urlsplit(ORIGIN).hostname:
            candidates.append({'source_id': source['id'], 'product': title, 'reason': 'offer_link_left_vendor_domain'})
            continue
        plain = clean(re.sub(r'\([A-Z]+\)', '', title)).casefold()
        currency = 'USD' if usd_cards.get(plain) == sale else None
        description = clean(PRICE.sub('', re.sub(r'You.re saving.*$', '', text)).replace('\u2192', '').replace('->', ''))
        conditions = [
            'Individual certification; bundles are listed as separate offers.',
            'Vendor-published pre-signup link; checkout not tested.',
            'Reference prices are vendor-advertised, not independently verified historical baselines.',
            'Expiry is shown by the vendor only as a countdown; no end date is established. Tax/VAT and regional eligibility not established.',
        ]
        if site_label:
            conditions.append(f'The vendor site currently labels the same discount "{site_label}"; the 2026 Black Friday article lists these prices.')
        deal = {
            'id': '', 'vendor': 'Practical DevSecOps', 'product': title,
            'description': description[:900] or 'Self-paced certification course.',
            'category': 'certifications', 'topics': topics_for(title),
            'campaign_type': 'black_friday', 'campaign_year': 2026,
            'eligibility_basis': basis, 'eligibility_evidence': dict(evidence),
            'source_id': source['id'], 'source_url': source['url'], 'discovery_urls': [],
            'offer_url': url, 'coupon': None, 'currency': currency, 'currency_symbol': '$',
            'sale_price': float(sale), 'regular_price': float(regular), 'discount_percent': float(discount),
            'billing_period': None, 'conditions': conditions,
            'scope': ['Individual certification; non-bundle; regional eligibility unspecified'],
            'starts_at': None, 'ends_at': None, 'expiry_label': None,
            'verification_status': 'vendor_published', 'last_offer_confirmed_at': None,
            'first_seen_at': None, 'price_history': [],
            'evidence_excerpt': f'{title}: ${sale_text} instead of ${regular_text} ({discount}% off) in "{heading}".',
            'marketplace': False, 'reference_price_basis': 'vendor_advertised',
        }
        deal['id'] = identity(deal)
        deals.append(deal)
    if not deals:
        raise ValueError('Practical DevSecOps parser found the campaign but no certification cards; selector review required')
    return deals, candidates, 'confirmed'
