"""Tests for scripts/taxonomy_drift_check.py (P1-S14-T03; 03 S6.4, 11 F6 and S6), with the fake provider.

No test reads a real key or opens a socket. urllib's urlopen raises in every test, the key variables are unset
(one test sets a sentinel to show a dry run never sends it), and the live providers are driven through an
injected `post`. A fake run writes under tmp_path only, never metrics/taxonomy-drift.json.

What is shown: no stored tag of an item reaches its prompt; the same seed gives the same prompts and another
seed another item and option order; the ranking and its ties; the label; --check failing on a missing file, an
agreement figure, a fake run, a Claude model, an incomplete run and a misordered ranking; the Claude-model
refusal; the request cap, retries included; a dry run with no network call; and no output under data/.
"""
import copy
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import taxonomy_drift_check as D  # noqa: E402

SCRIPT = os.path.join(ROOT, 'scripts', 'taxonomy_drift_check.py')
SENTINEL = 'SENTINEL-not-a-real-key-0123456789'


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError('a test opened a network connection')
    monkeypatch.setattr(urllib.request, 'urlopen', no_network)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setattr(D, '_sleep', lambda s: None)


@pytest.fixture(scope='module')
def irr():
    items, facets, vocab = D.irr_items(ROOT)
    return items, facets, vocab, D.irr_stored(ROOT, [x['id'] for x in items])


@pytest.fixture(scope='module')
def built():
    return D.build(ROOT, 'irr', 20261118)


@pytest.fixture(scope='module')
def fake_doc(tmp_path_factory):
    """One fake run over the 30 items, read back: the file every --check test starts from."""
    rc, out = fake_run(tmp_path_factory.mktemp('fake'))
    assert rc == 0
    with open(out, encoding='utf-8') as fh:
        return json.load(fh)


def benchmark_block(prompt):
    return json.loads(prompt.split('\nBENCHMARK\n', 1)[1].split('\n\nAnswer with', 1)[0])


def option_ids(prompt):
    body = prompt.split('\nOPTIONS, in no particular order, one JSON object per line\n', 1)[1]
    return [json.loads(line)['id'] for line in body.split('\n\nBENCHMARK\n', 1)[0].split('\n')]


def fake_run(tmp_path, seed=5, extra=(), answer=None):
    out = str(tmp_path / 'drift.json')
    rc = D.main(['--provider', 'fake', '--model', 'fake', '--seed', str(seed), '--out', out, *extra],
                provider=D.Fake(answer), log=lambda m: None)
    return rc, out


def as_live(doc):
    """A fake run's file dressed as a live one: what --check must accept when the shape is right."""
    doc = copy.deepcopy(doc)
    doc['run']['provider'], doc['run']['model'] = 'openai', 'gpt-test'
    return doc


def write(tmp_path, doc, name='m.json'):
    p = tmp_path / name
    p.write_text(json.dumps(doc, indent=1), encoding='utf-8')
    return str(p)


# ---- the prompt carries no stored tag --------------------------------------------------------------------------

def test_no_stored_tag_reaches_any_irr_prompt(irr, built):
    items, facets, vocab, stored = irr
    reqs, _, _ = built
    assert len(reqs) == 30 * 11
    for r in reqs:
        assert D.blind(r, stored[r.item['id']], vocab) == []
        prompt = r.prompt
        block = benchmark_block(prompt)
        assert set(block) == {'name', 'links'}                       # the instrument's item, less its id
        assert all(set(link) <= {'kind', 'url', 'arxiv_id', 'doi'} for link in block['links'])
        text = json.dumps(block, ensure_ascii=False).lower()
        values = [v for vals in stored[r.item['id']].values() if isinstance(vals, list) for v in vals]
        assert values and not [v for v in values if v.lower() in text]    # not even as a substring
        shown = option_ids(prompt)
        assert sorted(shown) == sorted(o['id'] for o in vocab[r.vocabulary])  # every option, none singled out
        assert r.schema['properties'][D.key(r.facets[0][0])]['items']['enum'] == shown
        facets_text = prompt.split('\nFACETS\n', 1)[1].split('\n\nOPTIONS', 1)[0]
        assert not [v for v in values if v in facets_text]
        for f, vals in stored[r.item['id']].items():
            for v in vals if isinstance(vals, list) else []:
                assert not re.search(r'%s["\']?\s*[:=]\s*\[?["\']?%s\b' % (re.escape(D.key(f)), re.escape(v)), prompt)
                assert not re.search(r'%s["\']?\s*[:=]\s*\[?["\']?%s\b' % (re.escape(f), re.escape(v)), prompt)


