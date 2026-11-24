#!/usr/bin/env python3
"""Liveness probes, the derived maintenance_status, and the bot's `dead` proposal (P5-S7-T01; 05 S7, 02 S8, 06 S3.3).

    uv run python -m ingest.liveness --dry-run          # probe live, print everything, write nothing
    uv run python -m ingest.liveness                    # the weekly run: append metrics/liveness/<yyyy>-W<ww>.jsonl,
                                                        # write any new proposal under metrics/liveness/proposals/
    uv run python -m ingest.liveness --derive-only      # no network: statuses and proposals from the recorded weeks
    uv run python -m ingest.liveness --only swe-bench,gaia --dry-run     # a small live trial
    uv run python -m ingest.liveness --dry-run --today 2026-11-23 \
        --root tests/ingest/fixtures/liveness/root --fixture tests/ingest/fixtures/liveness/http   # the fixture dry run

05 S7: "The weekly `health-check.yml` job records observable signals -- repo last-push date, dataset last-modified,
leaderboard last-updated, HTTP status -- into `metrics/`, and a benchmark whose every signal has been cold for twelve
months is proposed for `lifecycle: dead` by bot and confirmed by two humans. The signal is observable and linked; the
classification is human." 02 S8 owns the probe contract and the derivation of `maintenance_status`; 06 S3.3 makes
`pushed_at` the observable behind it and a 404 on a catalogued repository "signal, not error". This module is all of
it except the scheduled job, which is not added: 05 S9 places the leaderboard-liveness check in `freshness.yml`,
05 S7 in `health-check.yml`, and every workflow but pr-validate stays off until the maintainer enables one.

The signals. Per curated benchmark (data/benchmarks/<family>/, never _stubs/), from its own fields:

    git-host          repository (or leaderboard_url) on github.com    GET api.github.com/repos/{o}/{r}: pushed_at,
                                                                       archived. Dated exactly
    hf-dataset        dataset_url on huggingface.co/datasets/, else    GET huggingface.co/api/datasets/{id}:
                      external_ids.huggingface                         lastModified. Dated exactly
    hf-space          repository or leaderboard_url on                 GET huggingface.co/api/spaces/{id}:
                      huggingface.co/spaces/                           lastModified. Dated exactly
    leaderboard       any other leaderboard_url                        GET the page; 02 S8's fingerprint of its
                                                                       result-table rows. Undated: bounded only
    leaderboard-date  liveness.leaderboard_last_updated                the date a curator read off the board; no
                                                                       request. Dated exactly
    homepage          homepage, unless it is one of the pages above    GET with a Range header: liveness, a state,
                                                                       never a date

A package-release signal (02 S8's PyPI/npm/CRAN row) and a GitLab host are not read: no curated field names a
package, and no curated repository is on GitLab. A repository or dataset elsewhere (Zenodo, a DOI) has no dated API
wired, so it contributes nothing rather than a guess. The homepage is read with GET and a Range header, not 02 S8's
HEAD: 06 S7.2 says never HEAD (servers answer it 405) and the soft-404 rule needs the body.

The records. One JSON line per signal per probe, appended to metrics/liveness/<yyyy>-W<ww>.jsonl (the ISO week of
the run), carrying 02 S8's eight fields -- signal_type, url, http_method, http_status, observed_at, value (a date, a
SHA-256, or null), consecutive_failures, probe_blocked -- and benchmark, field, outcome, note and detail, so that
maintenance_status can be recomputed from the files alone. The outcome is one of:

    ok            a usable answer: the date, the fingerprint (null when the page has no result table), or, for a
                  homepage, that it answered
    not-modified  a 304 to the If-None-Match the last answer's ETag allows; its value is carried forward
    dead          02 S8's list: DNS failure, connection refused or reset, TLS failure, 404, 410, or a 2xx soft-404
                  (under 512 bytes saying "not found" / "no longer available", or a redirect to a site root other
                  than the recorded URL). Counted in consecutive_failures; a signal is dead at three in a row
    blocked       401, 403, 429 or an anti-bot interstitial: probe_blocked, contributes `unobservable`, never death
                  (OpenReview already 403s anonymous clients, 02 S8)
    refused       our own policy declined it (robots.txt, the no-collect list, a forbidden path, a zero budget):
                  probe_blocked as well, and visible as such
    error         anything else -- a 5xx, a timeout, an answer missing its field. Neither counts nor resets the
                  failures, and the last usable answer stands: "A single failure never changes a status"

An API's rate limit or a refused token is our budget, not a fact about the benchmark (06 S3.3: "Rate-limit
exhaustion is a soft failure: back off, resume next run"): that host is left for the rest of the run, nothing is
recorded for it, and the next run in the week picks it up.

The derivation (02 S8's table, `derive`). Each signal's latest probe is read: a blocked or refused one makes the
signal unobservable; three dead-class probes in a row make it dead (its last activity is the last date it gave, or
the first failure of the run); anything else keeps the last usable answer. An unchanged fingerprint is a lower bound,
never a date: until our own history of it reaches 180 days it is unobservable, and after that it dates the board's
last activity no later than our first observation. Then, for the benchmark: two or more of {homepage dead,
repository archived or removed, leaderboard gone, dataset removed} is `abandoned`; no dated signal at all is
`unobservable`; otherwise the most recent activity decides -- under 180 days `actively-maintained`, under 365
`slow`, under 730 `stale`, else `abandoned`. `published` applies the 30-day quarantine: a move toward `abandoned`
is held back and the value of 30 days earlier is published until it has held that long; a move away publishes at
once. Probing cadence follows 02 S8 too: weekly for actively-maintained and slow, monthly for stale, quarterly for
abandoned and unobservable -- except a benchmark still building its fingerprint history, which is probed weekly.

Coldness and the proposal. A benchmark is cold for twelve months when it has at least one maintenance signal, every
one of them is observable (a blocked or too-young signal could be hiding activity), and every one's last activity
is twelve calendar months or more before the run. Such a benchmark gets one proposal, unless its lifecycle is
already dormant, deprecated or retracted, or `maintenance_status_contested` is set (02 S8: "a maintainer's dated
public statement overrides a derived signal"). The proposal names 05 S7's word, `dead`, but
taxonomy/lifecycle.yaml has no such term: its ten lifecycle terms include none, `abandoned` is a maintenance_status
value (never hand-set), and 02 S11's legality matrix calls dormant / closed / abandoned "Fully dead". So the
proposed value is `dormant`, and the proposal tells the two confirmers what the signals cannot show: dormant's own
exclusion test forbids tagging it "on the originators' inactivity alone", so they must establish that no results
are being produced against the instrument, and turn it into `deprecated` where the maintainer advises against use,
or reject it where the benchmark is still in use. That choice of value is the maintainer's to confirm.

Where the proposal goes, and why: metrics/liveness/proposals/<benchmark-id>.json, written once and never rewritten.
Not data/: nothing here may reclassify an entry (05 S7: "the classification is human"), the schema refuses a
hand-written maintenance_status, and `dead` would not validate as a lifecycle value. Not
data/_ingest/unresolved/, the ledger the GitHub adapter's 404 lifecycle reviews go to: its rows carry a sentence,
not the linked evidence this proposal must (and the rule here is never to write under data/ at all). Beside the
weekly files instead, so each piece of evidence links to the week file and probe that produced it; one file per
benchmark, so two weekly PRs never touch one file and a proposal a person has resolved is never re-raised. The
confirmers record their two confirmations and the resolution in that file; the change to data/ is theirs
(P5-S7-T02). metrics/ is outside the citable core and the build never reads this directory. One caution for the
day the weekly job is switched on: 05 S2 has metrics/ "bot-written, auto-merged", and a pull request that adds a
proposal must not be, because the proposal exists to be read by people.

Politeness. Every request -- each redirect hop, each robots.txt -- passes `ProbeGate`, which is ingest/policy.yaml's
gate (no-collect, the forbidden paths, robots.txt read once per host per run under RFC 9309, a token bucket per
host, a per-run budget) with one widening for this module alone: a host the file does not list is not refused but
probed at one request every five seconds, 25 a run, because a liveness probe visits whatever a benchmark cites, as
the link-rot check does. One request at a time per host; redirects are followed by hand so every hop is admitted.
Every request carries the User-Agent every fetcher here sends. The transport is injected -- `NetworkTransport` live,
`FixtureProbeTransport` over recorded responses -- so every network read is mockable.

Credentials. Only what the environment holds: GH_API_TOKEN (as ingest/adapters/github.py reads it) goes to
api.github.com and HF_TOKEN to huggingface.co, in the Authorization header and nowhere else; both are optional
(GitHub's anonymous budget is 60 an hour, so an unauthenticated live run soft-fails part-way and resumes). Nothing
reads a credential store, and no token is ever printed or recorded.
"""
from __future__ import annotations

