"""scripts/check_croissant.py: every croissant-benchmark document passes mlcroissant and the extension schema, the
schema cannot admit a document that fails base conformance, the published context redefines nothing upstream, and no
committed file carries the Croissant specification's text (P4-S6-T04; 08 S5.8 "Validation in CI", 04 S5).

The verify is `uv run python scripts/check_croissant.py --all`, which pr-validate.yml's croissant-benchmark job runs
over the repository; the done-when: "Every document passes both validators in CI and a deliberately broken schema turns
the job red." The job's last step runs this file, so the red half is shown here, fast, over two fixture trees:

  tests/build/fixtures/minimal   one published benchmark and one withheld draft, so every part --all names is present
  tests/fixtures/corpus-20       twenty drafts and nothing published, the repository's shape today

  documents   each fixture document passes all three checks; a document broken for base conformance, for the
              extension schema or in its @context fails the one it breaks, by name; nothing is fetched to check them
  written     a DIR of written documents meets the same checks, and an empty DIR or a file that is not JSON fails;
              the worked examples (P4-S6-T05's verify: `check_croissant.py docs/croissant-benchmark/examples/`)
              pass them, one entry from each of their three domains, in the form their README regenerates
  schema     the committed schema passes all five rules; a deliberately broken schema fails each, and turns the
              command red, end to end
  context     the published context passes; one that redefines a schema.org term or drifts from the schema fails
  spec        the repository passes; a synthetic "specification" (no upstream text is committed, so none is used)
              shows a copied, a lightly edited and a marked-up passage caught, a short quotation and fenced code not
"""
import copy
import json
import os
import random
import re
import socket
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_croissant as C  # noqa: E402

croissant = C.croissant
MINIMAL = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')
CORPUS_20 = os.path.join(ROOT, 'tests', 'fixtures', 'corpus-20')
EXAMPLES = os.path.join(ROOT, 'docs', 'croissant-benchmark', 'examples')
FAMILIES = {'language': 'language', 'robotics': 'robotics-embodiment', 'chemistry': 'chemistry-materials'}


@pytest.fixture(scope='module')
def committed_schema():
    with open(os.path.join(ROOT, croissant.SCHEMA), encoding='utf-8') as fh:
        return json.load(fh)


@pytest.fixture
def schema(committed_schema):
    return copy.deepcopy(committed_schema)


@pytest.fixture(scope='module')
def built():
    return C.emitted(MINIMAL)


@pytest.fixture
def docs(built):
    return copy.deepcopy(built[0])


@pytest.fixture(scope='module')
def published():
    return C.published_context()


# ---- the documents ------------------------------------------------------------------------------------------------

def test_all_names_every_part_published_drafts_and_both_collections(built):
    docs, parts = built
    assert parts == {'published': 1, 'drafts': 1, 'collections': 2}
    assert sorted(docs) == ['_collection.jsonld', 'alpha-bench.jsonld', 'beta-bench.jsonld',
                            'preview/_collection.jsonld']
    assert [p['benchmarkId'] for p in docs['_collection.jsonld']['hasPart']] == ['alpha-bench']
    assert [p['benchmarkId'] for p in docs['preview/_collection.jsonld']['hasPart']] == ['alpha-bench', 'beta-bench']


def test_with_nothing_published_the_drafts_are_what_is_checked():
    """The repository's shape today: every benchmark a draft, the published collection empty."""
    docs, parts = C.emitted(CORPUS_20)
    assert parts == {'published': 0, 'drafts': 20, 'collections': 2}
    assert docs['_collection.jsonld']['hasPart'] == [] and len(docs['preview/_collection.jsonld']['hasPart']) == 20


def test_every_fixture_document_passes_all_three(docs, committed_schema, published):
    problems, notices = C.document_problems(docs, committed_schema, published)
    assert problems == [] and notices > 0


def test_nothing_is_fetched_to_check_them(monkeypatch, docs, committed_schema, published):
    """The upstream context is the pinned mlcroissant's and ours the committed file: a document names no context IRI
    a processor would have to resolve, and the check passes with every connection refused."""
    def refuse(*a, **k):
        raise OSError('no network in this test')
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    assert all(isinstance(d['@context'], dict) for d in docs.values())
    assert C.document_problems(docs, committed_schema, published)[0] == []