def test_the_stored_values_are_the_classifications_the_instrument_hides(irr):
    items, _, _, stored = irr
    assert 'the-well' in {x['id'] for x in items}
    well = stored['the-well']
    assert well['capability'] == ['scientific-prediction']
    assert well['domain.primary'] == ['physics/simulation-surrogates']
    assert isinstance(well['lifecycle'], str)                         # an abstention is not compared


def test_blind_catches_a_leak(irr, built):
    _, _, vocab, stored = irr
    r = next(x for x in built[0]
             if x.vocabulary == 'capabilities' and isinstance(stored[x.item['id']]['capability'], list))
    s = stored[r.item['id']]
    leaky = D.Request(r.n, dict(r.item, capability=s['capability']), r.vocabulary, r.facets, r.options)
    assert any('beyond' in e for e in D.blind(leaky, s, vocab))
    named = D.Request(r.n, dict(r.item, name=s['capability'][0]), r.vocabulary, r.facets, r.options)
    assert any('is a field of the item block' in e for e in D.blind(named, s, vocab))
    dropped = D.Request(r.n, r.item, r.vocabulary, r.facets, r.options[1:])
    assert any('not exactly' in e for e in D.blind(dropped, s, vocab))
    linked = D.Request(r.n, dict(r.item, links=r.item['links'] + [{'kind': 'tag', 'url': 'u', 'capability': 'x'}]),
                       r.vocabulary, r.facets, r.options)
    assert any('a link carries capability' in e for e in D.blind(linked, s, vocab))


def test_build_refuses_a_request_that_is_not_blind(monkeypatch, irr):
    items, facets, vocab, stored = irr
    first = next(x for x in items if isinstance(stored[x['id']]['domain.primary'], list))
    bad = [dict(x, name=stored[x['id']]['domain.primary'][0]) if x is first else x for x in items]
    monkeypatch.setattr(D, 'irr_items', lambda root: (bad, facets, vocab))
    with pytest.raises(D.Refused, match='is not blind'):
        D.build(ROOT, 'irr', 1)


def test_corpus_items_are_blind_too():
    reqs, stored, where = D.build(ROOT, 'corpus', 7, max_items=4)
    assert len({r.item['id'] for r in reqs}) == 4 and len(reqs) == 44
    assert where['stored_values'].startswith('data/benchmarks')
    for r in reqs:
        assert set(benchmark_block(r.prompt)) == {'name', 'links'}


# ---- order: deterministic per seed, shuffled across seeds ------------------------------------------------------

def test_the_same_seed_gives_the_same_prompts(irr):
    items, facets, vocab, _ = irr
    a, b = D.plan(items, facets, vocab, 11), D.plan(items, facets, vocab, 11)
    assert [(r.item['id'], r.vocabulary, r.prompt) for r in a] == [(r.item['id'], r.vocabulary, r.prompt) for r in b]
    assert D.requests_sha256(a) == D.requests_sha256(b)


def test_another_seed_shuffles_items_options_and_requests(irr):
    items, facets, vocab, _ = irr
    a, b = D.plan(items, facets, vocab, 11), D.plan(items, facets, vocab, 12)

    def item_order(reqs):
        seen = []
        for r in reqs:
            if r.item['id'] not in seen:
                seen.append(r.item['id'])
        return seen
    assert item_order(a) != item_order(b) and sorted(item_order(a)) == sorted(item_order(b))
    pick = {(r.item['id'], r.vocabulary): [o['id'] for o in r.options] for r in a}
    other = {(r.item['id'], r.vocabulary): [o['id'] for o in r.options] for r in b}
    assert sum(pick[k] != other[k] for k in pick if len(pick[k]) > 3) > 0.9 * sum(1 for k in pick if len(pick[k]) > 3)
    assert all(sorted(pick[k]) == sorted(other[k]) for k in pick)
    assert D.requests_sha256(a) != D.requests_sha256(b)
    five = {r.item['id'] for r in D.plan(items, facets, vocab, 11, max_items=5)}
    assert len(five) == 5 and five == {r.item['id'] for r in D.plan(items, facets, vocab, 11, max_items=5)}


