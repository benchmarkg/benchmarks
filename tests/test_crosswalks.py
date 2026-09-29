"""Tests for taxonomy/crosswalks/*.yaml (P0-S4-T09; 02 S5, 03 S2, 04 S8, 06 S3).

The verify: "every ours: key resolves to a real field path on the Pydantic models (not the generated
JSON Schema, which does not exist until P0-S5-T01), every hf-tags row carries source: hf_space_tag,
and pwc.yaml contains no free-text field".

`resolve()` (schema/paths.py) walks the models themselves: a dotted path from a root entity (`EvalConditions.sampling.
temperature`), through nested models, lists and optionals, to a declared or computed field. The
vocabulary a row names (`ours_values`, `candidates`) is checked against the Literal that field
carries, which the models build from taxonomy/ at import time.
"""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import CROISSANT_TERMS  # noqa: E402
from schema.paths import Unresolved, resolve, vocabulary  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

CROSSWALKS = os.path.join(ROOT, 'taxonomy', 'crosswalks')
NAMES = ['croissant', 'eee', 'helm', 'hf-tags', 'inspect-evals', 'pwc']
FAMILIES = {t['id'] for t in read_yaml(os.path.join(ROOT, 'taxonomy', 'domains.yaml'))['terms'] if not t.get('parent')}


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
    'Benchmark.external_ids.doi',                # a key the fixed set does not have
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
    assert {'test', 'submission', 'judge', 'eval'} <= namespaces
    for r in rows('hf-tags'):
        assert re.fullmatch(r'([a-z]+:)?([a-z-]+|\*)', r['tag']), r['tag']


# ---- hf-tags: every observed namespace, and nothing written directly (P5-S1-T01) ---------------

SPACES = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'hf-hub', 'spaces-leaderboard.json')
HF_USES = {'suggested', 'match-only', 'drop'}          # there is no direct write


def namespace(tag: str) -> str:
    return tag.split(':', 1)[0] if ':' in tag else '_free'


def fixture_tags() -> list[list[str]]:
    import json
    with open(SPACES, encoding='utf-8') as fh:
        return [s['tags'] for s in json.load(fh)]


def normalise_language(value: str, rule: dict) -> list[str]:
    """normalise.language as hf-tags.yaml states it -- the reference the adapter (P5-S1-T04) matches."""
    out = []
    for part in value.split(rule['split_on']):
        v = part.strip().casefold()
        v = rule['aliases'].get(v, v)                # get-default: most values have no alias
        if v and v not in rule['not_a_language']:
            out.append(v.title())
    return out


def test_every_observed_namespace_is_declared():
    declared = load('hf-tags')['namespaces']
    seen = {namespace(t) for tags in fixture_tags() for t in tags}
    assert seen <= set(declared), seen - set(declared)
    for ns in ('test', 'submission', 'judge', 'eval', 'modality', 'language', 'domain'):   # 06 S3.2's table
        assert ns in declared, ns


def test_every_namespace_maps_to_a_field_or_is_dropped():
    for ns, d in load('hf-tags')['namespaces'].items():
        assert d['use'] in HF_USES, ns
        if d['use'] == 'drop':
            assert d['drop_reason'] and 'ours' not in d, ns
        else:
            assert d['ours'], ns
            for path in d['ours']:
                resolve(path)


def test_nothing_maps_directly_onto_a_facet():
    doc = load('hf-tags')
    for r in doc['rows']:
        d = doc['namespaces'][namespace(r['tag'])]
        assert r['use'] == d['use'] and r['use'] in HF_USES - {'drop'}, r
        assert r['ours'] in d['ours'], r
        if r['use'] == 'suggested':                  # a hint, stamped and caveated (06 S1.1, S3.2)
            assert r['source'] == 'hf_space_tag' and r['caveat'] in doc['caveats'], r
        else:                                        # a join key is an identifier, never a facet
            assert not r['ours'].split('.')[1] in ('domain', 'capability', 'evaluation_method', 'data',
                                                   'lifecycle', 'governance', 'execution'), r
            assert vocabulary(resolve(r['ours'])) is None, r


def test_the_caveat_is_06s_measured_density():
    c = load('hf-tags')['caveats']['hf-tag-density']
    assert (c['namespace'], c['tagged'], c['sampled'], c['density']) == ('test', 128, 1000, 0.128)


def test_counts_are_06s_table_transcribed():
    with open(os.path.join(ROOT, '_plan', '06-sourcing-and-scraping.md'), encoding='utf-8') as fh:
        text = fh.read()
    section = text[text.index('### 3.2 HuggingFace Hub'):text.index('### 3.3 GitHub')]
    measured = {}
    for line in section.splitlines():
        m = re.match(r'^\| (`([a-z]+):`|free tags) \| (.*) \|$', line)
        if m:
            for value, n in re.findall(r'`([^`]+)` \((\d+)', m.group(3)):
                measured[('%s:%s' % (m.group(2), value)) if m.group(2) else value] = int(n)
    assert len(measured) == 26
    got = {r['tag']: r['count'] for r in rows('hf-tags') if r['count'] is not None}
    dropped = set(load('hf-tags')['namespaces']['_free']['drop'])
    assert got == {t: n for t, n in measured.items() if t not in dropped}
    assert {'benchmark', 'evaluation'} <= dropped and not dropped & set(got)   # measured, and dropped by name
    english = next(r for r in rows('hf-tags') if r['tag'] == 'language:english')
    assert english['count_variants'] == {'language:English': int(re.search(
        r'`english` \(\d+, plus (\d+) under a cased variant', section).group(1))}


def test_count_fixture_is_the_committed_fixtures():
    doc = load('hf-tags')
    spaces = fixture_tags()
    rule = doc['normalise']['language']
    for r in doc['rows']:
        if r['tag'] == 'arxiv:*':
            n = sum(t.startswith('arxiv:') for tags in spaces for t in tags)
        elif namespace(r['tag']) == 'language':
            n = sum(r['value'] in normalise_language(t.split(':', 1)[1], rule)
                    for tags in spaces for t in tags if t.startswith('language:'))
        else:
            n = sum(r['tag'] in tags for tags in spaces)
        assert r['count_fixture'] == n, (r['tag'], r['count_fixture'], n)


def test_the_language_rule_folds_every_cased_variant():
    doc = load('hf-tags')
    rule = doc['normalise']['language']
    assert normalise_language('english', rule) == normalise_language('English', rule) == ['English']
    assert normalise_language('日本語', rule) == normalise_language('Japanese', rule) == ['Japanese']
    assert normalise_language('English, Hindi', rule) == ['English', 'Hindi']
    assert normalise_language('pl', rule) == ['Polish'] and normalise_language('code', rule) == []
    values = {t.split(':', 1)[1] for tags in fixture_tags() for t in tags if t.startswith('language:')}
    folded = {}
    for v in values:
        for name in normalise_language(v, rule):
            folded.setdefault(name.casefold(), set()).add(name)
    assert all(len(names) == 1 for names in folded.values())       # one spelling per language
    for r in doc['rows']:
        if namespace(r['tag']) == 'language':
            assert normalise_language(r['tag'].split(':', 1)[1], rule) == [r['value']], r


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
