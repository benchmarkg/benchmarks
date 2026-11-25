"""Tests for the S8 emitter: facets.json, corpus.json and enums.json (P2-S1-T02; tools/build/emit.py; 08 S4.2, S3.2, S6).

The verify: "`uv run bench build --out build/ && uv run pytest tests/build/test_emit_artifacts.py && python
scripts/check_display_only_vocab.py --artifacts build/`", done when "the three artifacts carry exactly 08
S4.2's field lists, corpus.json holds no claim records, and no domain-group id appears in any of them".

The fixture, tests/fixtures/corpus-20/, is a frozen copy of twenty entries of data/ -- one from each of
the nineteen domain families, mostly the smallest by bytes and Sources, except that critpt, scicode and mmlu
stand for physics, code and general intelligence because they carry claims, and virtual-cell-challenge for
biology because its `wet-lab` reproducibility blocker is the one term id two fields of one facet share; and
kaggle-game-arena as the twentieth, for its subsets -- plus every record they need to build: the 11 metrics
they name, 15 claims (every claim on critpt and scicode, two of mmlu's), the 13 EvalConditions those claims
name, the 10 systems and 6 organizations the claims cite, and the 88 Sources all of those cite. Every file is
copied byte for byte from data/ as it stood on 2026-11-17 and is never edited; the taxonomy is the
repository's, which is what the build reads whatever data root it is given. Every entry is still
ai-drafted-unverified, which 05 S4
never publishes, so these tests build the fixture as the draft preview does (`drafts=True`,
scripts/preview_corpus.py): a draft that passes tier 1 is included. A test that needs something the frozen
records do not hold plants it in a temporary copy.

What is asserted: exactly 08 S4.2's field lists, with 11 S4's edition names on each facets.json row and the
format that says so; no claim record in corpus.json, and the refusal of one; no domain-group id in any of the
three, and the refusal of a planted one (and of a group id that equals a term id); byte-identical output
across two builds; NFC, LF and sorted keys; enums.json covering every facet file and every term; and the
claim-derived fields and the edition names, computed independently here.
"""
import copy
import glob
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unicodedata

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.taxonomy import FILES, read_yaml  # noqa: E402
from tools.build import artifacts, comparability, emit  # noqa: E402
from tools.validate import tiers  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'corpus-20')
CHECK = os.path.join(ROOT, 'scripts', 'check_display_only_vocab.py')
TAXONOMY = os.path.join(ROOT, 'taxonomy')

# 08 S4.2's rows, written out here rather than read from the emitter, so the test pins the plan: facets.json's is
# 08 S4.2's list with 11 S4's `editions` beside the aliases (the BM25 leg's edition names, P6-S1-T04).
FACETS_ROW = ['id', 'slug', 'name', 'aliases', 'editions', 'domain', 'subdomain', 'facets', 'year', 'lifecycle',
              'verification_max', 'condition_completeness_max', 'claim_count', 'headroom']
SEVEN = ['capability', 'evaluation_method', 'subject', 'data_properties', 'lifecycle', 'governance', 'execution']
CORPUS_KINDS = ['benchmark', 'system', 'organization', 'metric', 'source']
TERM = {'id', 'key', 'label', 'status', 'gloss'}


def group_ids() -> list[str]:
    return [g['id'] for g in read_yaml(os.path.join(TAXONOMY, 'domain_groups.yaml'))['groups']]


def run_check(art) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, CHECK, '--artifacts', str(art)], capture_output=True, text=True,
                          encoding='utf-8')


def read(out, name) -> dict:
    with open(os.path.join(out, name), encoding='utf-8') as fh:
        return json.load(fh)


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    """The fixture, built once as the preview, and written."""
    out = tmp_path_factory.mktemp('corpus-20')
    result = artifacts.build(FIXTURE, drafts=True)
    assert result.errors == []
    artifacts.write(result, str(out))
    return result, out


@pytest.fixture
def tree(tmp_path):
    """A writable copy of the fixture."""
    shutil.copytree(FIXTURE, tmp_path / 'root')
    return tmp_path / 'root'


def edit(tree, rel, old, new):
    path = tree / rel
    text = path.read_text(encoding='utf-8')
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')