def test_a_run_without_a_seed_draws_one_and_records_it(tmp_path):
    out = str(tmp_path / 'drift.json')
    assert D.main(['--provider', 'fake', '--model', 'fake', '--max-items', '1', '--out', out], provider=D.Fake(),
                  log=lambda m: None) == 0
    with open(out, encoding='utf-8') as fh:
        run = json.load(fh)['run']
    assert isinstance(run['seed'], int) and '--seed %d' % run['seed'] in run['tool']


# ---- the ranking ---------------------------------------------------------------------------------------------

def tiny():
    """Three items, a multi-valued facet over a, b, c and a single-valued one over x, y."""
    items = [{'id': 'i%d' % n, 'name': 'Item %d' % n, 'links': []} for n in (1, 2, 3)]
    vocab = {'capabilities': [{'id': t} for t in 'abc'], 'lifecycle': [{'id': t} for t in 'xy']}
    facets = [{'facet': 'capability', 'kind': 'multi', 'vocabulary': 'capabilities'},
              {'facet': 'lifecycle', 'kind': 'single', 'vocabulary': 'lifecycle'}]
    stored = {'i1': {'capability': ['a', 'b'], 'lifecycle': ['x']},
              'i2': {'capability': ['a'], 'lifecycle': ['x']},
              'i3': {'capability': ['c'], 'lifecycle': 'no stored value'}}
    model = {'i1': {'capability': ['c'], 'lifecycle': ['y']},
             'i2': {'capability': ['a', 'c'], 'lifecycle': ['x']},
             'i3': {'capability': [], 'lifecycle': ['y']}}
    reqs = D.plan(items, facets, vocab, 3)
    answers = {r.n: {f: model[r.item['id']][f] for f, _ in r.facets} for r in reqs}
    return reqs, answers, stored


def test_ranking_counts_each_term_and_shares_tied_ranks():
    reqs, answers, stored = tiny()
    ranked = D.rank(D.compare(reqs, answers, stored)[0])
    got = [(r['rank'], r['facet'], r['term'], r['defects'], r['stored_not_chosen'], r['chosen_not_stored'])
           for r in ranked]
    assert got == [(1, 'capability', 'c', 3, 1, 2),       # i1, i2 chose it unstored; i3 stored it, chose nothing
                   (2, 'capability', 'a', 1, 1, 0),       # i1
                   (2, 'capability', 'b', 1, 1, 0),       # i1
                   (2, 'lifecycle', 'x', 1, 1, 0),        # i1: the single-valued miss counts both terms
                   (2, 'lifecycle', 'y', 1, 0, 1)]
    assert ranked[0]['items'] == [{'item': 'i1', 'stored': ['a', 'b'], 'model': ['c']},
                                  {'item': 'i2', 'stored': ['a'], 'model': ['a', 'c']},
                                  {'item': 'i3', 'stored': ['c'], 'model': []}]
    skipped = D.compare(reqs, answers, stored)[1]
    assert skipped == [{'item': 'i3', 'facet': 'lifecycle', 'reason': 'no stored value'}]


def test_an_abstaining_or_failed_rater_is_not_compared():
    reqs, answers, stored = tiny()
    for r in reqs:
        if r.item['id'] == 'i1':
            answers[r.n] = 'rater: insufficient information'
    defects, skipped = D.compare(reqs, answers, stored)
    assert all(row['item'] != 'i1' for rows in defects.values() for row in rows)
    assert {(s['item'], s['reason']) for s in skipped} >= {('i1', 'rater: insufficient information')}


def test_a_stored_value_outside_the_options_is_not_compared():
    reqs, answers, stored = tiny()
    stored['i2']['lifecycle'] = ['saturated']                       # derived, so never offered
    defects, skipped = D.compare(reqs, answers, stored)
    assert ('lifecycle', 'saturated') not in defects
    assert {'item': 'i2', 'facet': 'lifecycle', 'reason': 'the stored value saturated is not a rated option'} in skipped


# ---- the output and its label ----------------------------------------------------------------------------------

