"""Recorded HTTP responses for offline adapter runs, and the header helpers they need.

Moved out of ingest/adapters/hf_hub.py (P5-S1-T03) by P3-S1-T03, when the Epoch adapter became the
second user. A fixture directory holds, per recorded response, the body as `<name>` and its
`<name>.headers.json`: {"url": ..., "status": ..., "headers": [[name, value], ...]}. A request for a
recorded URL replays it, or answers 304 when the request's If-None-Match matches the recorded ETag,
which is how an offline run proves the conditional path. A URL the set does not hold raises
FixtureMiss, never an empty answer. There is no network code in this module.
"""
import json
import os
import re

from ingest.http.backoff import Response


class FixtureMiss(Exception):
    """The fixture set holds no response for this URL."""


class NetworkForbidden(Exception):
    """--no-network, and something reached for the network."""


# ---- headers ----------------------------------------------------------------------------------

def header_values(headers, name):
    items = headers.items() if hasattr(headers, 'items') else headers
    return [v for k, v in items if k.lower() == name.lower()]


def header(headers, name):
    vals = header_values(headers, name)
    return vals[0] if vals else None


def etag_matches(if_none_match, etag):
    """RFC 9110 S13.1.2: If-None-Match uses the weak comparison -- W/ is ignored on both sides."""
    if not if_none_match or not etag:
        return False
    if if_none_match.strip() == '*':
        return True
    weak = lambda t: t.strip()[2:] if t.strip().startswith('W/') else t.strip()  # noqa: E731
    return any(weak(t) == weak(etag) for t in re.findall(r'(?:W/)?"[^"]*"', if_none_match))


# ---- transports -------------------------------------------------------------------------------

class FixtureTransport:
    """Recorded responses, keyed by the URL each `.headers.json` names. No network code at all."""

    def __init__(self, directory):
        self.index = {}
        for n in sorted(os.listdir(directory)):
            if n.endswith('.headers.json'):
                with open(os.path.join(directory, n), encoding='utf-8') as f:
                    meta = json.load(f)
                self.index[meta['url']] = (os.path.join(directory, n[:-len('.headers.json')]), meta)
        if not self.index:
            raise FileNotFoundError('no <name>.headers.json fixtures in %s' % directory)
        self.requests = []

    def get(self, url, headers):
        self.requests.append((url, dict(headers)))
        if url not in self.index:
            raise FixtureMiss(url)
        path, meta = self.index[url]
        if etag_matches(header(headers, 'If-None-Match'), header(meta['headers'], 'ETag')):
            kept = [(k, v) for k, v in meta['headers'] if k.lower() not in ('content-length', 'content-type')]
            return Response(304, kept, b'')
        with open(path, 'rb') as f:
            return Response(meta['status'], meta['headers'], f.read())


class NoNetwork:
    def get(self, url, headers):
        raise NetworkForbidden(url)