def rows(result) -> dict:
    return {r['id']: r for r in result.facets['benchmarks']}


# ---- the fixture is what the docstring says --------------------------------------------------------------

def test_the_fixture_is_twenty_drafts_across_every_family_and_builds_complete(built):
    result, _ = built
    families = {t.id for t in emit.taxonomy()['domains.yaml'].terms if t.parent is None}
    assert len(result.facets['benchmarks']) == 20
    assert {r['domain'] for r in result.facets['benchmarks']} == families
    assert result.excluded == []                         # every Source is cited, and nothing fails tier 1
    assert len(glob.glob(os.path.join(FIXTURE, 'data', 'claims', '**', '*.yaml'), recursive=True)) == 15
    published = artifacts.build(FIXTURE)                 # 05 S4: a draft is never published
    assert published.errors == [] and published.corpus['entities']['benchmark'] == []
    size = sum(os.path.getsize(p) for p in glob.glob(os.path.join(FIXTURE, '**', '*'), recursive=True) if os.path.isfile(p))
    assert size < 1_500_000


# ---- exactly 08 S4.2's field lists ----------------------------------------------------------------------

def test_facets_rows_carry_exactly_08_s4_2s_list(built):
    result, out = built
    facets = read(out, 'facets.json')
    assert list(emit.FACET_ROW) == FACETS_ROW
    assert sorted(facets) == ['artifact', 'benchmarks', 'claim_basis', 'drafts', 'format', 'vocabularies']
    assert facets['format'] == emit.FORMATS['facets'] == 3          # 3 since `editions` (P6-S1-T04)
    for row in facets['benchmarks']:
        assert sorted(row) == sorted(FACETS_ROW), row['id']
        assert sorted(row['facets']) == sorted(SEVEN), row['id']
        for facet, values in row['facets'].items():
            assert all(isinstance(v, str) for v in values) and len(set(values)) == len(values), (row['id'], facet)
        assert row['slug'] == row['id'] and row['subdomain'].split('/')[0] == row['domain']
        assert isinstance(row['claim_count'], int) and row['headroom'] is None
        assert row['year'] is None or isinstance(row['year'], int)
    assert 'domain_secondary' not in json.dumps(facets)  # secondaries are not in 08's list (emit.py docstring)


def test_editions_are_the_edition_names_and_nothing_else(built, tree):
    """11 S4: an edition enters retrieval as an alias string on its family's row, never as a row of its own. Each
    row's are read here from the benchmark's YAML, not from corpus.json."""
    result, _ = built
    want = {}
    for path in glob.glob(os.path.join(FIXTURE, 'data', 'benchmarks', '**', '*.yaml'), recursive=True):
        doc = read_yaml(path)
        want[doc['id']] = [v.get('label') or v['version'] for v in doc.get('versions') or []
                           if v.get('version_kind') == 'edition']
    assert {i: r['editions'] for i, r in rows(result).items()} == want
    assert rows(result)['virtual-cell-challenge']['editions'] == [
        'The inaugural edition, one cell line (H1 hESC)', 'Zero-shot across cell contexts']
    assert sum(1 for r in want.values() if r) == 1                  # the only fixture entry with versions
    # an edition with no label is named by its tag; a revision is not an edition
    vcc = 'data/benchmarks/biology-genetics/virtual-cell-challenge.yaml'
    edit(tree, vcc, '    label: Zero-shot across cell contexts\n', '')
    edit(tree, vcc, '(H1 hESC)\n    version_kind: edition', '(H1 hESC)\n    version_kind: revision')
    planted = artifacts.build(str(tree), drafts=True)
    assert planted.errors == []
    assert rows(planted)['virtual-cell-challenge']['editions'] == ['2026']


