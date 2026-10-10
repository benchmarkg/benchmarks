"""The prioritised re-verification queue: `bench report staleness` (P5-S7-T05; 05 S7).

The verify: `bench report staleness --format json` against tests/fixtures/corpus/ matches
tests/golden/reverification.json. Done when "Ordering matches the formula on a fixture corpus and the weekly issue
body matches its golden file". So:

  - the formula and its weights are 05 S7's, read against the plan's own block, and every lifecycle term in
    taxonomy/lifecycle.yaml has a weight (a new term fails the report rather than defaulting);
  - on the fixture corpus, every row's priority is recomputed here from its inputs, the order is by priority and
    not by age, and the json and the issue body are byte-identical to their golden files;
  - each attention input is read where 05 says: the latest analytics month on or before as_of, open disputes
    only, a published suite manifest; and --critical keeps only the active entries past 730 days;
  - freshness.yml runs weekly at 7 8 * * 1, inert until its variable is on, and renders the issue with the CLI.
"""
import json
import math
import os
import re
import shutil
from datetime import date

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from tools import cli
from tools.report import render
from tools.report import reverification as Q

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(ROOT, 'tests', 'fixtures', 'corpus')
GOLDEN = os.path.join(ROOT, 'tests', 'golden')
AS_OF = '2026-10-09'


def bench(*args):
    r = CliRunner().invoke(cli.app, ['report', 'staleness', '--root', CORPUS, '--as-of', AS_OF, *args])
    assert r.exit_code == 0, r.output
    return r.output


def golden(name):
    with open(os.path.join(GOLDEN, name), encoding='utf-8', newline='') as f:
        return f.read()


@pytest.fixture(scope='module')
def report():
    return Q.build(CORPUS, date.fromisoformat(AS_OF))


# ---- the formula is the plan's ----------------------------------------------------------------------------------

def test_the_weights_are_05_s7s():
    with open(os.path.join(ROOT, '_plan', '05-repository-and-workflow.md'), encoding='utf-8') as f:
        s7 = f.read().split('## 7. Freshness', 1)[1].split('\n## ', 1)[0]
    assert 'priority = staleness_days × volatility_weight × attention_weight' in s7
    line = re.search(r'volatility_weight:\s*(.*)', s7).group(1)
    named = dict((k, float(v)) for k, v in re.findall(r'([a-z-]+) ([0-9.]+)', line))
    assert named == {'active': 1.0, 'saturated': 0.6, 'deprecated': 0.3, 'dead': 0.2, 'retracted': 0.1}
    assert {k: Q.VOLATILITY[k] for k in named if k != 'dead'} == {k: v for k, v in named.items() if k != 'dead'}
    assert Q.VOLATILITY['dormant'] == named['dead']                 # the vocabulary has dormant, not dead
    assert 'attention_weight:   1 + log10(1 + pageviews_30d)' in s7
    assert '× %.1f if the entry is cited in any published suite manifest' % Q.SUITE_FACTOR in s7
    assert '× %.1f if any claim on it is disputed' % Q.DISPUTE_FACTOR in s7


