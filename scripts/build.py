#!/usr/bin/env python3
"""Assemble the portable static directory. No network or deployment during build."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlsplit
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://deals.teknoleet.com'
DEFAULT_TAXONOMY = {
    'categories': [
        {'id': 'training', 'label': 'Training & Labs'},
        {'id': 'certifications', 'label': 'Certifications & Exams'},
        {'id': 'software', 'label': 'Software & Tools'},
        {'id': 'hardware', 'label': 'Hardware'},
        {'id': 'books', 'label': 'Books & Bundles'},
    ],
    'topics': [
        {'id': 'offensive-security', 'label': 'Offensive Security'},
        {'id': 'blue-team-dfir', 'label': 'Blue Team & DFIR'},
        {'id': 'appsec', 'label': 'Application Security'},
        {'id': 'cloud-devsecops', 'label': 'Cloud & DevSecOps'},
        {'id': 'ai-security', 'label': 'AI Security'},
        {'id': 'osint', 'label': 'OSINT & Threat Intelligence'},
        {'id': 'reverse-engineering', 'label': 'Reverse Engineering'},
        {'id': 'hardware-physical', 'label': 'Hardware & Physical'},
        {'id': 'privacy-vpn', 'label': 'Privacy & VPN'},
        {'id': 'llm-security', 'label': 'LLM Security'},
        {'id': 'agent-security', 'label': 'Agent Security'},
        {'id': 'mcp-security', 'label': 'MCP Security'},
        {'id': 'adversarial-ml', 'label': 'Adversarial ML'},
        {'id': 'ai-for-security', 'label': 'AI for Security'},
    ],
}
AI_SPECIALTIES = {'llm-security', 'agent-security', 'mcp-security', 'adversarial-ml', 'ai-for-security'}


def parse_date(value):
    if not value or not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return date if date.tzinfo else None
    except ValueError:
        return None


def safe_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {'http', 'https'} and bool(parsed.hostname) and not parsed.username and not parsed.password and not any(ord(c) < 33 for c in value)
    except ValueError:
        return False


def display_date(value):
    date = parse_date(value)
    return date.astimezone(timezone.utc).strftime('%d %b %Y, %H:%M UTC') if date else 'Not yet checked'


def money(value, currency, symbol=''):
    if value is None:
        return ''
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid non-finite or negative monetary amount')
    amount = f'{value:,.2f}'.removesuffix('.00')
    return f'{currency} {amount}' if currency else f'{symbol}{amount}'


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def prepare_deals(snapshot, taxonomy):
    now = datetime.now(timezone.utc)
    categories = {entry['id'] for entry in taxonomy['categories']}
    topic_labels = {entry['id']: entry['label'] for entry in taxonomy['topics']}
    deals = []
    ids = set()
    for source_deal in snapshot.get('deals', []):
        deal = dict(source_deal)
        if deal.get('campaign_year') != 2026 or deal.get('verification_status') not in {'vendor_published', 'marketplace_published'}:
            raise ValueError('Public snapshot contains an ineligible campaign/status')
        if deal.get('eligibility_basis') not in {'explicit_2026', 'october_2026', 'vendor_campaign_window'} or not deal.get('eligibility_evidence'):
            raise ValueError('Public snapshot lacks date eligibility evidence')
        if deal.get('category') not in categories or not deal.get('id') or deal['id'] in ids:
            raise ValueError('Invalid category or duplicate offer identity')
        if not safe_url(deal.get('offer_url')) or not safe_url(deal.get('source_url')):
            raise ValueError('Unsafe offer or evidence link')
        if any(not safe_url(url) for url in deal.get('discovery_urls', [])):
            raise ValueError('Unsafe discovery URL')
        evidence = deal.get('eligibility_evidence')
        seller_authorized = evidence.get('seller_authorized') if isinstance(evidence, dict) else False
        if deal.get('marketplace') and deal['category'] == 'software' and not seller_authorized:
            raise ValueError('Software marketplace seller authorization missing')
        if not isinstance(deal.get('topics'), list) or not set(deal['topics']).issubset(topic_labels):
            raise ValueError('Unknown topic')
        confirmed = parse_date(deal.get('last_offer_confirmed_at'))
        ends = parse_date(deal.get('ends_at'))
        starts = parse_date(deal.get('starts_at'))
        if deal.get('ends_at') and not ends:
            raise ValueError('Expiry timestamps must include a time zone')
        if deal.get('starts_at') and not starts:
            raise ValueError('Start timestamps must include a time zone')
        if ends and ends <= now:
            continue
        cutoff = parse_date(deal.get('expiry_cutoff_at'))
        if deal.get('expiry_cutoff_at') and not cutoff:
            raise ValueError('Expiry cutoffs must include a time zone')
        if cutoff and cutoff <= now:
            continue
        if deal.get('expiry_label') == 'November 2026 only' and now >= datetime(2026, 12, 2, tzinfo=timezone.utc):
            continue
        deal['is_stale'] = not confirmed or (now - confirmed).total_seconds() > 10800 or (confirmed - now).total_seconds() > 300
        deal['is_upcoming'] = bool(starts and starts > now)
        deal.setdefault('currency', None)
        deal.setdefault('sale_price', None)
        deal.setdefault('regular_price', None)
        deal.setdefault('discount_percent', None)
        deal.setdefault('billing_period', None)
        deal.setdefault('conditions', [])
        deal.setdefault('coupon', None)
        deal.setdefault('expiry_label', None)
        deal.setdefault('ends_at', None)
        deal.setdefault('starts_at', None)
        deal.setdefault('discovery_urls', [])
        deal.setdefault('description', '')
        deal.setdefault('evidence_excerpt', '')
        deal.setdefault('price_history', [])
        deal.setdefault('marketplace', False)
        deal.setdefault('first_seen_at', None)
        discount = deal['discount_percent']
        if discount is not None and (isinstance(discount, bool) or not isinstance(discount, (int, float)) or not math.isfinite(discount) or not 0 <= discount <= 100):
            raise ValueError('Invalid percentage')
        deal['price_display'] = money(deal['sale_price'], deal['currency'], deal.get('currency_symbol', ''))
        deal['regular_display'] = money(deal['regular_price'], deal['currency'], deal.get('currency_symbol', ''))
        deal['vendor_initials'] = ''.join(word[0] for word in deal['vendor'].split()[:2]).upper()
        if len(deal['vendor_initials']) == 1:
            deal['vendor_initials'] = deal['vendor'][:2].upper()
        deal['confirmed_display'] = display_date(deal.get('last_offer_confirmed_at'))
        evidence = deal.get('eligibility_evidence')
        if isinstance(evidence, dict):
            deal['eligibility_evidence_display'] = evidence.get('campaign_text') or f"Originally published {evidence.get('original_published_at') or 'in October 2026'}; current official evidence supports this offer."
        else:
            deal['eligibility_evidence_display'] = str(evidence or '')
        deal['search_text'] = ' '.join([deal['vendor'], deal['product'], deal['description'], deal.get('coupon') or '', *(topic_labels[topic] for topic in deal['topics'])])
        ids.add(deal['id'])
        deals.append(deal)
    deals.sort(key=lambda deal: (deal['is_stale'], -(parse_date(deal.get('first_seen_at')) or datetime(1970, 1, 1, tzinfo=timezone.utc)).timestamp(), deal['product'].lower()))
    return deals


def json_for_html(value):
    """JSON that is safe inside a <script> element: no tag or line-separator characters."""
    text = json.dumps(value, ensure_ascii=False, allow_nan=False)
    for raw, escaped in [('<', '\\u003c'), ('>', '\\u003e'), ('&', '\\u0026'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        text = text.replace(raw, escaped)
    return text


def offer_schema(deal, category_labels):
    """Schema.org Offer. Prices are only emitted with a known currency code; nothing is inferred."""
    offer = {
        '@type': 'Offer', 'name': f"{deal['vendor']}: {deal['product']}", 'url': deal['offer_url'], 'category': category_labels.get(deal['category'], deal['category']),
        'description': deal['evidence_excerpt'] or deal['description'], 'seller': {'@type': 'Organization', 'name': deal['vendor']},
        'availability': 'https://schema.org/PreOrder' if deal['is_upcoming'] else 'https://schema.org/InStock',
    }
    if deal['sale_price'] is not None and deal['currency']:
        offer['price'] = deal['sale_price']
        offer['priceCurrency'] = deal['currency']
    if deal['starts_at']:
        offer['validFrom'] = deal['starts_at']
    if deal['ends_at']:
        offer['validThrough'] = deal['ends_at']
    return offer


def structured_data(route, title, description, context):
    site = {'@type': 'WebSite', '@id': f'{ORIGIN}/#website', 'name': 'Cybersecurity Deals', 'url': ORIGIN + '/', 'inLanguage': 'en', 'publisher': {'@type': 'Organization', 'name': 'Cybersecurity Deals', 'url': ORIGIN + '/'}}
    page = {'@type': 'WebPage', 'url': ORIGIN + route, 'name': title, 'description': description, 'isPartOf': {'@id': f'{ORIGIN}/#website'}}
    if context['collection'].get('last_completed_at'):
        page['dateModified'] = context['collection']['last_completed_at']
    graph = [site, page]
    if route == '/':
        graph.append({'@type': 'ItemList', 'name': 'Cybersecurity deals 2026', 'numberOfItems': len(context['deals']), 'itemListElement': [
            {'@type': 'ListItem', 'position': index, 'item': offer_schema(deal, context['category_labels'])} for index, deal in enumerate(context['deals'], 1)]})
    elif context.get('page_type') == 'methodology':
        graph.append({'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': question, 'acceptedAnswer': {'@type': 'Answer', 'text': answer}} for question, answer in METHODOLOGY_FAQ]})
    elif context.get('page_type') == 'sources':
        graph.append({'@type': 'Dataset', 'name': 'Cybersecurity Deals 2026 snapshot', 'description': 'Machine-readable list of current evidence-backed cybersecurity offers, sources and check times.', 'url': f'{ORIGIN}/sources/', 'distribution': [{'@type': 'DataDownload', 'encodingFormat': 'application/json', 'contentUrl': f'{ORIGIN}/data/snapshot.json'}]})
    return {'@context': 'https://schema.org', '@graph': graph}


METHODOLOGY_FAQ = [
    ('Which offers qualify for the 2026 directory?', 'An offer must explicitly belong to a 2026 campaign, or be supported by an article originally published in October 2026. A footer year, a course title containing a year, or an updated 2025 roundup is not enough. Offers with unresolved dates, conflicting prices, historical codes, or unsupported evidence are withheld; expired or withdrawn offers leave the directory.'),
    ('Are the deals checkout-tested?', 'No. Vendor-published means an official source supports the offer; marketplace-published means an allowed third-party seller supports it. Checkout, coupon redemption, stock and product quality are not tested or guaranteed.'),
    ('How fresh is the information?', 'Each offer carries its own confirmation time. After three hours without confirmation it is marked Recheck pending. Fetch failures keep last-known-good data without changing its confirmation time, and a blocked page does not prove a sale has ended.'),
    ('Are the advertised savings verified?', 'Prices stay in the source currency and crossed-out prices are vendor reference prices, not independently verified historical lows. Missing prices, expiry dates, VAT, renewal terms or time zones are never invented.'),
    ('Is Cybersecurity Deals a seller?', 'No. It is a directory with no accounts, submissions, paid placement or purchase flows. Always confirm final price, coupon, access duration, regional eligibility, taxes and renewal terms with the seller before buying.'),
]


def llms_text(deals, category_labels, collection):
    """llms.txt: a plain-text summary for AI crawlers and answer engines."""
    lines = ['# Cybersecurity Deals', '', '> Source-backed directory of 2026 cybersecurity and AI-security offers: training, certifications, software, hardware, books and VPNs. Every offer links to official vendor or marketplace evidence with its own confirmation time. No recycled historical codes, no checkout testing, no paid placement.', '',
             f"Last collection: {collection.get('last_completed_at') or 'none yet'}. Prices are in the vendor's original currency and are vendor claims.", '',
             '## Pages', '', f'- [Deals directory]({ORIGIN}/): searchable list with vendor, topic and category filters', f'- [Source coverage]({ORIGIN}/sources/): which sources are supported and when each was last fetched', f'- [Methodology]({ORIGIN}/methodology/): eligibility rules, evidence labels and freshness warnings', f'- [Machine-readable snapshot]({ORIGIN}/data/snapshot.json): all current offers as JSON', '',
             f'## Current offers ({len(deals)})', '']
    for deal in deals:
        price = f" {deal['price_display']}" + (f" (was {deal['regular_display']})" if deal['regular_display'] else '') if deal['price_display'] else ''
        coupon = f", code {deal['coupon']}" if deal['coupon'] else ''
        expiry = f", {deal['expiry_label']}" if deal['expiry_label'] else ''
        lines.append(f"- [{deal['vendor']}: {deal['product']}]({deal['offer_url']}):{price} {category_labels.get(deal['category'], deal['category'])}{coupon}{expiry}. Evidence: {deal['source_url']}")
    return '\n'.join(lines) + '\n'


def build(output=ROOT / 'dist', snapshot_path=ROOT / 'state/snapshot.json', review=True):
    snapshot = load_json(snapshot_path, {'schema_version': 1, 'edition': 2026, 'generated_at': None, 'collection': {'last_completed_at': None, 'source_count': 0, 'successful_sources': 0, 'failed_sources': 0}, 'sources': [], 'deals': []})
    if snapshot.get('schema_version') != 1 or snapshot.get('edition') != 2026:
        raise ValueError('Unsupported snapshot schema or edition')
    if snapshot_path.exists():
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from collector.state import validate_snapshot
        validate_snapshot(snapshot)
    taxonomy = load_json(ROOT / 'config/taxonomy.json', DEFAULT_TAXONOMY)
    deals = prepare_deals(snapshot, taxonomy)
    sources = [dict(source, offers_count=sum(deal['source_id'] == source['id'] for deal in deals)) for source in snapshot.get('sources', [])]
    for source in sources:
        if not safe_url(source.get('url')):
            raise ValueError(f'Invalid registered source URL: {source.get("id")}')
    collection = snapshot['collection']
    vendors = sorted({deal['vendor'] for deal in deals}, key=str.casefold)
    env = Environment(loader=FileSystemLoader(ROOT / 'web/templates'), autoescape=select_autoescape(['html']), undefined=StrictUndefined)
    out = output.resolve()
    if out == ROOT or ROOT not in out.parents:
        raise ValueError('Output must be a dedicated subdirectory of the project')
    temp = Path(tempfile.mkdtemp(prefix='.static-build-', dir=ROOT))
    try:
        (temp / 'assets').mkdir()
        css_path = ''
        js_path = ''
        for filename in ['styles.css', 'app.mjs']:
            content = (ROOT / 'web/assets' / filename).read_bytes()
            digest = hashlib.sha256(content).hexdigest()[:12]
            target = f'{Path(filename).stem}.{digest}{Path(filename).suffix}'
            (temp / 'assets' / target).write_bytes(content)
            if filename == 'styles.css':
                css_path = '/assets/' + target
            else:
                js_path = '/assets/' + target
        static = ROOT / 'web/public'
        if static.exists():
            shutil.copytree(static, temp, dirs_exist_ok=True)
        common = {
            'origin': ORIGIN, 'css_path': css_path, 'js_path': js_path, 'noindex': review,
            'collection': collection, 'sources': sources, 'deals': deals, 'vendors': vendors,
            'categories': taxonomy['categories'], 'primary_topics': [topic for topic in taxonomy['topics'] if topic['id'] not in AI_SPECIALTIES],
            'ai_topics': [topic for topic in taxonomy['topics'] if topic['id'] in AI_SPECIALTIES],
            'category_labels': {item['id']: item['label'] for item in taxonomy['categories']},
            'topic_labels': {item['id']: item['label'] for item in taxonomy['topics']},
            'topic_counts': {item['id']: sum(item['id'] in deal['topics'] for deal in deals) for item in taxonomy['topics']},
            'last_check_display': display_date(collection.get('last_completed_at')), 'review_mode': review,
            'stale_count': sum(deal['is_stale'] for deal in deals),
        }
        page_state = {'deals': deals, 'taxonomy': taxonomy, 'vendors': vendors, 'collection': collection, 'generated_at': snapshot.get('generated_at'), 'edition': 2026, 'schema_version': 1}
        common['page_state_json'] = json_for_html(page_state)
        pages = [
            ('index.html', 'index.html', '/', 'Cybersecurity Deals — Security for Less | 2026', 'Discover source-backed cybersecurity training, software, hardware and book offers for 2026. Search by vendor and topic, with transparent evidence and check times.', {}),
            ('sources/index.html', 'info.html', '/sources/', 'Source Coverage — Cybersecurity Deals 2026', 'See which cybersecurity deal sources are supported, historical or unavailable, and when each source was last successfully fetched.', {'page_type': 'sources', 'heading': 'Every source. In the open.', 'lead': 'See where the offers come from, what we can collect, and what still needs a closer look.'}),
            ('methodology/index.html', 'info.html', '/methodology/', 'How We Check Offers — Cybersecurity Deals 2026', 'Understand the 2026 eligibility rules, vendor evidence labels, stale-data warnings and advertised-price limitations behind Cybersecurity Deals.', {'page_type': 'methodology', 'heading': 'Good deals. Clear evidence.', 'lead': 'A directory should help you make a decision, not make promises it cannot substantiate.'}),
            ('404.html', '404.html', '/404', 'Page Not Found — Cybersecurity Deals', 'This page is not available. Return to the 2026 cybersecurity deals directory.', {'noindex': True}),
        ]
        for target, template, route, title, description, extra in pages:
            context = dict(common, route=route, title=title, description=description)
            context.update(extra)
            context['jsonld'] = json_for_html(structured_data(route, title, description, context))
            destination = temp / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(env.get_template(template).render(**context) + '\n', encoding='utf-8')
        (temp / 'data').mkdir()
        public_snapshot = dict(snapshot, sources=sources, deals=[{k: v for k, v in deal.items() if k not in {'search_text', 'vendor_initials', 'confirmed_display', 'price_display', 'regular_display', 'is_stale', 'is_upcoming', 'eligibility_evidence_display'}} for deal in deals])
        (temp / 'data/snapshot.json').write_text(json.dumps(public_snapshot, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        (temp / 'llms.txt').write_text(llms_text(deals, common['category_labels'], collection), encoding='utf-8')
        (temp / 'robots.txt').write_text('User-agent: *\nDisallow: /\n' if review else f'User-agent: *\nAllow: /\nSitemap: {ORIGIN}/sitemap.xml\n')
        urls = ''.join(f'<url><loc>{ORIGIN}{route}</loc></url>' for route in ['/', '/sources/', '/methodology/'])
        (temp / 'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
        (temp / '_headers').write_text('''/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'self'; object-src 'none'; form-action 'self'
  Cache-Control: public, max-age=0, must-revalidate
/assets/*
  Cache-Control: public, max-age=31536000, immutable
/fonts/*
  Cache-Control: public, max-age=31536000, immutable
/data/*
  Cache-Control: public, max-age=0, must-revalidate
''')
        if out.exists():
            backup = ROOT / '.dist-previous'
            if backup.exists():
                shutil.rmtree(backup)
            out.rename(backup)
            try:
                temp.rename(out)
            except Exception:
                backup.rename(out)
                raise
            shutil.rmtree(backup)
        else:
            temp.rename(out)
        print(f'Built {len(deals)} evidence-backed offers from {len(vendors)} vendors into {out}')
        return out
    finally:
        if temp.exists():
            shutil.rmtree(temp)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'state/snapshot.json')
    parser.add_argument('--production', action='store_true', help='Remove review notice/noindex; does not deploy or enable jobs')
    args = parser.parse_args()
    build(args.output, args.snapshot, review=not args.production)
