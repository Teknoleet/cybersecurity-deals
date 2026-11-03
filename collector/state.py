"""Small local JSON state. No raw page cache and no external state service."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from collector.policy import acceptable, identity, instant

SOURCE_KEYS = {'id', 'name', 'url', 'type', 'adapter', 'status', 'last_attempt_at',
               'last_successful_fetch_at', 'last_offer_confirmed_at', 'offers_count', 'note'}
DEAL_KEYS = {'id', 'vendor', 'product', 'description', 'category', 'topics', 'campaign_type',
             'campaign_year', 'eligibility_basis', 'eligibility_evidence', 'source_id',
             'source_url', 'discovery_urls', 'offer_url', 'coupon', 'currency', 'sale_price',
             'regular_price', 'discount_percent', 'billing_period', 'conditions', 'starts_at',
             'ends_at', 'expiry_label', 'verification_status', 'last_offer_confirmed_at',
             'first_seen_at', 'price_history', 'evidence_excerpt', 'marketplace'}
STATUSES = {'confirmed', 'discovery', 'historical', 'unavailable', 'unsupported', 'not_checked'}


def load_json(path, default=None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    # State/config is local, but reject accidental unbounded persisted input.
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError(f'JSON file too large: {path}')
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_snapshot(snapshot):
    """Dependency-free validation of required types and evidence invariants.

    The JSON Schema provides an independent full interchange contract. This
    validator also enforces cross-record identity, lifecycle and timestamp rules
    which JSON Schema alone cannot express.
    """
    required = {'schema_version', 'edition', 'generated_at', 'collection', 'sources', 'deals'}
    if set(snapshot) != required or snapshot['schema_version'] != 1 or snapshot['edition'] != 2026:
        raise ValueError('snapshot envelope is invalid')
    now = snapshot['generated_at']
    instant(now)
    if not isinstance(snapshot['sources'], list) or not isinstance(snapshot['deals'], list):
        raise ValueError('sources and deals must be lists')
    collection = snapshot['collection']
    if set(collection) != {'last_completed_at', 'source_count', 'successful_sources', 'failed_sources'}:
        raise ValueError('collection fields mismatch')
    for key in ('source_count', 'successful_sources', 'failed_sources'):
        if type(collection[key]) is not int or collection[key] < 0:
            raise ValueError('invalid collection count')
    if collection['last_completed_at']:
        if instant(collection['last_completed_at']) > instant(now):
            raise ValueError('collection completion cannot be in the future')
    if collection['source_count'] != len(snapshot['sources']):
        raise ValueError('source count mismatch')
    if collection['successful_sources'] + collection['failed_sources'] > collection['source_count']:
        raise ValueError('attempt count mismatch')
    source_ids = set()
    for source in snapshot['sources']:
        if set(source) != SOURCE_KEYS or source['status'] not in STATUSES or source['id'] in source_ids:
            raise ValueError('invalid or duplicate source')
        source_ids.add(source['id'])
        if type(source['offers_count']) is not int or source['offers_count'] < 0:
            raise ValueError('invalid source offer count')
        for key in ('last_attempt_at', 'last_successful_fetch_at', 'last_offer_confirmed_at'):
            if source[key] and instant(source[key]) > instant(now):
                raise ValueError('source timestamp in future')
    seen = set()
    for deal in snapshot['deals']:
        if not DEAL_KEYS.issubset(deal) or deal['id'] in seen or deal['id'] != identity(deal):
            raise ValueError('invalid or duplicate deal identity')
        seen.add(deal['id'])
        if deal['source_id'] not in source_ids:
            raise ValueError('deal points to unknown source')
        ok, reason = acceptable(deal, now)
        if not ok:
            raise ValueError(f'public deal violates policy: {reason}')
        for key in ('topics', 'discovery_urls', 'conditions', 'price_history'):
            if not isinstance(deal[key], list):
                raise ValueError('invalid list field')
        for key in ('vendor', 'product', 'description', 'evidence_excerpt'):
            if not isinstance(deal[key], str) or len(deal[key]) > 6000:
                raise ValueError('invalid text field')
        if deal['campaign_type'] not in {'black_friday', 'general_promotion'}:
            raise ValueError('invalid campaign type')
        if not isinstance(deal['marketplace'], bool):
            raise ValueError('invalid marketplace flag')
        if not (instant(deal['first_seen_at']) <= instant(deal['last_offer_confirmed_at']) <= instant(now)):
            raise ValueError('invalid offer timestamps')
        if len(deal['price_history']) > 90:
            raise ValueError('price history exceeds retention')
        for point in deal['price_history']:
            if set(point) != {'at', 'price', 'currency'} or instant(point['at']) > instant(deal['last_offer_confirmed_at']):
                raise ValueError('invalid price observation')
    for source in snapshot['sources']:
        if source['offers_count'] != sum(1 for x in snapshot['deals'] if x['source_id'] == source['id']):
            raise ValueError('source offer count mismatch')
    return True
