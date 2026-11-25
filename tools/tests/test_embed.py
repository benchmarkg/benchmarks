"""Tests for S6, the document embeddings: vectors.i8.bin and vectors.meta.json (P6-S1-T03; tools/build/embed.py; 08
S3.2, S4.2, S5.5; 11 S4).

The verify: "pytest tools/tests/test_embed.py", done when "One row per benchmark family (never per edition), 256 dims,
id order matching facets.json, and dequantised cosine within 1e-3 of the float matrix" -- the cosine read as row
fidelity, 1 - cos(dequantised row, float row), which is what a per-row int8 scheme can bound; tools/build/embed.py's
docstring says why, and the model test below measures the pairwise figure beside it.

No test needs the network or the weights except the last two, which are skipped unless model2vec is installed and the
pinned potion-base-8M is in the local Hugging Face cache (`uv run --extra embed python -m tools.build.embed --fetch`,
then `uv run --extra embed pytest tools/tests/test_embed.py`). Every other test encodes with Hashed, a deterministic
stand-in: a lower-cased pre-token is a fixed pseudo-random 256-vector seeded by its sha256, and a text is the unit mean
of its tokens', which is model2vec's computation over a made-up vocabulary.

The corpus is tests/fixtures/corpus-20/, built as the draft preview builds it (`drafts=True`), as
tests/build/test_emit_artifacts.py and tests/atlas/ build it: twenty frozen entries, one, virtual-cell-challenge,
with editions. The CLI test builds tests/build/fixtures/minimal/, whose one entry is published.

What is asserted: the card (identity whole with its editions, the taxonomy labels, the cut at the budget after a whole
word, in the encoder's own unit); the quantiser (the round-trip bound, one float32 scale per row, the int8 range and
-128 never, a zero row); the row tolerance and its refusal; the id order against facets.json and the refusals when
the corpus disagrees; the two files' formats, the scales surviving JSON; the honest empty matrix; the refusals of a
wrong-shaped or zero encoding; `bench build --embed` writing them, failing with nothing written when the model is
absent, and a build without --embed writing the same bytes as before and no vectors.
"""
import copy
import functools
import hashlib
import json
import os
import random
import re
import sys

import numpy as np
import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools import cli  # noqa: E402
from tools.build import artifacts, embed  # noqa: E402
from tools.build.emit import serialise  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'corpus-20')
MINIMAL = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')
META_KEYS = {'artifact', 'format', 'model', 'rows', 'dims', 'ids', 'scales', 'quantization', 'vectors', 'index', 'card',
             'cards_sha256'}
PRETOKEN = re.compile(r'\w+|[^\w\s]')


class Hashed:
    """The stand-in encoder (module docstring)."""

    identity = {'id': 'test/hashed-pretokens', 'revision': '0' * 40, 'dims': embed.DIMS,
                'library': 'tools/tests/test_embed.py'}
    unit = 'pre-tokens, lower-cased (the stand-in encoder)'

    def __init__(self):
        self.calls = 0

    @staticmethod
    def tokens(text):
        return PRETOKEN.findall(text.lower())

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def vector(token):
        seed = int.from_bytes(hashlib.sha256(token.encode('utf-8')).digest()[:8], 'little')
        return np.random.default_rng(seed).standard_normal(embed.DIMS)

    def count(self, text):
        return len(self.tokens(text))

    def encode(self, texts):
        self.calls += 1
        out = np.zeros((len(texts), embed.DIMS), dtype=np.float64)
        for i, t in enumerate(texts):
            toks = self.tokens(t)
            if toks:
                out[i] = np.mean([self.vector(k) for k in toks], axis=0)
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return (out / np.where(norms > 0, norms, 1.0)).astype(np.float32)


@pytest.fixture(scope='module')
def built():
    """The fixture as the draft preview builds it, and its vectors under the stand-in, once."""
    result = artifacts.build(FIXTURE, drafts=True)
    assert result.errors == []
    return result, embed.build(result.corpus, result.facets, Hashed())


