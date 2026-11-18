"""The issue-intake bot, step 2: comments, labels and the pull request (P2-S6-T04; 05-repository-and-workflow.md
S6, "The validation bot"; 08 S3.4 and S7.3; docs/bot-identity.md).

    python -m tools.intake.open_pr --event EVENT.json --result RESULT.json [--dry-run]

It acts on tools/intake/parse_form.py's RESULT.json:

  drafted   comments the YAML it will write (08 S3.4's 90-second budget runs to this comment), clears needs-fix,
            then opens the pull request on contrib/<issue>-<id> -- or updates the one already open for the issue --
            and edits the comment to link it
  invalid   comments the field-level errors only, labels needs-fix and leaves the issue open. The third failed
            attempt in a row adds needs-human and pings the steward .github/CODEOWNERS names for the entry's path,
            or says that no file names one
  human     a form the bot does not draft (correction, new-claim, dispute, taxonomy-term): comments that a
            maintainer takes it from here and labels needs-human; taxonomy-term never gets a pull request (05 S5)
  error     the bot's own failure: comments that it failed, never how (the run log has that), labels needs-human
            and exits 1, so the run is red for the maintainers
  skipped   no form label: nothing

One comment per issue. The bot finds its own by a hidden marker, `<!-- uaibi:issue-intake attempts=N -->`, posted
by the account it comments as, and replaces it: the new comment first, then the old one deleted. The thread stays
one bot comment long, the contributor is notified of each new result, and a steward's @-mention notifies (GitHub
sends no notification for a mention added by editing). N counts failed attempts in a row; a pass resets it.

Two tokens (docs/bot-identity.md; 08 S7.3):

  GITHUB_TOKEN     the workflow's own, with issues: write: the comment and the labels on the issue
  UAIBI_BOT_PAT    uaibi-bot's fine-grained PAT (contents and pull requests: write): the tree, the commit and the
                   branch through the git data API, then the pull request and its labels. A pull request opened
                   with GITHUB_TOKEN would not run pr-validate.yml.

The commit identity is the maintainer's decision for this task, and it overrides the ledger's "a Co-authored-by
trailer" for the contributor. The project allows three identities on a commit and no other: the commit is
authored and committed as intelligence-benchmark, and its message ends with exactly the two Co-authored-by
trailers of advancedintelligence and tatra-labs. commit_message() and commit_payload() raise IdentityError if
asked to write any other identity or trailer. The contributor is credited by the issue link alone, "From issue
#N" and "Closes #N" in the pull request body: no name or handle of theirs is written into the commit, the files
or the pull request.

The bot never merges. Nothing here calls a merge endpoint, and the tests assert no call does.

`--dry-run` makes no request and needs no token: it prints each call it would make.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.intake.parse_form import DEFAULT_REPO, PR_LABELS, TIERS  # noqa: E402

API = 'https://api.github.com'
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
MARKER = '<!-- uaibi:issue-intake attempts=%d -->'
MARKER_RE = re.compile(r'^<!-- uaibi:issue-intake attempts=(\d+) -->')
COMMENT_AUTHOR = 'github-actions[bot]'      # who GITHUB_TOKEN comments as
MAX_ATTEMPTS = 3                            # 05 S6: "After three failed attempts, adds needs-human"
NEEDS_FIX, NEEDS_HUMAN = 'needs-fix', 'needs-human'
BUDGET_S = 90                               # 08 S3.4: issue form submitted -> bot comment posted, < 90 s
CODEOWNERS = ('.github/CODEOWNERS', 'CODEOWNERS', 'docs/CODEOWNERS')   # GitHub's own search order
COMMENT_CAP = 60000                         # GitHub refuses a comment over 65,536 characters
FORM_NOUNS = {'correction': 'correction', 'new-claim': 'result claim', 'dispute': 'dispute',
              'taxonomy-term': 'vocabulary term proposal', 'new-benchmark': 'new benchmark'}


# ---- the commit identity -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Identity:
    name: str
    email: str

    def __str__(self):
        return '%s <%s>' % (self.name, self.email)


AUTHOR = Identity('intelligence-benchmark', 'intelligence.benchmark@gmail.com')
CO_AUTHORS = (Identity('advancedintelligence', 'advanced.intelligence.labs@gmail.com'),
              Identity('tatra-labs', 'tatra.labs@gmail.com'))
TRAILERS = tuple('Co-authored-by: %s' % i for i in CO_AUTHORS)
TRAILERISH = re.compile(r'^\s*[A-Za-z][A-Za-z0-9-]*-by\s*:', re.I)
ADDRESS = re.compile(r'[^\s<>@]+@[^\s<>@]+\.[A-Za-z]{2,}')


class IdentityError(ValueError):
    """A commit the bot was asked to write under an identity, or with a trailer, the project does not allow."""


def check_identity(author: Identity, committer: Identity, message: str) -> None:
    for role, who in (('author', author), ('committer', committer)):
        if (who.name, who.email) != (AUTHOR.name, AUTHOR.email):
            raise IdentityError('the bot commits only as %s; refusing %s %s' % (AUTHOR, role, who))
    lines = [line.strip() for line in message.rstrip('\n').split('\n')]
    for line in lines:
        if (TRAILERISH.match(line) or ADDRESS.search(line)) and line not in TRAILERS:
            raise IdentityError('a commit carries only the trailers %s; refusing %r' % ('; '.join(TRAILERS), line))
    if lines[-len(TRAILERS):] != list(TRAILERS) or sum(line in TRAILERS for line in lines) != len(TRAILERS):
        raise IdentityError('a commit message ends with exactly these trailers, once each: %s' % '; '.join(TRAILERS))


def commit_message(subject: str, body: str, trailers=TRAILERS) -> str:
    body = '\n\n'.join(textwrap.fill(' '.join(para.split()), 72) for para in body.strip().split('\n\n'))
    message = '%s\n\n%s\n\n%s\n' % (subject.strip(), body, '\n'.join(trailers))
    check_identity(AUTHOR, AUTHOR, message)
    return message


def commit_payload(message: str, tree: str, parents, when: datetime, author: Identity = AUTHOR,
                   committer: Identity = AUTHOR) -> dict:
    """The body of POST /repos/{repo}/git/commits. The identity is checked here, where it is written."""
    check_identity(author, committer, message)
    stamp = when.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return {'message': message, 'tree': tree, 'parents': list(parents),
            'author': {'name': author.name, 'email': author.email, 'date': stamp},
            'committer': {'name': committer.name, 'email': committer.email, 'date': stamp}}


# ---- the REST API ------------------------------------------------------------------------------------------

class GitHubError(RuntimeError):
    """A failed call. It names the method, the path and the status, never the token."""

    def __init__(self, method: str, path: str, status: int, detail: str = ''):
        super().__init__('%s %s: HTTP %s%s' % (method, path, status, ' (%s)' % detail if detail else ''))
        self.status = status


class GitHub:
    def __init__(self, token: str, api: str = API, opener: Callable = urllib.request.urlopen):
        self.token, self.api, self.opener = token, api.rstrip('/'), opener

    def call(self, method: str, path: str, payload: Any = None, ok_missing: bool = False) -> Any:
        if not self.token:
            raise GitHubError(method, path, 0, 'no token in the environment')
        req = urllib.request.Request(
            self.api + path, method=method, data=None if payload is None else json.dumps(payload).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': USER_AGENT,
                     'Content-Type': 'application/json'})
        try:
            with self.opener(req, timeout=30) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            if ok_missing and e.code == 404:
                return None
            try:
                detail = str(json.loads(e.read().decode('utf-8', 'replace')).get('message') or '')[:200]
            except (ValueError, AttributeError, OSError):
                detail = ''
            raise GitHubError(method, path, e.code, detail) from None
        except (urllib.error.URLError, OSError) as e:
            raise GitHubError(method, path, 0, str(getattr(e, 'reason', e))[:200]) from None
        return json.loads(raw.decode('utf-8')) if raw else None


class DryRun:
    """Prints each call and answers with placeholders, so the whole flow runs with no request and no token."""

    def __init__(self, who: str, out: Callable = print):
        self.who, self.out = who, out

    def call(self, method: str, path: str, payload: Any = None, ok_missing: bool = False) -> Any:
        shown = ''
        if payload is not None:
            shown = json.dumps(payload, ensure_ascii=False, default=str)
            shown = '  ' + (shown if len(shown) <= 300 else shown[:297] + '...')
        self.out('DRY RUN (%s)  %-6s %s%s' % (self.who, method, path, shown))
        if method == 'GET' and re.search(r'/(comments|matching-refs/.*)(\?|$)|/pulls\?', path):
            return []
        if method == 'GET' and '/git/ref/' in path:
            return {'object': {'sha': '<base commit>'}}
        if method == 'GET' and '/git/commits/' in path:
            return {'tree': {'sha': '<base tree>'}}
        if method == 'POST' and path.endswith('/git/trees'):
            return {'sha': '<new tree>'}
        if method == 'POST' and path.endswith('/git/commits'):
            return {'sha': '<new commit>'}
        if method == 'POST' and path.endswith('/pulls'):
            return {'number': 0, 'html_url': '<the new pull request>'}
        if method == 'POST' and path.endswith('/comments'):
            return {'id': 0}
        return {}


# ---- the issue's one bot comment -----------------------------------------------------------------------------

def own_comments(gh, repo: str, number: int, author: str | None) -> list[dict]:
    """The bot's own comments on the issue, oldest first: the marker at the start, posted as `author`."""
    out = []
    for page in range(1, 11):
        got = gh.call('GET', '/repos/%s/issues/%d/comments?per_page=100&page=%d' % (repo, number, page)) or []
        out += [c for c in got if MARKER_RE.match(c.get('body') or '')                 # get-default: API shape
                and (author is None or (c.get('user') or {}).get('login') == author)]  # get-default: as above
        if len(got) < 100:
            break
    return out


