"""Run manually: python3 -m collector.run --output state/snapshot.json.

The previous snapshot defaults to the same output. No schedule, publishing,
credentials, browser or paid API is used. Optional explicit source selection:
--source trainsec-black-friday --source github-0x90n --max-sources 2
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from collector.adapters import ADAPTER_VERSION
from collector.adapters import trainsec, github_markdown, html_discovery, practical_devsecops, structured_offers
from collector.http import SafeFetcher, FetchError, representation_url
from collector.policy import (acceptable, apply_overrides, deduplicate, digest,
                              identity, instant, observe, utcnow)
from collector.state import atomic_json, load_json, validate_snapshot

ROOT = Path(__file__).resolve().parent.parent
ADAPTERS = {'trainsec': trainsec.parse, 'github_markdown': github_markdown.parse,
            'html_discovery': html_discovery.parse, 'practical_devsecops': practical_devsecops.parse,
            'structured_offers': structured_offers.parse}


def source_record(source, previous=None):
    previous = previous or {}
    default_status = source.get('initial_status', 'not_checked' if source.get('adapter') else 'unsupported')
    return {key: value for key, value in {
        'id': source['id'], 'name': source['name'], 'url': source['url'],
        'type': source['type'], 'adapter': source.get('adapter'),
        'status': previous.get('status', default_status),
        'last_attempt_at': previous.get('last_attempt_at'),
        'last_successful_fetch_at': previous.get('last_successful_fetch_at'),
        'last_offer_confirmed_at': previous.get('last_offer_confirmed_at'),
        'offers_count': 0, 'note': previous.get('note', source.get('note', '')),
    }.items()}


def cache_payload(entry):
    return {k: entry[k] for k in ('body_sha256', 'adapter_version', 'adapter', 'url',
                                  'deals', 'candidates', 'status')}


def valid_cache(entry, source):
    if not entry:
        return False
    try:
        return (entry['adapter_version'] == ADAPTER_VERSION
                and entry['adapter'] == source['adapter']
                and representation_url(entry['url']) == representation_url(source.get('fetch_url', source['url']))
                and len(entry['body_sha256']) == 64
                and entry['validated_digest'] == digest(cache_payload(entry))
                and isinstance(entry['deals'], list) and isinstance(entry['candidates'], list)
                and entry['status'] in {'confirmed', 'historical', 'discovery'})
    except (KeyError, TypeError, ValueError):
        return False


def normalized_url(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/'), '', ''))


def collect(registry, previous, cache, fetcher, *, now=None, selected=None,
            max_sources=8, max_links=4, overrides=None):
    fixed_now = now
    clock = (lambda: fixed_now) if fixed_now is not None else utcnow
    now = clock()
    previous = previous or {'sources': [], 'deals': []}
    cache = deepcopy(cache or {})
    old_sources = {x['id']: x for x in previous.get('sources', [])}
    old_deals = previous.get('deals', [])
    old_by_id = {identity(x): x for x in old_deals}
    sources = registry['sources']
    records = {s['id']: source_record(s, old_sources.get(s['id'])) for s in sources}
    supported = {s['id']: s for s in sources if s.get('adapter') in ADAPTERS}
    if selected and set(selected) - set(s['id'] for s in sources):
        raise ValueError('unknown --source ID')
    initial = [s for s in sources if (s['id'] in selected if selected else s.get('enabled'))]
    queue = initial[:max_sources]
    attempted, succeeded, failed = set(), set(), set()
    replacement = {}
    candidates = []
    followed = 0
    official = {normalized_url(s['url']): s for s in supported.values()
                if s['type'] == 'official' and urlsplit(s['url']).hostname in registry['policy']['supported_official_domains']}
    while queue and len(attempted) < max_sources:
        source = queue.pop(0)
        sid = source['id']
        if sid in attempted:
            continue
        if sid not in supported:
            records[sid]['status'] = source.get('initial_status', 'unsupported')
            records[sid]['note'] = source.get('note', '') + ' No maintained adapter; not fetched.'
            continue
        attempted.add(sid)
        record = records[sid]
        record['last_attempt_at'] = clock()
        target = source.get('fetch_url', source['url'])
        entry = cache.get(sid)
        headers = {}
        if entry is not None and valid_cache(entry, source):
            if entry.get('etag'):
                headers['If-None-Match'] = entry['etag']
            if entry.get('last_modified'):
                headers['If-Modified-Since'] = entry['last_modified']
        try:
            response = fetcher.fetch(target, headers=headers)
            # A registered official adapter may never confer official status on
            # an unrelated destination reached through a redirect.
            if urlsplit(response.url).hostname != urlsplit(target).hostname:
                raise FetchError('final response left the registered source domain')
            if response.status == 304:
                if entry is None or not valid_cache(entry, source) or not headers:
                    raise FetchError('304 without a matching validated representation')
                if representation_url(response.url) != representation_url(entry['url']):
                    raise FetchError('304 target does not match cached representation URL')
                if (response.headers.get('etag') and entry.get('etag')
                        and response.headers['etag'] != entry['etag']):
                    raise FetchError('304 returned a conflicting entity tag')
                parsed = deepcopy(entry['deals'])
                discoveries = deepcopy(entry['candidates'])
                status = entry['status']
            elif response.status == 200:
                content_type = response.headers.get('content-type', '').lower()
                if content_type and not any(x in content_type for x in ('text/', 'application/xhtml+xml', 'application/octet-stream')):
                    raise FetchError('unsupported response content type')
                parsed, discoveries, status = ADAPTERS[source['adapter']](response.body, source)
                entry = {'url': representation_url(response.url), 'adapter': source['adapter'], 'adapter_version': ADAPTER_VERSION,
                         'body_sha256': hashlib.sha256(response.body).hexdigest(),
                         'etag': response.headers.get('etag'),
                         'last_modified': response.headers.get('last-modified'),
                         'deals': deepcopy(parsed), 'candidates': deepcopy(discoveries), 'status': status}
                entry['validated_digest'] = digest(cache_payload(entry))
                cache[sid] = entry
            else:
                raise FetchError(f'HTTP {response.status}')
            now = clock()
            record['last_successful_fetch_at'] = now
            record['status'] = status
            record['note'] = source.get('note', '') + (' Matched previously validated representation (304).' if response.status == 304 else ' Current representation parsed; checkout not tested.')
            # Publication is a reviewed registry decision: only official sources on an
            # explicitly supported domain may contribute offers, whatever the adapter.
            if parsed and (source['type'] != 'official' or urlsplit(target).hostname
                           not in registry['policy']['supported_official_domains']):
                raise ValueError('source is not an official supported domain; offers cannot publish')
            accepted = []
            for item in parsed:
                ok, reason = acceptable(item, now)
                if ok:
                    accepted.append(observe(item, old_by_id.get(identity(item)), now))
                else:
                    candidates.append({'source_id': sid, 'deal_id': identity(item), 'reason': reason})
            replacement[sid] = accepted
            if accepted:
                record['last_offer_confirmed_at'] = now
            # A parsed representation replaces all prior source offers. Unmatched
            # offers are withdrawal evidence, not reconfirmed by a page download.
            fresh_ids = {x['id'] for x in accepted}
            for old in old_deals:
                if old['source_id'] == sid and old['id'] not in fresh_ids:
                    candidates.append({'source_id': sid, 'deal_id': old['id'],
                                       'reason': 'withdrawn_or_no_longer_matched',
                                       'last_offer_confirmed_at': old['last_offer_confirmed_at']})
            succeeded.add(sid)
            candidates.extend(discoveries)
            # Following is deliberately narrower than a domain-wide crawl: only
            # exact known canonical supported official landing pages. Unknown
            # pages remain candidates even on a known vendor domain.
            for item in discoveries:
                if followed >= max_links or len(attempted) + len(queue) >= max_sources:
                    break
                linked = official.get(normalized_url(item.get('offer_url', '')))
                if linked and linked['id'] not in attempted and not any(x['id'] == linked['id'] for x in queue):
                    if selected and linked['id'] not in selected:
                        continue
                    queue.append(linked)
                    followed += 1
        except (FetchError, ValueError, TypeError, KeyError) as exc:
            failed.add(sid)
            record['status'] = 'unavailable'
            record['note'] = f'Fetch/extraction unavailable: {str(exc)[:280]}. Prior offer confirmation times are unchanged.'
            imported_times = sorted({x.get('eligibility_evidence', {}).get('observed_at')
                                     for x in old_deals if x['source_id'] == sid
                                     and x.get('eligibility_evidence', {}).get('observation_method') == 'first_party_tool_extraction'
                                     and x.get('eligibility_evidence', {}).get('observed_at')})
            if imported_times:
                record['note'] += f' Retained individually corroborated first-party research extraction observed at {imported_times[-1]}; not an automated HTTP success.'
            candidates.append({'source_id': sid, 'reason': 'fetch_or_extraction_unavailable', 'detail': str(exc)[:280]})
    now = clock()
    combined = []
    for old in old_deals:
        if old['source_id'] not in records:
            candidates.append({'source_id': old['source_id'], 'deal_id': old['id'], 'reason': 'source_removed_from_registry'})
            continue
        if old['source_id'] not in replacement:
            combined.append(deepcopy(old))
    for items in replacement.values():
        combined.extend(items)
    provenance = {}
    for candidate in candidates:
        discovered_url = candidate.get('offer_url')
        discovery_url = candidate.get('discovery_url')
        if discovered_url and discovery_url:
            provenance.setdefault(normalized_url(discovered_url), set()).add(discovery_url)
    for deal in combined:
        discovered = provenance.get(normalized_url(deal['offer_url']), set())
        discovered |= provenance.get(normalized_url(deal['source_url']), set())
        deal['discovery_urls'] = sorted(set(deal.get('discovery_urls', [])) | discovered)
    eligible = []
    for deal in combined:
        ok, reason = acceptable(deal, now)
        if ok:
            eligible.append(deal)
        else:
            candidates.append({'source_id': deal['source_id'], 'deal_id': deal['id'], 'reason': reason})
    public, conflicts = deduplicate(eligible)
    candidates.extend(conflicts)
    # Exclusions/corrections run after dedupe; protected evidence is rechecked.
    public = apply_overrides(public, overrides or {})
    final = []
    for deal in public:
        ok, reason = acceptable(deal, now)
        if ok:
            if deal.get('starts_at') and instant(deal['starts_at']) > instant(now):
                deal['offer_timing'] = 'upcoming'
            elif deal.get('offer_timing') == 'upcoming':
                deal.pop('offer_timing')
            final.append(deal)
        else:
            candidates.append({'deal_id': deal['id'], 'reason': reason})
    final.sort(key=lambda x: (x['first_seen_at'], x['id']), reverse=True)
    for sid, record in records.items():
        record['offers_count'] = sum(x['source_id'] == sid for x in final)
    snapshot = {'schema_version': 1, 'edition': 2026, 'generated_at': now,
                'collection': {'last_completed_at': now, 'source_count': len(records),
                               'successful_sources': len(succeeded), 'failed_sources': len(failed)},
                'sources': list(records.values()), 'deals': final}
    validate_snapshot(snapshot)
    # Candidate records are internal and bounded/deduplicated; never placed in
    # the public deals array. No full remote HTML is persisted.
    unique = {digest(x): x for x in candidates}
    return snapshot, {'edition': 2026, 'generated_at': now,
                      'candidates': list(unique.values())[:800]}, cache


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'state/snapshot.json')
    parser.add_argument('--previous', type=Path, help='defaults to --output')
    parser.add_argument('--config', type=Path, default=ROOT / 'config/sources.json')
    parser.add_argument('--overrides', type=Path, default=ROOT / 'config/overrides.json')
    parser.add_argument('--source', action='append', help='source ID; repeat or comma-separate')
    parser.add_argument('--max-sources', type=int, default=16)
    parser.add_argument('--max-links', type=int, default=4)
    args = parser.parse_args(argv)
    if not 1 <= args.max_sources <= 16 or not 0 <= args.max_links <= 4:
        parser.error('--max-sources must be 1..16 and --max-links 0..4')
    selected = [x for value in (args.source or []) for x in value.split(',')]
    fetcher = SafeFetcher()
    try:
        registry = load_json(args.config)
        previous = load_json(args.previous or args.output)
        if previous:
            # Validate at its original generation time. Expiry is evaluated at
            # the present run separately, not mistaken for corrupt prior state.
            validate_snapshot(previous)
        history_file = args.output.parent / 'history.json'
        history = load_json(history_file, {})
        snapshot, candidates, cache = collect(registry, previous, history.get('http_cache', {}), fetcher,
                                               selected=selected, max_sources=args.max_sources,
                                               max_links=args.max_links, overrides=load_json(args.overrides, {}))
        # Preserve unresolved review records across runs. Candidate retention is
        # bounded, and never restores a candidate to the public deals array.
        merged = {digest(x): x for x in history.get('candidates', [])}
        merged.update({digest(x): x for x in candidates['candidates']})
        candidates['candidates'] = list(merged.values())[-800:]
        history.update({'schema_version': 1, 'updated_at': snapshot['generated_at'],
                        'http_cache': cache, 'candidates': candidates['candidates']})
        atomic_json(history_file, history)
        atomic_json(args.output, snapshot)
        atomic_json(args.output.parent / 'candidates.json', candidates)
        status = {'completed_at': snapshot['generated_at'], 'output': str(args.output),
                  'offers': len(snapshot['deals']), **snapshot['collection'],
                  'requests': fetcher.total, 'partial_failure': snapshot['collection']['failed_sources'] > 0}
        atomic_json(args.output.parent / 'collector-status.json', status)
        print(f"Collection completed: {len(snapshot['deals'])} current offers; "
              f"{snapshot['collection']['successful_sources']} sources succeeded, "
              f"{snapshot['collection']['failed_sources']} unavailable; {fetcher.total} requests.")
        return 0  # A valid partial snapshot is intentional, not a build failure.
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f'Collection rejected; existing snapshot untouched: {exc}', file=sys.stderr)
        return 2
    finally:
        fetcher.close()


if __name__ == '__main__':
    raise SystemExit(main())