def test_corpus_json_carries_every_published_field_of_the_five_kinds(built):
    from schema.benchmark import Benchmark
    from schema.entities import Organization
    from schema.metric import Metric
    from schema.source import Source
    from schema.system import System
    _, out = built
    corpus = read(out, 'corpus.json')
    assert sorted(corpus) == ['artifact', 'drafts', 'entities', 'format', 'subsets']
    assert sorted(corpus['entities']) == sorted(CORPUS_KINDS)
    models = {'benchmark': Benchmark, 'system': System, 'organization': Organization, 'metric': Metric,
              'source': Source}
    for kind, records in corpus['entities'].items():
        fields = {f.alias or n for n, f in models[kind].model_fields.items()}
        assert records, kind
        for r in records:
            assert fields <= set(r), (kind, r['id'], sorted(fields - set(r)))
            assert not set(models[kind].model_computed_fields) & set(r), (kind, r['id'])
    assert {s['benchmark'] for s in corpus['subsets']} == {'kaggle-game-arena', 'virtual-cell-challenge'}


def test_enums_json_shape(built):
    _, out = built
    enums = read(out, 'enums.json')
    assert sorted(enums) == ['artifact', 'flat_facets', 'format', 'taxonomy', 'vocabularies']
    assert sorted(enums['flat_facets']) == sorted(SEVEN)
    for name, vocab in enums['vocabularies'].items():
        assert sorted(vocab) == ['facet_kind', 'file', 'gloss', 'terms', 'version'], name
        for t in vocab['terms']:
            assert TERM <= set(t) and set(t) - TERM <= {'field', 'parent', 'members', 'rank', 'machine_assignable'}, (name, t)


# ---- no claim records in corpus.json ----------------------------------------------------------------------

def test_corpus_json_holds_no_claim_record(built):
    _, out = built
    corpus = read(out, 'corpus.json')
    assert emit.claim_records(corpus) == []
    text = (out / 'corpus.json').read_text(encoding='utf-8')
    claims = [os.path.basename(p)[:-5] for p in glob.glob(os.path.join(FIXTURE, 'data', 'claims', '**', '*.yaml'), recursive=True)]
    assert claims and not [c for c in claims if c in text]


def test_a_claim_record_in_corpus_json_is_refused_and_nothing_is_written(built, tmp_path):
    result, _ = built
    claim = read_yaml(os.path.join(FIXTURE, 'data', 'claims', 'mmlu', 'claim-0dde30099ecc.yaml'))
    planted = json.loads(json.dumps(claim, default=str))
    for where in (lambda c: c['entities'].setdefault('claim', []).append(planted),
                  lambda c: c['entities']['benchmark'][0].update(results_observed=[dict(planted, id='x')])):
        corpus = copy.deepcopy(result.corpus)
        where(corpus)
        assert emit.claim_records(corpus)
        with pytest.raises(emit.Refused, match='claim record'):
            emit.write({'corpus.json': corpus, 'facets.json': result.facets, 'enums.json': result.enums},
                       str(tmp_path / 'out'))
        assert not (tmp_path / 'out').exists()


# ---- no domain-group id anywhere ------------------------------------------------------------------------

def test_no_domain_group_id_in_any_of_the_three(built):
    _, out = built
    pattern = emit.token_re(group_ids())
    for name in emit.ARTIFACTS:
        assert not pattern.search((out / name).read_text(encoding='utf-8')), name
    r = run_check(out)
    assert r.returncode == 0, r.stdout
    for name in emit.ARTIFACTS:
        assert 'PASS    %s' % name in r.stdout


def test_a_planted_group_id_fails_the_build_and_ci_9h(built, tree, tmp_path):
    gid = group_ids()[4]
    edit(tree, 'data/benchmarks/physics/critpt.yaml', 'aliases:\n', 'aliases:\n  - %s\n' % gid)
    result = artifacts.build(str(tree), drafts=True)
    assert result.corpus == {} and result.facets == {} and result.enums == {}
    assert any('corpus.json: entities.benchmark[' in e and gid in e for e in result.errors), result.errors
    assert any('facets.json: benchmarks[' in e and '.aliases[0]' in e for e in result.errors), result.errors
    # the same artifacts, built past the refusal and handed to write: refused again, nothing written
    clean, _ = built
    enums = copy.deepcopy(clean.enums)
    enums['vocabularies']['capability']['terms'][0]['gloss'] += ' See %s.' % gid     # a token in prose counts
    with pytest.raises(emit.Refused, match=gid):
        emit.write({'corpus.json': clean.corpus, 'facets.json': clean.facets, 'enums.json': enums}, str(tmp_path / 'out'))
    assert not (tmp_path / 'out').exists()
    # and CI 9h, over a directory holding that enums.json, names the path
    art = tmp_path / 'art'
    art.mkdir()
    for name, doc in (('corpus.json', clean.corpus), ('facets.json', clean.facets), ('enums.json', enums)):
        (art / name).write_bytes(emit.serialise(doc))
    r = run_check(art)
    assert r.returncode == 1 and 'enums.json vocabularies.capability.terms[0].gloss -> %s' % gid in r.stdout