import os
import sys

if __name__ == '__main__' and not __package__:
    # Run as a file, this directory is sys.path[0], and ingest/http/ would then shadow the standard library's
    # `http`, which urllib imports. Put the repository root there instead (as ingest/archive_sources.py does).
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import argparse  # noqa: E402
import glob  # noqa: E402
import hashlib  # noqa: E402
import html.parser  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import socket  # noqa: E402
import ssl  # noqa: E402
import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import date, datetime, timedelta, timezone  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ingest.adapters.github import REPO_URL  # noqa: E402
from ingest.http import policy  # noqa: E402
from ingest.http.fixture import FixtureTransport, header  # noqa: E402
from tools.build.adoption import read_jsonl  # noqa: E402
from tools.build.liveness import add_months, as_date  # noqa: E402

USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'   # ingest/policy.yaml's, as every fetcher sends it
METRICS = 'metrics/liveness'
PROPOSALS = 'metrics/liveness/proposals'
WEEK_FILE = re.compile(r'^\d{4}-W\d{2}\.jsonl$')
GITHUB_API = 'https://api.github.com'
HF_API = 'https://huggingface.co/api'
GITHUB_ACCEPT = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
HF_URL = re.compile(r'^https://huggingface\.co/(datasets|spaces)/([^/#?\s]+/[^/#?\s]+?)/?(?:[#?].*)?$')
TOKEN_ENV = {'api.github.com': 'GH_API_TOKEN', 'huggingface.co': 'HF_TOKEN'}
API_TYPES = ('git-host', 'hf-dataset', 'hf-space')
DATED_TYPES = API_TYPES + ('leaderboard-date',)
SIGNAL_TYPES = DATED_TYPES + ('leaderboard', 'homepage')
OUTCOMES = ('ok', 'not-modified', 'dead', 'blocked', 'refused', 'error')
INDICATORS = {                       # 02 S8's four, by the field the probed URL came from
    'homepage': 'homepage dead',
    'repository': 'repository archived or removed',
    'leaderboard_url': 'leaderboard gone',
    'dataset_url': 'dataset removed',
    'external_ids.huggingface': 'dataset removed',
}
REDIRECTS = (301, 302, 303, 307, 308)
MAX_REDIRECTS = 5
RANGE = 'bytes=0-32767'
FULL_BODY = 4 * 1024 * 1024
SOFT404_BYTES = 512                  # 02 S8: "response body under 512 bytes containing 'not found' ..."
DEAD_AFTER = 3                       # 02 S8: "three consecutive probes"
SHORT_HISTORY_DAYS = 180             # 02 S8: an unchanged fingerprint is unobservable until our history is longer
QUARANTINE_DAYS = 30                 # 02 S8: a move toward abandoned is withheld this long
THRESHOLDS = ((180, 'actively-maintained'), (365, 'slow'), (730, 'stale'))   # else abandoned
STATUSES = ('actively-maintained', 'slow', 'stale', 'abandoned', 'unobservable')   # taxonomy/maintenance.yaml
CADENCE_DAYS = {'stale': 28, 'abandoned': 91, 'unobservable': 91}          # 02 S8; weekly for the other two
COLD_MONTHS = 12                     # 05 S7: "every signal has been cold for twelve months"
PROBE_HOST = (0.2, 1, 25)            # rate, burst, max_requests for a host ingest/policy.yaml does not list
PROBE_BASIS = ('02 S8 probe protocol (ingest/liveness.py): a host ingest/policy.yaml does not list is probed at one '
               'request every 5 s, 25 a run, robots.txt and no-collect still binding')
PLAN_TERM = 'dead'                   # 05 S7's word; not a term of taxonomy/lifecycle.yaml
PROPOSED_VALUE = 'dormant'           # the vocabulary's term for it (02 S11: dormant/closed/abandoned is "Fully dead")
ALREADY_CLASSIFIED = ('dormant', 'deprecated', 'retracted')
SKIPPED_TAGS = frozenset({'script', 'style', 'noscript', 'template', 'svg', 'iframe'})
VOID_TAGS = frozenset({'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param',
                       'source', 'track', 'wbr'})
AD_SLOT = re.compile(r'(?:^|[\s_-])(?:ad|ads|advert\w*|sponsor\w*|banner)(?:$|[\s_-])', re.I)
NOT_FOUND = re.compile(rb'not found|no longer available', re.I)
# A challenge page names itself in its title. The scripts below also ride along on ordinary pages behind the same
# services (Cloudflare injects its challenge-platform script into served pages), so they mark an interstitial only
# on a refusal's status.
CHALLENGE_TITLES = (b'<title>just a moment', b'attention required! | cloudflare', b'<title>ddos-guard')
CHALLENGE_SCRIPTS = (b'/cdn-cgi/challenge-platform/', b'cf-chl-', b'_incapsula_resource', b'px-captcha',
                     b'captcha-delivery.com')


class Unsent(Exception):
    """A probe not sent this run and not recorded: our budget or our token, not a fact about the benchmark."""

    def __init__(self, host: str, reason: str):
        super().__init__('%s: %s' % (host, reason))
        self.host, self.reason = host, reason


