#!/usr/bin/env python3
"""The three adoption instruments of the Phase-8 gate, as one script (P8-S1-T02; 13-execution-runners.md S0.2,
05 S6; docs/adoption/instruments.md).

    python scripts/adoption_measure.py                                  # the plan: every query, and no request
    python scripts/adoption_measure.py --live [--rulings FILE]          # run the instruments against the APIs
    python scripts/adoption_measure.py --replay TRANSCRIPT.json         # the same counts from recorded responses
    python scripts/adoption_measure.py --live --rulings FILE --write docs/adoption/<YYYY>-Q<N>.md   # P8-S1-T04
    python scripts/adoption_measure.py --validate docs/adoption/<YYYY>-Q<N>.md   # does the published block replay?

14-roadmap.md owns the gate's wording and 13 S0.2 its instruments: a second adapter, scheduled reruns and the public
execution pages are built only when, over the six months after public v1, (1) at least 3 external contributors
have landed data through the issue form, (2) at least 1 external publication cites the Zenodo DOI, and (3) at
least 5 unsolicited rerun or verification requests have arrived. docs/adoption/instruments.md is where each
instrument stands, and it corrects 13 S0.2 twice. This script follows it in both places:

  (1) The pull requests the intake bot opens are labelled source:issue-form and say "From issue #N" and "Closes
      #N" (tools/intake/open_pr.py); the contributor is the author of issue N. 13 S0.2, and the ledger step this
      task copies, counted commit trailers, but the bot's commits carry only the maintainers' identities (the
      maintainer's call of 2026-11-18, P2-S6-T04), so no trailer names a contributor. Distinct authors count
      once each, less bots, every account the collaborators endpoint lists on the day, every author GitHub marks
      OWNER, MEMBER or COLLABORATOR, and the maintainer and alt accounts the rulings name.
  (2) For every DOI in instruments.md's table, concept and versions: OpenAlex (the DOI resolved to a work, then
      `cites:`), DataCite (citationCount and the citing DOIs) and Semantic Scholar (citations). Crossref's
      `works?filter=reference.doi:` does not exist (HTTP 400 filter-not-available, 2026-09-29); DataCite replaces
      it. A citing work counts once (by DOI where it has one), never when it is one of our own DOIs, and only
      when its authors are known and none is a maintainer; a DataCite-only citation's authors come from an
      OpenAlex singleton lookup, which costs nothing. A 404 is `not-indexed`, never zero (instruments.md).
  (3) Issues labelled request:rerun, open and closed, pull requests left out. Unsolicited is a triage judgement,
      recorded on the issue: the rerun-request form's answer to "Does this request answer a call for requests?"
      (.github/ISSUE_TEMPLATE/rerun-request.yml, P8-S1-T03), which triage confirms or corrects when it applies
      the label. A ruling by issue number overrules the form, and is the only judgement an issue opened some
      other way can carry; a labelled issue with neither is not counted.

"If a condition cannot be measured, it counts as failed" (13 S0.2). So a verdict is MET or FAILED, never unknown,
and a failed request is a reason whenever it could change the verdict. A failure that could only have found more
(a page of a list, an issue lookup, an instrument, a request with no ruling) fails a condition still below its
threshold; one that could only have removed some (condition 1's collaborators list) fails it whatever the count.
The count beside a failure is what could be measured, marked partial: never a silent zero.

The rulings are the human half (P8-S1-T04: "a human has ruled on which contributors and which requests count"), a
YAML file the script reads and never writes. It names people, so it lives outside the repository:

    maintainers:            # conditions 1 and 2: every maintainer and alt account, by any identifier
      - github:<login>
      - name:<a name as publications print it>
      - orcid:<0000-0000-0000-0000>
      - openalex:<A...>
      - s2:<Semantic Scholar authorId>
    unsolicited: [12, 15]   # condition 3: the request:rerun issues triage ruled unsolicited, whatever the form says
    solicited: [13]         # ... and those it ruled were not

Without it, condition 2 cannot rule out self-citation and condition 3 has only the forms' answers: both fail as
unmeasurable whenever there is something left to judge.

The network. Nothing is requested without --live. GitHub is read through its REST API, unauthenticated or with
GH_TOKEN from the environment, never through `gh`, which reads its stored login. The collaborators list needs a
token with push access; without one condition 1 fails as unmeasurable, which is the rule working. OPENALEX_API_KEY
and SEMANTIC_SCHOLAR_API_KEY come from the environment too (instruments.md's secrets). Each credential is added
inside the transport and nowhere else: recorded URLs, the transcript, messages and output say only whether it is
set. ingest/policy.yaml's no-collect and forbidden lists hold (07 S10.1); requests to a host are spaced at
policy.yaml's rates (DataCite, which it does not list, half a second apart), and a 429 or 5xx is retried as
07 S4.2 allows (ingest/http/backoff.py).

The raw output (13 S0.2: the file contains "the raw query output and the date it was run") is the transcript:
every request in order, its status and its response body. It is also what --replay reads and what the tests'
fixtures are. By default it names no one: GitHub logins, author names, ORCIDs and author ids become aliases
(`github-1`, `name-1`, `orcid-1`, ...), consistent across one run so the counts replay from it; e-mail addresses
and @-mentions are removed; issue bodies are dropped, all but the rerun-request form's answer, which condition 3
reads and which is kept as the bare word the form put before its colon. The report gives counts, issue
numbers and citing DOIs, never people. --identify keeps the identities, for the person confirming the exclusions,
and is refused with --write.

Publishing (P8-S1-T04, T05). --write puts the run between two marker comments in a Markdown file and leaves the
rest alone: that is where a person confirms the rulings and records the corroborating signals (13 S0.3).
--validate replays the block's own transcript, regenerates the block, compares the two byte for byte, and
requires both confirmation lines to be filled in.

Exit codes: 0 when the instruments ran (the gate reports; it blocks nothing) and, with --validate, the file
replays and is confirmed; 1 when --validate finds a difference or an unconfirmed ruling; 2 on input that does not
parse.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

REPO = 'benchmarkg/benchmarks'
INSTRUMENTS = 'docs/adoption/instruments.md'
GITHUB = 'https://api.github.com'
OPENALEX = 'https://api.openalex.org'
DATACITE = 'https://api.datacite.org'
S2 = 'https://api.semanticscholar.org/graph/v1'
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
FORM_LABEL, RERUN_LABEL = 'source:issue-form', 'request:rerun'
PER_PAGE, MAX_PAGES = 100, 10                   # instruments.md's `--limit 1000`
OA_PER_PAGE, OA_MAX_PAGES = 200, 25
S2_LIMIT, S2_MAX_PAGES = 1000, 10
OA_WORK = 'id,doi,display_name,cited_by_count'
OA_CITING = 'id,doi,display_name,publication_year,authorships'
S2_FIELDS = 'title,authors,externalIds'         # instruments.md's query
SPACING = {'api.github.com': 1.0, 'api.openalex.org': 0.2, 'api.semanticscholar.org': 1.05, 'api.datacite.org': 0.5}
CREDENTIALS = ('GH_TOKEN', 'OPENALEX_API_KEY', 'SEMANTIC_SCHOLAR_API_KEY')
COMMIT_RIGHTS = ('OWNER', 'MEMBER', 'COLLABORATOR')      # GitHub's author_association for push access
KINDS = ('github', 'name', 'orcid', 'openalex', 's2')
FORMAT = 1                                      # the transcript's shape

MET, FAILED = 'MET', 'FAILED'
CONDITIONS = {1: (3, 'external contributors landed data through the issue form'),
              2: (1, 'external publications cite the Zenodo DOI'),
              3: (5, 'unsolicited rerun or verification requests')}


def _qs(params: dict) -> str:
    return urllib.parse.urlencode(params, safe=':,*')


def _path(doi: str) -> str:
    return urllib.parse.quote(doi, safe='/:')


def issues_url(repo: str, label: str, state: str, page: int) -> str:
    return '%s/repos/%s/issues?%s' % (GITHUB, repo, _qs({'labels': label, 'state': state, 'per_page': PER_PAGE,
                                                         'page': page}))


def issue_url(repo: str, number: int) -> str:
    return '%s/repos/%s/issues/%d' % (GITHUB, repo, number)


def collaborators_url(repo: str, page: int) -> str:
    return '%s/repos/%s/collaborators?%s' % (GITHUB, repo, _qs({'per_page': PER_PAGE, 'page': page}))


def openalex_work_url(doi: str, select: str = OA_WORK) -> str:
    return '%s/works/doi:%s?%s' % (OPENALEX, _path(doi), _qs({'select': select}))


def openalex_cites_url(work: str, cursor: str) -> str:
    return '%s/works?%s' % (OPENALEX, _qs({'filter': 'cites:%s' % work, 'per_page': OA_PER_PAGE,
                                           'select': OA_CITING, 'cursor': cursor}))


def datacite_url(doi: str) -> str:
    return '%s/dois/%s' % (DATACITE, _path(doi))


def s2_citations_url(doi: str, offset: int) -> str:
    return '%s/paper/DOI:%s/citations?%s' % (S2, _path(doi), _qs({'fields': S2_FIELDS, 'offset': offset,
                                                                   'limit': S2_LIMIT}))


# ---- the transcript and its two sources -------------------------------------------------------------------------

@dataclass
class Exchange:
    """One request and what came back: the unit of the transcript."""
    url: str
    status: int | None
    body: object = None             # the parsed JSON response, when there is one
    error: str | None = None        # why there is no usable answer, when there is not

    @property
    def ok(self) -> bool:
        return self.status == 200 and self.error is None and self.body is not None

    def why(self) -> str:
        return self.error or 'HTTP %s' % self.status

    def as_dict(self) -> dict:
        d = {'url': self.url, 'status': self.status}
        if self.body is not None:
            d['body'] = self.body
        if self.error is not None:
            d['error'] = self.error
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'Exchange':
        if not isinstance(d, dict) or not isinstance(d.get('url'), str) or 'status' not in d:
            raise ValueError('a transcript exchange needs a url and a status')
        return cls(d['url'], d['status'], d.get('body'), d.get('error'))


def _json(raw: bytes):
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


class Live:
    """GET over urllib, each URL once, every exchange recorded. The credentials are added here and nowhere else."""

    def __init__(self, env=None, opener=None, clock=None, sleep=None, timeout: int = 60):
        env = os.environ if env is None else env
        self._secrets = {k: env.get(k) or None for k in CREDENTIALS}
        self.opener, self.timeout = opener, timeout
        self.clock, self.sleep = clock or time.monotonic, sleep or time.sleep
        self.exchanges: list[Exchange] = []
        self._seen: dict[str, Exchange] = {}
        self._last: dict[str, float] = {}

    def credentials(self) -> dict:
        """Which credentials are set: never their values."""
        return {k: v is not None for k, v in self._secrets.items()}

    def __call__(self, url: str) -> Exchange:
        if url not in self._seen:
            self._seen[url] = ex = self._fetch(url)
            self.exchanges.append(ex)
        return self._seen[url]

    def _scrub(self, text: str) -> str:
        for value in self._secrets.values():
            if value:
                text = text.replace(value, '[credential]')
        return text

    def _request(self, url: str):
        host = urllib.parse.urlsplit(url).hostname or ''
        headers, full = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}, url
        if host == 'api.github.com':
            headers.update({'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
            if self._secrets['GH_TOKEN']:
                headers['Authorization'] = 'Bearer %s' % self._secrets['GH_TOKEN']
        elif host == 'api.openalex.org' and self._secrets['OPENALEX_API_KEY']:
            full += ('&' if '?' in url else '?') + urllib.parse.urlencode({'api_key': self._secrets['OPENALEX_API_KEY']})
        elif host == 'api.semanticscholar.org' and self._secrets['SEMANTIC_SCHOLAR_API_KEY']:
            headers['x-api-key'] = self._secrets['SEMANTIC_SCHOLAR_API_KEY']
        return host, urllib.request.Request(full, headers=headers)

    def _fetch(self, url: str) -> Exchange:
        from ingest.http import policy
        from ingest.http.backoff import Response, SoftFail, retry
        try:
            policy.refuse(url)                           # 07 S10.1: no-collect and forbidden hold here too
        except policy.PolicyRefusal as e:
            return Exchange(url, None, error='refused by ingest/policy.yaml: %s' % e.reason)
        host, req = self._request(url)
        opener = self.opener or urllib.request.urlopen

        def once():
            last = self._last.get(host)
            if last is not None:
                wait = SPACING.get(host, 1.0) - (self.clock() - last)   # get-default: an unrated host gets 1 s
                if wait > 0:
                    self.sleep(wait)
            try:
                with opener(req, timeout=self.timeout) as r:
                    return Response(r.status, r.headers, r.read())
            except urllib.error.HTTPError as e:
                try:
                    raw = e.read()
                except Exception:                        # an error with no readable body is still its status
                    raw = b''
                return Response(e.code, e.headers or {}, raw)
            finally:
                self._last[host] = self.clock()

        try:
            resp = retry(once, clock=self.clock, sleep=self.sleep)
        except SoftFail as e:
            return Exchange(url, e.response.status, _json(e.response.body), self._scrub('retries spent: %s' % e.reason))
        except (urllib.error.URLError, OSError, ValueError) as e:
            return Exchange(url, None, error=self._scrub('unreachable: %s' % (getattr(e, 'reason', None) or e)))
        body = _json(resp.body)
        if resp.status == 200 and body is None:
            return Exchange(url, 200, error='HTTP 200, but the body is not JSON')
        return Exchange(url, resp.status, body)


class Replay:
    """Recorded exchanges, answered by URL. A URL the recording lacks is a failed request, as an unreachable host
    would be: a replay can find less than the run did, never more."""

    def __init__(self, exchanges):
        if not isinstance(exchanges, list):
            raise ValueError('the transcript has no list of exchanges')
        self._recorded: dict[str, Exchange] = {}
        for d in exchanges:
            ex = Exchange.from_dict(d)
            self._recorded.setdefault(ex.url, ex)
        self.exchanges: list[Exchange] = []
        self._seen: dict[str, Exchange] = {}

    def __call__(self, url: str) -> Exchange:
        if url not in self._seen:
            self._seen[url] = ex = self._recorded.get(url) or Exchange(url, None, error='not in the recording')
            self.exchanges.append(ex)
        return self._seen[url]


# ---- identities and the rulings ---------------------------------------------------------------------------------

def norm(kind: str, value) -> str | None:
    """One identifier, compared as: case-folded; ids and ORCIDs by their last path segment; names by their words."""
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    s = str(value).strip()
    if kind in ('openalex', 'orcid'):
        s = s.rstrip('/').rsplit('/', 1)[-1]
    if kind == 'name':
        s = ' '.join(re.sub(r'[^\w\s-]', ' ', s).split())
    return s.casefold() or None


def _ids(*pairs) -> frozenset:
    return frozenset((k, v) for k, v in ((k, norm(k, x)) for k, x in pairs) if v)


@dataclass(frozen=True)
class Rulings:
    maintainers: frozenset = frozenset()        # {(kind, normalised value)}
    unsolicited: frozenset = frozenset()        # issue numbers
    solicited: frozenset = frozenset()
    supplied: tuple = ()                        # ((kind, how many identities of that kind were given), ...)

    @property
    def checks_self_citation(self) -> bool:
        """Self-citation can be ruled out only against a maintainer identity a publication can carry."""
        return any(n for kind, n in self.supplied if kind != 'github')

    @classmethod
    def parse(cls, doc) -> 'Rulings':
        if doc is None:
            return cls()
        if not isinstance(doc, dict):
            raise ValueError('the rulings are not a mapping')
        unknown = sorted(set(doc) - {'maintainers', 'unsolicited', 'solicited', 'supplied'})
        if unknown:
            raise ValueError('the rulings have unknown key(s): %s' % ', '.join(unknown))
        entries = doc.get('maintainers') or []
        if not isinstance(entries, list):
            raise ValueError('rulings: maintainers is not a list')
        ids = set()
        for i, entry in enumerate(entries, 1):
            kind, sep, value = str(entry).partition(':')
            kind = kind.strip().casefold()
            if not sep or kind not in KINDS or norm(kind, value) is None:
                # the entry's value is a person's identifier: the message names its position, never the value
                raise ValueError('rulings: maintainer entry %d is not <kind>:<value>, kind one of %s'
                                 % (i, ', '.join(KINDS)))
            ids.add((kind, norm(kind, value)))

        def numbers(key):
            v = doc.get(key) or []
            if not isinstance(v, list) or not all(isinstance(n, int) and not isinstance(n, bool) for n in v):
                raise ValueError('rulings: %s is not a list of issue numbers' % key)
            return frozenset(v)

        unsolicited, solicited = numbers('unsolicited'), numbers('solicited')
        both = sorted(unsolicited & solicited)
        if both:
            raise ValueError('rulings: issue(s) ruled both unsolicited and solicited: %s' % _refs(both))
        supplied = doc.get('supplied')
        if supplied is None:
            supplied = Counter(k for k, _ in ids)
        if not isinstance(supplied, dict) or not all(k in KINDS and isinstance(n, int) for k, n in supplied.items()):
            raise ValueError('rulings: supplied is not a mapping of identifier kinds to counts')
        return cls(frozenset(ids), unsolicited, solicited, tuple(sorted(supplied.items())))

    def as_dict(self, aliases: dict | None = None) -> dict:
        """For the transcript. With `aliases`, only the identities the run saw, each as its alias: an identity it
        never saw matched nothing, and writing it down would name someone for no reason."""
        if aliases is None:
            maintainers = sorted('%s:%s' % kv for kv in self.maintainers)
        else:
            maintainers = sorted('%s:%s' % (k, aliases[(k, v)]) for k, v in self.maintainers if (k, v) in aliases)
        return {'maintainers': maintainers, 'supplied': dict(self.supplied),
                'unsolicited': sorted(self.unsolicited), 'solicited': sorted(self.solicited)}


def read_rulings(path: str) -> Rulings:
    from schema.taxonomy import read_yaml
    try:
        doc = read_yaml(path)
    except OSError:
        raise
    except Exception as e:                      # ruamel's own errors: the file is not YAML
        raise ValueError('%s does not parse as YAML: %s' % (path, type(e).__name__)) from e
    return Rulings.parse(doc)


# ---- the results ------------------------------------------------------------------------------------------------

@dataclass
class Result:
    condition: int
    count: int
    detail: dict
    raising: list = field(default_factory=list)     # failures that could only have found more
    lowering: list = field(default_factory=list)    # failures that could only have removed some
    counted: list = field(default_factory=list)     # what was counted, where that names no one
    people: dict = field(default_factory=dict)      # --identify only

    @property
    def threshold(self) -> int:
        return CONDITIONS[self.condition][0]

    @property
    def title(self) -> str:
        return CONDITIONS[self.condition][1]

    @property
    def complete(self) -> bool:
        return not self.raising and not self.lowering

    @property
    def reasons(self) -> list[str]:
        """Why the condition is not met; empty when it is. Never 'unknown': an unmeasurable reason fails it."""
        out = []
        if self.count < self.threshold:
            out.append('below the threshold%s: %d < %d' % ('' if self.complete else ' on what could be measured',
                                                         self.count, self.threshold))
            out += ['unmeasurable: %s' % r for r in self.raising]
        out += ['unmeasurable: %s' % r for r in self.lowering]
        return out

    @property
    def verdict(self) -> str:
        return FAILED if self.reasons else MET

    def as_dict(self, identify: bool = False) -> dict:
        d = {'condition': self.condition, 'title': self.title, 'threshold': self.threshold, 'count': self.count,
             'complete': self.complete, 'verdict': self.verdict, 'reasons': self.reasons, 'detail': self.detail,
             'counted': self.counted}
        if identify:
            d['people'] = self.people
        return d


def _refs(numbers) -> str:
    return ', '.join('#%d' % n for n in sorted(numbers))


def _failure(ex: Exchange, shape: str = 'an unexpected response shape') -> str:
    why = ex.why() if not ex.ok else shape
    if ex.status in (401, 403) and '/collaborators' in ex.url:
        why += ' (the collaborators list needs GH_TOKEN with push access)'
    return 'GET %s: %s' % (ex.url, why)


def github_list(get, url_for) -> tuple[list, list[str]]:
    """Every item of a paginated GitHub list, and the failures that cut it short."""
    items = []
    for page in range(1, MAX_PAGES + 1):
        ex = get(url_for(page))
        if not ex.ok or not isinstance(ex.body, list):
            return items, [_failure(ex, 'not a list')]
        items += ex.body
        if len(ex.body) < PER_PAGE:
            return items, []
    return items, ['GET %s: stopped after %d pages; there may be more' % (url_for(MAX_PAGES), MAX_PAGES)]


# ---- condition (1): contributors through the issue form ---------------------------------------------------------

LINK = re.compile(r'(?<![\w/#])(?:(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?|from\s+issue)\s+#(\d+)\b', re.I)


def linked_issues(body) -> list[int]:
    """The issues a pull request body closes or comes from: `#N` in this repository, never `owner/repo#N`."""
    return sorted({int(n) for n in LINK.findall(body)}) if isinstance(body, str) else []


def condition_1(get, repo: str, rulings: Rulings) -> Result:
    items, raising = github_list(get, lambda p: issues_url(repo, FORM_LABEL, 'closed', p))
    merged, unlinked, numbers = [], [], set()
    for it in items:
        pr = it.get('pull_request') if isinstance(it, dict) else None
        if not isinstance(pr, dict) or not pr.get('merged_at'):
            continue                            # an issue carrying the label, or a pull request closed unmerged
        merged.append(it.get('number'))
        links = linked_issues(it.get('body'))
        numbers.update(links)
        if not links:
            unlinked.append(it.get('number'))
    if unlinked:
        raising.append('%d merged pull request(s) link no issue, so their contributors are unknown: %s'
                       % (len(unlinked), ', '.join('#%s' % n for n in unlinked)))
    authors, linked_prs = {}, []
    for n in sorted(numbers):
        ex = get(issue_url(repo, n))
        user = ex.body.get('user') if ex.ok and isinstance(ex.body, dict) else None
        if not isinstance(user, dict) or not isinstance(user.get('login'), str):
            raising.append(_failure(ex, 'no user.login'))
            continue
        if 'pull_request' in ex.body:
            linked_prs.append(n)                # it links a pull request, not an issue a contributor opened
            continue
        login = user['login']
        a = authors.setdefault(norm('github', login), {'login': login, 'bot': False, 'rights': False})
        a['bot'] = a['bot'] or user.get('type') == 'Bot' or login.endswith('[bot]')
        a['rights'] = a['rights'] or ex.body.get('author_association') in COMMIT_RIGHTS
    listed, failed = github_list(get, lambda p: collaborators_url(repo, p))
    lowering = list(failed)                     # a collaborator the list could not show would have been excluded
    collaborators = set()
    for u in listed:
        if isinstance(u, dict) and isinstance(u.get('login'), str):
            collaborators.add(norm('github', u['login']))
        else:
            lowering.append('the collaborators list has an entry with no login')
    excluded, external, people = Counter(), [], {'counted': [], 'excluded': {}}
    for key in sorted(authors):
        a = authors[key]
        why = ('a bot' if a['bot'] else
               'commit rights' if key in collaborators or a['rights'] else
               'a maintainer or alt account' if ('github', key) in rulings.maintainers else None)
        if why:
            excluded[why] += 1
            people['excluded'][a['login']] = why
        else:
            external.append(key)
            people['counted'].append(a['login'])
    detail = {'merged_pull_requests': len(merged), 'linked_issues': len(numbers), 'linked_pull_requests': len(linked_prs),
              'authors': len(authors), 'collaborators': len(collaborators), 'excluded': dict(sorted(excluded.items())),
              'external': len(external)}
    return Result(1, len(external), detail, raising, lowering, people=people)


# ---- condition (2): publications citing the DOI -----------------------------------------------------------------

def _doi(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:)', '', value.strip(), flags=re.I).casefold()


def _short(value) -> str | None:
    return value.rstrip('/').rsplit('/', 1)[-1] if isinstance(value, str) and value.strip() else None


def openalex_authors(work: dict) -> list[frozenset]:
    out = []
    for a in work.get('authorships') or []:
        person = a.get('author') if isinstance(a, dict) else None
        person = person if isinstance(person, dict) else {}
        out.append(_ids(('openalex', person.get('id')), ('orcid', person.get('orcid')),
                        ('name', person.get('display_name')), ('name', a.get('raw_author_name') if isinstance(a, dict) else None)))
    return [ids for ids in out if ids]


def s2_authors(paper: dict) -> list[frozenset]:
    out = [_ids(('s2', a.get('authorId')), ('name', a.get('name')))
           for a in paper.get('authors') or [] if isinstance(a, dict)]
    return [ids for ids in out if ids]


class Citing:
    """The citing works the instruments report, merged by DOI, without our own DOIs."""

    def __init__(self, ours):
        self.ours = {_doi(d) for d in ours}
        self.works: dict[str, dict] = {}

    def add(self, doi, other_id, authors, instrument):
        doi = _doi(doi)
        key = 'doi:%s' % doi if doi else other_id
        if not key or doi in self.ours:
            return                                  # nothing to key it by, or one of our records citing another
        w = self.works.setdefault(key, {'doi': doi, 'instruments': set(), 'authors': []})
        w['instruments'].add(instrument)
        w['authors'] += authors


def _reading(doi, instrument, status, count=None, why=None) -> dict:
    r = {'doi': doi, 'instrument': instrument, 'status': status, 'count': count}
    if why:
        r['why'] = why
    return r


def openalex_reading(get, doi: str, citing: Citing) -> dict:
    ex = get(openalex_work_url(doi))
    if ex.status == 404:
        return _reading(doi, 'OpenAlex', 'not-indexed')
    work = _short(ex.body.get('id')) if ex.ok and isinstance(ex.body, dict) else None
    if not work:
        return _reading(doi, 'OpenAlex', 'failed', why=_failure(ex, 'no work id'))
    cursor, count = '*', None
    for _ in range(OA_MAX_PAGES):
        ex = get(openalex_cites_url(work, cursor))
        body = ex.body if ex.ok and isinstance(ex.body, dict) else {}
        meta, results = body.get('meta'), body.get('results')
        if not isinstance(meta, dict) or not isinstance(results, list) or not isinstance(meta.get('count'), int):
            return _reading(doi, 'OpenAlex', 'failed', count, _failure(ex))
        count = meta['count']
        for w in results:
            if isinstance(w, dict):
                citing.add(w.get('doi'), 'openalex:%s' % _short(w.get('id')) if _short(w.get('id')) else None,
                           openalex_authors(w), 'OpenAlex')
        cursor = meta.get('next_cursor')
        if not cursor or not results:
            return _reading(doi, 'OpenAlex', 'ok', count)
    return _reading(doi, 'OpenAlex', 'failed', count, 'stopped after %d pages; there may be more' % OA_MAX_PAGES)


def datacite_reading(get, doi: str, citing: Citing) -> dict:
    ex = get(datacite_url(doi))
    if ex.status == 404:
        return _reading(doi, 'DataCite', 'not-indexed')
    try:
        data = ex.body['data']
        count, listed = data['attributes']['citationCount'], data['relationships']['citations']['data']
        if not ex.ok or not isinstance(count, int) or not isinstance(listed, list):
            raise TypeError
    except (KeyError, TypeError, IndexError):
        return _reading(doi, 'DataCite', 'failed', why=_failure(ex))
    dois = [c['id'] for c in listed if isinstance(c, dict) and isinstance(c.get('id'), str)]
    for d in dois:
        citing.add(d, None, [], 'DataCite')
    if count > len(dois):                       # counted, but not listed: citing works nobody can check
        return _reading(doi, 'DataCite', 'failed', count,
                        'counts %d citation(s) but lists %d citing DOI(s)' % (count, len(dois)))
    return _reading(doi, 'DataCite', 'ok', count)


def s2_reading(get, doi: str, citing: Citing) -> dict:
    offset, count = 0, 0
    for _ in range(S2_MAX_PAGES):
        ex = get(s2_citations_url(doi, offset))
        if ex.status == 404 and offset == 0:
            return _reading(doi, 'Semantic Scholar', 'not-indexed')
        data = ex.body.get('data') if ex.ok and isinstance(ex.body, dict) else None
        if not isinstance(data, list):
            return _reading(doi, 'Semantic Scholar', 'failed', count or None, _failure(ex))
        for item in data:
            paper = item.get('citingPaper') if isinstance(item, dict) else None
            if not isinstance(paper, dict):
                continue
            ext = paper.get('externalIds') if isinstance(paper.get('externalIds'), dict) else {}
            pid = paper.get('paperId')
            citing.add(ext.get('DOI'), 's2:%s' % pid if pid else None, s2_authors(paper), 'Semantic Scholar')
            count += 1
        nxt = ex.body.get('next')
        if not isinstance(nxt, int) or not data:
            return _reading(doi, 'Semantic Scholar', 'ok', count)
        offset = nxt
    return _reading(doi, 'Semantic Scholar', 'failed', count, 'stopped after %d pages; there may be more' % S2_MAX_PAGES)


def condition_2(get, dois: list[str], rulings: Rulings) -> Result:
    citing, readings = Citing(dois), []
    for doi in dois:
        readings += [openalex_reading(get, doi, citing), datacite_reading(get, doi, citing),
                     s2_reading(get, doi, citing)]
    raising = ['%s for %s: %s' % (r['instrument'], r['doi'], r['why']) for r in readings if r['status'] == 'failed']
    if not any(r['status'] == 'ok' for r in readings):
        raising.append('no instrument returned a reading for any DOI')
    for key in sorted(citing.works):            # a DataCite-only citation: its authors from OpenAlex, for free
        w = citing.works[key]
        if not w['authors'] and w['doi']:
            ex = get(openalex_work_url(w['doi'], OA_CITING))
            if ex.ok and isinstance(ex.body, dict):
                w['authors'] += openalex_authors(ex.body)
    kinds, counted, unknown, unchecked = Counter(), [], [], []
    for key in sorted(citing.works):
        authors = citing.works[key]['authors']
        if not authors:
            kinds['authors unknown'] += 1
            unknown.append(key)
        elif any(ids & rulings.maintainers for ids in authors):
            kinds['self-citation'] += 1
        elif not rulings.checks_self_citation:
            kinds['not checked for self-citation'] += 1
            unchecked.append(key)
        else:
            kinds['external'] += 1
            counted.append(key)
    if unknown:
        raising.append('%d citing work(s) whose authors no instrument reports, so self-citation cannot be ruled out: '
                       '%s' % (len(unknown), ', '.join(unknown)))
    if unchecked:
        raising.append('%d citing work(s) not checked for self-citation: the rulings name no maintainer by name, '
                       'ORCID, OpenAlex or Semantic Scholar id' % len(unchecked))
    detail = {'citing_works': len(citing.works), 'by_kind': dict(sorted(kinds.items())), 'readings': readings}
    return Result(2, len(counted), detail, raising, [], counted)


# ---- condition (3): unsolicited rerun requests ------------------------------------------------------------------

RERUN_FORM = '.github/ISSUE_TEMPLATE/rerun-request.yml'
UNSOLICITED_FIELD = 'unsolicited'                # the dropdown's id in RERUN_FORM
UNSOLICITED_HEADING = 'Does this request answer a call for requests?'     # its label, the body's `### ` heading
ANSWERS = {'unsolicited': True, 'solicited': False}     # an option's word before its colon; "Not sure" has none


def form_answer(body) -> bool | None:
    """The rerun-request form's judgement in an issue body: True (unsolicited), False (solicited), or None when the
    body has no such heading, the answer is blank (`_No response_`) or "Not sure", or it is not an option's text. A
    submitted form is `### <label>`, a blank line, then the answer (tools/intake/parse_form.py); the first wins."""
    if not isinstance(body, str):
        return None
    m = re.search(r'^###[ \t]+%s[ \t]*\n(.*?)(?=^###[ \t]|\Z)' % re.escape(UNSOLICITED_HEADING),
                  body.replace('\r\n', '\n'), re.M | re.S)
    if m is None:
        return None
    word, colon, _ = m.group(1).strip().partition(':')
    return ANSWERS.get(word.strip().casefold()) if colon else None


def condition_3(get, repo: str, rulings: Rulings) -> Result:
    items, raising = github_list(get, lambda p: issues_url(repo, RERUN_LABEL, 'all', p))
    answers, shapeless = {}, 0                  # issue number -> the form's answer
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get('number'), int):
            shapeless += 1
        elif 'pull_request' not in it:
            answers[it['number']] = form_answer(it.get('body'))
    if shapeless:
        raising.append('%d listed item(s) with no issue number' % shapeless)
    judged, by_form, overruled = {}, 0, []
    for n, answer in answers.items():
        ruled = True if n in rulings.unsolicited else False if n in rulings.solicited else None
        if ruled is None:
            judged[n] = answer
            by_form += answer is not None
        else:                                   # a person's ruling overrules what the form says
            judged[n] = ruled
            if answer is not None and answer != ruled:
                overruled.append(n)
    counted = sorted(n for n, v in judged.items() if v is True)
    solicited = sorted(n for n, v in judged.items() if v is False)
    unjudged = sorted(n for n, v in judged.items() if v is None)
    if unjudged:
        raising.append('%d labelled request(s) carry no judgement on whether they were unsolicited, on the form or '
                       'in the rulings: %s' % (len(unjudged), _refs(unjudged)))
    detail = {'labelled': len(answers), 'unsolicited': len(counted), 'solicited': len(solicited),
              'unjudged': len(unjudged), 'by_form': by_form, 'overruled': sorted(overruled),
              'ruled_but_not_labelled': len((rulings.unsolicited | rulings.solicited) - set(answers))}
    return Result(3, len(counted), detail, raising, [], ['#%d' % n for n in counted])


# ---- one measurement --------------------------------------------------------------------------------------------

@dataclass
class Measurement:
    run_on: str
    repo: str
    dois: list
    rulings: Rulings
    results: list
    exchanges: list
    credentials: dict | None = None
    redacted: bool = False

    @property
    def verdict(self) -> str:
        return MET if all(r.verdict == MET for r in self.results) else FAILED


def measure(get, repo: str, dois: list[str], rulings: Rulings, run_on: str, credentials: dict | None = None,
            redacted: bool = False) -> Measurement:
    if not dois:
        raise ValueError('no DOI to measure condition 2 against')
    results = [condition_1(get, repo, rulings), condition_2(get, list(dois), rulings), condition_3(get, repo, rulings)]
    return Measurement(run_on, repo, list(dois), rulings, results, list(get.exchanges), credentials, redacted)


def from_transcript(doc, rulings: Rulings | None = None) -> Measurement:
    """Run the instruments over a transcript's own exchanges. Its recorded rulings hold unless `rulings` is given."""
    if not isinstance(doc, dict) or doc.get('format') != FORMAT:
        raise ValueError('not a format-%d adoption transcript' % FORMAT)
    for key in ('run_on', 'repo', 'dois', 'exchanges'):
        if key not in doc:
            raise ValueError('the transcript has no %s' % key)
    return measure(Replay(doc['exchanges']), doc['repo'], doc['dois'],
                   rulings if rulings is not None else Rulings.parse(doc.get('rulings')),
                   doc['run_on'], doc.get('credentials'), bool(doc.get('redacted')))