def record(**over):
    """A corpus.json benchmark record and its facets.json row, with only what a card reads."""
    row = {'aliases': over.pop('aliases', []), 'editions': over.pop('editions', [])}
    rec = {'id': 'demo', 'name': 'Demo Bench', 'tagline': 'Answer questions about demos.',
           'description': 'A short description.', 'domain': {'primary': 'code/repository-scale-se', 'secondary': []},
           'capability': ['deductive-reasoning'], 'evaluation_method': ['exact-match']}
    rec.update(over)
    row.update(id=rec['id'], name=rec['name'])
    return row, rec


# ---- the retrieval card -------------------------------------------------------------------------------------------

def test_one_card_and_one_row_per_family_never_per_edition(built):
    result, v = built
    rows = result.facets['benchmarks']
    assert len(v.cards) == len(v.ids) == len(rows) == len(result.corpus['entities']['benchmark']) == 20
    assert v.q.shape == (20, 256) and v.matrix.shape == (20, 256) and embed.DIMS == 256
    vcc = next(r for r in rows if r['id'] == 'virtual-cell-challenge')
    assert len(vcc['editions']) == 2                     # two editions, still one row
    assert not any('@' in i for i in v.ids)


def test_the_identity_lines_are_the_name_aliases_and_edition_names(built):
    result, v = built
    for row, c in zip(result.facets['benchmarks'], v.cards):
        lines = c.split('\n')
        assert lines[0] == row['name']
        for name in row['aliases'] + row['editions']:
            assert ' '.join(name.split()) in lines           # whole, as its own line: an alias string
    vcc = v.cards[v.ids.index('virtual-cell-challenge')].split('\n')
    assert vcc[:6] == ['Virtual Cell Challenge', 'VCC', 'Arc Virtual Cell Challenge', 'Virtual Cell Challenge 2026',
                       'The inaugural edition, one cell line (H1 hESC)', 'Zero-shot across cell contexts']


def test_the_rest_names_the_tagline_and_the_taxonomy_labels():
    row, rec = record(domain={'primary': 'code/repository-scale-se',
                              'secondary': ['reasoning-general/logical-deduction']},
                      capability=['deductive-reasoning', 'knowledge-recall'], evaluation_method=['exact-match'])
    lab = embed.labels()
    lines = embed.card(row, rec).split('\n')
    assert lines[1] == 'Answer questions about demos.'
    assert lines[2] == '%s: %s; %s' % (lab['domains.yaml']['code'], lab['domains.yaml']['code/repository-scale-se'],
                                       lab['domains.yaml']['reasoning-general/logical-deduction'])
    assert lines[3] == 'Deductive reasoning; Knowledge recall' and lines[4] == 'Exact match'
    assert lines[5] == 'A short description.' and len(lines) == 6
    assert '\n\n' not in embed.card(*record(capability=[], description=None))     # an empty field adds no line


def test_the_card_is_cut_to_the_budget_after_a_whole_word():
    words = ['word%d' % i for i in range(1000)]
    row, rec = record(description=' '.join(words), aliases=['DB'], editions=['Demo 2025'])
    identity, rest = embed.card_parts(row, rec)
    c = embed.card(row, rec)
    assert embed.pretokens(c) <= embed.CARD_TOKENS
    assert c.startswith(identity + '\n') and rest.startswith(c[len(identity) + 1:])
    kept = c.split()[-1]
    assert kept in words                                 # never a fragment of a word
    after = rest[len(c) - len(identity) - 1:].split()[0]
    assert embed.pretokens(c + ' ' + after) > embed.CARD_TOKENS          # and the most that fits
    assert embed.card(row, rec, budget=10 ** 6) == identity + '\n' + rest


def test_the_budget_is_counted_in_the_encoders_unit():
    row, rec = record(description=' '.join('alpha-beta' for _ in range(400)))
    hyphens = embed.card(row, rec)                       # a pre-token count: alpha, -, beta is three
    words = embed.card(row, rec, count=lambda t: len(t.split()))
    assert embed.pretokens(hyphens) <= 300 < embed.pretokens(words) and len(words.split()) <= 300
    assert len(words) > len(hyphens)