# ---- what is probed ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Target:
    benchmark: str
    signal_type: str
    field: str                       # the record field the signal comes from
    url: str | None                  # what is requested; for leaderboard-date, the board the date is about
    page: str | None                 # what a person opens to check it
    value: str | None = None         # leaderboard-date only: the curated date
    checked_on: str | None = None    # leaderboard-date only: liveness.last_checked

    @property
    def key(self) -> tuple:
        return (self.benchmark, self.signal_type, self.url)


def canonical(url: str | None) -> str:
    if not url:
        return ''
    u = urllib.parse.urlsplit(url.strip())
    query = '?' + u.query if u.query else ''
    return '%s://%s%s%s' % (u.scheme.lower(), (u.hostname or '').lower(), u.path.rstrip('/'), query)


def api_target(bid: str, fld: str, url: str) -> Target | None:
    """The dated API signal a repository, dataset or leaderboard URL has, or None."""
    m = REPO_URL.match(url)
    if m:
        return Target(bid, 'git-host', fld, '%s/repos/%s/%s' % (GITHUB_API, m.group(1), m.group(2)), url)
    m = HF_URL.match(url)
    if m:
        kind = 'hf-dataset' if m.group(1) == 'datasets' else 'hf-space'
        return Target(bid, kind, fld, '%s/%s/%s' % (HF_API, m.group(1), m.group(2)), url)
    return None


def targets(bid: str, rec: dict) -> list[Target]:
    """Every signal one benchmark record offers, each URL probed once."""
    out: list[Target] = []
    repo, ds, board, home = (rec.get(k) for k in ('repository', 'dataset_url', 'leaderboard_url', 'homepage'))
    for fld, url in (('repository', repo), ('dataset_url', ds)):
        t = api_target(bid, fld, url) if isinstance(url, str) else None
        if t:
            out.append(t)
    ext = (rec.get('external_ids') or {}).get('huggingface')      # optional block and key; None when absent
    if isinstance(ext, str) and ext and not any(t.signal_type == 'hf-dataset' for t in out):
        name = ext.split('datasets/', 1)[-1]
        out.append(Target(bid, 'hf-dataset', 'external_ids.huggingface', '%s/datasets/%s' % (HF_API, name),
                          'https://huggingface.co/datasets/%s' % name))
    if isinstance(board, str) and board:
        out.append(api_target(bid, 'leaderboard_url', board)
                   or Target(bid, 'leaderboard', 'leaderboard_url', board, board))
    live = rec.get('liveness') or {}                               # optional block; an empty one observes nothing
    curated = as_date(live.get('leaderboard_last_updated'))
    if curated:
        checked = as_date(live.get('last_checked'))
        out.append(Target(bid, 'leaderboard-date', 'liveness.leaderboard_last_updated', board or None, board or None,
                          curated.isoformat(), checked.isoformat() if checked else None))
    if isinstance(home, str) and home and canonical(home) not in {canonical(t.page) for t in out}:
        out.append(Target(bid, 'homepage', 'homepage', home, home))
    seen, unique = set(), []
    for t in out:
        if (t.signal_type, t.url) not in seen:
            seen.add((t.signal_type, t.url))
            unique.append(t)
    return unique


def catalogue(root: str) -> dict[str, tuple[str, dict]]:
    """{benchmark id: (its root-relative path, its record)} for every curated benchmark, never a stub."""
    from schema.taxonomy import read_yaml
    out = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'benchmarks', '*', '*.yaml'))):
        if os.path.basename(os.path.dirname(path)).startswith('_'):
            continue
        rec = read_yaml(path)
        out[rec['id']] = (os.path.relpath(path, root).replace(os.sep, '/'), rec)
    return out


# ---- the gate and the transports --------------------------------------------------------------------------------

class ProbeGate(policy.Gate):
    """ingest/policy.yaml's gate with one widening, for the probe alone: an unlisted host gets PROBE_HOST instead of
    a refusal. Everything else is the gate's: no-collect, the forbidden paths, robots.txt, the buckets, the budgets.
    The policy is copied, so the widening never leaks into the process-wide gate the adapters share."""

    def __init__(self, pol: policy.Policy, **kw):
        own = policy.Policy(dict(pol.hosts), pol.forbidden, pol.no_collect, pol.user_agent, pol.robots_token)
        super().__init__(own, **kw)

    def _listed(self, url, host):
        if host not in self.policy.hosts:
            rate, burst, cap = PROBE_HOST
            self.policy.hosts[host] = policy.HostPolicy(host, rate, burst, cap, PROBE_BASIS)
        return super()._listed(url, host)

    def budget(self, host: str) -> int | None:
        hp = self.policy.hosts.get(host)           # a host never asked has no entry yet, hence no budget to read
        return hp.max_requests if hp else None


@dataclass
class Reply:
    status: int | None               # None when nothing came back
    headers: list = field(default_factory=list)
    body: bytes = b''
    error: str | None = None
    failure: str | None = None       # 'dead' (02 S8's list) or 'error', when status is None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None                  # a 3xx surfaces as an HTTPError; the prober follows it, through the gate


def network_failure(e: BaseException) -> tuple[str, str]:
    """('dead' | 'error', what happened) for an exception urllib raised before any status came back."""
    reason = getattr(e, 'reason', e)
    text = ' '.join(str(reason).split())[:200]
    if isinstance(reason, socket.gaierror):
        return 'dead', 'DNS failure: %s' % text
    if isinstance(reason, (ConnectionRefusedError, ConnectionResetError)):
        return 'dead', 'connection refused or reset: %s' % text
    if isinstance(reason, ssl.SSLError):
        return 'dead', 'TLS failure: %s' % text
    if isinstance(reason, TimeoutError):
        return 'error', 'timed out: %s' % text
    return 'error', text or type(reason).__name__


def tokens_from_env() -> dict[str, str]:
    """{host: token} from the environment only: GH_API_TOKEN for api.github.com, HF_TOKEN for huggingface.co."""
    return {host: os.environ[var] for host, var in TOKEN_ENV.items() if os.environ.get(var)}


class NetworkTransport:
    """One GET over urllib, no redirect followed. The prober admits every URL first (robots.txt, the bucket, the
    budget); this re-checks the hard refusals, so no caller can point it at a no-collect host or a forbidden path.
    A token is attached only for the host it belongs to."""

    def __init__(self, gate: policy.Gate, tokens: dict[str, str] | None = None, timeout: int = 30):
        self.gate, self.tokens, self.timeout = gate, dict(tokens or {}), timeout
        self._opener = urllib.request.build_opener(_NoRedirect)

    def get(self, url, headers):
        self.gate.refuse(url)                                    # 07 S10.1: no-collect and forbidden, every code path
        host = (urllib.parse.urlsplit(url).hostname or '').lower()
        h = {'User-Agent': USER_AGENT, 'Accept': '*/*', **headers}
        token = self.tokens.get(host)
        if token:
            h['Authorization'] = 'Bearer ' + token
        try:
            with self._opener.open(urllib.request.Request(url, headers=h), timeout=self.timeout) as r:
                return Reply(r.status, list(r.headers.items()), r.read(FULL_BODY))
        except urllib.error.HTTPError as e:                      # urllib raises for 3xx, 304 and 4xx too
            try:
                body = e.read(FULL_BODY)
            except Exception:                                    # a body-less error response has nothing to read
                body = b''
            return Reply(e.code, list(e.headers.items()) if e.headers else [], body)
        except (urllib.error.URLError, OSError, ValueError) as e:
            kind, msg = network_failure(e)
            return Reply(None, [], b'', msg, kind)


