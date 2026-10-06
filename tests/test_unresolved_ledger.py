"""The unresolved lifecycle ledger (P3-S3-T07; 07 S5.5).

The done-when: "The same unresolved item does not reappear in full in every PR, and the over-90-day backlog is
visible as its own band." Both are held below against ingest/unresolved.py, with the rest of 07 S5.5's
lifecycle: carried items as one line, wontfix and blocked-upstream suppressed, a resolved item that reappears
flipped back to open.
"""
import os
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest import unresolved as U  # noqa: E402
from ingest.adapters.base import Unresolved  # noqa: E402
from schema.entities import UnresolvedFile, UnresolvedStatusFile  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

D1 = date(2026, 10, 6)


def item(key='csv:x', observed='claude-opus-4-6_120K', reason='unparseable'):
    return Unresolved(key, 'claim.system', observed, reason, [('system:claude-opus-4-6', 0.8)],
                      'Say whether 120K is a context window or a thinking budget.')


def row(u, status, first=D1, **kw):
    return {'fingerprint': u.fingerprint, 'source_key': u.source_key, 'observed': u.observed, 'field': u.field,
         'status': status, 'first_seen': first, 'last_seen': first, 'occurrences': 1, 'note': kw.get('note'),
         'decided_by': None, 'decided_on': None if status == 'open' else first}


# ---- the done-when ----------------------------------------------------------------------------------------

def test_an_item_appears_in_full_once_then_as_one_carried_line():
    u = item()
    first = U.diff([u], [], D1)
    assert first.new == [u] and '`claude-opus-4-6_120K`' in U.render(first, 'epoch')
    second = U.diff([u], first.rows, D1 + timedelta(days=7))
    body = U.render(second, 'epoch')
    assert second.new == [] and len(second.carried) == 1
    assert 'claude-opus-4-6_120K' not in body                       # not in full again
    assert '**Carried over: 1** (oldest 7 days) -> `data/_ingest/unresolved/epoch/status.yaml`' in body


def test_the_over_90_day_backlog_is_its_own_band():
    old, young, closed = item(observed='old'), item(observed='young'), item(observed='closed')
    rows = [row(old, 'open', D1 - timedelta(days=91)), row(young, 'open', D1 - timedelta(days=90)),
            row(closed, 'wontfix', D1 - timedelta(days=200), note='blank upstream row')]
    d = U.diff([old, young, closed], rows, D1)
    assert [r['observed'] for r in d.backlog()] == ['old']          # 90 days exactly is not over; wontfix is not open
    body = U.render(d, 'epoch')
    assert '**Open over 90 days: 1** (oldest first seen %s)' % (D1 - timedelta(days=91)).isoformat() in body
    assert '**Carried over: 2** (oldest 91 days)' in body           # the band is separate from the carried count


# ---- the rest of the lifecycle ----------------------------------------------------------------------------

def test_a_sighting_moves_last_seen_and_occurrences_but_never_first_seen():
    u = item()
    d = U.diff([u], [row(u, 'open', D1 - timedelta(days=30))], D1)
    r = d.rows[0]
    assert (r['first_seen'], r['last_seen'], r['occurrences']) == (D1 - timedelta(days=30), D1, 2)


def test_wontfix_and_blocked_upstream_are_counted_never_shown():
    w, b = item(observed='blank-row'), item(observed='no-leaderboard')
    rows = [row(w, 'wontfix', note='blank upstream row'), row(b, 'blocked-upstream', note='no public board')]
    d = U.diff([w, b], rows, D1 + timedelta(days=1))
    body = U.render(d, 'epoch')
    assert d.new == d.carried == d.reopened == [] and d.suppressed == {'wontfix': 1, 'blocked-upstream': 1}
    assert 'blank-row' not in body and 'no-leaderboard' not in body
    assert '**Suppressed:** 1 `wontfix` / 1 `blocked-upstream`' in body


def test_a_resolved_item_that_reappears_flips_back_to_open_in_full():
    u = item()
    d = U.diff([u], [row(u, 'resolved', note='alias added')], D1 + timedelta(days=3))
    r = d.rows[0]
    assert d.reopened == [u] and r['status'] == 'open' and r['decided_on'] is None
    assert r['note'].startswith('Reopened %s: it was resolved' % (D1 + timedelta(days=3)).isoformat())
    assert 'Reopened -- a resolution that did not hold (1)' in U.render(d, 'epoch')


def test_an_item_the_run_does_not_see_is_left_alone():
    gone, here = item(observed='gone'), item(observed='here')
    rows = [row(gone, 'open', D1 - timedelta(days=5))]
    d = U.diff([here], rows, D1)
    assert d.rows[0] == rows[0] and [r['observed'] for r in d.rows] == ['gone', 'here']


def test_the_same_item_twice_in_one_run_is_one_sighting():
    u = item()
    d = U.diff([u, u], [], D1)
    assert len(d.new) == 1 and d.rows[0]['occurrences'] == 1


def test_record_writes_a_ledger_the_schema_accepts_and_the_next_run_reads(tmp_path):
    u = item()
    d, body = U.record('demo', [u], D1, str(tmp_path))
    path = U.ledger_path('demo', str(tmp_path))
    rows = UnresolvedStatusFile.model_validate(read_yaml(path)).root
    assert len(rows) == 1 and rows[0].status == 'open'
    assert '&id' not in open(path, encoding='utf-8').read()          # dates are written, not anchored
    d2, body2 = U.record('demo', [u], D1 + timedelta(days=1), str(tmp_path))
    assert d2.carried and 'claude-opus-4-6_120K' not in body2


# ---- the committed ledger ---------------------------------------------------------------------------------

def test_the_epoch_ledger_holds_the_orphans_and_the_first_batch():
    rows = U.load('epoch')
    batch = UnresolvedFile.model_validate(read_yaml(os.path.join(
        ROOT, 'data', '_ingest', 'unresolved', 'epoch', '2026-09-28.yaml'))).root
    by = {r['fingerprint']: r for r in rows}
    assert len(rows) == 35
    assert sum(r['status'] == 'resolved' for r in rows) == 21                   # P3-S2-T04's orphan files
    for b in batch:                                                              # the 2026-09-28 batch, open
        assert by[b.fingerprint]['status'] == 'open' and by[b.fingerprint]['first_seen'] == date(2026, 9, 28)