def test_identity_is_never_cut():
    editions = ['Demo Challenge %d: the round on topic number %d' % (y, y) for y in range(1990, 2030)]
    row, rec = record(editions=editions)
    identity, _ = embed.card_parts(row, rec)
    assert embed.pretokens(identity) > embed.CARD_TOKENS
    assert embed.card(row, rec) == identity


def test_names_are_folded_and_given_once():
    row, rec = record(name='Demo  Bench', aliases=['Demo Bench', 'DB'], editions=['DB', 'Demo 2025'])
    assert embed.card_parts(row, rec)[0] == 'Demo Bench\nDB\nDemo 2025'


# ---- the quantiser ------------------------------------------------------------------------------------------------

def matrix(n=200, seed=20261125):
    """Rows of very different magnitudes and signs, one with a dominant coordinate (as potion's first principal
    component is), one negative-peaked, one zero."""
    rng = np.random.default_rng(seed)
    m = rng.standard_normal((n, 256)) * (10.0 ** rng.uniform(-3, 1, size=(n, 1)))
    m[1, 7] = 40.0
    m[2] = -np.abs(m[2])
    m[3] = 0.0
    return m.astype(np.float32)


def test_one_float32_scale_per_row_and_the_int8_range():
    m = matrix()
    q, scales = embed.quantise(m)
    assert q.dtype == np.int8 and q.shape == m.shape and len(scales) == len(m)
    assert int(q.min()) >= -127 and int(q.max()) <= 127               # symmetric: -128 never occurs
    peak = np.abs(m).max(axis=1)
    for i, s in enumerate(scales):
        assert isinstance(s, float)
        assert np.float32(s) == np.float32(peak[i] / np.float32(127))   # the shortest decimal gives it back exactly
        assert len(repr(s)) <= len(repr(float(np.float32(s))))
        if i != 3:
            assert int(np.abs(q[i]).max()) == 127                      # each row's peak is +-127
    assert scales[3] == 0.0 and not q[3].any()                          # a zero row is a zero scale
    assert int(q[2].min()) == -127


def test_the_round_trip_is_within_half_a_step():
    m = matrix()
    q, scales = embed.quantise(m)
    d = embed.dequantise(q, scales)
    assert d.dtype == np.float32
    half = np.asarray(scales, dtype=np.float64).astype(np.float32).astype(np.float64)[:, None] / 2
    err = np.abs(d.astype(np.float64) - m.astype(np.float64))
    assert (err <= half * (1 + 1e-4)).all()            # plus float32's rounding of q / scale and of q * scale
    assert (np.abs(q.astype(np.int16)) <= 127).all()


def test_the_dequantised_rows_are_within_the_cosine_tolerance(built):
    _, v = built
    cos = embed.row_cosines(embed.dequantise(v.q, v.scales), v.matrix)
    assert (1 - cos <= embed.TOLERANCE).all() and embed.TOLERANCE == 1e-3
    unit = embed.unit_rows(matrix()[[0, 1, 2] + list(range(4, 200))])     # random unit rows, one peaked, no zero
    q, scales = embed.quantise(unit)
    assert (1 - embed.row_cosines(embed.dequantise(q, scales), unit) <= embed.TOLERANCE).all()


def test_a_row_past_the_tolerance_refuses(built, monkeypatch):
    result, _ = built
    monkeypatch.setattr(embed, 'TOLERANCE', 0.0)
    with pytest.raises(embed.EmbedError, match='past the 0e\\+00 tolerance'):
        embed.build(result.corpus, result.facets, Hashed())


# ---- id order and the refusals ------------------------------------------------------------------------------------

def test_rows_follow_facets_json_order(built):
    result, v = built
    assert v.ids == [r['id'] for r in result.facets['benchmarks']] == v.meta['ids']
    assert v.ids == sorted(v.ids, key=lambda i: i.encode('utf-8'))
    for i in range(len(v.ids)):                                        # row i is row i's own card, encoded
        assert np.array_equal(v.matrix[i], embed.unit_rows(Hashed().encode([v.cards[i]]))[0])