class FixtureProbeTransport(FixtureTransport):
    """Recorded responses (ingest/http/fixture.py's format). A `.headers.json` may give `"status": null` with
    `"error"` and `"failure"` to record a DNS failure, a refused connection or a timeout. No network code."""

    def get(self, url, headers):
        r = super().get(url, headers)    # get-default: a recorded HTTP GET; FixtureMiss for an unrecorded URL
        meta = self.index[url][1]
        return Reply(r.status, list(r.headers), r.body, meta.get('error'), meta.get('failure'))

    def robots(self, url, user_agent):
        """The gate's robots.txt fetcher over the same set: a recorded robots.txt, else 404 (none)."""
        if url not in self.index:
            return 404, ''
        r = super().get(url, {})         # get-default: a recorded HTTP GET with no headers
        return r.status, r.body.decode('utf-8', 'replace')


class VirtualClock:
    """A clock the gate's buckets sleep on without waiting: the fixture dry run reports the pacing it would keep."""

    def __init__(self):
        self.t, self.waited = 0.0, 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s
        self.waited += s


@dataclass
class Got:
    status: int | None
    headers: list
    body: bytes
    final: str
    chain: list
    error: str | None = None
    failure: str | None = None


class Prober:
    """GET through the gate, redirects followed by hand so every hop is admitted."""

    def __init__(self, transport, gate: policy.Gate):
        self.transport, self.gate = transport, gate

    def fetch(self, url: str, headers: dict) -> Got:
        chain, cur = [], url
        for _ in range(MAX_REDIRECTS + 1):
            self.gate.admit(cur)
            r = self.transport.get(cur, dict(headers))   # get-default: an HTTP GET with request headers
            loc = header(r.headers, 'Location') if r.status in REDIRECTS else None
            if loc:
                chain.append(cur)
                cur = urllib.parse.urljoin(cur, loc)
                continue
            return Got(r.status, list(r.headers), r.body or b'', cur, chain, getattr(r, 'error', None),
                       getattr(r, 'failure', None))
        return Got(None, [], b'', cur, chain, 'more than %d redirects' % MAX_REDIRECTS, 'error')


# ---- reading a page ---------------------------------------------------------------------------------------------

class _Rows(html.parser.HTMLParser):
    """The text of every table row, scripts, styles and ad slots skipped (02 S8's normalisation)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []          # (tag, opened a skipped subtree)
        self.skipping = 0
        self.tables: list[list[str] | None] = []         # per open table: the row being read, or None
        self.rows: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        skip = tag in SKIPPED_TAGS or bool(AD_SLOT.search('%s %s' % (a.get('class') or '', a.get('id') or '')))
        if tag not in VOID_TAGS:
            self.stack.append((tag, skip))
            self.skipping += skip
        if self.skipping:
            return
        if tag == 'table':
            self.tables.append(None)
        elif tag == 'tr':
            if not self.tables:
                self.tables.append(None)
            self._close_row()
            self.tables[-1] = []
        elif tag in ('td', 'th') and self.tables and self.tables[-1] is not None:
            self.tables[-1].append('')

    def handle_endtag(self, tag):
        if not any(t == tag for t, _ in self.stack):
            return
        while self.stack:
            t, skip = self.stack.pop()
            self.skipping -= skip
            if t == tag:
                break
        if self.skipping:
            return
        if tag == 'tr' and self.tables:
            self._close_row()
        elif tag == 'table' and self.tables:
            self._close_row()
            self.tables.pop()

    def handle_data(self, data):
        if self.skipping or not self.tables or self.tables[-1] is None:
            return
        row = self.tables[-1]
        if not row:
            row.append('')
        row[-1] += data

    def _close_row(self):
        if self.tables and self.tables[-1] is not None:
            text = '\t'.join(' '.join(c.split()) for c in self.tables[-1]).strip()
            if text:
                self.rows.append(text)
            self.tables[-1] = None

    def close(self):
        super().close()
        while self.tables:
            self._close_row()
            self.tables.pop()


def fingerprint(body: bytes, content_type: str | None = None) -> tuple[str | None, dict]:
    """02 S8's `leaderboard_fingerprint`: the result-table rows, normalised and sorted, SHA-256'd. (None, why) when
    there are no rows to read -- a script-rendered board, say -- because hashing its shell would date nothing."""
    text = body.decode('utf-8', 'replace')
    if 'json' in (content_type or '').lower() or text.lstrip()[:1] in ('[', '{'):
        try:
            doc = json.loads(text)
        except ValueError:
            doc = None
        if doc is not None:
            rows = sorted(json.dumps(x, sort_keys=True, ensure_ascii=False) for x in doc) if isinstance(doc, list) \
                else [json.dumps(doc, sort_keys=True, ensure_ascii=False)]
            return hashlib.sha256('\n'.join(rows).encode('utf-8')).hexdigest(), {'basis': 'json', 'rows': len(rows)}
    p = _Rows()
    p.feed(text)
    p.close()
    if not p.rows:
        return None, {'basis': 'no-table-rows'}
    rows = sorted(p.rows)
    return hashlib.sha256('\n'.join(rows).encode('utf-8')).hexdigest(), {'basis': 'table-rows', 'rows': len(rows)}


def interstitial(got: Got) -> bool:
    """A Cloudflare-style challenge or another anti-bot page: blocked, never content and never death."""
    if (header(got.headers, 'cf-mitigated') or '').lower() == 'challenge':
        return True
    head = got.body[:65536].lower()
    return any(m in head for m in CHALLENGE_TITLES) or \
        (got.status in (403, 429, 503) and any(m in head for m in CHALLENGE_SCRIPTS))


def is_root(url: str) -> bool:
    u = urllib.parse.urlsplit(url)
    return u.path in ('', '/') and not u.query


def soft404(got: Got, url: str) -> str | None:
    """02 S8's soft-404 on a 2xx, or None."""
    if len(got.body) < SOFT404_BYTES and NOT_FOUND.search(got.body):
        return 'a %d-byte answer saying the page is not there (02 S8 soft-404)' % len(got.body)
    if canonical(got.final) != canonical(url) and is_root(got.final) and not is_root(url):
        return 'redirected to the site root %s (02 S8 soft-404)' % got.final
    return None


# ---- one probe, one record --------------------------------------------------------------------------------------

