"""The verification rule for machine-ingested claims, and the structural transcript check (P3-S4-T01).

04 S7 owns the ladder and settles the Epoch assignment; 07 S2.3 replaces 04's substring test (`Logs` contains
"-public") with a structural one, and records the result rather than asserting it:

    transcript_evidence(log_url)       absent        no log URL
                                       private       not on an allowlisted public host, or not an .eval file
                                       public        allowlisted host, .eval path, and one HEAD answered 2xx
                                       unreachable   allowlisted host and .eval path, and the HEAD did not

    verification_rule(family, t)       epoch-run + public                    -> independent-reproduction
                                       epoch-run + private or absent         -> maintainer-verified
                                       epoch-run + unreachable               -> maintainer-verified, labelled
                                                                                needs-scrutiny, and a link-rot entry
                                       external-scrape                        -> self-reported

Those are the four rules. The structural check is a host allowlist on the parsed URL -- its scheme and netloc,
not a substring anywhere in it -- plus the path's extension, plus one HEAD: a URL that merely contains
"-public" on another host, or an allowlisted host serving anything but an .eval, is not evidence.

The HEAD is cached in the adapter's state file (ingest/state/epoch.json, key `transcripts`), keyed by URL. A
2xx is trusted for 30 days, then re-checked (07 S2.3). A failure is not cached: it is retried on the next run,
so one transient error cannot hold a public transcript at rung 2 for a month. An unreachable transcript is the
link-rot detector for the 828 (07 S2.3): link_rot() turns each one into an entry in tools/check_links.py's
outcome vocabulary -- `dead` for a 403/404/410, `suspect` for anything else -- with the event it raises.

Two gates (07 S8, "enforced by gates rather than by good intentions"), in check_machine_claim():

  - a machine never assigns a rung above independent-reproduction: taxonomy/verification.yaml's
    `machine_assignable` decides, not this module;
  - independent-reproduction requires a reachable artifact_url: no public transcript, no rung 3.

What the HEAD found on 2026-10-05, across all 828 structurally public transcripts in the snapshot: the 72 on
the staging bucket answered 200; the 756 on the production bucket answered 403 AccessDenied (755) or reset the
connection (1), to HEAD and to a ranged GET alike, and the bucket refuses listing. The same files are linked
from the `Log viewer` column on logs.epoch.ai, which sits behind an AWS WAF human-verification page (HTTP 405
to any script), so no machine can reach them there either. By the rule as 07 S2.3 states it -- "no transcript,
no rung 3" -- 72 rows are independent-reproduction today and 756 drop to maintainer-verified with
needs-scrutiny. Whether a transcript a person can open behind a browser check counts is a curator's decision,
not this module's; until one is made the rule stays as written.

Rank and review state are separate axes (07 S2.3): rung 3 here means "a third party re-ran it and published the
transcript", not "a human here has opened it", which `ingestion.review_state` records.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPOCH_LOG_HOSTS = frozenset({                       # 07 S2.2: the two public buckets, and only those
    'epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com',
    'epoch-benchmarks-staging-public.s3.us-east-2.amazonaws.com',
})
LOG_SUFFIX = '.eval'                                # an Inspect-AI log
CACHE_DAYS = 30
NEEDS_SCRUTINY = 'needs-scrutiny'
FAMILIES = ('epoch-run', 'external-scrape')
RULES = ('epoch-run-public', 'epoch-run-private-or-absent', 'epoch-run-unreachable', 'external')
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
Access = Literal['public', 'private', 'absent', 'unreachable']


@dataclass(frozen=True)
class Transcript:
    url: str | None
    access: Access
    detail: str | None = None       # the HEAD's answer, when one was asked: 'HTTP 200', 'HTTP 403', 'timeout'
    checked_at: str | None = None


@dataclass(frozen=True)
class Assessment:
    """What the rule gives one row: its rung, the artifact_url, the PR labels, and which of the four rules."""
    verification: str
    artifact_url: str | None
    labels: tuple[str, ...]
    rule: str
    transcript: Transcript | None = None


# ---- the HEAD ---------------------------------------------------------------------------------------------

def head(url: str, timeout: int = 30) -> tuple[int | None, str]:
    """(status or None, detail) for one HEAD; a network failure is (None, its reason), never an exception.
    A URL the fetcher's policy refuses (07 S10.1) is (None, the refusal), and is never requested."""
    from ingest.http import policy
    try:
        policy.admit(url)
    except policy.PolicyRefusal as e:
        return None, 'refused by ingest/policy.yaml: %s' % type(e).__name__
    req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, 'HTTP %d' % r.status
    except urllib.error.HTTPError as e:
        return e.code, 'HTTP %d' % e.code
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, type(getattr(e, 'reason', e)).__name__


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


