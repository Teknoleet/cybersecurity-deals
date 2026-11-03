"""Conservative eligibility, identity, lifecycle and observation policy.

No adapter may publish a discovery record directly. Evidence must describe the
specific campaign and a currently accessible official/supported seller offer.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from urllib.parse import urlsplit

EDITION = 2026
CATEGORIES = {'training', 'certifications', 'software', 'hardware', 'books'}
TOPICS = {'offensive-security', 'blue-team-dfir', 'appsec', 'cloud-devsecops',
          'ai-security', 'osint', 'reverse-engineering', 'hardware-physical',
          'privacy-vpn', 'llm-security', 'agent-security', 'mcp-security',
          'adversarial-ml', 'ai-for-security'}


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def instant(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('timestamps must include a timezone')
    return value.astimezone(timezone.utc)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def clean(value):
    return re.sub(r'\s+', ' ', str(value)).strip()


def eligibility(evidence):
    """Only scoped campaign text or a substantiated ORIGINAL October publication.

    Footer text, product titles and general page text are deliberately not inputs.
    Adapters must supply a campaign excerpt from the relevant campaign container.
    """
    if evidence.get('historical') or evidence.get('date_conflict'):
        return None
    campaign = evidence.get('campaign_text', '')
    if (re.search(r'\b2026\b|\bBF2026\b', campaign, re.I)
            and re.search(r'black\s*friday|cyber\s*monday|sale|discount|promotion|BF2026', campaign, re.I)):
        return 'explicit_2026'
    date = evidence.get('original_published_at')
    if date and evidence.get('original_date_verified') and evidence.get('original_date_source'):
        try:
            instant(date)  # Require a real timezone-aware timestamp.
            dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
        if dt.year == 2026 and dt.month == 10:
            return 'october_2026'
    return None


def identity(deal):
    # Scope is explicit provenance when available, otherwise all restrictions.
    scope = deal.get('scope', deal.get('conditions', []))
    value = [clean(deal.get(k) or '').casefold() for k in
             ('vendor', 'product', 'coupon', 'billing_period')]
    value.append('|'.join(sorted(clean(x).casefold() for x in scope)) if isinstance(scope, list) else clean(scope).casefold())
    return digest(value)[:24]


def acceptable(deal, now):
    if deal.get('campaign_year') != EDITION:
        return False, 'wrong_campaign_year'
    coupon = deal.get('coupon') or ''
    if re.search(r'(?:BLACKFRIDAY|CYBERMONDAY|BFCM|BF)[_-]?(?:202[0-5]|25)\b', coupon, re.I):
        return False, 'historical_coupon'
    if deal.get('category') not in CATEGORIES or not set(deal.get('topics', [])).issubset(TOPICS):
        return False, 'unknown_taxonomy'
    if not deal.get('vendor') or not deal.get('product'):
        return False, 'missing_product'
    evidence = deal.get('eligibility_evidence', {})
    if eligibility(evidence) != deal.get('eligibility_basis'):
        return False, 'ineligible_date_evidence'
    if not evidence.get('official_corroboration'):
        return False, 'missing_current_official_corroboration'
    if deal.get('withdrawn') or deal.get('conflicting'):
        return False, 'withdrawn_or_conflicting'
    if deal.get('marketplace') and deal.get('category') == 'software' and not evidence.get('seller_authorized'):
        return False, 'unconfirmed_license_provenance'
    if deal.get('verification_status') not in {'vendor_published', 'marketplace_published'}:
        return False, 'unconfirmed_publication'
    for key in ('source_url', 'offer_url'):
        p = urlsplit(deal.get(key, ''))
        if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password:
            return False, 'unsafe_url'
    for key in ('sale_price', 'regular_price', 'discount_percent'):
        price = deal.get(key)
        if price is not None and (isinstance(price, bool) or not isinstance(price, (float, int)) or not math.isfinite(price) or price < 0):
            return False, 'invalid_price'
    if deal.get('discount_percent') is not None and deal['discount_percent'] > 100:
        return False, 'invalid_discount'
    if deal.get('sale_price') is None and deal.get('discount_percent') is None:
        return False, 'no_specific_offer'
    if deal.get('currency') is not None and not re.fullmatch(r'[A-Z]{3}', deal['currency']):
        return False, 'invalid_currency'
    try:
        if deal.get('starts_at'):
            instant(deal['starts_at'])
        if deal.get('ends_at') and instant(deal['ends_at']) <= instant(now):
            return False, 'expired'
        # Natural-language month restriction is real expiry evidence, not an
        # invented exact deadline. Never populate ends_at from a guessed zone.
        if deal.get('expiry_label') == 'November 2026 only':
            current = instant(now)
            # December 2 is beyond November in every civil timezone. This is a
            # conservative exclusion decision, not a fabricated ends_at value.
            if current >= instant('2026-12-02T00:00:00Z'):
                return False, 'expired_month_window'
    except (ValueError, TypeError):
        return False, 'invalid_date'
    return True, None


def deduplicate(deals):
    groups = {}
    for deal in deals:
        item = deepcopy(deal)
        item['id'] = identity(item)
        groups.setdefault(item['id'], []).append(item)
    public, conflicts = [], []
    for key, items in groups.items():
        prices = {(x.get('sale_price'), x.get('regular_price'), x.get('currency'),
                   x.get('currency_symbol'), x.get('discount_percent')) for x in items}
        if len(prices) > 1:
            conflicts.append({'reason': 'conflicting_prices', 'deal_id': key,
                              'offers': items})
            continue
        # A stale retained source must not override a newly confirmed identical
        # observation merely because it appeared first in the combined list.
        first = max(items, key=lambda x: x.get('last_offer_confirmed_at') or '')
        first_seen = [x.get('first_seen_at') for x in items if x.get('first_seen_at')]
        if first_seen:
            first['first_seen_at'] = min(first_seen)
        first['discovery_urls'] = sorted({u for x in items for u in x.get('discovery_urls', [])})
        first['provenance'] = sorted({u for x in items for u in
                                     [x['source_url'], *x.get('provenance', [])]})
        public.append(first)
    return public, conflicts


def apply_overrides(deals, config):
    """Reviewable text/taxonomy corrections only; no prices, dates, evidence or HTML.

    Overrides cannot create deals, change identity, URLs, eligibility or freshness.
    Exclusions take precedence over corrections. Unknown keys fail configuration.
    """
    if set(config) - {'exclude', 'corrections', 'notes'}:
        raise ValueError('unknown override configuration key')
    permitted = {'description', 'category', 'topics'}
    for change in config.get('corrections', {}).values():
        if set(change) - permitted:
            raise ValueError('override attempts to change a protected field')
        for key, value in change.items():
            values = value if isinstance(value, list) else [value]
            if any(not isinstance(x, str) or '<' in x or '>' in x or len(x) > 2000 for x in values):
                raise ValueError('overrides must be bounded plain text')
    excluded = set(config.get('exclude', []))
    result = []
    for item in deals:
        item = deepcopy(item)
        if item['id'] in excluded:
            continue
        item.update(config.get('corrections', {}).get(item['id'], {}))
        result.append(item)
    return result


def observe(deal, previous, now):
    deal = deepcopy(deal)
    deal['id'] = identity(deal)
    deal['last_offer_confirmed_at'] = now
    deal['first_seen_at'] = previous.get('first_seen_at', now) if previous else now
    history = deepcopy(previous.get('price_history', [])) if previous else []
    # Unknown currencies are not comparable to an ISO currency. Reset when the
    # underlying currency changes even though the offer identity remains stable.
    if previous and (previous.get('currency'), previous.get('currency_symbol')) != (deal.get('currency'), deal.get('currency_symbol')):
        history = []
    price = deal.get('sale_price')
    observation = {'at': now, 'price': price, 'currency': deal.get('currency')}
    if price is not None and (not history or history[-1]['price'] != price or history[-1]['currency'] != deal.get('currency')):
        history.append(observation)
    deal['price_history'] = history[-90:]
    return deal