def stamp(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def observed_on(r: dict) -> date:
    return date.fromisoformat(r['observed_at'][:10])


def key_of(r: dict) -> tuple:
    return (r['benchmark'], r['signal_type'], r['url'])


def usable(history: list[dict]) -> dict | None:
    """The last answer that gave a value."""
    for r in reversed(history):
        if r['outcome'] in ('ok', 'not-modified') and r['value'] is not None:
            return r
    return None


def make_record(t: Target, at: datetime, status: int | None, value, outcome: str, prev: dict | None,
                note: str | None = None, detail: dict | None = None, method: str | None = 'GET') -> dict:
    failures = prev['consecutive_failures'] if prev else 0
    if outcome == 'dead':
        failures += 1
    elif outcome in ('ok', 'not-modified'):
        failures = 0
    return {'benchmark': t.benchmark, 'signal_type': t.signal_type, 'field': t.field, 'url': t.url,
            'http_method': method, 'http_status': status, 'observed_at': stamp(at), 'value': value,
            'consecutive_failures': failures, 'probe_blocked': outcome in ('blocked', 'refused'),
            'outcome': outcome, 'note': note, 'detail': detail or {}}


def probe(t: Target, prober: Prober, history: list[dict], at: datetime) -> dict:
    """One signal, one record. Raises Unsent when the request is ours to retry next run, not a fact to record."""
    prev = history[-1] if history else None
    if t.signal_type == 'leaderboard-date':
        return make_record(t, at, None, t.value, 'ok', prev, method=None,
                           detail={'source': 'the curated record', 'checked_on': t.checked_on})
    last = usable(history)
    host = (urllib.parse.urlsplit(t.url).hostname or '').lower()
    headers: dict = {}
    if t.signal_type in API_TYPES:
        headers = dict(GITHUB_ACCEPT) if t.signal_type == 'git-host' else {'Accept': 'application/json'}
        if last and last['detail'].get('etag'):
            headers['If-None-Match'] = last['detail']['etag']
    elif t.signal_type == 'homepage':
        headers = {'Range': RANGE}
    try:
        got = prober.fetch(t.url, headers)
        if got.status == 416 and t.signal_type == 'homepage':     # a server that refuses the Range: ask for the page
            got = prober.fetch(t.url, {})
    except policy.BudgetExhausted as e:
        if prober.gate.budget(host) == 0:                          # "Zero. Link out only" (07 S10): permanent
            return make_record(t, at, None, None, 'refused', prev, note='%s: %s' % (type(e).__name__, e.reason))
        raise Unsent(host, 'the run budget for %s is spent; the next run resumes' % host)
    except policy.PolicyRefusal as e:
        return make_record(t, at, None, None, 'refused', prev, note='%s: %s' % (type(e).__name__, e.reason))
    detail = {'final_url': got.final} if got.chain else {}
    if got.status is None:
        return make_record(t, at, None, None, got.failure or 'error', prev, note=got.error, detail=detail)
    if t.signal_type in API_TYPES:
        return api_record(t, at, got, prev, last, detail)
    return page_record(t, at, got, prev, detail)


def api_record(t: Target, at: datetime, got: Got, prev: dict | None, last: dict | None, detail: dict) -> dict:
    s, host = got.status, (urllib.parse.urlsplit(t.url).hostname or '').lower()
    remaining = header(got.headers, 'X-RateLimit-Remaining')
    if s == 429 or (s == 403 and remaining == '0'):
        raise Unsent(host, 'HTTP %d: the API rate limit is spent (06 S3.3: a soft failure, resumed next run)' % s)
    if s == 401 and t.signal_type == 'git-host':
        raise Unsent(host, 'HTTP 401: the GH_API_TOKEN was refused')
    if s == 304 and last:
        return make_record(t, at, 304, last['value'], 'not-modified', prev, detail={**last['detail'], **detail})
    if s == 200:
        want = 'pushed_at' if t.signal_type == 'git-host' else 'lastModified'
        try:
            doc = json.loads(got.body)
        except ValueError:
            doc = None
        need = (want, 'archived') if t.signal_type == 'git-host' else (want,)
        if not isinstance(doc, dict) or not isinstance(doc.get(want), str) or \
                (t.signal_type == 'git-host' and not isinstance(doc.get('archived'), bool)):
            return make_record(t, at, 200, None, 'error', prev, detail=detail,
                               note='schema drift: the answer lacks %s' % ' or '.join(need))
        etag = header(got.headers, 'ETag')
        if etag:
            detail['etag'] = etag
        if t.signal_type == 'git-host':
            detail['archived'] = doc['archived']
        return make_record(t, at, 200, doc[want][:10], 'ok', prev, detail=detail)
    if s in (404, 410):
        return make_record(t, at, s, None, 'dead', prev, detail=detail,
                           note='%s answers %d: the %s has gone (06 S3.3: signal, not error)'
                           % (t.url, s, t.signal_type))
    if s in (401, 403, 451):
        why = ' (the Hub answers 401 for a private, gated or missing repository)' if s == 401 else ''
        return make_record(t, at, s, None, 'blocked', prev, detail=detail, note='HTTP %d%s' % (s, why))
    return make_record(t, at, s, None, 'error', prev, detail=detail, note='HTTP %d' % s)


def page_record(t: Target, at: datetime, got: Got, prev: dict | None, detail: dict) -> dict:
    s = got.status
    if interstitial(got):
        return make_record(t, at, s, None, 'blocked', prev, detail=detail,
                           note='an anti-bot interstitial (HTTP %d)' % s)
    if 200 <= s < 300:
        why = soft404(got, t.url)
        if why:
            return make_record(t, at, s, None, 'dead', prev, detail=detail, note=why)
        if t.signal_type == 'leaderboard':
            value, more = fingerprint(got.body, header(got.headers, 'Content-Type'))
            note = None if value else 'no result-table rows to fingerprint: unobservable, never stale'
            return make_record(t, at, s, value, 'ok', prev, detail={**detail, **more}, note=note)
        return make_record(t, at, s, None, 'ok', prev, detail=detail)
    if s in (404, 410):
        return make_record(t, at, s, None, 'dead', prev, detail=detail, note='HTTP %d' % s)
    if s in (401, 403, 429):
        return make_record(t, at, s, None, 'blocked', prev, detail=detail, note='HTTP %d' % s)
    return make_record(t, at, s, None, 'error', prev, detail=detail, note='HTTP %d' % s)


# ---- the derivation (02 S8) -------------------------------------------------------------------------------------

def by_key(records: list[dict]) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = {}
    for r in sorted(records, key=lambda r: r['observed_at']):       # stable: one probe's lines keep their order
        out.setdefault(key_of(r), []).append(r)
    return out


def assess(group: list[dict], as_of: date) -> dict:
    """One signal's state from its probes up to `as_of`: dated, bounded, dead, unobservable, or (homepage) a state."""
    recs = [r for r in group if observed_on(r) <= as_of]
    latest = recs[-1]
    kind, fld = latest['signal_type'], latest['field']
    out = {'signal_type': kind, 'field': fld, 'url': latest['url'], 'state': None, 'last_activity': None,
           'archived': False, 'short_history': False, 'basis': None, 'latest': latest, 'dated_by': None}
    good = [r for r in recs if r['outcome'] in ('ok', 'not-modified')]
    dead = latest['outcome'] == 'dead' and latest['consecutive_failures'] >= DEAD_AFTER
    if kind == 'homepage':
        out['state'] = 'dead' if dead else 'blocked' if latest['probe_blocked'] else 'live' if good else 'unknown'
        out['basis'] = latest['note'] or 'HTTP %s on %s' % (latest['http_status'], latest['observed_at'][:10])
        return out
    if latest['probe_blocked']:
        out.update(state='unobservable', basis='probe blocked on %s: %s' % (latest['observed_at'][:10], latest['note']))
        return out
    if kind == 'leaderboard' and good and good[-1]['value'] is None and not dead:
        out.update(state='unobservable',
                   basis='no result-table rows to fingerprint on %s' % good[-1]['observed_at'][:10])
        return out
    valued = [r for r in good if r['value'] is not None]
    if kind == 'leaderboard':
        dated, bounded, out['dated_by'], out['basis'], out['short_history'] = fingerprint_activity(valued, as_of)
    else:
        bounded = False
        dated = as_date(valued[-1]['value']) if valued else None
        if valued:
            first = valued[-1]                 # the probe that first read the current value (a 304 only carries it)
            for r in reversed(valued):
                if r['value'] != valued[-1]['value']:
                    break
                first = r
            out['dated_by'] = first
            out['archived'] = valued[-1]['detail'].get('archived') is True
            out['basis'] = '%s %s, first read on %s, last on %s' % (
                kind, dated.isoformat(), first['observed_at'][:10], valued[-1]['observed_at'][:10])
    if dead:
        since = first_failure(recs)
        out.update(state='dead', last_activity=(dated or since).isoformat(),
                   basis='%d consecutive dead probes since %s (%s)%s' % (
                       latest['consecutive_failures'], since.isoformat(), latest['note'],
                       '; last activity %s' % dated.isoformat() if dated else ''))
    elif dated is None:
        out.update(state='unobservable', basis=out['basis'] or 'no usable answer yet')
    else:
        out.update(state='bounded' if bounded else 'dated', last_activity=dated.isoformat())
    return out


def fingerprint_activity(valued: list[dict], as_of: date) -> tuple:
    """(activity date or None, bounded, the record that dates it, basis, short history) for a fingerprint's probes,
    read the way 02 S8 says: a change is an update dated at probe time; an unchanged fingerprint is a lower bound,
    and before 180 days of our own history it is no evidence at all."""
    if not valued:
        return None, False, None, None, False
    first = observed_on(valued[0])
    changes = [b for a, b in zip(valued, valued[1:]) if a['value'] != b['value']]
    if changes:
        when = observed_on(changes[-1])
        return when, False, changes[-1], ('fingerprint changed between probes, dated at the probe of %s'
                                          % when.isoformat()), False
    if (as_of - first).days < SHORT_HISTORY_DAYS:
        why = ('unchanged since our first observation on %s; under %d days of our own history, so no evidence '
               'either way' % (first.isoformat(), SHORT_HISTORY_DAYS))
        return None, False, valued[0], why, True
    return first, True, valued[0], ('unchanged since our first observation on %s: a lower bound on its staleness, '
                                    'not a date' % first.isoformat()), False


def first_failure(recs: list[dict]) -> date:
    """The date the current run of dead-class probes began (blocked and error probes in between neither break nor
    extend it)."""
    since = observed_on(recs[-1])
    for r in reversed(recs):
        if r['outcome'] in ('ok', 'not-modified'):
            break
        if r['outcome'] == 'dead':
            since = observed_on(r)
    return since


def derive(records: list[dict], as_of: date, named: list[Target] | None = None) -> dict:
    """maintenance_status for one benchmark's probe records, as of a date (02 S8's table), with its coldness.
    `named` is the signals the record names now: one of them with no probe yet is unobservable, so it holds
    back the twelve-month rule until it has been read."""
    groups = by_key([r for r in records if observed_on(r) <= as_of])
    signals = [assess(g, as_of) for g in groups.values()]
    signals += [unprobed(t) for t in named or [] if t.key not in groups]
    upkeep = [s for s in signals if s['signal_type'] != 'homepage']
    dated = [s for s in upkeep if s['last_activity']]
    indicators = sorted({INDICATORS[s['field']] for s in signals
                         if (s['state'] == 'dead' or s['archived']) and s['field'] in INDICATORS})
    last = max((as_date(s['last_activity']) for s in dated), default=None)
    days = (as_of - last).days if last else None
    if len(indicators) >= 2:
        status, basis = 'abandoned', 'two or more of 02 S8\'s four, each confirmed: %s' % ', '.join(indicators)
    elif last is None:
        status = 'unobservable'
        basis = ('every probe blocked or refused' if signals and all(s['latest'] and s['latest']['probe_blocked']
                                                                      for s in signals)
                 else 'no dated signal we can poll' if not upkeep else 'no signal dated yet: %s'
                 % '; '.join('%s %s' % (s['signal_type'], s['basis']) for s in upkeep))
    else:
        status = next((name for limit, name in THRESHOLDS if days < limit), 'abandoned')
        newest = max(dated, key=lambda s: s['last_activity'])
        basis = 'most recent activity %s (%s), %d days before %s' % (
            last.isoformat(), newest['signal_type'], days, as_of.isoformat())
    return {'status': status, 'basis': basis, 'as_of': as_of.isoformat(),
            'last_activity': last.isoformat() if last else None, 'days_since_activity': days,
            'indicators': indicators, 'signals': signals, 'coldness': coldness(upkeep, as_of),
            'building_history': any(s['short_history'] for s in upkeep),
            'unprobed': sum(1 for s in signals if s['latest'] is None)}


def unprobed(t: Target) -> dict:
    return {'signal_type': t.signal_type, 'field': t.field, 'url': t.url,
            'state': 'unknown' if t.signal_type == 'homepage' else 'unobservable', 'last_activity': None,
            'archived': False, 'short_history': False, 'basis': 'not read yet', 'latest': None, 'dated_by': None}


def coldness(upkeep: list[dict], as_of: date) -> dict:
    """05 S7's condition: every maintenance signal observable, and every one cold for twelve months."""
    out = {'signals': len(upkeep), 'cold_for_twelve_months': False, 'why': None}
    if not upkeep:
        out['why'] = 'no maintenance signal to read'
        return out
    blind = [s for s in upkeep if s['last_activity'] is None]
    if blind:
        out['why'] = 'not every signal is observable: %s' % ', '.join(
            '%s (%s)' % (s['signal_type'], s['basis']) for s in blind)
        return out
    warm = [s for s in upkeep if add_months(as_date(s['last_activity']), COLD_MONTHS) > as_of]
    if warm:
        out['why'] = 'active within twelve months: %s' % ', '.join(
            '%s %s' % (s['signal_type'], s['last_activity']) for s in warm)
        return out
    out['cold_for_twelve_months'] = True
    out['why'] = 'every one of %d signal(s) cold for twelve months or more' % len(upkeep)
    return out


def published(records: list[dict], as_of: date, named: list[Target] | None = None) -> dict:
    """derive(), with 02 S8's quarantine: a move toward abandoned is withheld for 30 days; a move away is not."""
    now = derive(records, as_of, named)
    out = dict(now, computed=now['status'], published=now['status'], withheld=None)
    if now['status'] == 'abandoned':
        then = derive(records, as_of - timedelta(days=QUARANTINE_DAYS), named)
        if then['status'] != 'abandoned':
            out['published'] = then['status']
            out['withheld'] = {'status': 'abandoned', 'computed_on': as_of.isoformat(),
                               'publishes_from': (as_of + timedelta(days=QUARANTINE_DAYS)).isoformat(),
                               'why': '02 S8: a transition toward abandoned is withheld for %d days' % QUARANTINE_DAYS}
    return out


def due(derived: dict, records: list[dict], today: date) -> bool:
    """02 S8's cadence: weekly for actively-maintained and slow, monthly for stale, quarterly for abandoned and
    unobservable; weekly while a fingerprint is still building its history; at once for a signal never read."""
    if not records or derived['unprobed']:
        return True
    last = max(observed_on(r) for r in records)
    if week_of(last) == week_of(today) or derived['building_history']:
        return True
    days = CADENCE_DAYS.get(derived['status'])
    return days is None or (today - last).days >= days


# ---- the proposal -----------------------------------------------------------------------------------------------

def lifecycle_terms(root: str = ROOT) -> set[str]:
    from schema.taxonomy import read_yaml
    doc = read_yaml(os.path.join(root, 'taxonomy', 'lifecycle.yaml'))
    return {t['id'] for t in doc['terms'] if t['field'] == 'lifecycle'}


def week_of(d: date) -> str:
    y, w, _ = d.isocalendar()
    return '%d-W%02d' % (y, w)


def week_file(d: date) -> str:
    return '%s/%s.jsonl' % (METRICS, week_of(d))


def link(r: dict | None) -> dict | None:
    """Where a probe record is: its week file, and the fields that find its line in it."""
    if r is None:
        return None
    return {'file': week_file(observed_on(r)), 'benchmark': r['benchmark'], 'signal_type': r['signal_type'],
            'url': r['url'], 'observed_at': r['observed_at'], 'http_status': r['http_status'],
            'outcome': r['outcome'], 'value': r['value']}


def proposal(bid: str, path: str, rec: dict, derived: dict, as_of: date) -> tuple[dict | None, str]:
    """The proposal 05 S7 asks for, or (None, why there is none)."""
    if rec.get('lifecycle') in ALREADY_CLASSIFIED:
        return None, 'lifecycle is already %s' % rec['lifecycle']
    if rec.get('maintenance_status_contested') is True:
        return None, ('maintenance_status is contested (%s, %s): a maintainer\'s dated public statement overrides '
                      'a derived signal (02 S8)' % (rec.get('contested_source'), rec.get('contested_statement_date')))
    cold = derived['coldness']
    if not cold['cold_for_twelve_months']:
        return None, cold['why']
    if PROPOSED_VALUE not in lifecycle_terms():
        raise AssertionError('%s is not a lifecycle term of taxonomy/lifecycle.yaml' % PROPOSED_VALUE)
    evidence = []
    for s in derived['signals']:
        evidence.append({
            'signal_type': s['signal_type'], 'field': s['field'], 'probed': s['url'],
            'page': (s['latest'] and s['latest']['detail'].get('final_url')) or page_of(rec, s),
            'state': s['state'], 'last_activity': s['last_activity'],
            'cold_days': (as_of - as_date(s['last_activity'])).days if s['last_activity'] else None,
            'basis': s['basis'], 'latest_probe': link(s['latest']), 'dated_by': link(s['dated_by'])})
    return {
        'proposal': 'lifecycle-%s' % PLAN_TERM,
        'benchmark': bid,
        'record': path,
        'opened_on': as_of.isoformat(),
        'opened_by': 'ingest/liveness.py (bot)',
        'rule': '05 S7: every signal cold for twelve months is proposed for lifecycle: dead by bot and confirmed '
                'by two humans. The signal is observable and linked; the classification is human.',
        'field': 'lifecycle',
        'current_value': rec.get('lifecycle'),
        'proposed_value': PROPOSED_VALUE,
        'plan_term': PLAN_TERM,
        'vocabulary_note': ('05 S7 says `dead`; taxonomy/lifecycle.yaml has no such term. `%s` is its term for an '
                            'instrument nobody maintains and nothing formally ended (02 S11 reads dormant / closed / '
                            'abandoned as "Fully dead"). Its exclusion test forbids tagging it on the originators\' '
                            'inactivity alone, which is all these signals show.' % PROPOSED_VALUE),
        'maintenance_status': {'computed': derived['computed'], 'published': derived['published'],
                               'withheld': derived['withheld'], 'basis': derived['basis'],
                               'indicators': derived['indicators']},
        'coldness': {'last_activity': derived['last_activity'], 'days_since_activity': derived['days_since_activity'],
                     'why': derived['coldness']['why']},
        'evidence': evidence,
        'to_confirm': [
            'Open every linked signal and check its date against the page itself.',
            'Establish that no results are being produced against the benchmark: the signals show the originators '
            'are inactive, which dormant\'s exclusion test says is not enough on its own. Still in use: reject, '
            'and the coldness stays maintenance_status evidence.',
            'Where the maintainer advises against use, the value is deprecated, not dormant.',
            'Two people confirm, each adding an entry to `confirmations` (who, when, what was checked), and the '
            'outcome and its rationale go in `resolution`, before any change to data/ (P5-S7-T02). No machine '
            'applies this file.',
        ],
        'status': 'open',
        'confirmations': [],
        'resolution': None,
    }, cold['why']


def page_of(rec: dict, s: dict) -> str | None:
    """The page a person opens for a signal: the record's own URL in the field the signal came from."""
    if s['field'] == 'external_ids.huggingface':
        name = str((rec.get('external_ids') or {})['huggingface'])
        return 'https://huggingface.co/datasets/%s' % name.split('datasets/', 1)[-1]
    if s['field'] == 'liveness.leaderboard_last_updated':
        return rec.get('leaderboard_url')
    return rec.get(s['field'])


# ---- writing, never under data/ ---------------------------------------------------------------------------------

def guard(root: str, path: str) -> str:
    """Refuse any path under data/: this module records and proposes; it never reclassifies (05 S7)."""
    data = os.path.normcase(os.path.abspath(os.path.join(root, 'data'))) + os.sep
    if os.path.normcase(os.path.abspath(path)).startswith(data):
        raise PermissionError('ingest/liveness.py never writes under data/ (05 S7: the classification is human): %s'
                              % path)
    return path


def append_week(root: str, d: date, lines: list[dict]) -> str:
    path = guard(root, os.path.join(root, *week_file(d).split('/')))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8', newline='\n') as fh:
        for line in lines:
            fh.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + '\n')
    return path