def test_the_corpus_order_never_reaches_the_bytes(built):
    result, v = built
    corpus = copy.deepcopy(result.corpus)
    random.Random(20261125).shuffle(corpus['entities']['benchmark'])
    again = embed.build(corpus, result.facets, Hashed())
    assert again.q.tobytes() == v.q.tobytes() and serialise(again.meta) == serialise(v.meta)


def test_facets_json_decides_the_order(built):
    result, v = built
    facets = dict(result.facets, benchmarks=list(reversed(result.facets['benchmarks'])))
    flipped = embed.build(result.corpus, facets, Hashed())
    assert flipped.ids == list(reversed(v.ids))
    assert flipped.q.tobytes() == v.q[::-1].tobytes() and flipped.scales == list(reversed(v.scales))


def test_a_corpus_that_disagrees_with_facets_json_refuses(built):
    result, _ = built
    corpus = copy.deepcopy(result.corpus)
    gone = corpus['entities']['benchmark'].pop()
    with pytest.raises(embed.EmbedError, match='%s.*only in facets.json' % gone['id']):
        embed.build(corpus, result.facets, Hashed())
    facets = dict(result.facets, benchmarks=result.facets['benchmarks'] + result.facets['benchmarks'][:1])
    with pytest.raises(embed.EmbedError, match='1 id\\(s\\) repeated'):
        embed.build(result.corpus, facets, Hashed())


class Wrong(Hashed):
    def __init__(self, shape=None, zero=None):
        super().__init__()
        self.shape, self.zero = shape, zero

    def encode(self, texts):
        out = super().encode(texts)
        if self.zero is not None:
            out[self.zero] = 0.0
        return out[:, :self.shape] if self.shape else out


def test_a_wrong_shape_or_a_zero_vector_refuses(built):
    result, _ = built
    with pytest.raises(embed.EmbedError, match=r'shape \(20, 128\), not \(20, 256\)'):
        embed.build(result.corpus, result.facets, Wrong(shape=128))
    with pytest.raises(embed.EmbedError, match='calvin pools to the zero vector'):
        embed.build(result.corpus, result.facets, Wrong(zero=0))


def test_the_published_matrix_is_honestly_empty(tmp_path):
    """05 S4 publishes no draft, and every fixture entry is one: zero rows, and no encoding at all."""
    published = artifacts.build(FIXTURE)
    assert published.errors == [] and published.facets['benchmarks'] == []
    enc = Hashed()
    v = embed.build(published.corpus, published.facets, enc)
    assert enc.calls == 0 and v.q.shape == (0, 256) and v.ids == [] and v.scales == []
    bin_path, meta_path = embed.write(v, str(tmp_path))
    assert os.path.getsize(bin_path) == 0
    meta = json.loads(open(meta_path, encoding='utf-8').read())
    assert meta['rows'] == 0 and meta['vectors']['bytes'] == 0 and 'drafts' not in meta
    assert meta['vectors']['sha256'] == hashlib.sha256(b'').hexdigest()


# ---- the two files ------------------------------------------------------------------------------------------------