def test_ci_9h_fails_an_emitted_artifact_it_cannot_parse_and_names_an_absent_one(built, tmp_path):
    _, out = built
    art = tmp_path / 'art'
    art.mkdir()
    shutil.copyfile(out / 'facets.json', art / 'facets.json')
    (art / 'corpus.json').write_text('{"artifact": "corpus", ', encoding='utf-8')
    r = run_check(art)
    assert r.returncode == 1 and 'corpus.json does not parse' in r.stdout
    assert 'NOT RUN enums.json' in r.stdout and 'PASS    facets.json' in r.stdout


def test_a_group_id_that_is_also_a_term_id_is_refused(monkeypatch):
    models = dict(emit.taxonomy())
    g = models['domain_groups.yaml']
    renamed = [g.groups[0].model_copy(update={'id': 'knowledge-recall'})] + list(g.groups[1:])
    models['domain_groups.yaml'] = g.model_copy(update={'groups': renamed})
    monkeypatch.setattr(emit, 'taxonomy', lambda: models)
    with pytest.raises(emit.Refused, match='knowledge-recall is also an id in taxonomy/capabilities.yaml'):
        emit.display_only_ids()
    spec = importlib.util.spec_from_file_location('check_display_only_vocab', CHECK)
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    assert check.check_homonyms(set(group_ids()), TAXONOMY) == []
    assert 'taxonomy/capabilities.yaml' in check.check_homonyms({'knowledge-recall'}, TAXONOMY)[0]


def test_no_group_id_is_another_vocabularys_id_today():
    assert emit.display_only_ids() == frozenset(group_ids())


# ---- enums.json covers every facet file and every term --------------------------------------------------

def test_enums_json_covers_every_facet_file_and_term(built):
    _, out = built
    enums = read(out, 'enums.json')
    declared = {}
    for path in sorted(glob.glob(os.path.join(TAXONOMY, '*.yaml'))):
        doc = read_yaml(path)
        if isinstance(doc, dict) and 'facet' in doc:
            declared[doc['facet']] = (os.path.basename(path), doc)
    assert sorted(declared) == sorted(f for _, f in emit.facet_files())
    assert sorted(enums['vocabularies']) == sorted(list(declared) + ['verification'])
    assert enums['taxonomy'] == open(os.path.join(TAXONOMY, 'VERSION'), encoding='utf-8').read().strip()
    for facet, (name, doc) in declared.items():
        vocab = enums['vocabularies'][facet]
        assert vocab['file'] == 'taxonomy/' + name and vocab['version'] == str(doc['version'])
        assert vocab['facet_kind'] == doc['facet_kind'] and vocab['gloss'] == ' '.join(doc['description'].split())
        items = doc['terms'] if 'terms' in doc else doc['groups']                       # capability_groups.yaml
        assert [t['id'] for t in vocab['terms']] == [t['id'] for t in items], facet
        for got, want in zip(vocab['terms'], items):
            assert got['label'] == want['label']
            assert got['status'] == want.get('status')                                  # a group has none
            assert got['gloss'] == (' '.join(want['definition'].split()) if 'definition' in want else None)
            assert got.get('field') == want.get('field')
            if 'members' in want:
                assert got['members'] == want['members']
    rungs = read_yaml(os.path.join(TAXONOMY, 'verification.yaml'))['rungs']
    assert [(t['id'], t['rank']) for t in enums['vocabularies']['verification']['terms']] == \
        sorted(((r['id'], r['rank']) for r in rungs), key=lambda x: x[1])


