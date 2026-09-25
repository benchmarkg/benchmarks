"""Tests for schema/validators.py, the tier-3 semantic rules (P0-S4-T08; 02 S11, 04 S12).

The verify: "a passing and a failing fixture for each of the eight rules, including the blocking
dormant-plus-accepting-submissions combination". The task registers every tier-3 rule 02 S11 and 04
S12 name -- more than eight -- and each has a fixture file under fixtures/semantic/ named for it, with
`pass` cases (no finding), `fail` cases (a blocking finding) and, for the warning-only rules or
branches, `warn` cases (findings, none blocking).

A fixture case is a partial Corpus: each record is an overlay on a small valid base record, so a case
states only what the rule is about.
"""
import copy
import glob
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema import validators as v  # noqa: E402
from schema.baseline import Baseline  # noqa: E402
from schema.benchmark import Benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.entities import IngestBatch  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

HERE = os.path.join(os.path.dirname(__file__), 'fixtures')
FILES = sorted(glob.glob(os.path.join(HERE, 'semantic', '*.yaml')))

BASE = {
    'benchmark': {
        'id': 'example-bench', 'name': 'Example Bench', 'tagline': 'A benchmark used in tests.',
        'domain': {'primary': 'code/repository-scale-se'},
        'learned_entrant_evidence': [{'system': 'Some Model', 'source': 'src-x', 'observed_on': '2026-09-25'}],
        'evaluation_target': 'learned-system', 'data': {'access': 'fully-open'}, 'homepage': 'https://example.org/',
        'curation': {'added_by': 'a-curator', 'added_on': '2026-09-25', 'last_verified': '2026-09-25', 'sources': ['src-x']},
    },
    'claim': {
        'id': 'claim-0123456789ab', 'system': 'example-model', 'benchmark': 'example-bench', 'metric': 'accuracy',
        'value': 0.5, 'date_reported': '2026-09-01', 'reported_by': 'org-x', 'verification': 'self-reported',
        'source': 'src-x',
    },
    'ingestion': {
        'batch': 'ingest-epoch-2026-09-16', 'source_adapter': 'epoch-benchmarks', 'adapter_version': '0.3.1',
        'source_record_id': 'gpqa-diamond:example-model', 'last_seen_upstream': '2026-09-16',
        'source_url': 'https://epoch.ai/data/benchmark_data.zip', 'source_licence': 'CC-BY-4.0',
        'licence_class': 'permissive-attribution', 'source_attribution': 'Epoch AI', 'ingested_at': '2026-09-16T23:14:00Z',
        'extraction_confidence': 1.0,
    },
    'system': {'id': 'example-model', 'name': 'Example Model', 'system_type': 'reasoning-model',
               'availability': 'generally-available', 'sources': ['src-x']},
    'metric': {'id': 'accuracy', 'name': 'Accuracy', 'definition': 'Share of items answered correctly.',
               'value_type': 'ratio', 'optimum': 'max', 'sources': ['src-x']},
    'baseline': {'id': 'base-a', 'benchmark_version': 'example-bench@1', 'kind': 'human-expert-average',
                 'metric': 'accuracy', 'value': 0.8, 'source': 'src-x'},
    'batch': read_yaml(os.path.join(HERE, 'entities', 'ingest-batch-epoch.yaml')),
}


def merge(base, overlay):
    out = copy.deepcopy(base)
    for k, val in (overlay or {}).items():
        out[k] = merge(out[k], val) if isinstance(val, dict) and isinstance(out.get(k), dict) else copy.deepcopy(val)
    return out


def corpus(case) -> v.Corpus:
    c = v.Corpus()
    for o in case.get('benchmarks', []):
        b = Benchmark.model_validate(merge(BASE['benchmark'], o))
        c.benchmarks[b.id] = b
    for o in case.get('conditions', []):
        x = EvalConditions.model_validate(o)
        c.conditions[x.id] = x
    for o in case.get('claims', []):
        o = dict(o)
        path = o.pop('path', 'data/claims/example-bench/c.yaml')
        if 'ingestion' in o:
            o['ingestion'] = merge(BASE['ingestion'], o['ingestion'])
        x = ResultClaim.model_validate(merge(BASE['claim'], o))
        c.claims[x.id], c.paths[x.id] = x, path
    for o in case.get('systems', []):
        x = System.model_validate(merge(BASE['system'], o))
        c.systems[x.id] = x
    for o in case.get('metrics', []):
        x = Metric.model_validate(merge(BASE['metric'], o))
        c.metrics[x.id] = x
    c.baselines = [Baseline.model_validate(merge(BASE['baseline'], o)) for o in case.get('baselines', [])]
    for o in case.get('batches', []):
        o = dict(o)
        path = o.pop('path')
        x = IngestBatch.model_validate(merge(BASE['batch'], o))
        c.batches[x.id], c.paths[x.id] = x, path
    for o in case.get('sources', []):
        c.sources[o['id']] = o
    c.derived = case.get('derived', {})
    c.retired = set(case.get('retired', []))
    c.live_terms = set(case.get('live_terms', []))
    return c


def cases():
    for path in FILES:
        rule_id = os.path.basename(path)[:-5]
        for kind, items in read_yaml(path).items():
            for i, case in enumerate(items):
                yield pytest.param(rule_id, kind, case, id='%s-%s-%d' % (rule_id, kind, i))


