"""The fetcher's politeness, enforced: per-host token buckets, robots.txt and the no-collect list (P5-S2-T01).

07 S10.1, "Enforcement, not discipline": the rate limit, robots.txt and the no-collect list are properties of
the HTTP client, not of the adapter, "because a rate limit that depends on every adapter author remembering it
will be violated by the eleventh adapter". This module is that client-side half. ingest/policy.yaml is its one
input; `Gate.admit(url)` is the question every live transport under ingest/ asks before each request, and it
answers by raising or by returning once the host's bucket allows the request:

  NoCollect          the host, or a parent of it, is on `no_collect` (06 S9.6: immediate and unconditional)
  Forbidden          the URL matches a `forbidden` pattern: drivendata.org/*/leaderboard_partial,
                     epoch.ai/inspect-viewer/, epoch.ai/frontiermath/tiers-1-4/benchmark-problems
  UnlistedHost       no entry under `hosts`
  BudgetExhausted    the host's `max_requests` for this run is spent (0: "link out only")
  RobotsDisallowed   the host's robots.txt, fetched once per run and cached, disallows the URL for our token

All five are PolicyRefusal. A refusal is never retried and never soft: it is the fetcher declining to act.

robots.txt is RFC 9309's, parsed here rather than by urllib.robotparser, which matches paths by prefix only and
so cannot read `Disallow: /*/leaderboard_partial` -- the very rule 07 S10.1 names. A 2xx body is parsed; a 4xx
(no robots.txt) allows everything; a 5xx or an unreachable host disallows everything for the run (RFC 9309
S2.3.1.3-4). The robots.txt request itself goes through the same no-collect, unlisted-host and bucket checks.

`refuse(url)` is the narrower check for code outside ingest/ that opens a URL (link-rot, archiving, the
copilot's source fetch): no-collect and forbidden only, since those tools visit whatever a Source cites.

One Gate per process is one run: `gate()` loads it on first use and every transport shares it, so the bucket
and the robots cache span all of a run's requests to a host.
"""
from __future__ import annotations

import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POLICY = os.path.join(ROOT, 'ingest', 'policy.yaml')
ROBOTS_TIMEOUT = 30


class PolicyRefusal(Exception):
    """The fetcher declines this request. Never retried."""

    def __init__(self, url: str, reason: str):
        super().__init__('%s: %s' % (url, reason))
        self.url, self.reason = url, reason


class NoCollect(PolicyRefusal):
    pass


class Forbidden(PolicyRefusal):
    pass


class UnlistedHost(PolicyRefusal):
    pass


class BudgetExhausted(PolicyRefusal):
    pass


class RobotsDisallowed(PolicyRefusal):
    pass


class PolicyError(ValueError):
    """ingest/policy.yaml is malformed."""


# ---- the policy file --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class HostPolicy:
    host: str
    rate: float                     # tokens a second
    burst: int = 1                  # bucket capacity
    max_requests: int | None = None  # per run; None is unbounded, 0 is never
    basis: str = ''


@dataclass(frozen=True)
class Rule:
    host: str
    path: str
    basis: str = ''

    def matches(self, host: str, path: str) -> bool:
        return under(host, self.host) and pattern(self.path).match(path) is not None


@dataclass(frozen=True)
class Policy:
    hosts: dict
    forbidden: tuple
    no_collect: tuple
    user_agent: str
    robots_token: str

    @classmethod
    def load(cls, path: str = POLICY) -> 'Policy':
        from schema.taxonomy import read_yaml
        return cls.from_dict(read_yaml(path), path)

    @classmethod
    def from_dict(cls, doc: dict, where: str = 'policy') -> 'Policy':
        hosts = {}
        for name, h in (doc.get('hosts') or {}).items():          # get-default: a policy may list none
            name = str(name).lower()
            rate, burst = float(h['rate']), int(h.get('burst', 1))  # get-default: strict pacing unless stated
            if rate <= 0 or burst < 1:
                raise PolicyError('%s: host %s needs rate > 0 and burst >= 1' % (where, name))
            if not h.get('basis'):
                raise PolicyError('%s: host %s states no basis (the section its numbers come from)' % (where, name))
            hosts[name] = HostPolicy(name, rate, burst, h.get('max_requests'), h['basis'])  # get-default: unbounded
        forbidden = tuple(Rule(str(r['host']).lower(), r['path'], r.get('basis', '')) for r in doc.get('forbidden') or [])  # get-default: a rule's basis is optional, none listed is valid
        no_collect = tuple(str(e['host'] if isinstance(e, dict) else e).lower() for e in doc.get('no_collect') or [])  # get-default: none yet
        for k in ('user_agent', 'robots_token'):
            if not doc.get(k):
                raise PolicyError('%s: %s is required' % (where, k))
        return cls(hosts, forbidden, no_collect, doc['user_agent'], doc['robots_token'])


