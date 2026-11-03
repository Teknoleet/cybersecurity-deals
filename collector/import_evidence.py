"""Explicit one-time reviewed research import; never invoked by collection.

This is not a network bypass: the importer does not fetch anything. It accepts
an attributed current first-party tool extraction, cross-checks each scoped
course/price against the captured HTML parser, and records the actual supplied
observation time. The automated last_successful_fetch_at remains null.

Ordinary fixture parsing in tests cannot create current state. Callers must
explicitly provide --observed-at, --method and --official-url; a receipt stores
input hashes and the method. Re-running an import cannot create a newer observed
time unless the caller explicitly supplies a new reviewed observation.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
from pathlib import Path
import re

from collector.adapters.trainsec import parse, PRICE, URL
from collector.policy import acceptable, clean, deduplicate, instant, observe, utcnow
from collector.run import ROOT, source_record
from collector.state import atomic_json, load_json, validate_snapshot


def corroborated(deal, markdown):
    # A matching URL is part of the title, followed by its OWN advertised pair.
    # This will not borrow another course's price or a global percentage banner.
    sections = re.split(r'(?m)(?=^### )', markdown)
    for section in sections:
        if not section.startswith('### '):
            continue
        title_line = section.splitlines()[0]
        if f'({deal["offer_url"]})' not in title_line:
            continue
        found = re.match(r'^### \[(.*?)\]\(', title_line)
        if not found or clean(found.group(1)) != deal['product']:
            continue
        prices = {(float(a.replace(',', '')), float(b.replace(',', '')))
                  for a, b in PRICE.findall(section)}
        return prices == {(deal['sale_price'], deal['regular_price'])}
    return False


def import_reviewed(registry, html, markdown, observed_at, method, official_url, *, now=None):
    now = now or utcnow()
    if official_url != URL or method != 'first_party_tool_extraction':
        raise ValueError('only the registered official TrainSec tool-extraction method is supported')
    if instant(observed_at) > instant(now):
        raise ValueError('evidence observation cannot be in the future')
    if (instant(now) - instant(observed_at)).total_seconds() > 24 * 3600:
        raise ValueError('initial reviewed import must be no older than 24 hours; obtain current evidence')
    preamble = markdown.split('## Malware Analysis')[0]
    if not all(phrase in preamble for phrase in
               ('November 2026 only', 'BF2026', '40% Discount', 'Live events, learning paths, bundles and subscriptions are not included')):
        raise ValueError('current corroboration is missing scoped campaign conditions')
    source = next(s for s in registry['sources'] if s['id'] == 'trainsec-black-friday')
    parsed, candidates, _ = parse(html, source)
    receipt = {'source_id': source['id'], 'source_url': official_url,
               'observed_at': observed_at, 'method': method,
               'html_sha256': hashlib.sha256(html).hexdigest(),
               'corroboration_sha256': hashlib.sha256(markdown.encode()).hexdigest(),
               'note': 'Reviewed current first-party extraction corroborates scoped captured HTML; no claim of automated HTTP success.'}
    deals = []
    for item in parsed:
        if not corroborated(item, markdown):
            candidates.append({'source_id': source['id'], 'product': item['product'],
                               'reason': 'reviewed_extraction_did_not_corroborate_course'})
            continue
        item['eligibility_evidence'].update({'observation_method': method,
                                             'observed_at': observed_at,
                                             'corroboration_sha256': receipt['corroboration_sha256']})
        ok, reason = acceptable(item, now)
        if ok:
            deals.append(observe(item, None, observed_at))
        else:
            candidates.append({'source_id': source['id'], 'product': item['product'], 'reason': reason})
    deals, conflicts = deduplicate(deals)
    candidates.extend(conflicts)
    if not deals:
        raise ValueError('no course-specific current first-party evidence was corroborated')
    records = [source_record(s) for s in registry['sources']]
    record = next(s for s in records if s['id'] == source['id'])
    record.update({'status': 'confirmed', 'last_offer_confirmed_at': observed_at,
                   'offers_count': len(deals),
                   'note': f'Reviewed first-party tool extraction at {observed_at}; automated raw HTTP not confirmed. Vendor-published; checkout not tested.'})
    snapshot = {'schema_version': 1, 'edition': 2026, 'generated_at': now,
                'collection': {'last_completed_at': None, 'source_count': len(records),
                               'successful_sources': 0, 'failed_sources': 0},
                'sources': records, 'deals': deals}
    validate_snapshot(snapshot)
    receipt['offers_corroborated'] = len(deals)
    return snapshot, {'edition': 2026, 'generated_at': now, 'candidates': candidates}, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', type=Path, required=True)
    parser.add_argument('--corroboration', type=Path, required=True)
    parser.add_argument('--observed-at', required=True)
    parser.add_argument('--method', choices=['first_party_tool_extraction'], required=True)
    parser.add_argument('--official-url', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'state/snapshot.json')
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('reviewed initial import refuses to overwrite existing state; ordinary collection preserves it')
    snapshot, candidates, receipt = import_reviewed(
        load_json(ROOT / 'config/sources.json'), args.html.read_bytes(),
        args.corroboration.read_text(encoding='utf-8'), args.observed_at, args.method, args.official_url)
    atomic_json(args.output, snapshot)
    atomic_json(args.output.parent / 'candidates.json', candidates)
    atomic_json(args.output.parent / 'reviewed-evidence-receipt.json', receipt)
    atomic_json(args.output.parent / 'history.json', {
        'schema_version': 1, 'updated_at': snapshot['generated_at'],
        'http_cache': {}, 'candidates': candidates['candidates'],
        'reviewed_evidence': [receipt],
    })
    print(f"Imported {len(snapshot['deals'])} individually corroborated offers; automatic fetch timestamps remain null.")


if __name__ == '__main__':
    main()