def test_every_facets_value_joins_to_exactly_one_enums_term(built):
    _, out = built
    enums, facets = read(out, 'enums.json'), read(out, 'facets.json')
    for row in facets['benchmarks']:
        for facet, values in row['facets'].items():
            spec = enums['flat_facets'][facet]
            terms = [t for v in spec['vocabularies'] for t in enums['vocabularies'][v]['terms']]
            for value in values:
                hits = [t for t in terms if t['key'] == value]
                assert len(hits) == 1, (row['id'], facet, value)
                assert hits[0].get('field', spec['fields'][0]) in spec['fields']
        assert [t['key'] for t in enums['vocabularies']['domain']['terms'] if t['key'] == row['subdomain']]
        if row['verification_max'] is not None:
            assert [t for t in enums['vocabularies']['verification']['terms'] if t['id'] == row['verification_max']]


def test_an_id_two_fields_of_one_facet_share_is_written_with_its_field(built):
    result, _ = built
    shared = set()
    for facet, (files, fields) in emit.FLAT_FACETS.items():
        seen = {}
        for name in files:
            for t in read_yaml(os.path.join(TAXONOMY, name))['terms']:
                seen.setdefault(t['id'], set()).add(t.get('field', fields[0]))
        shared |= {(facet, i) for i, fs in seen.items() if len(fs) > 1}
    assert ('execution', 'wet-lab') in shared                      # 02 S11 rule 11: by design
    keys = emit.term_keys()
    for facet, ident in shared:
        assert all(v == '%s:%s' % (f, i) for (f, i), v in keys[facet].items() if i == ident)
    assert all(v == i for facet, k in keys.items() for (f, i), v in k.items() if (facet, i) not in shared)
    vcc = rows(result)['virtual-cell-challenge']['facets']['execution']
    assert 'execution.reproducibility_blockers:wet-lab' in vcc and 'wet-lab' not in vcc
    wet = [t for t in result.enums['vocabularies']['execution']['terms'] if t['id'] == 'wet-lab']
    assert sorted(t['key'] for t in wet) == ['execution.compute_tier:wet-lab', 'execution.reproducibility_blockers:wet-lab']


def benchmark_field(dotted: str) -> bool:
    """Whether a dotted path names a Benchmark field, through its nested blocks."""
    from schema.benchmark import Benchmark
    model = Benchmark
    for part in dotted.split('.'):
        if not (isinstance(model, type) and part in model.model_fields):
            return False
        model = model.model_fields[part].annotation
    return True


def test_the_flat_facets_table_is_the_taxonomys():
    flat = []
    for name, (_, facet) in sorted(FILES.items()):
        doc = read_yaml(os.path.join(TAXONOMY, name))
        if facet is not None and doc['facet_kind'] == 'flat' and 'terms' in doc:     # not the capability groups
            flat.append(name)
    placed = [f for files, _ in emit.FLAT_FACETS.values() for f in files]
    assert sorted(placed) == flat and len(placed) == len(set(placed))     # every flat vocabulary, in one facet
    assert sorted(emit.FLAT_FACETS) == sorted(SEVEN)
    for facet, (files, fields) in emit.FLAT_FACETS.items():
        declared = {t['field'] for name in files for t in read_yaml(os.path.join(TAXONOMY, name))['terms'] if 'field' in t}
        assert declared == set(fields) or (not declared and len(fields) == 1), facet
        for field in fields:
            assert benchmark_field(field) != (field in emit.NOT_YET_DERIVED), field
    assert emit.NOT_YET_DERIVED == {'maintenance_status'}


# ---- the claim-derived fields ----------------------------------------------------------------------------