def under(host: str, parent: str) -> bool:
    """`host` is `parent` or a subdomain of it."""
    return host == parent or host.endswith('.' + parent)


def pattern(p: str) -> re.Pattern:
    """An RFC 9309 path pattern as a regex anchored at the start: `*` any run, a trailing `$` the end."""
    end = p.endswith('$')
    body = ''.join('.*' if c == '*' else re.escape(c) for c in (p[:-1] if end else p))
    return re.compile(body + ('$' if end else ''), re.S)


def split(url: str) -> tuple[str, str, str]:
    """(scheme, host, path with its query) of an http(s) URL; anything else is refused."""
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ('http', 'https') or not u.hostname:
        raise PolicyRefusal(url, 'not an http(s) URL with a host')
    return u.scheme, u.hostname.lower(), (u.path or '/') + ('?' + u.query if u.query else '')


# ---- robots.txt (RFC 9309) --------------------------------------------------------------------------------------

@dataclass
class Robots:
    rules: list = field(default_factory=list)   # [(allow, pattern text)] of the group that applies to us
    everything: bool | None = None              # True: allow all (4xx); False: disallow all (5xx, unreachable)
    status: int | None = None

    def allowed(self, path: str) -> bool:
        if self.everything is not None:
            return self.everything
        best = None                                   # (length, allow): the longest match wins, allow on a tie
        for allow, pat in self.rules:
            if pat == '':
                continue                              # "Disallow:" with no value disallows nothing
            if pattern(pat).match(path):
                key = (len(pat), allow)
                if best is None or key > best:
                    best = key
        return True if best is None else best[1]


def parse_robots(text: str, token: str) -> Robots:
    """The rules of the group naming `token` (case-insensitive), else of the `*` group (RFC 9309 S2.2.1)."""
    groups, agents, rules, in_rules = [], [], [], False
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if ':' not in line:
            continue
        key, value = (s.strip() for s in line.split(':', 1))
        key = key.lower()
        if key == 'user-agent':
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            agents.append(value.lower())
        elif key in ('allow', 'disallow') and agents:
            in_rules = True
            rules.append((key == 'allow', value))
    if agents:
        groups.append((agents, rules))
    mine = [r for a, r in groups if token.lower() in a]
    star = [r for a, r in groups if '*' in a]
    chosen = mine or star
    return Robots(rules=[rule for g in chosen for rule in g])