def test_the_two_files(built, tmp_path):
    result, v = built
    bin_path, meta_path = embed.write(v, str(tmp_path))
    assert [os.path.basename(p) for p in (bin_path, meta_path)] == ['vectors.i8.bin', 'vectors.meta.json']
    data = open(bin_path, 'rb').read()
    assert len(data) == 20 * 256                                       # no header, one signed byte a coordinate
    assert np.array_equal(np.frombuffer(data, dtype=np.int8).reshape(20, 256), v.q)
    raw = open(meta_path, 'rb').read()
    meta = json.loads(raw)
    assert serialise(meta) == raw                                      # 08 S6's canonical bytes
    assert set(meta) == META_KEYS | {'drafts'} and meta['drafts'] is True
    assert (meta['artifact'], meta['format'], meta['rows'], meta['dims']) == ('vectors', 1, 20, 256)
    assert meta['model'] == Hashed.identity
    assert meta['vectors'] == {'file': 'vectors.i8.bin', 'dtype': 'int8', 'layout': 'row-major, rows x dims, no header',
                               'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    assert meta['index'] == {'artifact': 'facets.json', 'format': 3} and result.facets['format'] == 3
    assert meta['quantization']['qmax'] == 127 and meta['quantization']['row_cosine_tolerance'] == 1e-3
    assert meta['card'] == {'budget': 300, 'unit': Hashed.unit, 'identity': ['name', 'aliases', 'editions'],
                            'rest': ['tagline', 'domain', 'capability', 'evaluation_method', 'description']}
    assert meta['cards_sha256'] == hashlib.sha256(''.join(c + '\n' for c in v.cards).encode('utf-8')).hexdigest()
    again = tmp_path / 'again'
    embed.write(embed.build(copy.deepcopy(result.corpus), result.facets, Hashed()), str(again))
    assert (again / 'vectors.i8.bin').read_bytes() == data and (again / 'vectors.meta.json').read_bytes() == raw


def test_what_a_loader_reads_back_is_what_was_quantised(built, tmp_path):
    """The file's bytes and the meta's JSON scales, read as a loader reads them, give the build's dequantised matrix
    bit for bit -- the scale's shortest decimal, parsed and rounded to float32, is the scale that was used."""
    _, v = built
    bin_path, meta_path = embed.write(v, str(tmp_path))
    meta = json.loads(open(meta_path, encoding='utf-8').read())
    q = np.frombuffer(open(bin_path, 'rb').read(), dtype=np.int8).reshape(meta['rows'], meta['dims'])
    loaded = q.astype(np.float32) * np.array([np.float32(s) for s in meta['scales']], dtype=np.float32)[:, None]
    assert loaded.tobytes() == embed.dequantise(v.q, v.scales).tobytes()
    assert (1 - embed.row_cosines(loaded, v.matrix) <= embed.TOLERANCE).all()


def test_the_model_is_pinned():
    assert embed.MODEL_ID == 'minishlab/potion-base-8M' and re.fullmatch(r'[0-9a-f]{40}', embed.REVISION)
    assert sorted(embed.WEIGHTS) == ['config.json', 'model.safetensors', 'tokenizer.json']
    assert all(re.fullmatch(r'[0-9a-f]{64}', d) for d in embed.WEIGHTS.values())


def test_verify_names_a_missing_or_altered_file(tmp_path):
    assert embed.verify(str(tmp_path)) == ['%s is missing' % n for n in sorted(embed.WEIGHTS)]
    for name in embed.WEIGHTS:
        (tmp_path / name).write_bytes(b'not the weights')
    assert all('does not hash to its pinned sha256' in b for b in embed.verify(str(tmp_path)))


# ---- bench build --embed ------------------------------------------------------------------------------------------

def test_bench_build_embed_writes_two_files_and_changes_nothing_else(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, 'ROOT', MINIMAL)
    monkeypatch.setattr(embed, 'encoder', Hashed)
    runner = CliRunner()
    res = runner.invoke(cli.app, ['build', '--embed', '--out', str(tmp_path / 'embed')])
    assert res.exit_code == 0, res.output
    assert 'embedded 1 benchmark family with test/hashed-pretokens' in res.output
    meta = json.loads((tmp_path / 'embed' / 'vectors.meta.json').read_text(encoding='utf-8'))
    assert meta['ids'] == ['alpha-bench'] and 'drafts' not in meta
    assert (tmp_path / 'embed' / 'vectors.i8.bin').stat().st_size == 256
    res = runner.invoke(cli.app, ['build', '--out', str(tmp_path / 'plain')])
    assert res.exit_code == 0, res.output
    assert 'embedded' not in res.output

    def files(top):
        return {os.path.relpath(os.path.join(d, n), top).replace(os.sep, '/')
                for d, _, names in os.walk(top) for n in names}
    plain, embedded = files(tmp_path / 'plain'), files(tmp_path / 'embed')
    assert embedded - plain == {'vectors.i8.bin', 'vectors.meta.json'} and plain <= embedded
    for rel in sorted(plain):                            # every other file, the manifest included, byte for byte
        assert (tmp_path / 'plain' / rel).read_bytes() == (tmp_path / 'embed' / rel).read_bytes(), rel
    manifest = json.loads((tmp_path / 'embed' / 'build-manifest.json').read_text(encoding='utf-8'))
    assert not any(n.startswith('vectors') for n in manifest['artifacts'])


def test_bench_build_embed_without_the_model_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, 'ROOT', MINIMAL)

    def absent():
        raise embed.EmbedError('not in the local Hugging Face cache')
    monkeypatch.setattr(embed, 'encoder', absent)
    res = CliRunner().invoke(cli.app, ['build', '--embed', '--out', str(tmp_path / 'out')])
    assert res.exit_code == 1 and 'not in the local Hugging Face cache' in res.output
    assert not (tmp_path / 'out').exists()


