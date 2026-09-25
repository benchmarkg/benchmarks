"""Tests for taxonomy/crosswalks/*.yaml (P0-S4-T09; 02 S5, 03 S2, 04 S8, 06 S3).

The verify: "every ours: key resolves to a real field path on the Pydantic models (not the generated
JSON Schema, which does not exist until P0-S5-T01), every hf-tags row carries source: hf_space_tag,
and pwc.yaml contains no free-text field".

`resolve()` walks the models themselves: a dotted path from a root entity (`EvalConditions.sampling.
temperature`), through nested models, lists and optionals, to a declared or computed field. The
vocabulary a row names (`ours_values`, `candidates`) is checked against the Literal that field
carries, which the models build from taxonomy/ at import time.
"""
import os
import re
import sys
import typing

import pytest
from pydantic import BaseModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.baseline import Baseline  # noqa: E402
from schema.benchmark import CROISSANT_TERMS, Benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.dispute import Dispute  # noqa: E402
from schema.entities import (Alias, BenchmarkVersion, IngestBatch, Leaderboard, Organization,  # noqa: E402
                             RatingPool, Subset)
from schema.metric import Metric  # noqa: E402
from schema.source import Source  # noqa: E402
from schema.system import System, SystemVersion  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

CROSSWALKS = os.path.join(ROOT, 'taxonomy', 'crosswalks')
NAMES = ['croissant', 'eee', 'helm', 'hf-tags', 'inspect-evals', 'pwc']
ENTITIES = {m.__name__: m for m in (Alias, Baseline, Benchmark, BenchmarkVersion, Dispute, EvalConditions,
                                    IngestBatch, Leaderboard, Metric, Organization, RatingPool, ResultClaim,
                                    Source, Subset, System, SystemVersion)}
FAMILIES = {t['id'] for t in read_yaml(os.path.join(ROOT, 'taxonomy', 'domains.yaml'))['terms'] if not t.get('parent')}


class Unresolved(LookupError):
    pass


def _args(tp):
    """Every type inside an annotation: through Optional, Union, list, dict values and Annotated."""
    origin = typing.get_origin(tp)
    if origin is typing.Annotated:
        return _args(typing.get_args(tp)[0])
    if origin is None:
        return [tp]
    if origin is typing.Literal:
        return [tp]
    out = []
    for a in typing.get_args(tp):
        out += _args(a)
    return out


def resolve(path: str):
    """The annotation at `path`, or Unresolved naming the first segment that does not exist."""
    root, *segments = path.split('.')
    if root not in ENTITIES or not segments:
        raise Unresolved('%s: no entity %s' % (path, root))
    models = [ENTITIES[root]]
    annotation = None
    for i, seg in enumerate(segments):
        name = seg[:-2] if seg.endswith('[]') else seg
        hit = None
        for m in models:
            if name in m.model_fields:
                hit = m.model_fields[name].annotation
            elif name in m.model_computed_fields:
                hit = m.model_computed_fields[name].return_type
            if hit is not None:
                break
        if hit is None:
            raise Unresolved('%s: %s has no field %s' % (path, '.'.join([root] + segments[:i]) or root, name))
        annotation = hit
        models = [a for a in _args(hit) if isinstance(a, type) and issubclass(a, BaseModel)]
        if i < len(segments) - 1 and not models:
            raise Unresolved('%s: %s is not a nested model' % (path, name))
    return annotation


def vocabulary(annotation) -> set[str] | None:
    """The Literal values a field accepts, or None when it is not a closed vocabulary."""
    values = [v for a in _args(annotation) if typing.get_origin(a) is typing.Literal for v in typing.get_args(a)]
    return set(values) if values else None


def load(name):
    return read_yaml(os.path.join(CROSSWALKS, name + '.yaml'))


def rows(name):
    doc = load(name)
    if name == 'inspect-evals':
        return doc['registry'] + doc['log']
    return doc['rows']