def attempts_in(comments: list[dict]) -> int:
    m = MARKER_RE.match(comments[-1]['body']) if comments else None
    return int(m.group(1)) if m else 0


def replace_comment(gh, repo: str, number: int, old: list[dict], body: str) -> dict:
    new = gh.call('POST', '/repos/%s/issues/%d/comments' % (repo, number), {'body': body}) or {}
    for c in old:
        gh.call('DELETE', '/repos/%s/issues/comments/%s' % (repo, c['id']), ok_missing=True)
    return new


def set_labels(gh, repo: str, number: int, have: list[str], add=(), remove=()):
    if [x for x in add if x not in have]:
        gh.call('POST', '/repos/%s/issues/%d/labels' % (repo, number), {'labels': list(add)})
    for x in remove:
        if x in have:
            gh.call('DELETE', '/repos/%s/issues/%d/labels/%s' % (repo, number, urllib.parse.quote(x, safe='')),
                    ok_missing=True)


# ---- the steward -------------------------------------------------------------------------------------------

def codeowners(root: str) -> tuple[str | None, list[tuple[str, list[str]]]]:
    """(the CODEOWNERS file GitHub would read, its rules in order), or (None, []) when there is none."""
    for rel in CODEOWNERS:
        path = os.path.join(root, *rel.split('/'))
        if os.path.exists(path):
            rules = []
            with open(path, encoding='utf-8') as fh:
                for line in fh:
                    line = line.split('#', 1)[0].strip()
                    if line:
                        pattern, *owners = line.split()
                        rules.append((pattern, owners))
            return rel, rules
    return None, []