def completeness(root) -> dict[str, float | None]:
    """claim id -> condition_completeness, as the quality tier computes it (tools/validate/tiers.py
    quality_tier), from the records under `root` and the repository's comparability profiles."""
    from schema.benchmark import load_benchmark
    from schema.claim import ResultClaim
    from schema.conditions import EvalConditions
    profiles = comparability.load_profiles()
    resolved = {}
    for path in glob.glob(os.path.join(root, 'data', 'benchmarks', '*', '*.yaml')):
        b = load_benchmark(path)
        resolved[b.id] = comparability.resolve_profile(b, profiles)
    conditions = {}
    for path in glob.glob(os.path.join(root, 'data', 'conditions', '*.yaml')):
        cond = EvalConditions.model_validate(read_yaml(path))
        conditions[cond.id] = cond
    out = {}
    for path in glob.glob(os.path.join(root, 'data', 'claims', '**', '*.yaml'), recursive=True):
        c = ResultClaim.model_validate(read_yaml(path))
        cond = conditions[c.eval_conditions] if c.eval_conditions else None
        out[c.id] = comparability.compute_for_claim(c, resolved[c.benchmark.split('@')[0]], cond).condition_completeness
    return out


def test_the_claim_derived_fields_over_the_frozen_claims(built):
    result, _ = built
    rank = {r['id']: r['rank'] for r in read_yaml(os.path.join(TAXONOMY, 'verification.yaml'))['rungs']}
    computed = completeness(FIXTURE)
    expect = {}
    for path in glob.glob(os.path.join(FIXTURE, 'data', 'claims', '**', '*.yaml'), recursive=True):
        c = read_yaml(path)
        e = expect.setdefault(c['benchmark'].split('@')[0], {'claim_count': 0, 'verification_max': None,
                                                             'condition_completeness_max': None})
        e['claim_count'] += 1
        if e['verification_max'] is None or rank[c['verification']] > rank[e['verification_max']]:
            e['verification_max'] = c['verification']
        done = computed[c['id']]
        if done is not None and (e['condition_completeness_max'] is None or done > e['condition_completeness_max']):
            e['condition_completeness_max'] = done
    assert sorted(expect) == ['critpt', 'mmlu', 'scicode']
    for bid, row in rows(result).items():
        got = {k: row[k] for k in ('claim_count', 'verification_max', 'condition_completeness_max')}
        assert got == expect.get(bid, {'claim_count': 0, 'verification_max': None, 'condition_completeness_max': None}), bid
    assert rows(result)['critpt']['verification_max'] == 'maintainer-verified' and rows(result)['critpt']['claim_count'] == 8
    assert rows(result)['mmlu']['verification_max'] == 'self-reported'
    assert result.facets['claim_basis'] == {'tiers': ['curated', 'machine-ingested'], 'verification_threshold': None,
                                            'date_window': None, 'verification_ladder': '0.1.0'}


INGESTION = '''ingestion:
  batch: ingest-epoch-2026-09-16
  source_adapter: epoch-benchmarks
  adapter_version: 0.3.1
  source_record_id: mmlu.csv#model=falcon-7b&metric=mmlu
  last_seen_upstream: 2026-09-16
  source_url: https://epoch.ai/data/benchmark_data.zip
  source_licence: CC-BY-4.0
  licence_class: permissive-attribution
  source_attribution: Epoch AI, Capabilities and Benchmarking.
  ingested_at: 2026-09-16T23:14:00Z
  extraction_confidence: 0.9
'''