def dois_from(root: str) -> list[str]:
    """The DOIs in instruments.md's table, concept first: the one place a new version's DOI is added."""
    with open(os.path.join(root, *INSTRUMENTS.split('/')), encoding='utf-8') as fh:
        text = fh.read()
    m = re.search(r'^## The DOIs\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if m is None:
        raise ValueError('%s has no "## The DOIs" section' % INSTRUMENTS)
    dois = []
    for line in m.group(1).splitlines():
        if line.startswith('|'):
            dois += [d for d in re.findall(r'`(10\.\d{4,9}/[^`\s]+)`', line) if d not in dois]
    if not dois:
        raise ValueError('%s lists no DOI' % INSTRUMENTS)
    return dois


# ---- the raw output, naming no one ------------------------------------------------------------------------------

EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
MENTION = re.compile(r'(?<![\w@])@(?!(?:%s)-\d+\b)[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?' % '|'.join(KINDS))
DROPPED = '[dropped: no instrument reads it]'
FREE_TEXT = ('body', 'title', 'display_name', 'message', 'raw_affiliation_strings', 'descriptions', 'description')
NOT_PEOPLE = ('Bot', 'Organization')            # GitHub account types that name no person


def kept_body(body) -> str:
    """An issue's body as the raw output keeps it: dropped, all but the rerun-request form's answer, which condition
    3 reads, kept as the bare word the form puts before its colon and nothing the requester could have typed."""
    answer = form_answer(body)
    if answer is None:
        return DROPPED
    return '[dropped, all but the answer condition 3 reads]\n\n### %s\n\n%s:' % (
        UNSOLICITED_HEADING, 'Unsolicited' if answer else 'Solicited')


KEPT_BODIES = frozenset({DROPPED, kept_body('### %s\n\nUnsolicited:' % UNSOLICITED_HEADING),
                         kept_body('### %s\n\nSolicited:' % UNSOLICITED_HEADING)})


class Redactor:
    """Person identifiers out of a transcript, consistently: one alias per (kind, normalised value), so the counts
    replay from the redacted copy exactly as from the original."""

    def __init__(self):
        self.aliases: dict[tuple, str] = {}
        self._n = Counter()
        self._real: dict[str, str] = {}             # an identity's text as it appeared -> its alias
        self._known = None

    def alias(self, kind: str, value):
        v = norm(kind, value)
        if v is None:
            return value
        if (kind, v) not in self.aliases:
            self._n[kind] += 1
            self.aliases[(kind, v)] = '%s-%d' % (kind, self._n[kind])
        text = value.strip() if isinstance(value, str) else ''
        if len(text) >= 3 and not text.isdigit():   # a bare number is an id, never a name in running text
            self._real[text.casefold()] = self.aliases[(kind, v)]
        return self.aliases[(kind, v)]

    def exchanges(self, exchanges: list[dict]) -> list[dict]:
        structured = [self._walk(e) for e in exchanges]
        if self._real:
            self._known = re.compile(r'(?<![\w-])(%s)(?![\w-])' % '|'.join(
                re.escape(s) for s in sorted(self._real, key=len, reverse=True)), re.I)
        return [self._scrub(e) for e in structured]

    def _walk(self, node):
        if isinstance(node, list):
            return [self._walk(v) for v in node]
        if not isinstance(node, dict):
            return node
        if isinstance(node.get('login'), str):      # a GitHub account; a bot's or an organisation's stays
            kept = node.get('type') in NOT_PEOPLE
            return {'login': node['login'] if kept else self.alias('github', node['login']), 'type': node.get('type')}
        out = {}
        for k, v in node.items():
            if k == 'authorships' and isinstance(v, list):
                out[k] = [self._authorship(a) for a in v]
            elif k == 'authors' and isinstance(v, list):            # Semantic Scholar
                out[k] = [{'authorId': self.alias('s2', a.get('authorId')), 'name': self.alias('name', a.get('name'))}
                          if isinstance(a, dict) else a for a in v]
            elif k in ('creators', 'contributors') and isinstance(v, list):    # DataCite
                out[k] = [{'name': self.alias('name', c.get('name'))} if isinstance(c, dict) else c for c in v]
            elif k == 'xml':                                          # DataCite's base64 metadata: names inside
                out[k] = DROPPED
            else:
                out[k] = self._walk(v)
        if 'number' in node and 'user' in node and 'pull_request' not in node and 'body' in node:
            out['body'] = kept_body(node['body'])   # an issue's body is its author's own words
        return out

    def _authorship(self, a):
        if not isinstance(a, dict):
            return a
        out = {k: self._walk(v) for k, v in a.items() if k not in ('author', 'raw_author_name')}
        person = a.get('author')
        if isinstance(person, dict):
            out['author'] = {'id': self.alias('openalex', person.get('id')),
                             'display_name': self.alias('name', person.get('display_name')),
                             'orcid': self.alias('orcid', person.get('orcid'))}
        if 'raw_author_name' in a:
            out['raw_author_name'] = self.alias('name', a['raw_author_name'])
        return out

    def _scrub(self, node, key=None):
        """E-mail addresses out of every string; identities and @-mentions out of free text only, so the request
        URLs, DOIs and ids a replay depends on are never touched."""
        if isinstance(node, list):
            return [self._scrub(v, key) for v in node]
        if isinstance(node, dict):
            return {k: self._scrub(v, k) for k, v in node.items()}
        if not isinstance(node, str) or node in KEPT_BODIES:   # ours, naming no one: an alias must not reach it
            return node
        text = EMAIL.sub('[e-mail]', node)
        if key not in FREE_TEXT:
            return text
        if self._known is not None:
            text = self._known.sub(lambda m: self._real[m.group(1).casefold()], text)
        return MENTION.sub('@[handle]', text)


def transcript(m: Measurement, identify: bool = False) -> dict:
    """The raw output: every exchange, redacted unless `identify` (or already redacted)."""
    exchanges, rulings, redacted = [e.as_dict() for e in m.exchanges], m.rulings.as_dict(), m.redacted
    if not redacted and not identify:
        r = Redactor()
        exchanges = r.exchanges(exchanges)
        rulings, redacted = m.rulings.as_dict(r.aliases), True
    return {'format': FORMAT, 'run_on': m.run_on, 'repo': m.repo, 'dois': m.dois, 'credentials': m.credentials,
            'redacted': redacted, 'rulings': rulings, 'exchanges': exchanges}


def published(m: Measurement) -> Measurement:
    """The measurement as a reader of the redacted raw output gets it: replayed from that output, so what is
    published is by construction what --validate reproduces. Redaction must not move a count; if it ever did,
    nothing is published."""
    if m.redacted:
        return m
    r = from_transcript(transcript(m))
    if [(x.count, x.verdict, x.reasons) for x in r.results] != [(x.count, x.verdict, x.reasons) for x in m.results]:
        raise ValueError('redacting the raw output changed a count or a reason; nothing is published (run with '
                         '--identify to see the unredacted measurement)')
    return r


def report(m: Measurement, identify: bool = False) -> dict:
    return {'run_on': m.run_on, 'repo': m.repo, 'dois': m.dois, 'gate': m.verdict,
            'conditions': [r.as_dict(identify) for r in m.results], 'transcript': transcript(m, identify)}


# ---- the Markdown block, --write and --validate -----------------------------------------------------------------

BEGIN = '<!-- adoption-measure:begin -- generated by scripts/adoption_measure.py --write; --validate replays it -->'
END = '<!-- adoption-measure:end -->'
FENCE = '````'
CONFIRMATIONS = ('Condition 1: exclusions confirmed', 'Condition 3: unsolicited rulings confirmed')
STATUS = {'ok': 'read', 'not-indexed': 'not indexed', 'failed': 'FAILED'}


def _counted_line(r: Result) -> str:
    d = r.detail
    if r.condition == 1:
        excluded = ', '.join('%d as %s' % (n, why) for why, n in d['excluded'].items()) or 'none'
        return ('- condition 1: %d merged `%s` pull request(s), linking %d issue(s) by %d author(s); excluded %s; '
                '**%d external**.' % (d['merged_pull_requests'], FORM_LABEL, d['linked_issues'], d['authors'],
                                      excluded, d['external']))
    if r.condition == 2:
        kinds = ', '.join('%d %s' % (n, k) for k, n in d['by_kind'].items()) or 'none'
        return ('- condition 2: %d citing work(s) outside our own DOIs: %s. Counted: %s.'
                % (d['citing_works'], kinds, ', '.join('`%s`' % c for c in r.counted) or 'none'))
    return ('- condition 3: %d issue(s) labelled `%s`; %d judged unsolicited (%s), %d solicited, %d with no '
            'judgement. Judged by the form\'s answer alone: %d; the form overruled by the rulings: %s.'
            % (d['labelled'], RERUN_LABEL, d['unsolicited'], ', '.join(r.counted) or 'none', d['solicited'],
               d['unjudged'], d['by_form'], _refs(d['overruled']) or 'none'))


def block(m: Measurement, identify: bool = False) -> str:
    """The generated section of docs/adoption/<YYYY>-Q<N>.md. Deterministic, from the measurement alone."""
    t = transcript(m, identify)
    lines = [BEGIN, '', '### The run', '',
             'Run on **%s** over `%s` and the DOIs %s: %d request(s), every one in the raw output below.'
             % (m.run_on, m.repo, ', '.join('`%s`' % d for d in m.dois), len(m.exchanges))]
    if m.credentials is not None:
        lines.append('Credentials: %s.' % '; '.join('%s %s' % (k, 'set' if v else 'not set')
                                                    for k, v in sorted(m.credentials.items())))
    lines += ['', '### The three conditions', '',
              '| # | condition (14-roadmap.md, Phase 8) | needs | counted | verdict |',
              '| --- | --- | --- | --- | --- |']
    for r in m.results:
        lines.append('| %d | %s | ≥ %d | %d%s | **%s** |' % (r.condition, r.title, r.threshold, r.count,
                                                          '' if r.complete else ' (partial)', r.verdict))
    lines += ['', '**The gate: %s.** All three conditions must be met, and a condition that cannot be measured '
                  'counts as failed (13 §0.2).' % m.verdict, '', '### Why', '']
    for r in m.results:
        if r.reasons:
            lines += ['- condition %d: %s' % (r.condition, why) for why in r.reasons]
        elif r.raising:                             # met on what was measured; what was not could only add
            lines += ['- condition %d: met; not measured, and able only to add: %s' % (r.condition, x)
                      for x in r.raising]
        else:
            lines.append('- condition %d: met' % r.condition)
    lines += ['', '### What was counted', ''] + [_counted_line(r) for r in m.results]
    lines += ['', '| DOI | instrument | reading | citations it reports |', '| --- | --- | --- | --- |']
    for rd in m.results[1].detail['readings']:
        lines.append('| `%s` | %s | %s | %s |' % (rd['doi'], rd['instrument'], STATUS[rd['status']],
                                                   '--' if rd['count'] is None else rd['count']))
    if identify:
        people = m.results[0].people
        lines += ['', '### People (--identify: never commit this)', '',
                  '- condition 1, counted: %s' % (', '.join(people['counted']) or 'none'),
                  '- condition 1, excluded: %s' % (', '.join('%s (%s)' % kv for kv in sorted(people['excluded'].items()))
                                                   or 'none')]
    lines += ['', '### Raw query output', '',
              'Every request in order, with its status and response body (13 §0.2). %s' % (
                  'Person identifiers are aliases (`github-1`, `name-1`, ...), consistent across this file; e-mail '
                  'addresses and @-mentions are removed, and issue bodies are dropped, all but the rerun-request '
                  'form\'s answer, which condition 3 reads. `--validate` replays the counts above from it.'
                  if t['redacted'] else
                  '**Identities are not redacted (--identify): do not commit this.**'),
              '', '<details><summary>%d request(s)</summary>' % len(m.exchanges), '', FENCE + 'json',
              json.dumps(t, indent=1, sort_keys=True, ensure_ascii=False), FENCE, '', '</details>', '', END]
    return '\n'.join(lines) + '\n'


def _block_of(text: str) -> str | None:
    i, j = text.find(BEGIN), text.find(END)
    if i < 0 or j < i:
        return None
    return text[i:j + len(END)] + '\n'


def _transcript_of(blk: str) -> dict:
    m = re.search(r'^%sjson\n(.*?)\n%s$' % (FENCE, FENCE), blk, re.M | re.S)
    if m is None:
        raise ValueError('the generated block carries no raw query output')
    return json.loads(m.group(1))


PREAMBLE = """# Adoption measurement, run on {date}

- **Task:** P8-S1-T04 or P8-S1-T05 (13-execution-runners.md §0.2, §0.3)
- **Instruments:** [instruments.md](instruments.md), run by `scripts/adoption_measure.py`. The generated block
  below replays with `python scripts/adoption_measure.py --validate {path}`
- **Status:** agent draft. The counts are mechanical; the exclusions and the unsolicited rulings are a person's.
"""

POSTSCRIPT = """## Human rulings

<!-- P8-S1-T04: a person confirms the exclusions behind condition 1 (every maintainer and alt account is in the
rulings; `--identify` shows who was counted, and its output is never committed) and the "unsolicited" judgement
behind condition 3 (13 §0.2: a request answering a call for requests does not count). Write the date and what was
checked, not who: the commit says who. `--write` never touches anything outside the generated block, and
`--validate` fails while either line below reads "--". -->

- **Condition 1: exclusions confirmed:** --
- **Condition 3: unsolicited rulings confirmed:** --

## Corroborating signals, which are not the gate

<!-- 13 §0.3: independent forks carrying commits not in our history, and referrer data on the corpus.json and
facets.json asset paths. Recorded as corroboration; neither decides anything. -->

- **Forks:** --
- **Asset referrers:** --
"""


def confirmation(text: str, label: str) -> str | None:
    m = re.search(r'^- \*\*%s:\*\*[ \t]*(.*)$' % re.escape(label), text, re.M)
    return m.group(1).strip() if m else None


def write(path: str, m: Measurement) -> None:
    """Replace the generated block in `path`, or create the file around it."""
    m = published(m)
    new = block(m)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        old = _block_of(text)
        if old is None:
            raise ValueError('%s exists and has no generated block to replace' % path)
        text = text.replace(old, new)
    else:
        text = PREAMBLE.format(date=m.run_on, path=path.replace(os.sep, '/')) + '\n' + new + '\n' + POSTSCRIPT
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def validate(path: str) -> tuple[list[str], Measurement]:
    """What stops `path` standing as a measurement: differences between its block and a replay of the block's own
    raw output, and confirmation lines not filled in. Empty when it stands."""
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    old = _block_of(text)
    if old is None:
        raise ValueError('%s has no generated block between %s and %s' % (path, BEGIN, END))
    m = from_transcript(_transcript_of(old))
    problems = []
    new = block(m)
    if new != old:
        import difflib
        problems.append('the block does not replay from its own raw output:')
        problems += difflib.unified_diff(old.splitlines(), new.splitlines(), 'published', 'replayed', lineterm='')
    for label in CONFIRMATIONS:
        if confirmation(text, label) in (None, '', '--'):
            problems.append('"%s" is not filled in' % label)
    return problems, m


def plan(repo: str, dois: list[str], env) -> str:
    """What --live would request, and which credentials it would use. Requests nothing."""
    lines = ['adoption_measure: the plan; nothing was requested (--live runs it)', '',
             'condition 1 (>= 3 external contributors through the issue form)',
             '  GET %s' % issues_url(repo, FORM_LABEL, 'closed', 1),
             '  GET %s/repos/%s/issues/N   for each issue N a merged pull request closes' % (GITHUB, repo),
             '  GET %s' % collaborators_url(repo, 1),
             'condition 2 (>= 1 external publication citing the DOI), DOI each of %s, W its OpenAlex work' % ', '.join(dois),
             '  GET %s' % openalex_work_url('DOI'),
             '  GET %s' % openalex_cites_url('W', '*'),
             '  GET %s' % datacite_url('DOI'),
             '  GET %s' % s2_citations_url('DOI', 0),
             '  GET %s   for a citing DOI only DataCite reports' % openalex_work_url('CITING-DOI', OA_CITING),
             'condition 3 (>= 5 unsolicited rerun requests)',
             '  GET %s' % issues_url(repo, RERUN_LABEL, 'all', 1), '']
    lines += ['%s: %s' % (k, 'set' if env.get(k) else 'not set') for k in CREDENTIALS]
    return '\n'.join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--repo', default=REPO)
    p.add_argument('--doi', action='append', help='a DOI for condition 2 (repeatable); default: instruments.md\'s')
    src = p.add_mutually_exclusive_group()
    src.add_argument('--live', action='store_true', help='run the instruments against the APIs')
    src.add_argument('--replay', metavar='TRANSCRIPT', help='run them over a recorded transcript (JSON)')
    src.add_argument('--validate', metavar='DOC', help="exit 1 unless DOC's block replays and its rulings are confirmed")
    p.add_argument('--rulings', metavar='FILE', help='the human rulings (YAML); it names people, so keep it outside the repo')
    p.add_argument('--json', action='store_true', help='the counts and the raw output as JSON')
    p.add_argument('--write', metavar='DOC', help='put the run into DOC between its markers')
    p.add_argument('--identify', action='store_true', help='keep identities in the output, for the person confirming')
    a = p.parse_args(argv)
    if a.write and not (a.live or a.replay):
        p.error('--write goes with --live or --replay')
    if a.write and a.identify:
        p.error('--identify names people, and a file is never written with them (--write)')
    try:
        if a.validate:
            problems, m = validate(a.validate)
            if problems:
                print('adoption_measure --validate: %s does not stand\n%s' % (a.validate, '\n'.join(problems)),
                      file=sys.stderr)
                return 1
            print('adoption_measure --validate: %s replays and is confirmed (gate %s)' % (a.validate, m.verdict))
            return 0
        rulings = read_rulings(a.rulings) if a.rulings else None
        if a.replay:
            with open(a.replay, encoding='utf-8') as fh:
                m = from_transcript(json.load(fh), rulings)
        elif a.live:
            get = Live()
            m = measure(get, a.repo, a.doi or dois_from(a.root), rulings or Rulings(), date.today().isoformat(),
                        get.credentials())
        else:
            print(plan(a.repo, a.doi or dois_from(a.root), os.environ))
            return 0
        if a.write:
            write(a.write, m)
            print('adoption_measure: wrote %s (gate %s)' % (a.write, m.verdict))
            return 0
        if not a.identify:
            m = published(m)
    except (OSError, ValueError) as e:              # a file that does not parse or exist; a transcript out of shape
        print('adoption_measure: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(report(m, a.identify), indent=2, sort_keys=True, ensure_ascii=False) if a.json
          else block(m, a.identify))
    return 0


if __name__ == '__main__':
    sys.exit(main())