def _matches(pattern: str, path: str) -> bool:
    """gitignore-style, as CODEOWNERS reads it, enough for paths: `*` is everything; a pattern with a leading or
    inner `/` is anchored at the root; a match on a directory covers what is under it."""
    anchored = pattern.startswith('/') or '/' in pattern.strip('/')
    pat = pattern.strip('/')
    if pat in ('', '*', '**'):
        return True
    parts = path.strip('/').split('/')
    for start in ([0] if anchored else range(len(parts))):
        for end in range(start + 1, len(parts) + 1):
            if fnmatch.fnmatchcase('/'.join(parts[start:end]), pat):
                return True
    return False


def owners_for(rules: list[tuple[str, list[str]]], path: str) -> list[str]:
    """The owners of `path`: the last matching rule wins, as in GitHub."""
    owners: list[str] = []
    for pattern, who in rules:
        if _matches(pattern, path):
            owners = who
    return owners


def steward_line(root: str, path: str) -> str:
    where, rules = codeowners(root)
    if where is None:
        return ('No CODEOWNERS file names a steward yet, so nobody is pinged by name; the needs-human label asks '
                'the maintainers.')
    owners = owners_for(rules, path)
    if not owners:
        return ('%s names no steward for `%s`, so nobody is pinged by name; the needs-human label asks the '
                'maintainers.' % (where, path))
    return '%s: %s names you as the steward for `%s`. Could you help with this submission?' % (
        ' '.join(owners), where, path)


