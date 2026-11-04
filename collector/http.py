"""Bounded public-only HTTP. No browser, proxy environment, auth or retries.

DNS is checked twice and the socket connects to a validated numerical address,
not a fresh DNS lookup. TLS still uses the original hostname. Redirect targets
are revalidated and robots-checked; robots retrieval itself never follows a
redirect (fail closed). Robots 404/410 means an explicitly absent policy.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import ipaddress
import socket
import time
from typing import Any, cast
from urllib.parse import urlsplit, urljoin, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3 import PoolManager
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError

USER_AGENT = 'CyberDealsCollector/1.0 (+source-transparent research; no checkout)'
MAX_BYTES = 2 * 1024 * 1024


class FetchError(RuntimeError):
    pass


def representation_url(url):
    """HTTP resource identity: retain path, trailing slash and query exactly."""
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ''))


def public_addresses(host, port):
    if not host or host.casefold().rstrip('.') in {'localhost', 'metadata.google.internal'} or host.endswith(('.local', '.localhost', '.internal')):
        raise FetchError('local or metadata hostname blocked')
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchError('DNS lookup failed') from exc
    if not addresses:
        raise FetchError('empty DNS answer')
    for _, _, _, _, address in addresses:
        ip = ipaddress.ip_address(str(address[0]).split('%')[0])
        if not ip.is_global or ip.is_multicast or ip.is_reserved or getattr(ip, 'ipv4_mapped', None):
            raise FetchError('non-public DNS/address blocked')
    return addresses


def validate_url(url):
    try:
        parsed = urlsplit(url)
        if (parsed.scheme not in {'https', 'http'} or not parsed.hostname or
                parsed.username is not None or parsed.password is not None or
                parsed.port not in {None, 80, 443} or '\\' in url or any(ord(c) < 33 for c in url)):
            raise FetchError('unsafe URL or port')
        host = parsed.hostname.encode('idna').decode('ascii').lower()
        public_addresses(host, parsed.port or (443 if parsed.scheme == 'https' else 80))
        return parsed
    except (ValueError, UnicodeError) as exc:
        raise FetchError('malformed URL') from exc


def public_socket(connection: HTTPConnection):
    try:
        addresses = public_addresses(connection.host, connection.port)
        last = None
        # Two validated transport addresses cap worst-case connection work.
        # There are no automatic retries or proxy fallbacks.
        for family, socktype, proto, _, address in addresses[:2]:
            sock = socket.socket(family, socktype, proto)
            try:
                timeout = connection.timeout
                sock.settimeout(timeout if isinstance(timeout, (int, float)) else 4)
                for option in connection.socket_options or []:
                    sock.setsockopt(*option)
                sock.connect(address)
                return sock
            except OSError as exc:
                sock.close()
                last = exc
        raise last or OSError('no usable address')
    except (OSError, FetchError) as exc:
        raise NewConnectionError(connection, str(exc)) from exc


class PublicHTTPConnection(HTTPConnection):
    def _new_conn(self):
        return public_socket(self)


class PublicHTTPSConnection(HTTPSConnection):
    def _new_conn(self):
        return public_socket(self)


class PublicHTTPPool(HTTPConnectionPool):
    # urllib3's mutable connection Protocol has invariant upstream annotations.
    ConnectionCls = cast(Any, PublicHTTPConnection)


class PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = cast(Any, PublicHTTPSConnection)


class PublicAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {'http': PublicHTTPPool, 'https': PublicHTTPSPool}


@dataclass
class Response:
    status: int
    url: str
    body: bytes
    headers: dict


class SafeFetcher:
    def __init__(self, *, deadline_seconds=180, max_requests=48, per_domain=12, max_bytes=MAX_BYTES):
        self.deadline = time.monotonic() + deadline_seconds
        self.max_requests = max_requests
        self.per_domain = per_domain
        self.max_bytes = min(max_bytes, MAX_BYTES)
        self.counts = Counter()
        self.robots = {}
        self.last_request = {}
        self.total = 0
        self.session = requests.Session()
        self.session.trust_env = False
        adapter = PublicAdapter(max_retries=0, pool_connections=4, pool_maxsize=1)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.headers['User-Agent'] = USER_AGENT

    def close(self):
        self.session.close()

    def _request(self, url, headers=None):
        p = validate_url(url)
        domain = p.hostname.casefold()
        remaining = self.deadline - time.monotonic()
        if remaining <= 0 or self.total >= self.max_requests or self.counts[domain] >= self.per_domain:
            raise FetchError('request budget exhausted')
        self.total += 1
        self.counts[domain] += 1
        # Prevent Set-Cookie state from turning public collection into a session.
        self.session.cookies.clear()
        try:
            with self.session.get(url, headers=headers or {}, stream=True,
                                  allow_redirects=False, timeout=(min(4, remaining), min(7, remaining))) as response:
                body = bytearray()
                if response.status_code not in {301, 302, 303, 307, 308, 304}:
                    length = response.headers.get('Content-Length')
                    if length and int(length) > self.max_bytes:
                        raise FetchError('response exceeds size limit')
                    for block in response.iter_content(16384):
                        if time.monotonic() > self.deadline:
                            raise FetchError('collection deadline reached')
                        body.extend(block)
                        if len(body) > self.max_bytes:
                            raise FetchError('decoded response exceeds size limit')
                self.last_request[domain] = time.monotonic()
                return Response(response.status_code, url, bytes(body),
                                {k.lower(): v for k, v in response.headers.items()})
        except (requests.RequestException, OSError, ValueError) as exc:
            raise FetchError(str(exc)[:250]) from exc

    def _obey_robots(self, url):
        p = urlsplit(url)
        origin = f'{p.scheme}://{p.netloc}'
        if origin not in self.robots:
            response = self._request(origin + '/robots.txt')
            robot = RobotFileParser()
            if response.status in {404, 410}:
                robot.parse(['User-agent: *', 'Disallow:'])
            elif response.status == 200:
                body = response.body.decode('utf-8', errors='replace')
                if '<html' in body.lower() or '<!doctype' in body.lower():
                    raise FetchError('robots returned HTML; fail closed')
                robot.parse(body.splitlines())
            else:
                raise FetchError(f'robots unavailable ({response.status}); fail closed')
            self.robots[origin] = robot
        robot = self.robots[origin]
        if not robot.can_fetch(USER_AGENT, url):
            raise FetchError('robots disallows this path')
        delay = robot.crawl_delay(USER_AGENT) or 0.2
        rate = robot.request_rate(USER_AGENT)
        if rate and rate.requests:
            delay = max(delay, rate.seconds / rate.requests)
        wait = max(0, delay - (time.monotonic() - self.last_request.get(p.hostname, 0)))
        if time.monotonic() + wait >= self.deadline:
            raise FetchError('robots delay exceeds remaining budget')
        time.sleep(wait)

    def fetch(self, url, headers=None):
        current = url
        for redirect in range(4):
            validate_url(current)
            self._obey_robots(current)
            response = self._request(current, headers)
            if response.status not in {301, 302, 303, 307, 308}:
                return response
            if redirect == 3:
                raise FetchError('redirect limit exceeded')
            location = response.headers.get('location')
            if not location:
                raise FetchError('redirect missing location')
            target = urljoin(current, location)
            validate_url(target)
            if representation_url(target) != representation_url(current):
                headers = {}  # ETags/Last-Modified belong to one URI, even on the same host.
            current = target
        raise FetchError('redirect loop')
