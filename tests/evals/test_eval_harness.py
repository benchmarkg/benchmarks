"""The pooling grading harness behind `bench eval` (P6-S3-T09; 11-ai-features.md S7, 05 S3 and S9).

The verify is `bench eval --split all --report`. Over the repository, where every gold label is still null, it must say
plainly that nothing can be graded and print no number (tests/cli/test_eval_cmd.py). The metrics and the intervals are
held here instead, on a synthetic labelled fixture (tests/fixtures/evals/synthetic-labelled.yaml): a temporary tree
holding a copy of the real golden set with the fixture's invented labels written in, invented entries, invented
rankings and invented model outputs, every expected number computed by hand. No test calls the API, and none needs a
key: the Batch API transport is driven by a fake opener.
"""
import copy
import json
import os
import shutil
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.evals import batch, golden, harness, metrics, retrieval, stats  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'evals', 'synthetic-labelled.yaml')
with open(FIXTURE, encoding='utf-8') as _fh:
    FX = yaml.safe_load(_fh)
LEXICAL_FIXTURE = os.path.join(ROOT, 'site', 'test', 'fixtures', 'lexical-bm25.json')
PERSON = 'a maintainer'


# ---- stats: the Wilson interval and the verdicts ----------------------------------------------------------------

@pytest.mark.parametrize('s, n, lo, hi', [
    (19, 20, 0.7639, 0.9911), (34, 40, 0.7093, 0.9294), (170, 200, 0.7939, 0.8929), (18, 20, 0.6990, 0.9721),
    (17, 20, 0.6396, 0.9476), (0, 20, 0.0, 0.1611), (20, 20, 0.8389, 1.0), (12, 12, 0.7575, 1.0), (3, 4, 0.3006, 0.9544),
])
def test_wilson_matches_the_formula_and_the_docstring_figures(s, n, lo, hi):
    got = stats.wilson(s, n)
    assert got == pytest.approx((lo, hi), abs=1e-4)
    assert 0.0 <= got[0] <= s / n <= got[1] <= 1.0


def test_wilson_refuses_an_empty_or_impossible_count():
    with pytest.raises(ValueError):
        stats.wilson(0, 0)
    with pytest.raises(ValueError):
        stats.wilson(5, 4)


def test_z_is_the_0975_quantile():
    from statistics import NormalDist
    assert stats.Z95 == pytest.approx(NormalDist().inv_cdf(0.975), abs=1e-15)


def test_a_bar_fails_only_when_the_interval_clears_it():
    at_least = stats.Bar(stats.AT_LEAST, 0.95)
    # 11 S7's abstention bar at n = 20: two misses straddle it, three fail it
    assert stats.rate(18, 20, at_least)['verdict'] == stats.INCONCLUSIVE
    assert stats.rate(17, 20, at_least)['verdict'] == stats.FAIL
    # a point estimate on the right side with a straddling interval is inconclusive too, and says which side it is on
    r = stats.rate(20, 20, at_least)
    assert (r['verdict'], r['point_meets_bar']) == (stats.INCONCLUSIVE, True)
    assert stats.rate(199, 200, at_least)['verdict'] == stats.PASS          # [0.972, 0.999]: the whole interval clears
    at_most = stats.Bar(stats.AT_MOST, 0.05)
    assert stats.rate(0, 100, at_most)['verdict'] == stats.PASS             # [0, 0.037]
    assert stats.rate(0, 12, at_most)['verdict'] == stats.INCONCLUSIVE      # [0, 0.243]
    assert stats.rate(1, 3, at_most)['verdict'] == stats.FAIL               # lower bound 0.0615 > 0.05


def test_a_hard_zero_fails_on_one_occurrence_at_any_n():
    zero = stats.Bar(stats.ASSERT, 0.0)
    assert stats.rate(0, 3, zero)['verdict'] == stats.PASS
    assert stats.rate(1, 10000, zero)['verdict'] == stats.FAIL
    one = stats.rate(1999, 2000, stats.Bar(stats.ASSERT, 1.0))
    assert one['verdict'] == stats.FAIL and 'interval' in one and 'hard zero' in one['interval_note']


# ---- metrics on the synthetic fixture -----------------------------------------------------------------------------