# ---- the comments ------------------------------------------------------------------------------------------

def _fence(text: str) -> str:
    run = max((len(m.group(0)) for m in re.finditer(r'`+', text)), default=0)
    return '`' * max(3, run + 1)


def _bench_file(result: dict) -> tuple[str, str]:
    rel = next(p for p in result['files'] if p.startswith('drafts/benchmarks/'))
    return rel, result['files'][rel]


def success_comment(result: dict, pr: dict | None, note: str = '') -> str:
    rel, text = _bench_file(result)
    src = next((p for p in result['files'] if p.startswith('drafts/sources/')), None)
    if len(text) > COMMENT_CAP - 4000:
        text = text[:COMMENT_CAP - 4000] + '\n# ... (cut here to fit a comment; the pull request has the whole file)\n'
    fence = _fence(text)
    if pr is None:
        link = 'opening now; this comment links it in a moment.'
    elif pr.get('html_url'):
        link = '%s (opened by the bot; a person reviews it before anything is merged).' % pr['html_url']
    else:
        link = 'none yet.'
    return '\n'.join([
        MARKER % 0,
        '**The bot validated this submission and drafted the entry.** It passed `bench validate --single --tier %s`. '
        'This is the YAML it writes, as `%s`:' % (','.join(TIERS), rel),
        '',
        '%syaml\n%s%s' % (fence, text, fence),
        '',
        'The issue body itself is saved beside it%s, and every quote above is checked against it.'
        % (' as `%s`' % src if src else ''),
        '',
        '**Pull request:** %s' % link,
        '',
        '**What happens next.** A curator checks each field against the sources you linked, confirms the proposed '
        'id `%s`, fills in what the form does not ask, and then promotes the entry into the index; nothing is '
        'published before that. If you edit this issue meanwhile, the bot checks it again and updates the same '
        'pull request.' % result['entity_id'],
    ] + (['', note] if note else [])) + '\n'