def broken_documents():
    def no_dataset(d):
        d['@type'] = ['cb:Benchmark']
        return 'fails Croissant base conformance'

    def headline_yes(d):
        d['metrics'][0]['isHeadline'] = 'yes'
        return "fails the extension schema at /metrics/0/isHeadline: 'yes' is not of type 'boolean'"

    def unbound_key(d):
        d['benchmarkScore'] = 1
        return "fails the extension schema at /: Additional properties are not allowed ('benchmarkScore'"

    def redefines_name(d):                                      # an upstream key: a language container upstream
        d['@context']['name'] = 'cb:name'
        return ("its @context is not the upstream context plus %s (missing none; extra none; differing ['name'])"
                % croissant.CONTEXT)

    def binds_a_schema_org_term(d):
        d['@context']['headline'] = 'cb:headline'
        return "(missing none; extra ['headline']; differing none)"

    def drops_a_term(d):
        del d['@context']['tasks']
        return "missing ['tasks']; extra none; differing none)"

    def croissant_1_0(d):
        d['conformsTo'] = ['http://mlcommons.org/croissant/1.0', croissant.EXTENSION_VERSION]
        return "fails the extension schema at /conformsTo/0: 'http://mlcommons.org/croissant/1.1' was expected"
    return [no_dataset, headline_yes, unbound_key, redefines_name, binds_a_schema_org_term, drops_a_term,
            croissant_1_0]


@pytest.mark.parametrize('break_it', broken_documents(), ids=lambda f: f.__name__)
def test_a_deliberately_broken_document_fails_what_it_breaks(break_it, docs, committed_schema, published):
    want = break_it(docs['alpha-bench.jsonld'])
    problems, _ = C.document_problems(docs, committed_schema, published)
    assert problems and all(p.startswith('alpha-bench.jsonld: ') for p in problems), problems
    assert any(want in p for p in problems), problems


# ---- written documents: DIR (P4-S6-T05) ---------------------------------------------------------------------------

def write_documents(folder, docs):
    folder.mkdir()
    for name, doc in docs.items():
        (folder / name).write_bytes(croissant.serialise(doc))
    return str(folder)


def test_a_directory_of_written_documents_meets_the_same_checks(monkeypatch, tmp_path, docs, capsys):
    """Both kinds, read from disk: a benchmark document and the collection, by file name; one broken goes red."""
    monkeypatch.setattr(C, 'spec_problems', lambda root: ([], {}))
    folder = write_documents(tmp_path / 'written', {n: docs[n] for n in ('alpha-bench.jsonld', '_collection.jsonld')})
    assert C.main([folder]) == 0
    out = capsys.readouterr().out
    assert 'croissant: written: 2 document(s) checked under ' in out and 'croissant: 0 problem(s)' in out
    docs['alpha-bench.jsonld']['metrics'][0]['isHeadline'] = 'yes'
    (tmp_path / 'written' / 'alpha-bench.jsonld').write_bytes(croissant.serialise(docs['alpha-bench.jsonld']))
    assert C.main([folder]) == 1
    out = capsys.readouterr().out
    assert re.search(r"^BLOCKING  croissant  .*written/alpha-bench\.jsonld: fails the extension schema at "
                     r"/metrics/0/isHeadline: 'yes' is not of type 'boolean'$", out, re.M), out
    assert 'croissant: 1 problem(s)' in out


def test_an_empty_missing_or_unreadable_directory_fails_rather_than_passing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(C, 'spec_problems', lambda root: ([], {}))
    (tmp_path / 'empty').mkdir()
    (tmp_path / 'broken').mkdir()
    (tmp_path / 'broken' / 'x.jsonld').write_text('{"@type": ', encoding='utf-8')
    assert C.main([str(tmp_path / n) for n in ('empty', 'missing', 'broken')]) == 1
    out = capsys.readouterr().out
    assert out.count('holds no .jsonld document to check, which is never a pass') == 2
    assert re.search(r'^BLOCKING  croissant  .*broken/x\.jsonld: cannot be read as JSON', out, re.M), out
    assert 'croissant: 3 problem(s)' in out