def check(got: dict, want: dict):
    assert set(got) == set(want), (sorted(got), sorted(want))
    for name, w in want.items():
        g = got[name]
        assert g['value'] == pytest.approx(w['value'], abs=1e-4), name
        assert g['n'] == w['n'], name
        assert g['interval'] == pytest.approx(w['interval'], abs=1e-4), name
        assert g['verdict'] == w['verdict'], name


def test_ndcg_by_hand():
    gold = FX['labels']['nl_search']['nl_search-01']
    assert metrics.ndcg(FX['runs']['lexical']['nl_search-01'], gold) == pytest.approx(0.836888, abs=1e-6)
    assert metrics.ndcg(FX['runs']['dense']['nl_search-01'], gold) == pytest.approx(0.989037, abs=1e-6)
    assert metrics.ndcg([], gold) == 0.0
    assert metrics.ndcg(sorted(gold, key=gold.get, reverse=True), gold) == pytest.approx(1.0)


def test_nl_search_metrics_on_the_fixture():
    for config in ('lexical', 'dense'):
        pairs = [(FX['runs'][config][i], g) for i, g in FX['labels']['nl_search'].items()]
        check(metrics.nl_search(pairs), FX['expected']['nl_search'][config]['all'])
    assert metrics.nl_search([]) == {}


def allowed_slots():
    with open(os.path.join(ROOT, batch.SCHEMA), encoding='utf-8') as fh:
        facets = json.load(fh)['$defs']['Facets']['properties']
    return {s: set(p['items']['enum']) for s, p in facets.items() if s != 'year_min'}


def test_facet_translation_metrics_on_the_fixture():
    pairs = [(g, FX['outputs']['facet_translation'][i]) for i, g in FX['labels']['facet_translation'].items()]
    check(metrics.facet_translation(pairs, allowed_slots()), FX['expected']['facet_translation']['all'])


def test_over_constraint_reads_a_family_as_its_subdomains():
    allowed = allowed_slots()

    def subs(f):
        return {s for s in allowed['domain_subdomain'] if s.startswith(f + '/')}
    fam = {'domain_family': ['domain:language']}
    sub = {'domain_subdomain': ['domain:language/translation']}
    assert metrics.over_constrained(fam, sub, subs) is True                 # narrower than the gold's family
    assert metrics.over_constrained(sub, fam, subs) is False                # the family admits the subdomain
    assert metrics.over_constrained({}, fam, subs) is True                  # the gold filters nothing
    assert metrics.over_constrained(fam, {}, subs) is False                 # no hard filter rejects nothing
    assert metrics.over_constrained({'year_min': 2020}, {'year_min': 2024}, subs) is True
    assert metrics.over_constrained({'access': ['data_properties:fully-open']},
                                    {'access': ['data_properties:fully-open', 'data_properties:gated-registration']},
                                    subs) is False                          # OR within a slot: looser


def test_abstention_on_the_fixture():
    pairs = [(g, FX['outputs']['abstention'][i]) for i, g in FX['labels']['abstention'].items()]
    check(metrics.abstention(pairs), FX['expected']['abstention']['all'])


# ---- golden: the real set, and the holdout --------------------------------------------------------------------------

def test_the_real_golden_set_loads_and_holds_no_label():
    docs, _ = golden.load(ROOT)
    assert set(docs) == set(golden.SPLITS)
    assert sum(len(golden.labelled(d)) for d in docs.values()) == 0


def test_holdout_is_proportional_stable_and_bounded():
    docs, _ = golden.load(ROOT)
    held = golden.holdout(docs, list(golden.SPLITS), 30)
    assert len(held) == len(set(held)) == 30 and held == golden.holdout(docs, list(golden.SPLITS), 30)
    per = {s: sum(1 for i in held if i.startswith(s + '-')) for s in golden.SPLITS}
    assert per == {'nl_search': 15, 'facet_translation': 9, 'suite_build': 4, 'abstention': 2}   # 40 items, 3/4 each
    assert set(golden.holdout(docs, ['nl_search'], 5)) <= set(golden.holdout(docs, ['nl_search'], 6))
    assert golden.holdout(docs, ['nl_search'], 0) == []
    with pytest.raises(ValueError):
        golden.holdout(docs, ['abstention'], 4)


# ---- retrieval: RRF, the pool, the refusals, and the bridge to the site's BM25 leg -------------------------------

def corpus_of(ids):
    return retrieval.Corpus(rows=[{'id': i, 'name': i, 'aliases': [], 'editions': []} for i in ids],
                            records={}, drafts=True)