def failure_comment(result: dict, attempts: int, steward: str | None) -> str:
    lines = [MARKER % attempts,
             '**The bot could not draft this submission yet.** Here is what to fix. The issue stays open: edit it '
             '(the `...` menu on the issue, then Edit) and the bot checks it again.', '']
    lines += ['- %s' % e['message'] for e in result['errors']]
    lines.append('')
    if attempts < MAX_ATTEMPTS:
        lines.append('This was attempt %d. After %d, a maintainer is asked to help.' % (attempts, MAX_ATTEMPTS))
    elif steward is not None:
        lines.append('This was attempt %d. After %d tries the form is more likely the problem than you are, so the '
                     'issue is labelled needs-human. %s' % (attempts, MAX_ATTEMPTS, steward))
    else:
        lines.append('This was attempt %d. A maintainer has been asked to help (label needs-human).' % attempts)
    return '\n'.join(lines) + '\n'


def human_comment(result: dict) -> str:
    noun = FORM_NOUNS.get(result['form']) or 'submission'
    if result['form'] == 'taxonomy-term':
        rest = ('A vocabulary term goes through an Architecture Decision Record and two reviewers (05 S5), so no '
                'pull request is opened for it. A maintainer takes it from here (label needs-human).')
    else:
        rest = ('The bot does not draft a %s itself yet, so a maintainer takes it from here (label needs-human) '
                'and links the pull request to this issue.' % noun)
    return '%s\n**The bot read this %s and every required answer is there.** %s\n' % (MARKER % 0, noun, rest)


def error_comment(attempts: int) -> str:
    return ('%s\n**The bot hit a problem of its own while reading this issue.** It is not something in your '
            'submission that the bot can name. The maintainers have been asked to look (label needs-human); the '
            'details are in the workflow run\'s log, not here.\n' % (MARKER % attempts))


# ---- the pull request --------------------------------------------------------------------------------------

def pr_body(result: dict, number: int) -> str:
    ident = result['entity_id']
    return '\n'.join([
        'From issue #%d.' % number,
        '',
        'Closes #%d' % number,
        '',
        'The issue-intake bot drafted this entry from the new-benchmark form (05 S6, Path A), and it passed '
        '`bench validate --single --tier %s`:' % ','.join(TIERS),
        '',
        '- `drafts/benchmarks/%s.yaml`: the draft, `ai-drafted-unverified`. Every populated field quotes the '
        'answer on the form; none has been checked against the sources the issue links.' % ident,
        '- `drafts/sources/%s.yaml`: the issue body, which those quotes are checked against.' % result['source_id'],
        '',
        'Before the entry is promoted into `data/`, a curator:',
        '',
        '1. confirms the proposed id `%s` or chooses another (04 S3: an id is permanent, and a person allocates '
        'it);' % ident,
        '2. checks each field against the sources the issue links, and ticks it into `provenance.fields_verified`;',
        '3. fills what the form does not ask (`learned_entrant_evidence`, `data.access`, `task`) from a source, or '
        'leaves it null;',
        '4. works through `curation.review_checks`, then promotes the entry (`bench promote`).',
        '',
        'The bot never merges: a person reviews this pull request, then merges or closes it.',
    ]) + '\n'