def plant_claim(tree, rel, cid, verification='independent-reproduction', ingested=True):
    text = (tree / 'data/claims/mmlu/claim-0dde30099ecc.yaml').read_text(encoding='utf-8')
    text = text.replace('id: claim-0dde30099ecc', 'id: %s' % cid).replace('verification: self-reported',
                                                                          'verification: %s' % verification)
    text = text.replace('eval_conditions: cond-6173a6a331a4\n', '') + (INGESTION if ingested else '')
    path = tree / rel / ('%s.yaml' % cid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def test_a_machine_ingested_claim_counts_toward_all_three(tree):
    plant_claim(tree, 'data/claims/_ingested/epoch/mmlu', 'claim-00000000beef')
    result = artifacts.build(str(tree), drafts=True)
    assert result.errors == []
    mmlu = rows(result)['mmlu']
    assert (mmlu['claim_count'], mmlu['verification_max']) == (3, 'independent-reproduction')   # 07 S11.4
    assert mmlu['condition_completeness_max'] == 0.375          # no conditions: 0.0, which a maximum ignores


def test_a_vendor_claim_is_never_read(tree):
    plant_claim(tree, 'vendor/pwc-archive/claims/mmlu', 'claim-00000000cafe', ingested=False)
    result = artifacts.build(str(tree), drafts=True)
    assert result.errors == []
    assert rows(result)['mmlu']['claim_count'] == 2             # 08 S3.2: vendor/ never reaches a CC-BY artifact


def test_a_claim_the_models_refuse_fails_the_build(tree):
    edit(tree, 'data/claims/critpt/claim-683480dddf58.yaml', 'verification: maintainer-verified', 'verification: hearsay')
    result = artifacts.build(str(tree), drafts=True)
    assert result.corpus == {}
    assert any('claim-683480dddf58 is a claim on published benchmark critpt, but fails tier 1' in e for e in result.errors)


def test_a_claim_whose_conditions_are_missing_fails_the_build(tree):
    os.remove(tree / 'data/conditions/cond-fdd2eda50f13.yaml')
    result = artifacts.build(str(tree), drafts=True)
    assert any('names eval_conditions cond-fdd2eda50f13, but no data/conditions/ file holds it' in e
               for e in result.errors), result.errors


def test_a_claim_on_an_unpublished_benchmark_is_not_read(tree):
    os.remove(tree / 'data/benchmarks/physics/critpt.yaml')
    edit(tree, 'data/claims/critpt/claim-683480dddf58.yaml', 'verification: maintainer-verified', 'verification: hearsay')
    result = artifacts.build(str(tree), drafts=True)
    assert result.errors == [] and 'critpt' not in rows(result)


# ---- determinism (08 S6) ------------------------------------------------------------------------------------

def test_two_builds_are_byte_identical(built, tmp_path):
    _, first = built
    artifacts.write(artifacts.build(FIXTURE, drafts=True), str(tmp_path / 'again'))
    for name in emit.ARTIFACTS:
        assert (first / name).read_bytes() == (tmp_path / 'again' / name).read_bytes(), name


def test_nfc_lf_one_line_and_sorted_keys(built):
    _, out = built

    def sorted_keys(pairs):
        assert [k for k, _ in pairs] == sorted(k for k, _ in pairs)
        return dict(pairs)

    for name in emit.ARTIFACTS:
        raw = (out / name).read_bytes()
        assert b'\r' not in raw and raw.endswith(b'}\n') and raw.count(b'\n') == 1, name
        text = raw.decode('utf-8')
        assert unicodedata.is_normalized('NFC', text), name
        json.loads(text, object_pairs_hook=sorted_keys)


def test_a_decomposed_string_is_written_composed(tree, tmp_path):
    edit(tree, 'data/benchmarks/code/scicode.yaml', 'name: SciCode\n', 'name: "SciCode Cafe\\u0301"\n')
    artifacts.write(artifacts.build(str(tree), drafts=True), str(tmp_path))
    for name in ('corpus.json', 'facets.json'):
        text = (tmp_path / name).read_text(encoding='utf-8')
        assert 'SciCode Café' in text and 'Café' not in text


def test_files_are_read_and_records_written_in_byte_order(built):
    result, _ = built
    paths = tiers.discover(FIXTURE)
    assert paths == sorted(paths, key=lambda p: p.encode('utf-8'))
    for kind, records in result.corpus['entities'].items():
        ids = [r['id'] for r in records]
        assert ids == sorted(ids, key=lambda i: i.encode('utf-8')), kind
    ids = [r['id'] for r in result.facets['benchmarks']]
    assert ids == sorted(ids, key=lambda i: i.encode('utf-8'))


# ---- the preview path writes all three ---------------------------------------------------------------------

def test_the_preview_script_writes_the_three_artifacts(tmp_path):
    spec = importlib.util.spec_from_file_location('preview_corpus', os.path.join(ROOT, 'scripts', 'preview_corpus.py'))
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    assert preview.main(['--root', FIXTURE, '--out', str(tmp_path)]) == 0
    for name in emit.ARTIFACTS:
        assert read(tmp_path, name)['artifact'] == name[:-5]
    assert read(tmp_path, 'facets.json')['drafts'] is True
