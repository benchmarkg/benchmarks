"""Tests for scripts/check_warnings_triaged.py and data/_analysis/warning-triage.yaml (P1-S13-T04; 04 S12).

The verify: `bench validate --tier all --json | python scripts/check_warnings_triaged.py`. Done when "Zero
validation errors and every remaining warning has a recorded triage decision." The synthetic cases hand the
check a report, so they test the triage rules without the validator; the last case runs the validator over the
repository.
"""
import datetime as dt
import io
import json
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_warnings_triaged as C  # noqa: E402

TODAY = dt.date(2026, 11, 17)
SUBSET = 'alpha#full replaces capability with fewer terms, dropping sample-efficiency: confirm the drop'


def finding(rule, entity, message='a signal', tier=4, severity='quality'):
    return {'tier': tier, 'tier_name': 'quality', 'rule': rule, 'severity': severity, 'entity': entity,
            'path': None, 'message': message, 'auto_fix': None, 'related': [entity]}


def report(*found, blocking=0):
    return {'tiers': ['schema', 'ref', 'semantic', 'quality'], 'scope': 'all', 'files': 1, 'exit_code': 1 if blocking
            else 0, 'blocking': blocking, 'findings': list(found)}


def row(rule, lines, decision='accepted', **over):
    out = {'rule': rule, 'decision': decision, 'reason': 'The signal is right and stays.',
           'decided_by': 'a curator', 'decided_on': dt.date(2026, 11, 1), 'findings': lines}
    out.update(over)
    return {k: v for k, v in out.items() if v is not None}


def triage(root, rows):
    path = root / 'data' / '_analysis' / 'warning-triage.yaml'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({'version': 1, 'decisions': rows}, sort_keys=False), encoding='utf-8')
    return C.load(str(root))[0]


def run(tmp_path, rows, rep, strict=False):
    return C.check(rep, triage(tmp_path, rows), TODAY, strict)


def test_every_finding_triaged_passes(tmp_path):
    rep = report(finding('no-baseline', 'alpha'), finding('subset-drops-terms', 'alpha', SUBSET, 3, 'warning'))
    rows = [row('no-baseline', [{'entity': 'alpha'}], 'deferred', owner='P3-S6'),
            row('subset-drops-terms', [{'entity': 'alpha', 'detail': 'alpha#full capability: sample-efficiency',
                                        'note': 'The full split has no budget.'}])]
    errs, resolved, tally = run(tmp_path, rows, rep)
    assert errs == [] and resolved == []
    assert tally['4/no-baseline'] == {'findings': 1, 'deferred': 1}
    assert tally['3/subset-drops-terms'] == {'findings': 1, 'accepted': 1}


def test_an_untriaged_warning_fails(tmp_path):
    rep = report(finding('no-baseline', 'alpha'), finding('no-baseline', 'beta', 'no baseline record'))
    errs, _, tally = run(tmp_path, [row('no-baseline', [{'entity': 'alpha'}])], rep)
    assert errs == ['untriaged: no-baseline beta: no baseline record'] and tally['4/no-baseline']['untriaged'] == 1


def test_a_blocking_finding_fails_even_when_every_warning_is_triaged(tmp_path):
    rep = report(finding('schema', 'alpha', 'bad enum', 1, 'blocking'), blocking=1)
    errs, _, _ = run(tmp_path, [row('no-baseline', [{'entity': 'gamma'}])], rep)
    assert errs[0].startswith('1 blocking finding(s)') and 'bad enum' in errs[1]


def test_a_changed_subject_is_triaged_afresh(tmp_path):
    """A decision confirms one drop: when the subset drops another term the old line no longer matches."""
    moved = SUBSET.replace('sample-efficiency', 'perception, sample-efficiency')  # the validator sorts them
    rep = report(finding('subset-drops-terms', 'alpha', moved, 3, 'warning'))
    rows = [row('subset-drops-terms', [{'entity': 'alpha', 'detail': 'alpha#full capability: sample-efficiency'}])]
    errs, resolved, _ = run(tmp_path, rows, rep)
    assert errs == ['untriaged: subset-drops-terms alpha [alpha#full capability: perception, sample-efficiency]: '
                    + moved]
    assert resolved == [('subset-drops-terms', 'alpha', 'alpha#full capability: sample-efficiency')]


def test_a_resolved_line_is_listed_and_fails_only_when_strict(tmp_path):
    rows = [row('tagline-length', [{'entity': 'alpha'}])]
    errs, resolved, _ = run(tmp_path, rows, report())
    assert errs == [] and resolved == [('tagline-length', 'alpha', None)]
    errs, _, _ = run(tmp_path, rows, report(), strict=True)
    assert errs == ['resolved, still listed: tagline-length alpha (drop the line from %s)' % C.TRIAGE]