def open_pull_request(bot, repo: str, number: int, result: dict, now: datetime, base: str = 'main') -> dict:
    """The branch, the commit and the pull request, through the API with the bot's token. Idempotent across edits:
    the branch already opened for the issue is reused, a tree identical to its head makes no new commit, and an
    open pull request is updated rather than duplicated."""
    prefix = 'contrib/%d-' % number
    refs = [r for r in bot.call('GET', '/repos/%s/git/matching-refs/heads/%s' % (repo, prefix)) or []
            if str(r.get('ref') or '').startswith('refs/heads/' + prefix)]
    branch = refs[0]['ref'][len('refs/heads/'):] if refs else prefix + result['entity_id']
    base_sha = bot.call('GET', '/repos/%s/git/ref/heads/%s' % (repo, base))['object']['sha']
    base_tree = bot.call('GET', '/repos/%s/git/commits/%s' % (repo, base_sha))['tree']['sha']
    entries = [{'path': p, 'mode': '100644', 'type': 'blob', 'content': t} for p, t in sorted(result['files'].items())]
    tree = bot.call('POST', '/repos/%s/git/trees' % repo, {'base_tree': base_tree, 'tree': entries})['sha']
    head = None
    if refs:
        current = refs[0]['object']['sha']
        if bot.call('GET', '/repos/%s/git/commits/%s' % (repo, current))['tree']['sha'] == tree:
            head = current
    if head is None:
        message = commit_message(
            'intake: draft %s from issue #%d' % (result['entity_id'], number),
            'The issue-intake bot\'s draft from the new-benchmark form of issue #%d (05 S6, Path A): '
            'drafts/benchmarks/%s.yaml and the issue snapshot its quotes are checked against. '
            'ai-drafted-unverified; a curator checks it against the linked sources before anything is promoted.'
            % (number, result['entity_id']))
        head = bot.call('POST', '/repos/%s/git/commits' % repo, commit_payload(message, tree, [base_sha], now))['sha']
        if refs:
            bot.call('PATCH', '/repos/%s/git/refs/heads/%s' % (repo, branch), {'sha': head, 'force': True})
        else:
            bot.call('POST', '/repos/%s/git/refs' % repo, {'ref': 'refs/heads/' + branch, 'sha': head})
    owner = repo.split('/')[0]
    pulls = bot.call('GET', '/repos/%s/pulls?state=open&head=%s' % (
        repo, urllib.parse.quote('%s:%s' % (owner, branch), safe=''))) or []
    title = '%s (issue #%d)' % (result['title'], number)
    if pulls:
        pr = pulls[0]
        bot.call('PATCH', '/repos/%s/pulls/%d' % (repo, pr['number']), {'title': title, 'body': pr_body(result, number)})
    else:
        pr = bot.call('POST', '/repos/%s/pulls' % repo, {'title': title, 'head': branch, 'base': base,
                                                         'body': pr_body(result, number)})
    bot.call('POST', '/repos/%s/issues/%d/labels' % (repo, pr['number']), {'labels': list(PR_LABELS)})
    return pr


# ---- the run -----------------------------------------------------------------------------------------------

def _when(stamp: str | None) -> datetime | None:
    return datetime.fromisoformat(stamp.replace('Z', '+00:00')) if stamp else None


def budget(event: dict, now: datetime) -> str:
    """How long after the submission or the edit the comment was posted (08 S3.4: under 90 s)."""
    issue = event.get('issue') or {}
    start = _when(issue.get('created_at') if event.get('action') == 'opened' else issue.get('updated_at'))
    if start is None:
        return 'comment posted (no event time to measure the budget from)'
    took = (now - start).total_seconds()
    return 'comment posted %.0f s after the issue was %s (budget %d s)%s' % (
        took, 'opened' if event.get('action') == 'opened' else 'edited', BUDGET_S,
        '' if took <= BUDGET_S else ': OVER BUDGET')


