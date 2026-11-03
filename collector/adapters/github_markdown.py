"""Discovery only. A GitHub list never establishes current official evidence.

Historical lists are classified from the campaign heading, not body course years,
Q1 2026 end dates or footer dates. Coupon values are never imported or published.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
from collector.policy import clean

LINK = re.compile(r'https?://[^\s<>\]\)"\x27]+')


def parse(body, source):
    text = body.decode('utf-8', errors='replace') if isinstance(body, bytes) else body
    headings = [line for line in text.splitlines()[:35] if line.startswith(('# ', '## '))]
    heading = ' '.join(headings)
    historical = bool(re.search(r'\b202[0-5]\b', heading))
    status = 'historical' if historical else 'discovery'
    candidates = []
    seen = set()
    section = ''
    for line in text.splitlines():
        if line.startswith('#'):
            section = clean(line.lstrip('# '))[:160]
        for match in LINK.finditer(line):
            url = match.group().rstrip('.,;\\')
            try:
                p = urlsplit(url)
                if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password:
                    continue
            except ValueError:
                continue
            if url in seen or p.hostname in {'github.com', 'raw.githubusercontent.com'}:
                continue
            seen.add(url)
            # Do not preserve the historical line containing coupons and prices.
            candidates.append({'source_id': source['id'], 'discovery_url': source['url'],
                               'offer_url': url, 'section': section,
                               'reason': 'historical_campaign' if historical else 'needs_official_2026_evidence',
                               'entry_status': 'unconfirmed' if re.search(r'coming soon|expected|unconfirmed|smoke signals', line, re.I) else 'discovered',
                               'campaign_year': 2025 if historical else None,
                               'automatic_publication': False})
            if len(candidates) >= 400:
                break
        if len(candidates) >= 400:
            break
    return [], candidates, status
