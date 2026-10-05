"""Tests for ingest/verification.py, the four verification rules and the structural transcript check (P3-S4-T01;
04 S7, 07 S2.2-2.3).

No test reaches the network: every HEAD goes to a probe the test supplies. The last test runs the rules over the
real Epoch snapshot in epochdl/ (gitignored, so skipped where it is absent) and checks 04 S7's structural counts,
with every HEAD answering 200. Live, on 2026-10-05, 756 of the 828 did not (ingest/verification.py says why).
"""
import csv
import os
import socket
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest import verification as v  # noqa: E402

PUB = 'https://epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com/inspect_ai_logs/abc.eval'
STAGING = 'https://epoch-benchmarks-staging-public.s3.us-east-2.amazonaws.com/inspect_ai_logs/def.eval'
PRIV = 'https://epoch-benchmarks-production-private.s3.us-east-2.amazonaws.com/inspect_ai_logs/ghi.eval'
T0 = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('a test reached for the network')
    monkeypatch.setattr(socket, 'socket', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)


class Probe:
    """A HEAD that answers from a table (default 200) and counts what it was asked."""

    def __init__(self, answers=None, default=200):
        self.answers, self.default, self.asked = answers or {}, default, []

    def __call__(self, url):
        self.asked.append(url)
        status = self.answers.get(url, self.default)      # get-default: the table lists only the exceptions
        return (status, 'HTTP %d' % status) if status else (None, 'TimeoutError')


def heads(probe=None, state=None, now=T0):
    return v.HeadCache(state if state is not None else {}, probe or Probe(), lambda: now)


# ---- the four rules (04 S7) -------------------------------------------------------------------------------

def test_rule_1_an_epoch_run_with_a_public_transcript_is_independent_reproduction():
    a = v.assess('epoch-run', PUB, heads())
    assert (a.verification, a.artifact_url, a.labels, a.rule) == ('independent-reproduction', PUB, (), 'epoch-run-public')
    assert v.assess('epoch-run', STAGING, heads()).verification == 'independent-reproduction'


@pytest.mark.parametrize('log, access', [(PRIV, 'private'), ('', 'absent'), (None, 'absent'), ('   ', 'absent')])
def test_rule_2_an_epoch_run_with_a_private_or_blank_log_is_maintainer_verified(log, access):
    probe = Probe()
    a = v.assess('epoch-run', log, heads(probe))
    assert (a.verification, a.rule, a.transcript.access, a.labels) == (
        'maintainer-verified', 'epoch-run-private-or-absent', access, ())
    assert probe.asked == []                               # nothing to ask: no HEAD is spent on a private log


@pytest.mark.parametrize('status, outcome', [(404, 'dead'), (403, 'dead'), (410, 'dead'), (503, 'suspect'),
                                             (None, 'suspect')])
def test_rule_3_an_unreachable_public_transcript_drops_to_maintainer_verified_and_is_link_rot(status, outcome):
    a = v.assess('epoch-run', PUB, heads(Probe({PUB: status})))
    assert (a.verification, a.rule, a.labels) == ('maintainer-verified', 'epoch-run-unreachable', ('needs-scrutiny',))
    assert a.artifact_url == PUB                           # kept: it is what the link-rot entry names
    [rot] = v.link_rot([a])
    assert rot['url'] == PUB and rot['outcome'] == outcome and rot['checked_at'] == '2026-10-05T12:00:00Z'
    assert rot['event'] == {'dead': 'lifecycle-review', 'suspect': 'human-review'}[outcome]


@pytest.mark.parametrize('log', [PUB, PRIV, '', None])
def test_rule_4_an_external_scrape_is_self_reported_whatever_its_log_column(log):
    probe = Probe()
    a = v.assess('external-scrape', log, heads(probe))
    assert (a.verification, a.artifact_url, a.rule, a.labels) == ('self-reported', None, 'external', ())
    assert probe.asked == []


def test_an_unknown_family_is_refused_not_defaulted():
    with pytest.raises(ValueError, match="family 'leaderboard-scrape'"):
        v.assess('leaderboard-scrape', PUB, heads())


# ---- the check is structural, not a substring -------------------------------------------------------------

@pytest.mark.parametrize('url', [
    'https://evil.example/epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com/x.eval',   # host in the path
    'https://epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com.evil.example/x.eval',   # host as a prefix
    'https://my-public-bucket.s3.amazonaws.com/x.eval',                                            # "-public" elsewhere
    'https://epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com/x.json',                # not a log
    'https://epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com/x.eval.zip',
    'http://epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com/x.eval',                 # not https
    'https://epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com/x?f=.eval',             # extension in a query
])
def test_a_url_that_merely_looks_public_is_private_and_never_asked(url):
    probe = Probe()
    t = v.transcript_evidence(url, heads(probe))
    assert t.access == 'private' and probe.asked == []


def test_a_structurally_public_url_is_still_only_public_after_its_head():
    assert v.transcript_evidence(PUB, heads(Probe({PUB: 404}))).access == 'unreachable'


# ---- the HEAD cache ---------------------------------------------------------------------------------------