def proposal_path(root: str, bid: str) -> str:
    return os.path.join(root, *PROPOSALS.split('/'), '%s.json' % bid)


def write_proposal(root: str, p: dict) -> str:
    path = guard(root, proposal_path(root, p['benchmark']))
    if os.path.exists(path):
        raise FileExistsError('%s exists: a proposal is opened once and resolved by people, never rewritten' % path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(p, fh, indent=2, ensure_ascii=False)
        fh.write('\n')
    return path


def load_history(root: str) -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(root, *METRICS.split('/'), '*.jsonl'))):
        if WEEK_FILE.match(os.path.basename(path)):
            out += read_jsonl(path)
    return out


# ---- one run ----------------------------------------------------------------------------------------------------

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def run(root: str, prober: Prober | None, *, now=utcnow, only: set[str] | None = None, limit: int | None = None,
        dry_run: bool = False, derive_only: bool = False) -> dict:
    """Probe what is due, derive every benchmark's status, open the proposals the twelve-month rule calls for."""
    at = now()
    today = at.date()
    cat = catalogue(root)
    ids = [b for b in sorted(cat) if not only or b in only]
    history = load_history(root)
    # A benchmark's signals are the ones its record names now: a repository or board a curator has since replaced
    # keeps its lines in metrics/ but is no longer one of the benchmark's signals.
    tgs = {bid: targets(bid, cat[bid][1]) for bid in ids}
    named = {bid: {t.key for t in tgs[bid]} for bid in ids}
    mine: dict[str, list[dict]] = {bid: [] for bid in ids}
    for r in history:
        if r['benchmark'] in named and key_of(r) in named[r['benchmark']]:
            mine[r['benchmark']].append(r)
    week = week_of(today)
    done = {key_of(r) for r in history if week_of(observed_on(r)) == week}
    report = {'week': week, 'file': week_file(today), 'as_of': today.isoformat(), 'benchmarks': len(ids),
              'probed': [], 'not_due': [], 'already_this_week': 0, 'soft_fails': [], 'lines': [],
              'statuses': {}, 'proposals': [], 'already_proposed': [], 'not_proposed': {}, 'written': []}
    spent: set[str] = set()
    if not derive_only:
        groups = by_key(history)
        for bid in ids:
            if limit is not None and len(report['probed']) >= limit:
                break
            before = mine[bid]
            if not due(derive(before, today, tgs[bid]), before, today):
                report['not_due'].append(bid)
                continue
            sent = False
            for t in tgs[bid]:
                if t.key in done:
                    report['already_this_week'] += 1
                    continue
                host = (urllib.parse.urlsplit(t.url).hostname or '').lower() if t.url else None
                if host in spent and t.signal_type != 'leaderboard-date':
                    continue
                try:
                    history_of = groups.get(t.key, [])          # get-default: a signal never probed has no history
                    line = probe(t, prober, history_of, at)
                except Unsent as e:
                    spent.add(e.host)
                    report['soft_fails'].append(str(e))
                    continue
                report['lines'].append(line)
                mine[bid].append(line)
                sent = True
            if sent:
                report['probed'].append(bid)
    for bid in ids:
        path, rec = cat[bid]
        d = published(mine[bid], today, tgs[bid])
        d['contested'] = bool(rec.get('maintenance_status_contested'))
        report['statuses'][bid] = d
        p, why = proposal(bid, path, rec, d, today)
        if p is None:
            report['not_proposed'][bid] = why
        elif os.path.exists(proposal_path(root, bid)):
            report['already_proposed'].append(bid)
        else:
            report['proposals'].append(p)
    if not dry_run:
        if report['lines']:
            report['written'].append(append_week(root, today, report['lines']))
        for p in report['proposals']:
            report['written'].append(write_proposal(root, p))
    return report