def test_the_output_is_labelled_a_defect_count_with_no_agreement_figure(fake_doc):
    doc = fake_doc
    text = json.dumps(doc)
    assert doc['measure'] == 'defect count' and doc['not_an_agreement_statistic'] is True
    assert 'defect count' in doc['label'].lower() and 'not an agreement statistic' in doc['label'].lower()
    assert D.figures(doc) == [] and D.problems(as_live(doc)) == []
    assert not re.search(r'kappa|jaccard|"f1|percent|\d%', text, re.I)
    assert doc['ranked'] and [r['rank'] for r in doc['ranked']][0] == 1
    run = doc['run']
    assert run['seed'] == 5 and run['prompt_sha256'] == D.PROMPT_SHA256 and run['complete'] is True
    assert run['items'] == 30 and run['requests_planned'] == run['requests_sent'] == 330
    assert 'Claude' in run['drafting_family'] and run['provider'] == 'fake'


def test_a_fake_run_never_writes_the_metric(tmp_path):
    default = os.path.join(ROOT, *D.METRICS.split('/'))
    before = os.path.exists(default) and os.path.getmtime(default)
    assert D.main(['--provider', 'fake', '--model', 'fake', '--seed', '1'], provider=D.Fake(), log=lambda m: None) == 2
    assert (os.path.exists(default) and os.path.getmtime(default)) == before


@pytest.mark.parametrize('flag, path', [('--out', 'data/drift.json'), ('--out', 'data/_analysis/drift.json'),
                                        ('--out', 'taxonomy/_irr/drift.json'), ('--out-prompts', 'data/p.jsonl')])
def test_no_output_under_data(tmp_path, flag, path):
    args = ['--provider', 'fake', '--model', 'fake', '--seed', '1', flag, os.path.join(ROOT, *path.split('/'))]
    if flag == '--out-prompts':
        args += ['--dry-run', '--out', str(tmp_path / 'x.json')]
    assert D.main(args, provider=D.Fake(), log=lambda m: None) == 2
    assert not os.path.exists(os.path.join(ROOT, *path.split('/')))


# ---- --check ---------------------------------------------------------------------------------------------------

