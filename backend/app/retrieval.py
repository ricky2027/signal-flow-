"""Bounded public-source retrieval. URLs must first occur in provider citations.
DNS is resolved and validated before connecting to a pinned public address.
"""

import http.client
import socket
import ssl
import asyncio
from html.parser import HTMLParser
from ipaddress import ip_address
from urllib.parse import urlsplit, urljoin, urlunsplit, parse_qsl, urlencode
from app.schemas import validate_url


class RetrievalError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def canonical_url(url):
    """Remove only known tracking parameters; preserve content-changing queries."""
    validate_url(url)
    u = urlsplit(url)
    tracking = {"gclid", "fbclid", "dclid", "msclkid", "msockid", "mc_cid", "mc_eid", "_ga"}
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in tracking]
    host = u.hostname.lower()
    port = u.port
    if port and (u.scheme, port) not in (("https", 443), ("http", 80)):
        host += f":{port}"
    return urlunsplit((u.scheme.lower(), host, u.path or "/", urlencode(query), ""))


class RetrievedText(str):
    """String-compatible retrieval result, carrying the verified redirect target."""
    def __new__(cls, value, url):
        obj = super().__new__(cls, value)
        obj.url = url
        return obj


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def normalize(s):
    return " ".join(s.split())


def _fetch(url):
    for _ in range(4):
        validate_url(url)
        u = urlsplit(url)
        port = u.port or (443 if u.scheme == "https" else 80)
        if port not in (80, 443):
            raise ValueError("Nonstandard port blocked")
        addresses = socket.getaddrinfo(u.hostname, port, type=socket.SOCK_STREAM)
        ips = {a[4][0] for a in addresses}
        if not ips or any(not ip_address(ip).is_global for ip in ips):
            raise ValueError("Non-public DNS blocked")
        ip = sorted(ips)[0]
        conn = http.client.HTTPConnection(u.hostname, port, timeout=8)
        raw = socket.create_connection((ip, port), timeout=8)
        conn.sock = (
            ssl.create_default_context().wrap_socket(raw, server_hostname=u.hostname)
            if u.scheme == "https"
            else raw
        )
        try:
            conn.request(
                "GET",
                u.path + ("?" + u.query if u.query else ""),
                headers={
                    "User-Agent": "SignalflowResearch/0.1",
                    "Accept": "text/html,text/plain",
                },
            )
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Missing redirect target")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise RetrievalError(f"http_{response.status}")
            content_type = response.getheader("Content-Type", "")
            if not any(t in content_type for t in ("text/html", "text/plain")):
                raise RetrievalError("unsupported_source_type")
            data = response.read(1_000_001)
            if len(data) > 1_000_000:
                raise RetrievalError("source_too_large")
            parser = Text()
            parser.feed(data.decode("utf-8", errors="replace"))
            return RetrievedText(normalize(" ".join(parser.parts))[:100000], canonical_url(url))
        finally:
            conn.close()
    raise ValueError("Too many redirects")


async def fetch(url):
    # Blocking DNS/socket work is isolated; connection/read timeouts bound its lifetime.
    return await asyncio.to_thread(_fetch, url)