def run_of(name, corpus, ranked_ids):
    at = {r['id']: n for n, r in enumerate(corpus.rows)}
    return retrieval.Run(name, ranked={q: [(at[i], 1.0 / (k + 1)) for k, i in enumerate(ids)]
                                       for q, ids in ranked_ids.items()})


def test_rrf_is_the_sites_formula_with_ties_by_row():
    a, b = [(0, 9.0), (1, 8.0), (2, 7.0)], [(2, 0.9), (1, 0.8)]
    got = dict(retrieval.rrf([a, b]))
    assert got[1] == pytest.approx(1 / 62 + 1 / 62) and got[2] == pytest.approx(1 / 63 + 1 / 61)
    assert got[0] == pytest.approx(1 / 61)
    assert [r for r, _ in retrieval.rrf([[(5, 1.0)], [(3, 1.0)]])] == [3, 5]     # equal scores: by row


def test_the_pool_is_the_union_of_each_configurations_top_20():
    ids = ['e%02d' % i for i in range(40)]
    corpus = corpus_of(ids)
    lex = run_of('lexical', corpus, {'q': ids[:30]})
    den = run_of('dense', corpus, {'q': ids[10:40]})
    off = retrieval.Run('fused', reason='not here')
    pool = retrieval.pool(corpus, [lex, den, off], 'q')
    assert [e['id'] for e in pool] == sorted(set(ids[:20]) | set(ids[10:30]),
                                             key=lambda i: (min(ids[:20].index(i) if i in ids[:20] else 99,
                                                                ids[10:30].index(i) if i in ids[10:30] else 99), i))
    assert len(pool) == 30
    shared = next(e for e in pool if e['id'] == 'e10')
    assert shared['configurations'] == ['lexical', 'dense'] and shared['best_rank'] == 1


def test_lexical_refuses_without_node_or_minisearch(tmp_path):
    corpus = corpus_of(['a'])
    runs = retrieval.lexical(corpus, {'q': 'a'}, root=str(tmp_path), node=sys.executable)
    assert [r.ran for r in runs] == [False, False] and 'npm ci' in runs[0].reason
    assert retrieval.fused(runs[0], retrieval.Run('dense', reason='x')).ran is False


def test_dense_ranks_by_cosine_over_the_dequantised_rows(monkeypatch):
    """The dense configuration with a fake encoder and a fake matrix: cosine order, equal scores by row; and a refusal
    from tools/build/embed.py becomes a reason, not an exception."""
    np = pytest.importorskip('numpy')
    from tools.build import embed
    rows = np.array([[0, 127], [127, 0], [90, 90], [0, 127]], dtype=np.int8)       # rows 0 and 3 are the same vector
    monkeypatch.setattr(embed, 'build', lambda corpus, facets, enc: type('V', (), {'q': rows, 'scales': [1 / 127] * 4}))

    class Fake:
        def encode(self, texts):
            return np.array([[0.0, 2.0] if t == 'up' else [1.0, 0.0] for t in texts])
    run = retrieval.dense(corpus_of(['a', 'b', 'c', 'd']), {'q1': 'up', 'q2': 'right'}, encoder=Fake())
    assert [r for r, _ in run.ranked['q1']] == [0, 3, 2, 1]
    assert [r for r, _ in run.ranked['q2']] == [1, 2, 0, 3]
    assert run.ranked['q1'][0][1] == pytest.approx(1.0)

    def refuse(corpus, facets, enc):
        raise embed.EmbedError('the model is not cached')
    monkeypatch.setattr(embed, 'build', refuse)
    off = retrieval.dense(corpus_of(['a']), {'q': 'x'}, encoder=Fake())
    assert not off.ran and 'the model is not cached' in off.reason and 'embed' in off.reason


def bridge_ready():
    return shutil.which('node') and os.path.isdir(os.path.join(ROOT, retrieval.MINISEARCH))