def test_check_fails_while_the_metrics_file_is_missing(tmp_path, capsys):
    assert D.main(['--check', '--out', str(tmp_path / 'absent.json')]) == 1
    assert 'does not exist' in capsys.readouterr().out
    proc = subprocess.run([sys.executable, SCRIPT, '--check', '--out', str(tmp_path / 'absent.json')],
                          capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 1 and 'API key' in proc.stdout


def test_check_accepts_a_well_formed_live_run_and_refuses_a_fake_one(tmp_path, capsys, fake_doc):
    doc = fake_doc
    assert D.main(['--check', '--out', write(tmp_path, doc, 'fake.json')]) == 1
    assert "provider is 'fake'" in capsys.readouterr().out
    assert D.main(['--check', '--out', write(tmp_path, as_live(doc))]) == 0
    assert 'not an agreement statistic' in capsys.readouterr().out


def mutations():
    def add_figure(d):
        d['agreement'] = 0.91

    def add_kappa(d):
        d['run']['kappa'] = 1

    def add_percent(d):
        d['run']['note'] = 'the raters agree on 91% of items'

    def add_fraction(d):
        d['ranked'][0]['share_of_items'] = 0.5

    def relabel(d):
        d['label'] = 'Inter-rater agreement between the model and the catalogue.'

    def unflag(d):
        d['not_an_agreement_statistic'] = False

    def claude(d):
        d['run']['model'] = 'claude-opus-5'

    def incomplete(d):
        d['run']['complete'] = False

    def misorder(d):
        d['ranked'][0], d['ranked'][-1] = d['ranked'][-1], d['ranked'][0]

    def miscount(d):
        d['ranked'][0]['defects'] += 1

    def no_seed(d):
        del d['run']['seed']
    return [add_figure, add_kappa, add_percent, add_fraction, relabel, unflag, claude, incomplete, misorder,
            miscount, no_seed]


@pytest.mark.parametrize('mutate', mutations(), ids=lambda f: f.__name__)
def test_check_fails_an_agreement_figure_or_a_broken_file(tmp_path, mutate, fake_doc):
    doc = as_live(fake_doc)
    assert D.problems(doc) == []
    mutate(doc)
    assert D.problems(doc)
    assert D.main(['--check', '--out', write(tmp_path, doc, 'mutated.json')]) == 1


# ---- the Claude refusal --------------------------------------------------------------------------------------

@pytest.mark.parametrize('model', ['claude-opus-5', 'us.anthropic.claude-sonnet-5-v1', 'Claude-Haiku-4-5',
                                   'fable-5', 'anthropic/some-model', 'opus-5'])
def test_a_claude_model_is_refused(tmp_path, model, capsys):
    prompts = tmp_path / 'p.jsonl'
    for provider in ('openai', 'gemini'):
        assert D.main(['--provider', provider, '--model', model, '--dry-run', '--out-prompts', str(prompts)]) == 2
        assert 'Claude' in capsys.readouterr().err
    assert not prompts.exists()


def test_other_families_are_not_refused():
    for model in ('gpt-5', 'gpt-4.1-mini', 'o4-mini', 'gemini-2.5-pro', 'gemini-2.5-flash'):
        assert D.claude_refusal('openai', model) is None


# ---- the request cap -------------------------------------------------------------------------------------------

def test_a_plan_over_the_cap_is_refused_before_any_request(tmp_path, capsys):
    fake = D.Fake()
    out = tmp_path / 'drift.json'
    assert D.main(['--provider', 'fake', '--model', 'fake', '--seed', '1', '--max-requests', '329', '--out', str(out)],
                  provider=fake, log=lambda m: None) == 2
    assert fake.seen == [] and not out.exists()
    assert 'needs 330 requests' in capsys.readouterr().err


def test_a_live_run_needs_a_cap(capsys):
    assert D.main(['--provider', 'openai', '--model', 'gpt-test']) == 2
    assert '--max-requests' in capsys.readouterr().err


def test_retries_count_against_the_cap_and_nothing_is_sent_past_it(irr):
    items, facets, vocab, _ = irr
    reqs = D.plan(items, facets, vocab, 2, max_items=1)             # 11 requests

    class Flaky(D.Fake):
        def rate(self, req):
            self.seen.append(req)
            raise D.Retry('HTTP 503')
    flaky = Flaky()
    answers, sent, complete = D.rate_all(reqs, flaky, max_requests=7)
    assert sent == len(flaky.seen) == 7 and complete is False
    assert answers[reqs[1].n] == 'rater: request failed after 3 attempts (HTTP 503)'
    assert all(answers[r.n].startswith('not sent') for r in reqs[2:])


def test_a_live_provider_through_the_cap(tmp_path, monkeypatch):
    """The OpenAI client with an injected `post`: one post per planned request, answers parsed and checked."""
    posts = []

    def post(body):
        posts.append(body)
        schema = body['response_format']['json_schema']['schema']
        ans = {k: (v['items']['enum'][:1] if k != D.INSUFFICIENT else False) for k, v in schema['properties'].items()}
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(ans)}}]}
    client = D.OpenAI('gpt-test', 4096, secret=SENTINEL, post=post)
    out = str(tmp_path / 'drift.json')
    rc = D.main(['--provider', 'openai', '--model', 'gpt-test', '--seed', '9', '--max-items', '2',
                 '--max-requests', '22', '--out', out], provider=client, log=lambda m: None)
    assert rc == 0 and len(posts) == 22
    with open(out, encoding='utf-8') as fh:
        doc = json.load(fh)
    assert D.problems(doc) == [] and doc['run']['provider'] == 'openai' and doc['run']['requests_sent'] == 22
    assert SENTINEL not in json.dumps(doc) and SENTINEL not in json.dumps(posts)


