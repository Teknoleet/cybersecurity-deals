"""Regression checks: HTTP validators never migrate between resource URIs."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from collector.http import Response, SafeFetcher, representation_url
from collector.run import collect, valid_cache
from collector.state import load_json

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = load_json(ROOT / 'config/sources.json')
SOURCE = REGISTRY['sources'][0]
REGISTRY = {**REGISTRY, 'sources': [SOURCE]}
BODY = (ROOT / 'tests/fixtures/trainsec.html').read_bytes()
NOW = '2026-11-03T10:00:00Z'
LATER = '2026-11-03T11:00:00Z'
HEADERS = {'content-type': 'text/html', 'etag': '"same-tag"'}


def run(response, previous=None, cache=None, now=NOW):
    fetcher = Mock()
    fetcher.fetch.return_value = response
    snapshot, _, stored = collect(REGISTRY, previous, cache or {}, fetcher, now=now)
    return snapshot, stored, fetcher


class ResourceIdentityTests(TestCase):
    def test_query_and_trailing_slash_are_resource_identity(self):
        self.assertNotEqual(representation_url(SOURCE['url']), representation_url(SOURCE['url'] + '?variant=2'))
        self.assertNotEqual(representation_url(SOURCE['url']), representation_url(SOURCE['url'].rstrip('/')))
        self.assertEqual(representation_url(SOURCE['url']), representation_url(SOURCE['url'] + '#section'))

    def test_query_changed_304_cannot_refresh_original(self):
        first, cache, _ = run(Response(200, SOURCE['url'], BODY, HEADERS))
        later, _, _ = run(Response(304, SOURCE['url'] + '?different=representation', b'', HEADERS), first, cache, LATER)
        self.assertEqual(later['deals'], first['deals'])
        self.assertEqual(later['sources'][0]['status'], 'unavailable')
        self.assertEqual(later['sources'][0]['last_offer_confirmed_at'], NOW)

    def test_redirected_200_cache_uses_actual_final_uri(self):
        final_url = 'https://trainsec.net/old-offer-resource/'
        first, cache, _ = run(Response(200, final_url, BODY, HEADERS))
        self.assertEqual(cache[SOURCE['id']]['url'], final_url)
        self.assertFalse(valid_cache(cache[SOURCE['id']], SOURCE))
        later, _, fetcher = run(Response(304, SOURCE['url'], b'', HEADERS), first, cache, LATER)
        self.assertEqual(fetcher.fetch.call_args.kwargs['headers'], {})
        self.assertEqual(later['deals'], first['deals'])
        self.assertEqual(later['sources'][0]['last_offer_confirmed_at'], NOW)
        self.assertEqual(later['sources'][0]['status'], 'unavailable')

    def test_same_host_redirect_drops_conditional_headers(self):
        for destination in ['?variant=2', '/different-resource/']:
            with self.subTest(destination=destination):
                fetcher = SafeFetcher()
                requests = [Response(302, SOURCE['url'], b'', {'location': destination}), Response(200, 'https://trainsec.net/different-resource/', BODY, HEADERS)]
                try:
                    with patch('collector.http.validate_url'), patch.object(fetcher, '_obey_robots'), patch.object(fetcher, '_request', side_effect=requests) as request:
                        fetcher.fetch(SOURCE['url'], headers={'If-None-Match': '"same-tag"'})
                    self.assertEqual(request.call_args_list[0].args[1], {'If-None-Match': '"same-tag"'})
                    self.assertEqual(request.call_args_list[1].args[1], {})
                finally:
                    fetcher.close()
