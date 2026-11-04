"""Discovery only, for roundups, trackers and vendor pages without a maintained offer parser.

Records the page heading, its declared publication date and outbound links as
candidates. It never publishes an offer, price or coupon. A heading naming an
earlier edition classifies the page as historical.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup

from collector.policy import clean

IGNORED_HOSTS = {'twitter.com', 'x.com', 'facebook.com', 'linkedin.com', 'youtube.com', 'instagram.com',
                 'github.com', 'reddit.com', 'bsky.app', 'mastodon.social', 'wordpress.org', 'google.com'}


def parse(body, source):
    soup = BeautifulSoup(body, 'html.parser')
    for element in soup(['script', 'style', 'noscript']):
        element.decompose()
    h1 = soup.find('h1')
    heading = clean(h1.get_text(' ', strip=True) if h1 else (soup.title.get_text() if soup.title else ''))[:200]
    published = None
    for meta in soup.find_all('meta'):
        if (meta.get('property') or meta.get('name') or '').lower() in {'article:published_time', 'datepublished'} and meta.get('content'):
            published = clean(meta['content'])[:40]
            break
    historical = bool(re.search(r'\b202[0-5]\b', heading)) and not re.search(r'\b2026\b', heading)
    status = 'historical' if historical else 'discovery'
    own_host = (urlsplit(source['url']).hostname or '').casefold()
    candidates, seen, section = [], set(), ''
    for element in soup.find_all(['h1', 'h2', 'h3', 'a']):
        if element.name != 'a':
            section = clean(element.get_text(' ', strip=True))[:160]
            continue
        url = urljoin(source['url'], str(element.get('href', ''))).split('#')[0]
        try:
            p = urlsplit(url)
        except ValueError:
            continue
        host = (p.hostname or '').casefold()
        if (p.scheme not in {'http', 'https'} or not host or p.username or p.password or url in seen
                or host == own_host or host.removeprefix('www.') in IGNORED_HOSTS):
            continue
        seen.add(url)
        candidates.append({'source_id': source['id'], 'discovery_url': source['url'], 'offer_url': url,
                           'section': section, 'page_heading': heading, 'published_at': published,
                           'reason': 'historical_campaign' if historical else 'needs_official_2026_evidence',
                           'campaign_year': None, 'automatic_publication': False})
        if len(candidates) >= 300:
            break
    return [], candidates, status