def run(rule_id, case):
    return v.validate(corpus(case), case.get('level', 'stub'), only=rule_id)


# ---- the verify ---------------------------------------------------------------------------------

@pytest.mark.parametrize('rule_id, kind, case', list(cases()))
def test_fixture(rule_id, kind, case):
    findings = run(rule_id, case)
    assert all(f.rule == rule_id for f in findings)
    if kind == 'pass':
        assert findings == [], [str(f) for f in findings]
    elif kind == 'fail':
        assert v.blocking(findings), 'expected a blocking finding, got %s' % [str(f) for f in findings]
    elif kind == 'warn':
        assert findings and not v.blocking(findings), [str(f) for f in findings]
    else:
        raise AssertionError('unknown fixture kind %s' % kind)


def test_every_rule_has_a_fixture_file_and_every_file_names_a_rule():
    assert sorted(os.path.basename(p)[:-5] for p in FILES) == sorted(v.RULES)


@pytest.mark.parametrize('path', FILES, ids=[os.path.basename(p) for p in FILES])
def test_every_rule_has_a_passing_and_a_failing_fixture(path):
    doc = read_yaml(path)
    assert doc.get('pass'), 'no passing fixture'
    assert doc.get('fail') or doc.get('warn'), 'no failing fixture'


def test_the_rules_the_task_names_are_all_registered():
    for r in ('lifecycle-triple', 'contamination-evidence', 'contaminated-lifecycle', 'judge-model', 'reference-grader',
              'headroom-guard-4', 'one-primary-baseline', 'licence-placement', 'retired-id-ledger'):
        assert r in v.RULES, r


def test_dormant_plus_accepting_submissions_is_blocking():
    findings = run('lifecycle-triple', {'benchmarks': [{'lifecycle': 'dormant', 'activity': 'accepting-submissions'}]})
    assert [f.severity for f in findings] == ['blocking']
    assert 'dormant' in findings[0].message


# ---- details the fixtures do not show -----------------------------------------------------------

@pytest.mark.parametrize('rule_id, case', [
    ('private-server-blocker', {'benchmarks': [{'data': {'access': 'private-test-server'}}]}),
    ('unreleasable-blocker', {'benchmarks': [{'data': {'data_provenance': ['unreleasable-confidential']}}]}),
    ('wet-lab-execution', {'benchmarks': [{'execution': {'compute_tier': 'wet-lab'}}]}),
    ('no-harness-blocker', {'benchmarks': [{'execution': {'harness_availability': 'none'}}]}),
    ('rating-pool-required', {'benchmarks': [{'evaluation_method': ['tournament-play']}]}),
])
def test_auto_fix_rules_propose_the_value_and_never_write_it(rule_id, case):
    c = corpus(case)
    before = c.benchmarks['example-bench'].model_dump()
    findings = v.validate(c, only=rule_id)
    assert findings and all(f.auto_fix for f in findings)
    assert c.benchmarks['example-bench'].model_dump() == before


def test_a_missing_derived_value_is_neither_a_pass_nor_a_failure():
    # No derived headroom: guard 4 says nothing. No derived maintenance_status: only the lifecycle half runs.
    assert run('headroom-guard-4', {'benchmarks': [{'evaluation_method': ['ordinal-grading']}]}) == []
    assert run('lifecycle-triple', {'benchmarks': [{'lifecycle': 'active', 'activity': 'accepting-submissions'}]}) == []


def test_the_subset_warning_names_the_dropped_terms():
    f = run('subset-drops-terms', {'benchmarks': [{'capability': ['planning', 'knowledge-recall'],
                                                   'subsets': [{'id': 'example-bench#a', 'label': 'A',
                                                                'capability_override': ['planning']}]}]})
    assert 'knowledge-recall' in f[0].message


def test_findings_render_with_severity_rule_and_fix():
    f = v.Finding('rating-pool-required', 'blocking', 'roboarena', 'm', 'comparability.rating_pool_required = true')
    assert str(f) == 'BLOCKING rating-pool-required roboarena: m [auto-fix offered: comparability.rating_pool_required = true]'


def test_the_repository_corpus_loads_and_every_rule_runs():
    c = v.load_corpus()
    assert set(c.benchmarks) == {'casp', 'roboarena', 'swe-bench'}
    findings = v.validate(c, 'full')
    assert all(f.rule in v.RULES and f.severity in ('blocking', 'warning') for f in findings)


def test_the_cli_exits_non_zero_on_a_blocking_finding(tmp_path, capsys):
    import shutil
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), tmp_path / 'taxonomy')
    (tmp_path / 'data' / 'benchmarks').mkdir(parents=True)
    import json
    doc = merge(BASE['benchmark'], {'lifecycle': 'dormant', 'activity': 'accepting-submissions'})
    (tmp_path / 'data' / 'benchmarks' / 'example-bench.yaml').write_text(json.dumps(doc), encoding='utf-8')
    assert v.main(['--root', str(tmp_path)]) == 1
    assert 'BLOCKING lifecycle-triple example-bench' in capsys.readouterr().out
    doc['lifecycle'] = 'active'
    (tmp_path / 'data' / 'benchmarks' / 'example-bench.yaml').write_text(json.dumps(doc), encoding='utf-8')
    assert v.main(['--root', str(tmp_path)]) == 0