@dataclass
class HeadCache:
    """One HEAD per URL, a 2xx remembered for CACHE_DAYS in `state['transcripts']` (the adapter saves the state)."""
    state: dict
    probe: Callable[[str], tuple[int | None, str]] = head
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    asked: list = field(default_factory=list)

    def check(self, url: str) -> tuple[bool, str, str]:
        """(reachable, detail, checked_at)."""
        cache = self.state.setdefault('transcripts', {})
        hit, now = cache.get(url), self.now()       # get-default: an unseen URL has no entry
        if hit and now - datetime.fromisoformat(hit['checked_at'].replace('Z', '+00:00')) < timedelta(days=CACHE_DAYS):
            return True, hit['detail'], hit['checked_at']
        self.asked.append(url)
        status, detail = self.probe(url)
        ok = status is not None and 200 <= status < 300
        if ok:
            cache[url] = {'checked_at': iso(now), 'detail': detail}
        else:
            cache.pop(url, None)                    # a failure is asked again next run, never trusted for 30 days
        return ok, detail, iso(now)


# ---- the check and the rule -------------------------------------------------------------------------------

def structurally_public(log_url: str) -> bool:
    """An https URL on an allowlisted host whose path is an .eval file -- parsed, not searched."""
    u = urlsplit(log_url)
    return u.scheme == 'https' and u.netloc in EPOCH_LOG_HOSTS and u.path.endswith(LOG_SUFFIX) and not u.query


def transcript_evidence(log_url: str | None, heads: HeadCache) -> Transcript:
    """07 S2.3. Host allowlist + extension + one (cached) HEAD."""
    url = (log_url or '').strip()
    if not url:
        return Transcript(None, 'absent')
    if not structurally_public(url):
        return Transcript(url, 'private')
    ok, detail, at = heads.check(url)
    return Transcript(url, 'public' if ok else 'unreachable', detail, at)


def verification_rule(family: str, t: Transcript) -> str:
    """04 S7 / 07 S2.3, encoded once, not copied into 6,598 records."""
    if family not in FAMILIES:
        raise ValueError('no verification rule for family %r (have: %s)' % (family, ', '.join(FAMILIES)))
    if family == 'epoch-run' and t.access == 'public':
        return 'independent-reproduction'
    if family == 'epoch-run':
        return 'maintainer-verified'           # private, blank, and any unreachable
    return 'self-reported'


def assess(family: str, log_url: str | None, heads: HeadCache) -> Assessment:
    """One row's rung, artifact_url and labels. An external row's log column is never read: none has one."""
    if family == 'external-scrape':
        return Assessment(verification_rule(family, Transcript(None, 'absent')), None, (), 'external')
    t = transcript_evidence(log_url, heads)
    rule = ('epoch-run-public' if t.access == 'public' else
            'epoch-run-unreachable' if t.access == 'unreachable' else 'epoch-run-private-or-absent')
    labels = (NEEDS_SCRUTINY,) if t.access == 'unreachable' else ()
    a = Assessment(verification_rule(family, t), t.url, labels, rule, t)
    check_machine_claim(a.verification, a.transcript)
    return a


# ---- the gates and the accounting --------------------------------------------------------------------------

def machine_assignable(root: str = ROOT) -> dict[str, int]:
    """Rung id -> rank, for the rungs taxonomy/verification.yaml lets a machine assign."""
    from schema.taxonomy import read_yaml
    rungs = read_yaml(os.path.join(root, 'taxonomy', 'verification.yaml'))['rungs']
    return {r['id']: r['rank'] for r in rungs if r['machine_assignable']}


def check_machine_claim(verification: str, transcript: Transcript | None, root: str = ROOT) -> None:
    """07 S8's two gates on an ingested claim's verification. Raises ValueError on either."""
    allowed = machine_assignable(root)
    if verification not in allowed:
        raise ValueError('%s is not machine-assignable (taxonomy/verification.yaml); an adapter may assign only %s'
                         % (verification, ', '.join(sorted(allowed, key=allowed.get))))
    if verification == 'independent-reproduction' and not (transcript and transcript.url and transcript.access == 'public'):
        raise ValueError('independent-reproduction needs a reachable artifact_url (07 S2.3); transcript is %s'
                         % (transcript.access if transcript else 'missing'))


def link_rot(assessments) -> list[dict]:
    """Each unreachable transcript as a link-rot entry, in tools/check_links.py's outcome vocabulary."""
    from tools.check_links import EVENTS
    out = []
    for a in assessments:
        t = a.transcript
        if t is None or t.access != 'unreachable':
            continue
        outcome = 'dead' if t.detail in ('HTTP 403', 'HTTP 404', 'HTTP 410') else 'suspect'
        out.append({'url': t.url, 'outcome': outcome, 'event': EVENTS[outcome], 'detail': t.detail,
                    'checked_at': t.checked_at, 'consequence': 'independent-reproduction -> maintainer-verified'})
    return sorted(out, key=lambda e: e['url'])


def tally(assessments, unmatched: int = 0) -> dict:
    """Every row accounted for by the four rules, and the unmatched count beside them (14, Phase 3 exit)."""
    rules = Counter(a.rule for a in assessments)
    rungs = Counter(a.verification for a in assessments)
    return {'rules': {r: rules[r] for r in RULES}, 'verification': dict(sorted(rungs.items())),
            'needs_scrutiny': sum(1 for a in assessments if NEEDS_SCRUTINY in a.labels),
            'unmatched': unmatched, 'rows': sum(rules.values()) + unmatched}