def fetch_robots(url: str, user_agent: str, timeout: int = ROBOTS_TIMEOUT) -> tuple[int | None, str]:
    """(status or None, body) of one robots.txt GET. The gate calls this only after its own checks."""
    req = urllib.request.Request(url, headers={'User-Agent': user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(512 * 1024).decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, ''
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, ''


# ---- the gate ---------------------------------------------------------------------------------------------------

class Bucket:
    """A token bucket: `rate` tokens a second up to `burst`; take() sleeps until one is free."""

    def __init__(self, rate: float, burst: int, clock: Callable[[], float], sleep: Callable[[float], None]):
        self.rate, self.burst, self.clock, self.sleep = rate, burst, clock, sleep
        self.tokens, self.at = float(burst), None

    def take(self) -> float:
        now = self.clock()
        if self.at is not None:
            self.tokens = min(self.burst, self.tokens + (now - self.at) * self.rate)
        self.at = now
        waited = 0.0
        if self.tokens < 1:
            waited = (1 - self.tokens) / self.rate
            self.sleep(waited)
            self.at = now + waited
            self.tokens = 1.0
        self.tokens -= 1
        return waited


class Gate:
    def __init__(self, policy: Policy, robots: Callable[[str, str], tuple[int | None, str]] = fetch_robots,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.policy, self.robots_fetch, self.clock, self.sleep = policy, robots, clock, sleep
        self.buckets: dict[str, Bucket] = {}
        self.robots: dict[str, Robots] = {}
        self.counts: dict[str, int] = {}
        self.log: list[tuple[str, str]] = []           # (url, 'sent' | the refusal's class name), in order
        self._lock = threading.Lock()

    @classmethod
    def load(cls, path: str = POLICY, **kw) -> 'Gate':
        return cls(Policy.load(path), **kw)

    # the hard refusals, which hold for every caller -------------------------------------------------------------
    def refuse(self, url: str) -> None:
        _, host, path = split(url)
        for nc in self.policy.no_collect:
            if under(host, nc):
                self._refused(url, NoCollect(url, 'on the no-collect list (%s): refused outright (06 S9.6)' % nc))
        for rule in self.policy.forbidden:
            if rule.matches(host, path):
                self._refused(url, Forbidden(url, 'matches the forbidden %s%s (%s)' % (rule.host, rule.path, rule.basis)))

    def _refused(self, url, exc):
        self.log.append((url, type(exc).__name__))
        raise exc

    def _listed(self, url: str, host: str) -> HostPolicy:
        hp = self.policy.hosts.get(host)                 # get-default: an unlisted host is the refusal below
        if hp is None:
            self._refused(url, UnlistedHost(url, 'host %s has no entry in ingest/policy.yaml (07 S10.1)' % host))
        if hp.max_requests is not None and self.counts.get(host, 0) >= hp.max_requests:  # get-default: none sent yet
            self._refused(url, BudgetExhausted(url, 'host %s: %d of %d requests this run'
                                               % (host, self.counts.get(host, 0), hp.max_requests)))  # get-default: none sent yet counts zero
        return hp

    def _spend(self, host: str, hp: HostPolicy) -> None:
        bucket = self.buckets.setdefault(host, Bucket(hp.rate, hp.burst, self.clock, self.sleep))
        bucket.take()
        self.counts[host] = self.counts.get(host, 0) + 1   # get-default: the first request to the host

    def robots_for(self, scheme: str, host: str) -> Robots:
        if host not in self.robots:
            url = '%s://%s/robots.txt' % (scheme, host)
            self.refuse(url)
            self._spend(host, self._listed(url, host))
            status, body = self.robots_fetch(url, self.policy.user_agent)
            self.log.append((url, 'sent'))
            if status is not None and 200 <= status < 300:
                r = parse_robots(body, self.policy.robots_token)
            elif status is not None and 400 <= status < 500:
                r = Robots(everything=True)              # RFC 9309 S2.3.1.3: unavailable, crawl freely
            else:
                r = Robots(everything=False)             # S2.3.1.4: unreachable, assume complete disallow
            r.status = status
            self.robots[host] = r
        return self.robots[host]

    def admit(self, url: str) -> None:
        """Return when `url` may be requested now; raise a PolicyRefusal when it may not be at all."""
        with self._lock:
            scheme, host, path = split(url)
            self.refuse(url)
            hp = self._listed(url, host)
            robots = self.robots_for(scheme, host)
            if not robots.allowed(path):
                why = 'robots.txt unreachable (%s): nothing is fetched this run' % robots.status \
                    if robots.everything is False else 'disallowed by %s://%s/robots.txt for %s' % (
                        scheme, host, self.policy.robots_token)
                self._refused(url, RobotsDisallowed(url, why))
            hp = self._listed(url, host)                 # the robots.txt request may have spent the last token
            self._spend(host, hp)
            self.log.append((url, 'sent'))


class PolicedTransport:
    """Any transport with `get(url, headers)`, behind the gate: the wrapper for a transport defined elsewhere."""

    def __init__(self, inner, gate: Gate):
        self.inner, self.gate = inner, gate

    def get(self, url, headers):
        self.gate.admit(url)
        return self.inner.get(url, headers)               # get-default: a transport's GET, not a dict lookup


_GATE: Gate | None = None


def gate() -> Gate:
    """The run's gate: loaded from ingest/policy.yaml on first use, shared by every transport in the process."""
    global _GATE
    if _GATE is None:
        _GATE = Gate.load()
    return _GATE


def admit(url: str) -> None:
    gate().admit(url)


def refuse(url: str) -> None:
    """The hard refusals only, for code outside ingest/ that opens a URL: no-collect and forbidden."""
    gate().refuse(url)