def test_every_lifecycle_term_has_a_weight_and_a_new_one_fails_the_report(tmp_path):
    terms = Q.lifecycle_terms(ROOT)
    assert len(terms) == 10 and set(terms) == set(Q.VOLATILITY)
    shutil.copytree(os.path.join(CORPUS, 'data'), tmp_path / 'data')
    (tmp_path / 'taxonomy').mkdir()
    yaml = YAML()
    with open(os.path.join(ROOT, 'taxonomy', 'lifecycle.yaml'), encoding='utf-8') as f:
        doc = yaml.load(f)
    doc['terms'].append({'id': 'mothballed', 'label': 'Mothballed', 'field': 'lifecycle'})
    with open(tmp_path / 'taxonomy' / 'lifecycle.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(doc, f)
    with pytest.raises(Q.ReportError, match='mothballed'):
        Q.build(str(tmp_path), date.fromisoformat(AS_OF))


# ---- the ordering on the fixture corpus -------------------------------------------------------------------------

def test_every_priority_is_the_formula_over_its_inputs(report):
    for r in report['rows']:
        att = (1 + math.log10(1 + r['pageviews_30d'])) * (1.5 if r['in_suite'] else 1) * (2 if r['disputed'] else 1)
        assert r['attention_weight'] == pytest.approx(att)
        assert r['priority'] == pytest.approx(r['staleness_days'] * r['volatility_weight'] * att, abs=1e-4)


def test_the_queue_is_ordered_by_priority_not_by_age(report):
    rows = report['rows']
    assert [r['id'] for r in rows] == ['beta', 'alpha', 'gamma', 'delta', 'zeta', 'theta', 'eta', 'iota', 'epsilon']
    assert [r['priority'] for r in rows] == sorted((r['priority'] for r in rows), reverse=True)
    assert [r['rank'] for r in rows] == list(range(1, 10))
    by_age = sorted(rows, key=lambda r: -r['staleness_days'])
    assert by_age[0]['id'] == 'zeta' and rows[0]['id'] == 'beta'      # oldest-first would put zeta first


def test_the_json_report_matches_its_golden_file():
    assert bench('--format', 'json') == golden('reverification.json')


def test_the_weekly_issue_body_matches_its_golden_file():
    assert bench('--issue') == golden('reverification-issue.md')


def test_the_report_is_deterministic(report):
    assert render(report, 'json') == render(Q.build(CORPUS, date.fromisoformat(AS_OF)), 'json')


# ---- each input, read where 05 says -----------------------------------------------------------------------------

def rows(report):
    return {r['id']: r for r in report['rows']}


def test_pageviews_are_the_latest_month_on_or_before_as_of_and_only_the_entrys_own_pages(report):
    r = rows(report)
    assert report['summary']['analytics_month'] == '2026-09'
    assert r['beta']['pageviews_30d'] == 999            # its page and the page under it; /benchmarks/betamax/ is not
    assert r['alpha']['pageviews_30d'] == 0             # 2026-11 is after as_of
    assert r['delta']['pageviews_30d'] == 0             # 2026-08 is superseded by 2026-09


def test_with_no_analytics_committed_attention_is_one_and_the_report_says_why(tmp_path):
    shutil.copytree(os.path.join(CORPUS, 'data'), tmp_path / 'data')
    rep = Q.build(str(tmp_path), date.fromisoformat(AS_OF))
    assert rep['summary']['analytics_month'] is None and 'no analytics' in rep['summary']['analytics_note']
    assert all(r['pageviews_30d'] == 0 for r in rep['rows'])


def test_only_an_open_dispute_makes_an_entry_disputed(report):
    r = rows(report)
    assert r['epsilon']['disputed'] and r['epsilon']['attention_weight'] == pytest.approx(6.0)
    assert not r['iota']['disputed']                    # its only dispute was resolved


def test_a_published_suite_manifest_raises_its_entries(report):
    r = rows(report)
    assert r['gamma']['in_suite'] and r['gamma']['attention_weight'] == pytest.approx(3.0)    # listed as gamma@v2
    assert report['summary']['suite_manifests'] == 1


def test_stubs_are_never_queued(report):
    assert 'stub' not in rows(report)


def test_critical_keeps_only_active_entries_past_730_days():
    doc = json.loads(bench('--critical', '--format', 'json'))
    assert [r['id'] for r in doc['rows']] == ['alpha']
    assert doc['report'] == 'staleness --critical' and doc['summary']['critical'] == 1
    assert not rows(Q.build(CORPUS, date.fromisoformat(AS_OF)))['delta']['critical']   # 1377 days, but deprecated


def test_the_other_reports_refuse_the_staleness_options():
    r = CliRunner().invoke(cli.app, ['report', 'quality', '--critical'])
    assert r.exit_code == 2


def test_the_repository_itself_reports(tmp_path):
    # The report's own default, the data commit's date: a fixed AS_OF falls behind the corpus, and an entry
    # verified after it would count negative days (P1-S3-T01's entries, verified 2026-10-10).
    rep = Q.build(ROOT)
    assert rep['summary']['entries'] == len(rep['rows']) > 0
    assert all(r['priority'] >= 0 for r in rep['rows'])


# ---- the weekly workflow ----------------------------------------------------------------------------------------

def test_freshness_yml_opens_the_weekly_issue_from_the_cli():
    with open(os.path.join(ROOT, '.github', 'workflows', 'freshness.yml'), encoding='utf-8') as f:
        wf = YAML(typ='safe', pure=True).load(f)
    on = wf['on']
    assert on['schedule'] == [{'cron': '7 8 * * 1'}] and 'workflow_dispatch' in on
    job = wf['jobs']['reverification']
    assert "vars.FRESHNESS_SCHEDULE == 'on'" in job['if']               # inert while Actions are off
    assert wf['permissions'] == {'contents': 'read', 'issues': 'write'}
    script = '\n'.join(s.get('run', '') for s in job['steps'])          # get-default: a `uses:` step has no run
    assert 'bench report staleness --issue' in script and '--label reverification' in script
    assert 'staleness-critical' in script
    assert all(re.search(r'@[0-9a-f]{40} ', s['uses'] + ' ') for s in job['steps'] if 'uses' in s)