# ---- the dry run ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize('provider', ['openai', 'gemini'])
def test_a_dry_run_makes_no_network_call_and_reads_no_key(tmp_path, monkeypatch, capsys, provider):
    monkeypatch.setenv('OPENAI_API_KEY', SENTINEL)
    monkeypatch.setenv('GEMINI_API_KEY', SENTINEL)
    prompts = tmp_path / 'prompts.jsonl'
    assert D.main(['--provider', provider, '--model', 'model-x', '--seed', '4', '--dry-run',
                   '--out-prompts', str(prompts)]) == 0              # urlopen raises if anything calls it
    text = prompts.read_text(encoding='utf-8')
    assert SENTINEL not in text and SENTINEL not in capsys.readouterr().out
    rows = [json.loads(line) for line in text.splitlines()]
    assert len(rows) == 330 and [r['request'] for r in rows] == list(range(1, 331))
    body = rows[0]['body']
    if provider == 'openai':
        assert body['model'] == 'model-x' and body['response_format']['json_schema']['strict'] is True
        assert body['messages'][0]['content'] == D.SYSTEM
    else:
        schema = body['generationConfig']['responseSchema']
        assert schema['type'] == 'OBJECT' and 'additionalProperties' not in json.dumps(schema)
        assert body['systemInstruction']['parts'][0]['text'] == D.SYSTEM
    assert not os.path.exists(str(tmp_path / 'drift.json'))


def test_a_dry_run_hashes_the_prompts_a_live_run_would_send(tmp_path, capsys, irr):
    items, facets, vocab, _ = irr
    D.main(['--provider', 'openai', '--model', 'm', '--seed', '6', '--dry-run', '--out-prompts', str(tmp_path / 'p')])
    assert D.requests_sha256(D.plan(items, facets, vocab, 6)) in capsys.readouterr().out


# ---- keys and errors ---------------------------------------------------------------------------------------------

def http_error(code, body, headers=None):
    return urllib.error.HTTPError('https://api.openai.com/v1/chat/completions', code, 'error', headers or {},
                                  io.BytesIO(json.dumps(body).encode('utf-8')))


def test_an_error_never_carries_the_key():
    e = D.failure(http_error(401, {'error': {'message': 'Incorrect API key provided: %s' % SENTINEL,
                                             'type': 'invalid_request_error', 'code': 'invalid_api_key'}}),
                  'openai', 'gpt-test', SENTINEL)
    assert isinstance(e, D.Fatal) and SENTINEL not in str(e) and 'invalid_api_key' in str(e)
    e = D.failure(http_error(400, {'error': {'message': 'bad schema near %s' % SENTINEL, 'code': 'x'}}),
                  'openai', 'gpt-test', SENTINEL)
    assert isinstance(e, D.Fatal) and SENTINEL not in str(e) and 'bad schema' in str(e)
    e = D.failure(http_error(429, {'error': {'code': 'rate_limit_exceeded'}}, {'Retry-After': '7'}),
                  'openai', 'gpt-test', SENTINEL)
    assert isinstance(e, D.Retry) and e.wait == 7.0


def test_a_live_run_without_its_key_is_refused(tmp_path, capsys):
    assert D.main(['--provider', 'gemini', '--model', 'gemini-test', '--max-requests', '400',
                   '--out', str(tmp_path / 'm.json')]) == 2
    assert 'GEMINI_API_KEY is not set' in capsys.readouterr().err


def test_a_corpus_run_waits_for_the_irr_run(tmp_path, capsys):
    assert D.main(['--provider', 'openai', '--model', 'gpt-test', '--scope', 'corpus', '--max-requests', '5000',
                   '--out', str(tmp_path / 'm.json')]) == 2
    assert 'IRR sample' in capsys.readouterr().err


# ---- answers -----------------------------------------------------------------------------------------------------

def test_answers_are_checked_on_the_way_in(irr):
    items, facets, vocab, _ = irr
    r = next(x for x in D.plan(items, facets, vocab, 1, max_items=1) if x.vocabulary == 'domains')
    ids = [o['id'] for o in r.options]
    ok = {'domain_primary': ids[:1], 'domain_secondary': ids[1:3], D.INSUFFICIENT: False}
    assert D.validate(ok, r) == {'domain.primary': sorted(ids[:1]), 'domain.secondary': sorted(ids[1:3])}
    assert D.validate(dict(ok, **{D.INSUFFICIENT: True}), r) is None
    for bad in (dict(ok, domain_primary=ids[:2]), dict(ok, domain_secondary=['not-a-term']),
                {'domain_primary': ids[:1], D.INSUFFICIENT: False}, dict(ok, **{D.INSUFFICIENT: 'no'})):
        with pytest.raises(D.Unrated):
            D.validate(bad, r)
    with pytest.raises(D.Unrated):
        D.parse('not json', r)