ALL_ROWS = [(n, i, r) for n in NAMES for i, r in enumerate(rows(n))]


# ---- the verify ---------------------------------------------------------------------------------

def test_the_six_crosswalks_exist():
    assert sorted(f[:-5] for f in os.listdir(CROSSWALKS) if f.endswith('.yaml')) == NAMES
    for n in NAMES:
        assert load(n)['crosswalk'] == n


@pytest.mark.parametrize('name, i, row', ALL_ROWS, ids=['%s-%d' % (n, i) for n, i, _ in ALL_ROWS])
def test_every_ours_key_resolves_to_a_live_model_field(name, i, row):
    resolve(row['ours'])


def test_resolution_reads_the_pydantic_models_not_a_generated_schema():
    # P0-S5-T01 generates schema/generated/; nothing here may depend on it.
    assert resolve('EvalConditions.sampling.temperature') == (float | None)
    assert resolve('Benchmark.execution.inspect_evals_available') is bool          # a computed field
    assert resolve('Metric.higher_is_better') == (bool | None)


@pytest.mark.parametrize('path', [
    'EvalConditions.shot_count',                 # a misspelling
    'Benchmark.data.licence',                    # 06 S3.2 names it; the model does not have it
    'Benchmark.external_ids.arxiv',              # likewise
    'Benchmark.name.first',                      # a scalar has no fields
    'HumanBaseline.value',                       # a renamed entity
    'Benchmark',                                 # an entity is not a field
])
def test_a_path_that_does_not_exist_is_refused(path):
    with pytest.raises(Unresolved):
        resolve(path)


def test_every_hf_tags_row_carries_source_hf_space_tag():
    for r in rows('hf-tags'):
        assert r.get('source') == 'hf_space_tag', r


def test_hf_tags_cover_the_four_namespaces():
    namespaces = {r['tag'].split(':')[0] for r in rows('hf-tags')}
    assert namespaces == {'test', 'submission', 'judge', 'eval'}
    for r in rows('hf-tags'):
        assert re.fullmatch(r'(test|submission|judge|eval):[a-z-]+', r['tag']), r['tag']


FREE_TEXT_KEYS = {'note', 'notes', 'description', 'definition', 'label', 'text', 'comment', 'rationale', 'summary'}
TOKEN = re.compile(r'^[A-Za-z0-9._:/-]{1,80}$')          # 06 S3.9's rule for data/_crosswalk/*.csv