def handle(event: dict, result: dict, gh, bot, root: str = ROOT, now: Callable = None,
           author: str | None = COMMENT_AUTHOR, out: Callable = print) -> int:
    """Act on one result. Returns the exit code: 0 when the issue got its answer, 1 when the bot failed."""
    now = now or (lambda: datetime.now(timezone.utc))
    issue = event.get('issue') or {}
    repo = (event.get('repository') or {}).get('full_name') or os.environ.get('GITHUB_REPOSITORY') or DEFAULT_REPO
    base = (event.get('repository') or {}).get('default_branch') or 'main'               # get-default: as above
    number = int(issue.get('number') or result.get('issue') or 0)
    have = [lb['name'] if isinstance(lb, dict) else str(lb) for lb in issue.get('labels') or []]
    status = result.get('status')
    if status == 'skipped' or not number:
        out('intake: no form label on issue #%d; nothing to do' % number)
        return 0
    old = own_comments(gh, repo, number, author)
    previous = attempts_in(old)
    if status == 'invalid':
        attempts = previous + 1
        steward = steward_line(root, result.get('steward_path') or 'data/') if attempts == MAX_ATTEMPTS else None
        replace_comment(gh, repo, number, old, failure_comment(result, attempts, steward))
        out(budget(event, now()))
        set_labels(gh, repo, number, have, [NEEDS_FIX] + ([NEEDS_HUMAN] if attempts >= MAX_ATTEMPTS else []))
        out('intake: issue #%d: %d field-level error(s), attempt %d' % (number, len(result['errors']), attempts))
        return 0
    if status == 'human':
        replace_comment(gh, repo, number, old, human_comment(result))
        out(budget(event, now()))
        set_labels(gh, repo, number, have, [NEEDS_HUMAN], [NEEDS_FIX])
        out('intake: issue #%d: %s form, labelled for a maintainer' % (number, result.get('form')))
        return 0
    if status != 'drafted':
        replace_comment(gh, repo, number, old, error_comment(previous))
        set_labels(gh, repo, number, have, [NEEDS_HUMAN])
        out('::error::intake: issue #%d: the bot failed (status %s); see the parse step\'s log' % (number, status))
        return 1
    comment = replace_comment(gh, repo, number, old, success_comment(result, None))
    out(budget(event, now()))
    set_labels(gh, repo, number, have, (), [NEEDS_FIX])
    try:
        pr = open_pull_request(bot, repo, number, result, now(), base)
    except (GitHubError, IdentityError) as e:
        out('::error::intake: issue #%d: could not open the pull request: %s' % (number, e))
        gh.call('PATCH', '/repos/%s/issues/comments/%s' % (repo, comment.get('id')), {'body': success_comment(
            result, {}, '**The bot could not open the pull request.** That is a problem on the bot\'s side, not '
                        'yours: the maintainers have been asked to look (label needs-human).')})
        set_labels(gh, repo, number, have, [NEEDS_HUMAN])
        return 1
    gh.call('PATCH', '/repos/%s/issues/comments/%s' % (repo, comment.get('id')), {'body': success_comment(result, pr)})
    out('intake: issue #%d: drafted %s, pull request %s' % (number, result['entity_id'], pr.get('html_url')))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--event', required=True, help='the issues event JSON ($GITHUB_EVENT_PATH)')
    p.add_argument('--result', required=True, help="parse_form.py's RESULT.json")
    p.add_argument('--dry-run', action='store_true', help='print every call; make none')
    p.add_argument('--root', default=ROOT, help='the checkout, for .github/CODEOWNERS')
    p.add_argument('--author', default=os.environ.get('INTAKE_COMMENT_AUTHOR') or COMMENT_AUTHOR,
                   help='the login the bot comments as, which marks its own comments')
    a = p.parse_args(argv)
    with open(a.event, encoding='utf-8') as fh:
        event = json.load(fh)
    try:
        with open(a.result, encoding='utf-8') as fh:
            result = json.load(fh)
    except (OSError, ValueError):
        result = {'status': 'error'}                   # step 1 wrote nothing: the bot's failure, said as such
    if a.dry_run:
        gh, bot = DryRun('GITHUB_TOKEN'), DryRun('UAIBI_BOT_PAT')
    else:
        gh, bot = GitHub(os.environ.get('GITHUB_TOKEN') or ''), GitHub(os.environ.get('UAIBI_BOT_PAT') or '')

    def out(line: str):
        print(line)
        summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary and line.startswith('comment posted'):
            with open(summary, 'a', encoding='utf-8') as fh:
                fh.write('- %s\n' % line)
            if line.endswith('OVER BUDGET'):
                print('::warning::intake: %s' % line)
    try:
        return handle(event, result, gh, bot, a.root, author=a.author, out=out)
    except GitHubError as e:                          # the issue side failed: there is nowhere to say so but here
        print('::error::intake: %s' % e)
        return 1


if __name__ == '__main__':
    sys.exit(main())
