#!/usr/bin/env python3
"""Check generated static output without a browser or any external requests."""
from pathlib import Path
from html.parser import HTMLParser
import json
import re

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.cards = []
        self.inside_header = False
        self.header_nav = False
        self.state = ''
        self.in_state = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'header':
            self.inside_header = True
        if tag == 'nav' and self.inside_header:
            self.header_nav = True
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        if tag in {'a', 'link', 'img', 'script'}:
            link = attrs.get('href') or attrs.get('src')
            if link:
                self.links.append(link)
        if 'deal-card' in (attrs.get('class') or '').split():
            self.cards.append(attrs.get('data-deal-id'))
        if tag == 'script' and attrs.get('id') == 'page-state':
            self.in_state = True

    def handle_endtag(self, tag):
        if tag == 'header':
            self.inside_header = False
        if tag == 'script':
            self.in_state = False

    def handle_data(self, data):
        if self.in_state:
            self.state += data


def check():
    assert (DIST / 'index.html').is_file(), 'Build output is missing'
    for path in DIST.rglob('*.html'):
        text = path.read_text()
        document = Document()
        document.feed(text)
        assert '<title>' in text and 'name="description"' in text, path
        assert not document.header_nav, 'Header navigation must remain absent'
        for removed in ['by TEKNOLEET', 'monitored hourly', 'Hourly monitoring', 'EXAMPLE LABS', 'SAMPLE DEFENSE', 'DEMO ACADEMY']:
            assert removed not in text, f'Removed or fictional text in {path}: {removed}'
        for url in document.links:
            assert not url.lower().startswith(('javascript:', 'vbscript:')), f'Unsafe URL in {path}'
            if not url.startswith('/') or url.startswith('//'):
                continue
            target = DIST / url.lstrip('/').split('?', 1)[0].split('#', 1)[0]
            if target.is_dir():
                target /= 'index.html'
            assert target.is_file(), f'Missing local asset/link: {url} in {path}'
        if path == DIST / 'index.html':
            assert {'category', 'vendor', 'search', 'collection-time'} <= document.ids
            assert 'Last Check' in text
            state = json.loads(document.state)
            assert state['schema_version'] == 1 and state['edition'] == 2026
            assert len(document.cards) == len(state['deals'])
            assert len(set(document.cards)) == len(document.cards)
            for offer in state['deals']:
                assert offer['campaign_year'] == 2026
                assert offer['last_offer_confirmed_at'], 'Offer confirmation must be explicit'
    assert all((DIST / route / 'index.html').is_file() for route in ('', 'sources', 'methodology'))
    assert 'noindex' in (DIST / '404.html').read_text()
    styles = next((DIST / 'assets').glob('styles.*.css')).read_text()
    for url in re.findall(r'url\([\'\"]?(/[^)\'\"]+)', styles):
        assert (DIST / url.lstrip('/')).is_file(), f'Missing stylesheet asset {url}'
    print('Static output checks passed: approved copy, meaningful HTML, data, routes and local assets.')


if __name__ == '__main__':
    check()