# ---- the pinned model, when it is here ----------------------------------------------------------------------------

def _model_here() -> bool:
    try:
        import model2vec  # noqa: F401
    except ImportError:
        return False
    folder = embed.cached()
    return folder is not None and not embed.verify(folder)


needs_model = pytest.mark.skipif(not _model_here(), reason='model2vec and the pinned potion-base-8M weights are not '
                                 'here: uv run --extra embed python -m tools.build.embed --fetch')


@pytest.fixture(scope='module')
def potion():
    return embed.encoder()


@needs_model
def test_the_pinned_model_embeds_the_fixture(built, potion):
    result, _ = built
    assert potion.identity == {'id': embed.MODEL_ID, 'revision': embed.REVISION, 'dims': 256,
                               'library': 'model2vec 0.10.0'}
    v = embed.build(result.corpus, result.facets, potion)
    assert v.q.shape == (20, 256) and v.ids == [r['id'] for r in result.facets['benchmarks']]
    assert all(potion.count(c) <= embed.CARD_TOKENS for c in v.cards)    # no fixture identity is over budget
    assert np.allclose(np.linalg.norm(v.matrix.astype(np.float64), axis=1), 1.0, atol=1e-6)
    assert (1 - embed.row_cosines(embed.dequantise(v.q, v.scales), v.matrix) <= embed.TOLERANCE).all()
    again = embed.build(copy.deepcopy(result.corpus), result.facets, potion)
    assert again.q.tobytes() == v.q.tobytes() and serialise(again.meta) == serialise(v.meta)
    assert v.meta['card']['unit'] == potion.unit and v.meta['model']['revision'] == embed.REVISION


@needs_model
def test_the_dequantised_matrix_ranks_as_the_float_one(built, potion):
    """A float query against the dequantised rows: what the cosine loop computes. Each family is found by a
    description of it, and the pairwise movement the module docstring states is measured, not assumed."""
    result, _ = built
    v = embed.build(result.corpus, result.facets, potion)
    deq = embed.unit_rows(embed.dequantise(v.q, v.scales))
    for query, want in (('medical licensing exam questions', 'medqa'), ('formal theorem proving olympiad', 'minif2f'),
                        ('object detection in images', 'coco'), ('robot manipulation following language instructions',
                                                                  'calvin'),
                        ('Zero-shot across cell contexts', 'virtual-cell-challenge')):     # an edition's name
        q = potion.encode([query])[0]
        assert v.ids[int(np.argmax(deq @ q))] == want == v.ids[int(np.argmax(v.matrix @ q))], query
    f = v.matrix.astype(np.float64)
    moved = np.abs(f @ f.T - f @ deq.astype(np.float64).T)
    print('query-row cosine movement over %d pairs: mean %.1e, max %.1e' % (moved.size, moved.mean(), moved.max()))
    assert moved.mean() < 1e-3 and moved.max() < 1e-2