@pytest.mark.parametrize('over, message', [
    ({'decision': 'ignored'}, "decision 'ignored' is not one of accepted, deferred"),
    ({'decision': 'deferred'}, 'a deferral names its owner'),
    ({'reason': ' '}, 'no reason'),
    ({'decided_by': None}, 'keys must be'),
    ({'decided_by': ''}, 'no decided_by'),
    ({'decided_on': '2026-11'}, 'is not a date'),
    ({'decided_on': dt.date(2026, 12, 1)}, 'is after today'),
    ({'findings': []}, '`findings` lists the lines'),
    ({'suppress': True}, 'keys must be'),
])
def test_a_malformed_row_fails(tmp_path, over, message):
    errs, _, _ = run(tmp_path, [row('no-baseline', [{'entity': 'alpha'}], **over)],
                     report(finding('no-baseline', 'alpha')))
    assert any(message in e for e in errs), errs


@pytest.mark.parametrize('rule, line, message', [
    ('subset-drops-terms', {'entity': 'alpha'}, 'rule subset-drops-terms lines carry a detail'),
    ('no-baseline', {'entity': 'alpha', 'detail': 'x'}, 'rule no-baseline lines carry no detail'),
    ('no-baseline', {'entity': 'alpha', 'why': 'x'}, 'a line is {entity, optionally detail and note}'),
    ('no-baseline', 'alpha', 'a line is {entity, optionally detail and note}'),
])
def test_a_malformed_line_fails(tmp_path, rule, line, message):
    errs, _, _ = run(tmp_path, [row(rule, [line])], report())
    assert any(message in e for e in errs), errs


def test_a_line_is_triaged_once(tmp_path):
    rows = [row('no-baseline', [{'entity': 'alpha'}]), row('no-baseline', [{'entity': 'alpha'}], 'deferred',
                                                           owner='P4-S2-T05')]
    errs, _, _ = run(tmp_path, rows, report(finding('no-baseline', 'alpha')))
    assert errs == ['%s decisions[1] (no-baseline) findings[0]: no-baseline alpha is already triaged by '
                    'decisions[0]' % C.TRIAGE]


@pytest.mark.parametrize('rule, message, want', [
    ('subset-drops-terms', SUBSET, 'alpha#full capability: sample-efficiency'),
    ('material-waived', 'material fields waived: shots (No prompt (none) at all.), chain_of_thought (No text.)',
     'shots, chain_of_thought'),
    ('private-server-submission', "access private-test-server with submission_process ['sandboxed-rerun', "
     "'maintainer-run']: possible, and worth a note", 'maintainer-run, sandboxed-rerun'),
    ('private-server-submission', 'access private-test-server with submission_process unset: possible', 'unset'),
    ('unarchived-source', 'archive_status failed: gave up after 5 runs; last: x: y', 'failed'),
    ('unarchived-source', 'archive_status pending', 'pending'),
    ('no-baseline', 'no baseline record, and so no value_absent_reason either', None),
])
def test_the_detail_of_a_finding(rule, message, want):
    assert C.detail(finding(rule, 'alpha', message)) == want


def test_no_triage_file_fails(tmp_path):
    assert C.load(str(tmp_path)) == (None, ['%s does not exist' % C.TRIAGE])


def test_main_reads_the_report_on_stdin(tmp_path, monkeypatch, capsys):
    triage(tmp_path, [row('no-baseline', [{'entity': 'alpha'}])])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(report(finding('no-baseline', 'alpha')))))
    assert C.main(['--root', str(tmp_path), '--today', '2026-11-17', '--markdown']) == 0
    out = capsys.readouterr().out
    assert '| 4/no-baseline | 1 | 1 | 0 | 0 |' in out and out.rstrip().endswith('0 triaged line(s) resolved since')
    monkeypatch.setattr(sys, 'stdin', io.StringIO('not json'))
    assert C.main(['--root', str(tmp_path)]) == 2


def test_the_repository_passes():
    from tools.validate import tiers
    rep = tiers.run(ROOT, 'all', today=TODAY).as_dict()
    rows, errs = C.load(ROOT)
    assert errs == []
    errs, _, tally = C.check(rep, rows, TODAY)
    assert errs == []
    assert sum(c['findings'] for c in tally.values()) == len([f for f in rep['findings']
                                                              if f['severity'] in C.TRIAGED])