def _scalars(node, path=''):
    if isinstance(node, dict):
        for k, v in node.items():
            yield path + '.' + str(k), str(k), None
            yield from _scalars(v, path + '.' + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _scalars(v, '%s[%d]' % (path, i))
    else:
        yield path, None, node


def free_text(doc) -> list[str]:
    bad = []
    for path, key, value in _scalars(doc):
        if key is not None and key in FREE_TEXT_KEYS:
            bad.append('%s: a free-text key' % path)
        elif isinstance(value, str) and not TOKEN.match(value):
            bad.append('%s: %r is free text' % (path, value))
    return bad


def test_pwc_contains_no_free_text_field():
    assert free_text(load('pwc')) == []


@pytest.mark.parametrize('doc', [
    {'rows': [{'theirs': 'id', 'note': 'x'}]},
    {'rows': [{'theirs': 'id', 'description': 'Question answering over tables.'}]},
    {'counterpart': 'Papers with Code'},                              # a space is prose
    {'rows': [{'theirs': 'x' * 81}]},
])
def test_the_free_text_check_catches_prose(doc):
    assert free_text(doc)


# ---- the vocabulary each row names --------------------------------------------------------------

@pytest.mark.parametrize('name, i, row', ALL_ROWS, ids=['%s-%d' % (n, i) for n, i, _ in ALL_ROWS])
def test_every_named_term_is_in_the_fields_vocabulary(name, i, row):
    terms = list(row.get('ours_values') or []) + list(row.get('candidates') or [])
    if not terms:
        return
    if row.get('value_kind') == 'domain-family':
        assert set(terms) <= FAMILIES, set(terms) - FAMILIES
        return
    vocab = vocabulary(resolve(row['ours']))
    assert vocab is not None, '%s is not a closed vocabulary' % row['ours']
    assert set(terms) <= vocab, set(terms) - vocab


# ---- each file's posture ------------------------------------------------------------------------

def test_helm_is_ancestry_never_equivalence():
    assert load('helm')['relation'] == 'ancestry'
    for r in rows('helm'):
        assert r['relation'] == 'ancestry', r
        assert 'fidelity' not in r and 'equivalent' not in r and 'theirs' not in r, r
        assert r['kind'] in ('project', 'scenario', 'metric', 'field'), r
    projects = {r['helm'] for r in rows('helm') if r['kind'] == 'project'}
    assert projects == {'Capabilities', 'Safety', 'VHELM', 'HEIM', 'ToRR', 'MedHELM', 'AudioHELM'}   # 03 S2


def test_eee_carries_04_s8s_one_to_one_rows():
    got = {(r['ours'], r['theirs']) for r in rows('eee') if r['fidelity'] == 'one-to-one'}
    for pair in [('EvalConditions.sampling.temperature', 'generation_config.generation_args.temperature'),
                 ('EvalConditions.sampling.top_p', 'generation_config.generation_args.top_p'),
                 ('EvalConditions.max_output_tokens', 'generation_config.generation_args.max_tokens'),
                 ('EvalConditions.tools_allowed', 'agentic_eval_config.available_tools'),
                 ('EvalConditions.message_limit', 'eval_limits.message_limit'),
                 ('EvalConditions.token_limit', 'eval_limits.token_limit'),
                 ('Benchmark.external_ids.every_eval_ever', 'evaluation_name')]:
        assert pair in got, pair


def test_eee_fidelity_is_coherent():
    for r in rows('eee'):
        assert r['fidelity'] in ('one-to-one', 'lossy', 'one-way-hint', 'unmappable', 'unconfirmed'), r
        if r['theirs'] is None:
            assert r['fidelity'] in ('unmappable', 'lossy', 'unconfirmed'), r
        if r['fidelity'] == 'unmappable':
            assert r['theirs'] is None, r
    assert any(r['ours'] == 'EvalConditions.judge_model' and r['fidelity'] == 'unmappable' for r in rows('eee'))


def test_croissant_agrees_with_the_serialiser():
    assert {r['ours'].split('.', 1)[1]: r['theirs'] for r in rows('croissant')} == CROISSANT_TERMS


def test_inspect_evals_rows_carry_13_s4_4s_partition():
    for r in load('inspect-evals')['log']:
        assert r['class'] in ('run-fact', 'entry-fact', 'absence-answerable'), r
        assert r['ours'].startswith('EvalConditions.'), r
        if r['class'] == 'entry-fact':
            assert r['theirs'] is None, r                  # the log never answers an entry fact
    classes = {r['ours'].split('.')[1]: r['class'] for r in load('inspect-evals')['log']}
    assert classes['training_data_policy'] == 'entry-fact'
    assert classes['provider_snapshot'] == 'absence-answerable'


def test_pwc_output_is_06s_four_columns():
    doc = load('pwc')
    assert doc['columns'] == ['our_id', 'pwc_id', 'match_method', 'match_score']
    assert doc['match_methods'] == ['exact-name', 'hf-paperswithcode-id', 'arxiv-id', 'manual']
    for r in rows('pwc'):
        assert r['match_method'] in doc['match_methods'] and r['use'] in ('stored', 'match-only'), r
    stored = {r['ours'] for r in rows('pwc') if r['use'] == 'stored'}
    assert stored == {'Benchmark.external_ids.papers_with_code'}                  # an identifier and nothing else


def test_every_crosswalk_says_whether_it_was_verified():
    for n in NAMES:
        doc = load(n)
        assert isinstance(doc['verified'], bool) and doc['counterpart_licence'], n