def test_the_worked_examples_pass_one_entry_from_each_of_three_domains(committed_schema, published):
    """P4-S6-T05: language, robotics and chemistry, each its entry's document as the emitter writes it (sorted keys,
    indented: docs/croissant-benchmark/README.md regenerates them), each from the domain its file names."""
    from ruamel.yaml import YAML
    docs, unread = C.written([EXAMPLES])
    assert unread == [] and sorted(os.path.basename(n) for n in docs) == ['chemistry.jsonld', 'language.jsonld',
                                                                           'robotics.jsonld']
    assert C.document_problems(docs, committed_schema, published)[0] == []
    for name, doc in docs.items():
        with open(os.path.join(ROOT, name), encoding='utf-8') as fh:
            assert fh.read() == json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + '\n', name
        [entry] = [os.path.join(d, f) for d, _, fs in os.walk(os.path.join(ROOT, 'data', 'benchmarks'))
                   for f in fs if f == doc['benchmarkId'] + '.yaml']
        with open(entry, encoding='utf-8') as fh:
            primary = YAML(typ='safe').load(fh)['domain']['primary']
        assert primary.split('/')[0] == FAMILIES[os.path.basename(name)[:-len('.jsonld')]], (name, primary)


# ---- the schema ---------------------------------------------------------------------------------------------------

def test_the_committed_schema_holds_to_base_conformance(committed_schema, docs):
    assert C.schema_problems(committed_schema, C.samples_of(docs)) == []


def test_without_documents_the_probes_say_they_did_not_run(monkeypatch, capsys):
    monkeypatch.setattr(C, 'spec_problems', lambda root: ([], {}))
    assert C.main([]) == 0
    assert 'the essentials and minimal probes NOT RUN (they need --all)' in capsys.readouterr().out


def broken_schemas():
    defs = lambda s: s['$defs']                                     # noqa: E731

    def not_a_schema(s):
        defs(s)['TaskNode']['type'] = 'objekt'
        return 'not a valid Draft 2020-12 schema'

    def redefines_a_schema_org_term(s):
        defs(s)['Context']['properties']['headline'] = {'const': 'cb:headline', 'type': 'string'}
        defs(s)['Context']['required'].append('headline')
        return 'the Context binds headline to our namespace, redefining a schema.org term'

    def redefines_an_upstream_key(s):
        defs(s)['Context']['properties']['recordSet'] = {'const': 'cb:recordSet', 'type': 'string'}
        defs(s)['Context']['required'].append('recordSet')
        return 'the Context binds recordSet to our namespace, redefining an upstream context key'

    def moves_the_vocab(s):
        defs(s)['Context']['properties']['@vocab']['const'] = 'https://example.org/'
        return "the Context must require @vocab, pinned to 'https://schema.org/'"

    def lets_a_term_go_unbound(s):
        defs(s)['Context']['required'].remove('tasks')
        return "the Context must require tasks, pinned to 'cb:tasks'"

    def admits_an_unbound_key(s):
        defs(s)['MetricNode']['properties']['benchmarkScore'] = {'type': 'number'}
        return 'MetricNode admits benchmarkScore, which no context binds'

    def loosens_the_type(s):
        defs(s)['BenchmarkDocument']['properties']['@type'] = {'type': 'array', 'items': {'type': 'string'}}
        return 'admits a BenchmarkDocument with an @type without sc:Dataset'

    def loosens_conforms_to(s):
        defs(s)['CollectionDocument']['properties']['conformsTo'] = {'type': 'array', 'items': {'type': 'string'}}
        return 'admits a CollectionDocument with a conformsTo without %s' % croissant.CROISSANT_VERSION

    def makes_the_type_optional(s):
        defs(s)['BenchmarkDocument']['required'].remove('@type')
        return "doesn't extend https://schema.org/Dataset"

    def makes_conforms_to_optional(s):
        defs(s)['BenchmarkDocument']['required'].remove('conformsTo')
        return 'contains forbidden characters'                     # read as Croissant 1.0, whose names are stricter
    return [not_a_schema, redefines_a_schema_org_term, redefines_an_upstream_key, moves_the_vocab,
            lets_a_term_go_unbound, admits_an_unbound_key, loosens_the_type, loosens_conforms_to,
            makes_the_type_optional, makes_conforms_to_optional]