def test_a_good_head_is_cached_for_30_days_then_asked_again():
    state, probe = {}, Probe()
    v.transcript_evidence(PUB, heads(probe, state, T0))
    v.transcript_evidence(PUB, heads(probe, state, T0 + timedelta(days=29, hours=23)))
    assert probe.asked == [PUB] and state['transcripts'][PUB] == {'checked_at': '2026-10-05T12:00:00Z', 'detail': 'HTTP 200'}
    v.transcript_evidence(PUB, heads(probe, state, T0 + timedelta(days=30)))
    assert probe.asked == [PUB, PUB] and state['transcripts'][PUB]['checked_at'] == '2026-11-04T12:00:00Z'


def test_a_failed_head_is_not_cached_and_a_recovered_one_is_public_next_run():
    state = {}
    assert v.transcript_evidence(PUB, heads(Probe({PUB: 503}), state)).access == 'unreachable'
    assert 'transcripts' in state and PUB not in state['transcripts']
    assert v.transcript_evidence(PUB, heads(Probe(), state, T0 + timedelta(hours=1))).access == 'public'


def test_a_link_that_dies_is_caught_when_its_30_days_are_up():
    state = {}
    v.transcript_evidence(PUB, heads(Probe(), state, T0))
    assert v.transcript_evidence(PUB, heads(Probe({PUB: 404}), state, T0 + timedelta(days=10))).access == 'public'
    assert v.transcript_evidence(PUB, heads(Probe({PUB: 404}), state, T0 + timedelta(days=31))).access == 'unreachable'
    assert PUB not in state['transcripts']


def test_the_network_head_turns_a_failure_into_a_status_not_an_exception(monkeypatch):
    def down(req, timeout):
        assert req.get_method() == 'HEAD'
        raise v.urllib.error.URLError(TimeoutError('timed out'))
    monkeypatch.setattr(v.urllib.request, 'urlopen', down)
    assert v.head(PUB) == (None, 'TimeoutError')


# ---- the gates (07 S8) ------------------------------------------------------------------------------------

def test_the_machine_assignable_rungs_come_from_the_taxonomy():
    assert v.machine_assignable() == {'self-reported': 1, 'maintainer-verified': 2, 'independent-reproduction': 3}


@pytest.mark.parametrize('rung', ['held-out-server', 'prospective-experiment', 'third-party-audited',
                                  'sandboxed-rerun', 'curator-verified'])
def test_a_machine_may_not_assign_rungs_4_to_7(rung):
    with pytest.raises(ValueError, match='not machine-assignable'):
        v.check_machine_claim(rung, v.Transcript(PUB, 'public'))


@pytest.mark.parametrize('t', [None, v.Transcript(None, 'absent'), v.Transcript(PRIV, 'private'),
                               v.Transcript(PUB, 'unreachable')])
def test_independent_reproduction_needs_a_reachable_transcript(t):
    with pytest.raises(ValueError, match='reachable artifact_url'):
        v.check_machine_claim('independent-reproduction', t)


# ---- the accounting ---------------------------------------------------------------------------------------

def test_the_tally_accounts_for_every_row_by_rule_with_the_unmatched_beside():
    h = heads(Probe({STAGING: 404}))
    rows = [v.assess('epoch-run', PUB, h), v.assess('epoch-run', STAGING, h), v.assess('epoch-run', PRIV, h),
            v.assess('epoch-run', '', h), v.assess('external-scrape', None, h)]
    assert v.tally(rows, unmatched=3) == {
        'rules': {'epoch-run-public': 1, 'epoch-run-private-or-absent': 2, 'epoch-run-unreachable': 1, 'external': 1},
        'verification': {'independent-reproduction': 1, 'maintainer-verified': 3, 'self-reported': 1},
        'needs_scrutiny': 1, 'unmatched': 3, 'rows': 8}


EPOCHDL = os.path.join(ROOT, 'epochdl')


@pytest.mark.skipif(not os.path.isdir(EPOCHDL), reason='epochdl/ (the Epoch snapshot) is gitignored and absent')
def test_the_real_snapshot_gives_04_s7s_counts():
    from ingest.mappings.schema import load_all
    stanzas, probe = load_all('epoch'), Probe()
    h, assessed, unmatched = heads(probe), [], 0
    for name in sorted(os.listdir(EPOCHDL)):
        if not name.endswith('.csv') or name in ('benchmark_metadata.csv', 'model_metadata.csv'):
            continue
        s = stanzas.get('csv:' + name[:-4])                # get-default: an orphan file has no stanza (P3-S2-T04)
        with open(os.path.join(EPOCHDL, name), encoding='utf-8', newline='') as fh:
            rows = list(csv.DictReader(fh))
        if s is None:
            unmatched += len(rows)
            continue
        col = s.artifact.log_column if s.artifact else None
        assessed += [v.assess(s.family, row[col] if col else None, h) for row in rows]
    t = v.tally(assessed, unmatched)
    assert t['rows'] == 6598
    # 04 S7: 828 public, 459 private + ~263 blank; this snapshot has 258 blank. Every external row self-reported.
    assert t['rules']['epoch-run-public'] == 828 and t['rules']['epoch-run-private-or-absent'] == 459 + 258
    assert t['rules']['epoch-run-unreachable'] == 0 and t['verification']['self-reported'] == t['rules']['external']
    assert len(probe.asked) == len(set(probe.asked)) == 828    # one HEAD per public transcript, none for the rest
