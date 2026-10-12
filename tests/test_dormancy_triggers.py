"""The dormancy triggers on a fake clock (P0-S7-T04; SUCCESSION.md item 5, 05 S10).

The verify: "a fake clock at 89, 91, 179 and 181 days gives no-op, succession issue, no banner, banner". The
clock is `state(last, today)`'s `today`; the last human commit is read from a throwaway git repository whose
history mixes a curator's commit with a bot's and an ingest batch, neither of which may reset the clock.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import dormancy as D  # noqa: E402

LAST = dt.date(2026, 3, 1)


def at(days):
    return D.state(LAST, LAST + dt.timedelta(days=days))


# ---- the verify: 89, 91, 179, 181 ----------------------------------------------------------------

def test_verify_day_89_is_a_no_op():
    s = at(89)
    assert (s['succession'], s['banner']) == (False, False)


def test_verify_day_91_opens_the_succession_issue_and_not_the_banner():
    s = at(91)
    assert (s['succession'], s['banner']) == (True, False)
    calls = []

    def fake(*args):
        calls.append(args)
        return '[]' if args[:2] == ('issue', 'list') else 'https://github.com/o/r/issues/7\n'
    assert D.open_succession_issue(s, run=fake) == 'opened and pinned https://github.com/o/r/issues/7'
    assert [c[:2] for c in calls] == [('issue', 'list'), ('issue', 'create'), ('issue', 'pin')]
    assert calls[1][calls[1].index('--title') + 1] == 'Maintainer succession'


def test_verify_day_179_has_no_banner():
    s = at(179)
    assert (s['succession'], s['banner']) == (True, False) and D.banner_text(s) is None


def test_verify_day_181_turns_the_banner_on():
    s = at(181)
    assert (s['succession'], s['banner']) == (True, True)
    assert D.banner_text(s) == ('This index has not been curated since 2026-03-01. Data older than that should '
                                'be checked against primary sources.')


def test_the_thresholds_are_the_days_themselves():
    assert at(90)['succession'] and not at(89)['succession']
    assert at(180)['banner'] and not at(179)['banner']


# ---- what counts as a human commit --------------------------------------------------------------------

def git(repo, *args, name='Curator', email='curator@example.invalid', when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email, GIT_COMMITTER_NAME=name,
               GIT_COMMITTER_EMAIL=email)
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    return subprocess.run(['git', *args], cwd=repo, env=env, check=True, capture_output=True, text=True).stdout


def commit(repo, rel, text, msg, **who):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    git(repo, 'add', '-A', **who)
    git(repo, 'commit', '-q', '-m', msg, **who)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / 'repo'
    r.mkdir()
    git(r, 'init', '-q', '-b', 'main')
    commit(r, 'data/benchmarks/a.yaml', 'id: a\n', 'curate a', when='2026-03-01T10:00:00+00:00')
    commit(r, 'README.md', 'x\n', 'docs only', when='2026-04-01T10:00:00+00:00')
    commit(r, 'data/sources/s.yaml', 'id: s\n', 'archive sources', name='uaibi-bot', email='bot@example.invalid',
           when='2026-05-01T10:00:00+00:00')
    commit(r, 'data/claims/c.yaml', 'id: c\n', 'ingest: epoch batch 2026-06-01', when='2026-06-01T10:00:00+00:00')
    commit(r, 'data/claims/d.yaml', 'id: d\n', 'refresh', name='github-actions[bot]',
           email='41898282+github-actions[bot]@users.noreply.github.com', when='2026-07-01T10:00:00+00:00')
    return r


def test_bots_ingests_and_commits_outside_data_do_not_reset_the_clock(repo):
    assert D.last_human_commit(str(repo)) == dt.date(2026, 3, 1)


def test_a_curators_commit_does(repo):
    commit(repo, 'data/benchmarks/b.yaml', 'id: b\n', 'curate b', when='2026-08-15T10:00:00+00:00')
    assert D.last_human_commit(str(repo)) == dt.date(2026, 8, 15)


def test_the_cli_writes_the_state_the_site_reads(repo, tmp_path):
    out = tmp_path / 'build' / 'dormancy.json'
    assert D.main(['--root', str(repo), '--today', '2026-08-30', '--out', str(out)]) == 0
    got = json.loads(out.read_text(encoding='utf-8'))
    assert got['days'] == 182 and got['succession'] and got['banner']
    assert got['banner_text'].startswith('This index has not been curated since 2026-03-01.')


def test_an_open_issue_is_not_opened_twice():
    calls = []

    def fake(*args):
        calls.append(args)
        return json.dumps([{'number': 7, 'title': 'Maintainer succession'}])
    assert D.open_succession_issue(at(120), run=fake) == 'already open'
    assert [c[:2] for c in calls] == [('issue', 'list')]


def test_the_banner_text_is_succession_mds():
    with open(os.path.join(ROOT, 'SUCCESSION.md'), encoding='utf-8') as fh:
        promised = re.search(r'\*"(This index has not been curated since) &lt;date&gt;\. (.+?)"\*',
                             ' '.join(fh.read().split()))
    assert promised, 'SUCCESSION.md no longer quotes the banner'
    text = D.banner_text(at(200))
    assert text.startswith(promised.group(1)) and text.endswith(promised.group(2))


# ---- the wiring --------------------------------------------------------------------------------------

def test_health_check_runs_the_triggers_on_an_odd_cron():
    with open(os.path.join(ROOT, '.github', 'workflows', 'health-check.yml'), encoding='utf-8') as fh:
        wf = YAML(typ='safe').load(fh)
    [cron] = [c['cron'] for c in wf['on']['schedule']]
    minute, hour = cron.split()[:2]
    assert minute not in ('0', '*') and int(minute) % 2 == 1 and int(hour) % 2 == 1, cron
    assert wf['permissions'] == {'contents': 'read', 'issues': 'write'}
    steps = wf['jobs']['dormancy']['steps']
    assert any(s.get('run', '').endswith('python -m tools.dormancy --apply') for s in steps)  # get-default: a uses: step has no run
    [checkout] = [s for s in steps if s.get('uses', '').startswith('actions/checkout@')]  # get-default: a run: step has no uses
    assert checkout['with']['fetch-depth'] == 0


def test_the_site_layout_renders_the_banner_from_the_build():
    with open(os.path.join(ROOT, 'site', 'src', 'layouts', 'Base.astro'), encoding='utf-8') as fh:
        base = fh.read()
    assert "bannerText(dormancy())" in base and 'data-staleness-banner' in base