@pytest.mark.parametrize('break_it', broken_schemas(), ids=lambda f: f.__name__)
def test_a_deliberately_broken_schema_fails(break_it, schema, docs):
    want = break_it(schema)
    problems = C.schema_problems(schema, C.samples_of(docs))
    assert any(want in p for p in problems), problems
    assert all(p.startswith(croissant.SCHEMA + ': ') for p in problems), problems


def test_a_deliberately_broken_schema_turns_the_command_red(monkeypatch, tmp_path, schema, capsys):
    """End to end, as the job runs it: --all over a fixture tree, with the committed schema and then a broken one."""
    monkeypatch.setattr(C, 'spec_problems', lambda root: ([], {}))     # its own tests are below; the scan takes a while
    assert C.main(['--corpus', MINIMAL]) == 0
    out = capsys.readouterr().out
    assert 'croissant: documents: 4 checked -- 1 published benchmark(s), 1 draft(s)' in out
    assert 'croissant: 0 problem(s)' in out
    schema['$defs']['BenchmarkDocument']['required'].remove('@type')
    path = tmp_path / 'broken.schema.json'
    path.write_text(json.dumps(schema), encoding='utf-8')
    assert C.main(['--corpus', MINIMAL, '--schema', str(path)]) == 1
    out = capsys.readouterr().out
    assert re.search(r'^BLOCKING  croissant  \S*broken\.schema\.json: admits a BenchmarkDocument with only ', out, re.M)
    assert 'croissant: 1 problem(s)' in out


def test_a_schema_that_is_no_schema_is_reported_not_crashed_on(monkeypatch, tmp_path, schema, capsys):
    monkeypatch.setattr(C, 'spec_problems', lambda root: ([], {}))
    schema['$defs']['TaskNode']['type'] = 'objekt'
    path = tmp_path / 'broken.schema.json'
    path.write_text(json.dumps(schema), encoding='utf-8')
    assert C.main(['--corpus', MINIMAL, '--schema', str(path)]) == 1
    out = capsys.readouterr().out
    assert 'broken.schema.json: not a valid Draft 2020-12 schema' in out and 'croissant: 1 problem(s)' in out


def test_a_build_that_fails_is_a_failure_not_an_empty_pass(monkeypatch, capsys):
    from tools.build.emit import Refused
    monkeypatch.setattr(C, 'spec_problems', lambda root: ([], {}))

    def refuse(corpus):
        raise Refused(['build: a deliberately failing build'])
    monkeypatch.setattr(C, 'emitted', refuse)
    assert C.main(['--all']) == 1
    assert 'BLOCKING  croissant  build: a deliberately failing build' in capsys.readouterr().out


# ---- the published context ----------------------------------------------------------------------------------------

def test_the_published_context_redefines_nothing_upstream(published, committed_schema):
    assert C.context_problems(published, committed_schema) == []
    assert published['@context'][0] == croissant.CROISSANT_VERSION


def test_a_published_context_that_redefines_or_drifts_fails(published, committed_schema):
    bad = copy.deepcopy(published)
    bad['@context'][1].update({'name': 'cb:name', 'headline': 'cb:headline'})
    problems = C.context_problems(bad, committed_schema)
    assert '%s: name redefines an upstream context key; name ours differently' % croissant.CONTEXT in problems
    assert '%s: headline redefines a schema.org term; name ours differently' % croissant.CONTEXT in problems
    assert any("(extra ['headline', 'name']; missing none)" in p for p in problems), problems
    bad = copy.deepcopy(published)
    bad['@context'][1]['tasks'] = 'https://example.org/tasks'
    assert any("tasks is bound to 'https://example.org/tasks'" in p for p in C.context_problems(bad, committed_schema))
    bad = copy.deepcopy(published)
    bad['@context'].reverse()
    assert 'the upstream context first' in C.context_problems(bad, committed_schema)[0]