@pytest.mark.skipif(not bridge_ready(), reason='needs Node and `npm ci` in site/')
def test_the_bridge_runs_the_sites_bm25_leg_exactly():
    """lexical_runs.mjs over the site's own frozen fixture returns the site test's frozen ranked lists and scores."""
    with open(LEXICAL_FIXTURE, encoding='utf-8') as fh:
        fx = json.load(fh)
    corpus = retrieval.Corpus(rows=fx['rows'], records={}, drafts=False)
    queries = {'q%02d' % n: q['q'] for n, q in enumerate(fx['queries']) if 'survivors' not in q}
    lex, wide = retrieval.lexical(corpus, queries, ROOT)
    assert lex.ran and wide.ran, (lex.reason, wide.reason)
    for n, q in enumerate(fx['queries']):
        if 'survivors' in q:
            continue
        got = [[corpus.rows[r]['id'], round(s, 4)] for r, s in lex.ranked['q%02d' % n]]
        assert got == q['ranked'], q['q']
        # with no tagline, description or maintainer the wide index matches the same rows
        assert {r for r, _ in wide.ranked['q%02d' % n]} == {r for r, _ in lex.ranked['q%02d' % n]}, q['q']


@pytest.mark.skipif(not bridge_ready(), reason='needs Node and `npm ci` in site/')
def test_the_wide_configuration_finds_what_a_description_says():
    corpus = retrieval.Corpus(rows=[{'id': 'alpha', 'name': 'Alpha', 'aliases': [], 'editions': []},
                                    {'id': 'beta', 'name': 'Beta', 'aliases': [], 'editions': []}],
                              records={'beta': {'tagline': '', 'description': 'Questions in Swahili and Yoruba',
                                                'governance': {'maintainer': 'A university lab'}}}, drafts=True)
    lex, wide = retrieval.lexical(corpus, {'q': 'yoruba questions'}, ROOT)
    assert lex.ids(corpus, 'q') == [] and wide.ids(corpus, 'q') == ['beta']


# ---- batch: the seam ----------------------------------------------------------------------------------------------

def test_model_ids_come_from_the_config():
    from schema.taxonomy import read_yaml
    rows = read_yaml(os.path.join(ROOT, batch.CONFIG))['models']
    for user in ('F1', 'F2', batch.JUDGE):
        got = batch.model_for(user)
        assert got in [m['id'] for m in rows if user in (m.get('used_by') or [])]
    with pytest.raises(batch.BatchError):
        batch.model_for('no-such-feature')


def test_an_f1_request_has_the_batch_shape():
    item = {'id': 'facet_translation-05', 'query': 'benchmarks for translation'}
    schema = batch.facetquery_schema()
    req = batch.f1_request(item, 'model-from-config', 'SYSTEM', schema)
    assert req['custom_id'] == item['id'] and batch.CUSTOM_ID.match(req['custom_id'])
    p = req['params']
    assert p['model'] == 'model-from-config' and p['max_tokens'] >= 1
    assert p['messages'] == [{'role': 'user', 'content': item['query']}]
    assert p['output_config'] == {'format': {'type': 'json_schema', 'schema': schema}}
    assert not set(batch.REFUSED_PARAMS) & set(p) and 'thinking' not in p
    assert batch.body([req]) == {'requests': [req]}
    with pytest.raises(batch.BatchError):
        batch.body([req, req])                                              # a repeated custom_id
    with pytest.raises(batch.BatchError):
        batch.body([dict(req, params=dict(p, temperature=1))])              # a 400 on API version 2026-10-21
    with pytest.raises(batch.BatchError):
        batch.f1_request({'id': 'has space', 'query': 'x'}, 'm', 's', schema)


def test_every_golden_id_is_a_valid_custom_id():
    docs, _ = golden.load(ROOT)
    assert all(batch.CUSTOM_ID.match(it['id']) for d in docs.values() for it in d['items'])


def test_the_run_refuses_without_a_key_and_while_nothing_is_built():
    s = batch.status(['F1', 'F2', batch.JUDGE], env={})
    assert s.key is False
    for f in ('F1', 'F2', batch.JUDGE):
        assert any('ANTHROPIC_API_KEY is not set' in r for r in s.refusals[f])
        assert batch.NOT_BUILT[f] in s.refusals[f]
    with_key = batch.status(['F1'], env={'ANTHROPIC_API_KEY': 'not-a-real-key'})
    assert with_key.refusals['F1'] == [batch.NOT_BUILT['F1']]
    with pytest.raises(batch.BatchError):
        batch.Transport('')