def render(report: dict, dry_run: bool) -> list[str]:
    out = ['liveness %s (as of %s): %d benchmark(s); %d probed, %d line(s); %d not due; %d signal(s) already probed '
           'this week' % (report['week'], report['as_of'], report['benchmarks'], len(report['probed']),
                          len(report['lines']), len(report['not_due']), report['already_this_week'])]
    out += ['  soft fail: %s' % s for s in report['soft_fails']]
    for bid, d in sorted(report['statuses'].items()):
        held = d['withheld']
        shown = d['published'] + (' (computed %s, withheld to %s)' % (held['status'], held['publishes_from'])
                                  if held else '')
        out.append('  %-28s %-46s %s%s' % (bid, shown, d['basis'], '  [contested]' if d['contested'] else ''))
    out.append('proposals: %d new, %d already open' % (len(report['proposals']), len(report['already_proposed'])))
    for p in report['proposals']:
        out.append('  %s/%s.json: lifecycle %s -> %s (05 S7\'s `%s`): %s' % (
            PROPOSALS, p['benchmark'], p['current_value'], p['proposed_value'], p['plan_term'], p['coldness']['why']))
    out.append('dry run: nothing written' if dry_run else 'wrote %d file(s)' % len(report['written']))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', default=ROOT, help='the tree holding data/benchmarks/ and metrics/liveness/')
    ap.add_argument('--today', type=date.fromisoformat, default=None, help='run as of this date (noon UTC)')
    ap.add_argument('--fixture', help='recorded responses in place of the network')
    ap.add_argument('--dry-run', action='store_true', help='print the lines, statuses and proposals; write nothing')
    ap.add_argument('--derive-only', action='store_true', help='probe nothing: derive from the recorded weeks')
    ap.add_argument('--only', help='comma-separated benchmark ids')
    ap.add_argument('--limit', type=int, help='probe at most this many benchmarks')
    ap.add_argument('--lines', action='store_true', help='also print every probe line')
    a = ap.parse_args(argv)
    now = (lambda: datetime(a.today.year, a.today.month, a.today.day, 12, tzinfo=timezone.utc)) if a.today else utcnow
    prober, clock = None, None
    if not a.derive_only:
        if a.fixture:
            transport = FixtureProbeTransport(a.fixture)
            clock = VirtualClock()
            gate = ProbeGate(policy.Policy.load(), robots=transport.robots, clock=clock, sleep=clock.sleep)
        else:
            gate = ProbeGate(policy.Policy.load())
            transport = NetworkTransport(gate, tokens_from_env())
        prober = Prober(transport, gate)
    only = {s.strip() for s in a.only.split(',')} if a.only else None
    report = run(a.root, prober, now=now, only=only, limit=a.limit, dry_run=a.dry_run, derive_only=a.derive_only)
    if a.lines:
        for line in report['lines']:
            print(json.dumps(line, sort_keys=True, ensure_ascii=False))
    for line in render(report, a.dry_run):
        print(line)
    if prober is not None:
        sent = sum(1 for _, what in prober.gate.log if what == 'sent')
        print('requests: %d sent through the gate, %d refused%s' % (
            sent, len(prober.gate.log) - sent, '; pacing kept: %.0f s' % clock.waited if clock else ''))
    if a.dry_run and report['proposals']:
        print(json.dumps(report['proposals'], indent=2, ensure_ascii=False))
    return 4 if report['soft_fails'] else 0


if __name__ == '__main__':
    sys.exit(main())