# ---- the specification guard ------------------------------------------------------------------------------------

def test_the_repository_carries_no_copy_of_the_specification():
    problems, stats = C.spec_problems(ROOT)
    assert problems == []
    assert stats['scanned'] > 1000


def test_the_fingerprints_are_hashes_from_the_two_versions():
    with open(os.path.join(ROOT, C.FINGERPRINTS), encoding='utf-8') as fh:
        doc = json.load(fh)
    assert doc['method'] == C.fingerprint([])['method']
    assert [s['name'] for s in doc['sources']] == ['croissant-spec-1.0.md', 'croissant-spec-1.1.md']
    assert all(len(s['sha256']) == 64 for s in doc['sources'])
    fps = C.load_fingerprints()
    assert len(fps) >= 1000 and doc['fingerprints'] == sorted(fps)
    assert all(len(h) == 16 and int(h, 16) % C.SAMPLE == 0 for h in fps)


def test_fingerprints_from_another_method_are_refused(tmp_path):
    (tmp_path / 'scripts').mkdir()
    doc = C.fingerprint([])
    doc['method']['shingle'] = C.SHINGLE + 1
    (tmp_path / C.FINGERPRINTS).write_text(json.dumps(doc), encoding='utf-8')
    problems, _ = C.spec_problems(str(tmp_path), files=[])
    assert len(problems) == 1 and 'regenerate it with --fingerprint' in problems[0]


@pytest.fixture
def specification(tmp_path):
    """A synthetic specification: seeded nonsense prose, with one fenced example. No upstream text is used."""
    rng = random.Random(20261126)
    vocab = ['%s%s' % (rng.choice('bcdfghklmnprstvz'), rng.choice(['ala', 'eno', 'iru', 'oki', 'uma']))
             for _ in range(400)]
    prose = ' '.join(rng.choice(vocab) for _ in range(3000))
    fence = '```json\n{"@type": "sc:Dataset", "name": "example example example example example example example"}\n```'
    path = tmp_path / 'spec.md'
    path.write_text('# A specification\n\n%s\n\n%s\n' % (prose[:len(prose) // 2], fence)
                    + prose[len(prose) // 2:], encoding='utf-8')
    return prose.split(), C.fingerprint([str(path)]), fence


def scan(tmp_path, fps, **files):
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding='utf-8')
    return C.spec_problems(str(tmp_path), set(fps['fingerprints']), sorted(files))


def test_a_copied_passage_turns_the_guard_red(tmp_path, specification):
    words, fps, _ = specification
    passage = ' '.join(words[1000:1150])
    edited = words[1400:1700]
    for i in range(0, len(edited), 20):                         # a word changed in every twenty: still a copy
        edited[i] = 'changed'
    marked_up = ''.join('<span class="w">%s</span> ' % w for w in words[2000:2150])
    problems, stats = scan(tmp_path, fps, **{'copy.md': 'Intro.\n\n' + passage, 'edited.txt': ' '.join(edited),
                                             'marked.html': '<p>%s</p>' % marked_up})
    assert sorted(p.split(':')[0] for p in problems) == ['copy.md', 'edited.txt', 'marked.html'], problems
    assert all('CC BY-ND 4.0: link to it, never commit its text' in p for p in problems)
    assert stats['scanned'] == 3


def test_a_short_quotation_and_the_fenced_examples_stay_below_it(tmp_path, specification):
    words, fps, fence = specification
    problems, stats = scan(tmp_path, fps, **{'quote.md': 'As the specification puts it, "%s".' % ' '.join(words[10:25]),
                                             'example.jsonld': fence.split('\n')[1]})
    assert problems == [] and stats['most'] < C.THRESHOLD


def test_a_tree_it_cannot_list_fails_rather_than_passing_unscanned(tmp_path):
    problems, stats = C.spec_problems(str(tmp_path / 'missing'), set())
    assert len(problems) == 1 and 'none is vouched for' in problems[0] and stats == {}