class FakeResponse:
    def __init__(self, data: bytes):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_the_transport_and_the_results_parser_with_a_fake(monkeypatch):
    from ingest.http import policy
    monkeypatch.setattr(policy, 'refuse', lambda url: None)
    seen, states = [], iter(['in_progress', 'ended'])
    lines = '\n'.join(json.dumps(x) for x in [
        {'custom_id': 'b', 'result': {'type': 'succeeded', 'message': {
            'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '{"intent": "lookup"}'}]}}},
        {'custom_id': 'a', 'result': {'type': 'succeeded', 'message': {'stop_reason': 'refusal', 'content': []}}},
        {'custom_id': 'c', 'result': {'type': 'errored', 'error': {'type': 'invalid_request_error'}}},
        {'custom_id': 'd', 'result': {'type': 'expired'}}])

    def opener(req, timeout):
        seen.append((req.get_method(), req.full_url, dict(req.header_items())))
        if req.full_url.endswith('/results'):
            return FakeResponse(lines.encode('utf-8'))
        if req.get_method() == 'POST':
            return FakeResponse(b'{"id": "msgbatch_x", "processing_status": "in_progress"}')
        return FakeResponse(json.dumps({'id': 'msgbatch_x', 'processing_status': next(states)}).encode('utf-8'))
    t = batch.Transport('not-a-real-key', opener=opener)
    req = batch.f1_request({'id': 'a', 'query': 'q'}, 'm', 's', {'type': 'object'})
    assert batch.submit([req], t)['id'] == 'msgbatch_x'
    assert batch.wait('msgbatch_x', t, sleep=lambda s: None)['processing_status'] == 'ended'
    got = batch.results('msgbatch_x', t)
    assert got['b'] == {'type': 'succeeded', 'output': {'intent': 'lookup'}}
    assert got['a']['type'] == 'errored' and 'refusal' in got['a']['error']
    assert got['c']['type'] == 'errored' and got['d'] == {'type': 'expired'}
    method, url, headers = seen[0]
    assert (method, url) == ('POST', batch.API_URL)
    assert {k.lower(): v for k, v in headers.items()}['anthropic-version'] == batch.API_VERSION
    assert [s[0] for s in seen] == ['POST', 'GET', 'GET', 'GET']


# ---- the harness end to end on a labelled copy of the set -----------------------------------------------------------

@pytest.fixture
def labelled_tree(tmp_path):
    """A temporary tree: the real golden set with the fixture's synthetic labels written in, the FacetQuery schema,
    the homograph declarations, the model config, and one empty file per synthetic entry."""
    for rel in ('schema/generated/facetquery.schema.json', 'taxonomy/homographs.yaml', 'config/ai-models.yaml'):
        os.makedirs(tmp_path / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), tmp_path / rel)
    os.makedirs(tmp_path / 'data' / 'benchmarks' / 'fixture')
    for e in FX['entries']:
        (tmp_path / 'data' / 'benchmarks' / 'fixture' / ('%s.yaml' % e)).write_text('id: %s\n' % e, encoding='utf-8')
    os.makedirs(tmp_path / 'evals' / 'golden')
    for split in golden.SPLITS:
        with open(os.path.join(ROOT, 'evals', 'golden', '%s.yaml' % split), encoding='utf-8') as fh:
            doc = yaml.safe_load(fh)
        labels = FX['labels'].get(split, {})                     # get-default: suite_build has no synthetic label
        for it in doc['items']:
            if it['id'] in labels:
                it['gold'] = copy.deepcopy(labels[it['id']])
        if labels:
            doc.update(labelled_by=PERSON, labelled_on='2026-11-25', labelled_against='0123456789abcdef')
        with open(tmp_path / 'evals' / 'golden' / ('%s.yaml' % split), 'w', encoding='utf-8') as fh:
            yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
    return str(tmp_path)


def synthetic_configurations(corpus, queries):
    runs = [run_of(name, corpus, {q: FX['runs'][name].get(q, []) for q in queries})    # get-default: unlisted, empty
            for name in ('lexical', 'dense')]
    return runs + [retrieval.fused(runs[0], runs[1]), retrieval.Run('lexical-wide', reason='not in this fixture')]


def evaluate(tree, **kw):
    import datetime
    return harness.evaluate(tree, env={}, today=datetime.date(2026, 11, 25), corpus=corpus_of(FX['entries']),
                            configurations=synthetic_configurations, **kw)


def test_the_harness_grades_the_fixture_and_writes_the_results_file(labelled_tree):
    doc = evaluate(labelled_tree, outputs=FX['outputs'])
    assert doc['graded'] is True and doc['corpus'] == {'drafts': True, 'benchmarks': 8}
    nl = doc['results']['nl_search']['configurations']
    for config in ('lexical', 'dense'):
        check(nl[config]['populations']['all'], FX['expected']['nl_search'][config]['all'])
    check(nl['lexical']['populations']['generated'], FX['expected']['nl_search']['lexical']['generated'])
    assert set(nl['lexical']['populations']) == {'all', 'generated', 'not-generated'}
    assert nl['lexical']['judged@20'] == {'judged': 5, 'retrieved': 8}     # 05, and item 02's 07 and 08, ungraded
    assert 'fused' in nl                                          # RRF of the two synthetic runs is graded too
    check(doc['results']['facet_translation']['configurations']['F1']['populations']['all'],
          FX['expected']['facet_translation']['all'])
    assert all(m['smoke_test'] for m in doc['results']['facet_translation']['configurations']['F1']['populations']
               ['all'].values())
    check(doc['results']['abstention']['configurations']['F1']['populations']['all'],
          FX['expected']['abstention']['all'])
    assert set(doc['not_measured']['suite_build']) == set(metrics.BARS['suite_build'])
    assert doc['model_run']['ran'] is False and doc['model_run']['api_key_present'] is False
    # the pool: each configuration's top 20, unioned, for nl_search and suite_build items alike
    assert doc['pool']['items']['nl_search-01']['size'] == 5 and doc['pool']['without_pooling'] == 25 * 8
    path = harness.write(doc, labelled_tree)
    assert os.path.basename(path) == '2026-11-25-unknown.json'      # a tree outside git: the commit is unknown
    with open(path, encoding='utf-8') as fh:
        assert json.load(fh) == json.loads(json.dumps(doc))
    text = harness.report(doc)
    assert '| nl_search | lexical | all | recall@20 | 0.750 | [0.301, 0.954] | 4 | >= 0.900 | inconclusive |' in text
    assert 'lexical-wide: NOT RUN: not in this fixture' in text and 'Nothing can be graded' not in text


def test_without_model_outputs_only_nl_search_is_graded(labelled_tree):
    doc = evaluate(labelled_tree)
    assert list(doc['results']) == ['nl_search']
    assert 'needs the F1 outputs' in doc['not_measured']['facet_translation']['macro_f1']


def test_the_holdout_publishes_train_and_test_apart(labelled_tree):
    doc = evaluate(labelled_tree, holdout=30, outputs=FX['outputs'])
    assert doc['holdout']['n'] == 30
    for split in ('nl_search', 'facet_translation', 'abstention'):
        for cfg in doc['results'][split]['configurations'].values():
            pops = cfg['populations']
            first = next(iter(pops['all']))
            assert sum(pops[p][first]['n'] for p in ('train', 'test') if p in pops) == pops['all'][first]['n']


def test_with_no_label_nothing_is_graded_and_nothing_written(tmp_path):
    for rel in ('evals/golden', 'schema/generated', 'taxonomy', 'config'):
        os.makedirs(tmp_path / rel, exist_ok=True)
    for split in golden.SPLITS:
        shutil.copy(os.path.join(ROOT, 'evals', 'golden', '%s.yaml' % split), tmp_path / 'evals' / 'golden')
    for rel in ('schema/generated/facetquery.schema.json', 'taxonomy/homographs.yaml', 'config/ai-models.yaml'):
        shutil.copy(os.path.join(ROOT, rel), tmp_path / rel)
    doc = evaluate(str(tmp_path), judge=True)
    assert doc['graded'] is False and doc['results'] == {}
    assert harness.write(doc, str(tmp_path)) is None and not os.path.exists(tmp_path / 'evals' / 'results')
    text = harness.report(doc)
    assert 'Nothing can be graded yet. 0 of 40 gold labels are set' in text
    assert '## Metrics' not in text and '| recall@20 |' not in text
    assert '--judge, self-eval-judge' in text and 'never gates' in text


def test_a_broken_golden_set_stops_the_run(labelled_tree):
    path = os.path.join(labelled_tree, 'evals', 'golden', 'nl_search.yaml')
    with open(path, encoding='utf-8') as fh:
        doc = yaml.safe_load(fh)
    doc['items'][0]['gold'] = {'not-an-entry': 3}
    with open(path, 'w', encoding='utf-8') as fh:
        yaml.safe_dump(doc, fh, sort_keys=False)
    with pytest.raises(harness.EvalError) as e:
        evaluate(labelled_tree)
    assert any('not-an-entry' in line for line in e.value.errors)
