"""Config-driven official adapter for schema.org Offer data (JSON-LD).

A vendor's own 2026 campaign page often describes its products with
``<script type="application/ld+json">`` blocks. This adapter publishes those
offers without a vendor-specific parser, under the same evidence bar as the
maintained adapters:

* the registry entry must be ``type: official`` with a ``structured`` block
  naming the vendor, category and topics (reviewed configuration, not page text);
* the page's own ``<h1>`` must name the 2026 Black Friday / Cyber Monday campaign;
  structured data, footers and product names never establish eligibility;
* each published offer needs a price and must link to the vendor's own domain.
  Being on the vendor's 2026 campaign page is the eligibility criterion; prices
  are not checked against history or a reference. A vendor reference price
  (``ListPrice``/``StrikethroughPrice``) is shown only when it is above the sale
  price; otherwise the offer publishes with its price alone. A currency that is
  not an ISO code is shown as unspecified rather than guessed.

Coupon values are never read from structured data. A date-only ``validThrough``
is shown as the vendor's date and enforced only once it has passed in every
time zone; no exact deadline or vendor time zone is invented.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup

from collector.policy import CATEGORIES, SEASONAL, TOPICS, clean, eligibility, identity, instant

ITEM_TYPES = {'Product', 'Course', 'SoftwareApplication', 'WebApplication', 'MobileApplication',
              'Service', 'Book', 'EducationalOccupationalProgram', 'ProductGroup'}
REFERENCE_TYPES = ('ListPrice', 'StrikethroughPrice', 'MSRP', 'SRP')
UNAVAILABLE = ('SoldOut', 'OutOfStock', 'Discontinued', 'PreOrder', 'PreSale')
CAMPAIGN_HEADING = re.compile(r'(black\s*friday|cyber\s*monday|bfcm).*\b2026\b|\b2026\b.*(black\s*friday|cyber\s*monday|bfcm)', re.I)
MAX_SCRIPTS, MAX_NODES, MAX_OFFERS = 64, 2000, 200


def settings(source):
    """Validate reviewed registry configuration; misconfiguration fails closed."""
    config = source.get('structured')
    if source.get('type') != 'official' or not isinstance(config, dict):
        raise ValueError('structured_offers requires an official source with a "structured" block')
    if set(config) - {'vendor', 'category', 'topics', 'item_types'}:
        raise ValueError('unknown structured_offers configuration key')
    vendor = clean(config.get('vendor') or '')
    topics = config.get('topics')
    if not vendor or len(vendor) > 200:
        raise ValueError('structured_offers vendor is required')
    if config.get('category') not in CATEGORIES:
        raise ValueError('structured_offers category is not in the taxonomy')
    if not isinstance(topics, list) or not topics or not set(topics).issubset(TOPICS):
        raise ValueError('structured_offers topics must be known taxonomy topics')
    types = config.get('item_types', sorted(ITEM_TYPES))
    if not isinstance(types, list) or not set(types).issubset(ITEM_TYPES):
        raise ValueError('structured_offers item_types must be supported schema.org types')
    return vendor, config['category'], list(dict.fromkeys(topics)), set(types)


def types_of(node):
    value = node.get('@type', [])
    values = value if isinstance(value, list) else [value]
    return {str(x).rsplit('/', 1)[-1] for x in values if isinstance(x, str)}


def walk(value, found, budget):
    """Collect JSON-LD dict nodes breadth-first, bounded against hostile documents."""
    stack = [value]
    while stack and budget[0] < MAX_NODES:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(reversed(item))
        elif isinstance(item, dict):
            budget[0] += 1
            found.append(item)
            for key in ('@graph', 'hasVariant', 'itemListElement', 'item', 'mainEntity', 'isRelatedTo'):
                if key in item:
                    stack.append(item[key])


def text(value, limit):
    if isinstance(value, list):
        value = next((x for x in value if isinstance(x, str)), '')
    if not isinstance(value, str):
        return ''
    # JSON-LD descriptions sometimes carry markup; keep plain text only.
    return clean(BeautifulSoup(value, 'html.parser').get_text(' ', strip=True))[:limit]


def amount(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number >= 0 else None


def currency_of(node):
    value = node.get('priceCurrency')
    return value.strip().upper() if isinstance(value, str) and re.fullmatch(r'\s*[A-Za-z]{3}\s*', value) else None


def as_list(value):
    return value if isinstance(value, list) else [value] if value is not None else []


def prices(offer):
    """Return (sale, reference, currency) from structured fields; unclear parts become None."""
    currency = currency_of(offer)
    stated_invalid = currency is None and offer.get('priceCurrency') not in (None, '')
    sale = amount(offer.get('price'))
    reference, conflicting = None, False
    for spec in as_list(offer.get('priceSpecification')):
        if not isinstance(spec, dict):
            continue
        spec_currency = currency_of(spec) or currency
        price_type = str(spec.get('priceType') or '')
        value = amount(spec.get('price'))
        if value is None or (currency and spec_currency != currency):
            continue
        if not stated_invalid:
            currency = currency or spec_currency
        if any(x in price_type for x in REFERENCE_TYPES):
            conflicting = conflicting or (reference is not None and reference != value)
            reference = value
        elif sale is None and not price_type:
            sale = value
    # Two different reference prices: show none rather than pick one.
    return sale, None if conflicting else reference, None if stated_invalid else currency


def timestamp(value):
    """Timezone-aware instant, a bare calendar date, or nothing. Never a guessed zone."""
    if not isinstance(value, str) or not value.strip():
        return None, None
    value = value.strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        try:
            return None, date.fromisoformat(value)
        except ValueError:
            return None, None
    try:
        return instant(value).isoformat().replace('+00:00', 'Z'), None
    except (ValueError, TypeError):
        return None, None


def cutoff(day):
    """First instant at which ``day`` has ended in every civil time zone (UTC-12)."""
    end = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1, hours=12)
    return end.isoformat().replace('+00:00', 'Z')


def vendor_host(url, base):
    host = (urlsplit(url).hostname or '').casefold()
    return bool(host) and (host == base or host.endswith('.' + base))


def parse(body, source):
    vendor, category, topics, allowed_types = settings(source)
    soup = BeautifulSoup(body, 'html.parser')
    scripts = [x.get_text() for x in soup.find_all('script', type=re.compile(r'^\s*application/ld\+json\s*$', re.I))][:MAX_SCRIPTS]
    for element in soup(['script', 'style', 'noscript', 'nav', 'footer']):
        element.decompose()
    h1 = soup.find('h1')
    heading = clean(h1.get_text(' ', strip=True)) if h1 else ''
    intro = []
    for element in (h1.find_all_next(['p', 'h2']) if h1 else []):
        if element.name == 'h2' or len(intro) >= 6:
            break
        value = clean(element.get_text(' ', strip=True))
        if value:
            intro.append(value)
    campaign = ' '.join([heading, *intro])[:1500]
    evidence = {'campaign_text': campaign, 'official_corroboration': True, 'structured_data': True, 'vendor_page': True,
                'scope': f'schema.org offers on the {vendor} 2026 campaign page',
                'checkout_tested': False}
    basis = eligibility(evidence)
    # The vendor's own page heading must name the 2026 campaign. Structured data
    # alone (often site-wide, cached or template-generated) is not campaign evidence.
    if not (basis == 'explicit_2026' and CAMPAIGN_HEADING.search(heading)) and not (basis == 'vendor_campaign_window' and SEASONAL.search(heading)):
        return [], [{'source_id': source['id'], 'source_url': source['url'],
                     'reason': 'structured_campaign_missing_or_changed',
                     'evidence_excerpt': campaign[:600]}], 'discovery'

    base = (urlsplit(source['url']).hostname or '').casefold().removeprefix('www.')
    nodes, budget, candidates = [], [0], []
    for raw in scripts:
        try:
            walk(json.loads(raw), nodes, budget)
        except (json.JSONDecodeError, RecursionError, ValueError):
            candidates.append({'source_id': source['id'], 'source_url': source['url'],
                               'reason': 'malformed_structured_data'})
    deals, examined, truncated = [], 0, False
    for node in nodes:
        if not types_of(node) & allowed_types:
            continue
        name = text(node.get('name'), 200)
        if not name:
            continue
        for offer in as_list(node.get('offers')):
            if examined >= MAX_OFFERS:
                truncated = True
                break
            examined += 1
            if not isinstance(offer, dict):
                continue

            def reject(reason):
                candidates.append({'source_id': source['id'], 'product': name, 'reason': reason})

            kinds = types_of(offer)
            if 'AggregateOffer' in kinds:
                reject('aggregate_offer_needs_review')  # A price range is not one offer.
                continue
            if kinds and 'Offer' not in kinds:
                continue
            if any(x in str(offer.get('availability') or '') for x in UNAVAILABLE):
                reject('structured_offer_not_available')
                continue
            sale, reference, currency = prices(offer)
            if sale is None:
                reject('structured_offer_missing_price')  # No price at all: nothing to list.
                continue
            if reference is not None and (reference <= 0 or sale >= reference):
                reference = None  # Not a crossed-out price; publish the price alone.
            url = urljoin(source['url'], str(offer.get('url') or node.get('url') or source['url']))
            parts = urlsplit(url)
            if (parts.scheme not in {'http', 'https'} or parts.username or parts.password
                    or not vendor_host(url, base)):
                reject('offer_link_left_vendor_domain')
                continue
            starts_at, start_day = timestamp(offer.get('validFrom'))
            ends_at, end_day = timestamp(offer.get('validThrough') or offer.get('priceValidUntil'))
            raw_end = offer.get('validThrough') or offer.get('priceValidUntil')
            if (offer.get('validFrom') and not (starts_at or start_day)) or (raw_end and not (ends_at or end_day)):
                # An unreadable end date must not turn into an open-ended offer.
                reject('invalid_structured_date')
                continue
            discount = ((1 - sale / reference) * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if reference else None
            plan = text(offer.get('name'), 120)
            product = f'{name} — {plan}' if plan and plan.casefold() != name.casefold() else name
            conditions = [
                'Prices are read from the vendor page\'s schema.org structured data; checkout not tested.',
                'Tax/VAT, renewal terms and regional eligibility are not established.',
            ]
            if reference is None:
                conditions.append('The vendor publishes no crossed-out price for this item, so no discount size is shown.')
            if currency is None:
                conditions.append('The vendor data does not state a valid currency code; confirm it with the seller.')
            if start_day:
                conditions.append(f'The vendor gives a start date of {start_day.isoformat()} without a time zone.')
            expiry_label, expiry_cutoff = None, None
            if end_day:
                expiry_label = f'Until {end_day.isoformat()} (vendor date; time zone not stated)'
                expiry_cutoff = cutoff(end_day)
            deal = {
                'id': '', 'vendor': vendor, 'product': product,
                'description': text(node.get('description'), 900) or f'{vendor} offer from its 2026 campaign page.',
                'category': category, 'topics': topics,
                'campaign_type': 'black_friday', 'campaign_year': 2026,
                'eligibility_basis': basis, 'eligibility_evidence': dict(evidence),
                'source_id': source['id'], 'source_url': source['url'], 'discovery_urls': [],
                'offer_url': url, 'coupon': None, 'currency': currency, 'currency_symbol': None,
                'sale_price': float(sale), 'regular_price': float(reference) if reference else None,
                'discount_percent': float(discount) if discount is not None else None,
                'billing_period': None, 'conditions': conditions,
                'scope': [f'Structured offer "{product}" in {currency or "an unspecified currency"}; regional eligibility unspecified'],
                'starts_at': starts_at, 'ends_at': ends_at, 'expiry_label': expiry_label,
                'verification_status': 'vendor_published', 'last_offer_confirmed_at': None,
                'first_seen_at': None, 'price_history': [],
                'evidence_excerpt': (f'{product}: {sale} {currency or ""} instead of {reference} {currency or ""} ({discount}% off) on "{heading[:200]}".'
                                     if reference else f'{product}: {sale} {currency or ""} on "{heading[:200]}".').replace('  ', ' '),
                'marketplace': False, 'reference_price_basis': 'vendor_advertised',
            }
            if expiry_cutoff:
                deal['expiry_cutoff_at'] = expiry_cutoff
            deal['id'] = identity(deal)
            deals.append(deal)
    if truncated:
        candidates.append({'source_id': source['id'], 'source_url': source['url'],
                           'reason': 'structured_offer_limit_reached', 'detail': f'Only the first {MAX_OFFERS} offers were examined.'})
    if not deals:
        candidates.append({'source_id': source['id'], 'source_url': source['url'],
                           'reason': 'structured_campaign_without_publishable_offers',
                           'evidence_excerpt': campaign[:600]})
        return [], candidates, 'discovery'
    return deals, candidates, 'confirmed'
