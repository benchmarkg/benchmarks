"""Tests for the query encoder's static files and parity fixture (P6-S1-T01; tools/build/query_encoder.py; 11 S4 "The
embedding decision"; 08 S5.5).

The verify is the JavaScript side's, `cd site && npm test -- encoder.parity` (site/test/encoder.parity.test.mjs), which
runs the encoder against the fixture this module's subject writes. These hold the Python side: the residual plane's
bound and bit layout, the pruning's union, the corpus texts it reads (whole cards, every label), and that the committed
files agree with their meta, the model pin and git's binary detection. No test needs the weights but the last, which
regenerates every file from the repository and compares bytes (the --check), and is skipped unless model2vec and the
pinned potion-base-8M are in the local Hugging Face cache (`uv run --extra embed python -m tools.build.embed --fetch`,
then `uv run --extra embed pytest tools/tests/test_query_encoder.py`).
"""
import hashlib
import json
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.build import artifacts, embed, query_encoder as Q  # noqa: E402

CORPUS_20 = os.path.join(ROOT, 'tests', 'fixtures', 'corpus-20')
OUT = os.path.join(ROOT, Q.OUT)


def committed(name: str) -> bytes:
    with open(os.path.join(OUT, name), 'rb') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def meta():
    return json.loads(committed(Q.META))


# ---- the residual -------------------------------------------------------------------------------------------------

def test_the_residual_quarters_the_int8_step():
    rng = np.random.default_rng(7)
    rows = (rng.standard_normal((50, 256)) * rng.uniform(0.01, 3, (50, 1))).astype(np.float32)
    q, scales = embed.quantise(rows)
    codes = Q.residual(rows, q, scales)
    assert codes.dtype == np.uint8 and codes.min() == 0 and codes.max() == Q.LEVELS - 1
    s = np.asarray(scales, dtype=np.float64).astype(np.float32).reshape(-1, 1).astype(np.float64)
    alone = np.abs(Q.dequantise(q, scales) - rows)
    both = np.abs(Q.dequantise(q, scales, codes) - rows)
    assert (alone <= s / 2 * (1 + 1e-5)).all() and (both <= s / 8 * (1 + 1e-4)).all()
    assert both.max() < alone.max() / 3


def test_four_codes_a_byte_the_first_in_the_low_bits():
    codes = np.array([1, 2, 3, 0, 3, 3, 3, 3], dtype=np.uint8)
    assert Q.pack(codes) == bytes([1 | 2 << 2 | 3 << 4, 0xff])


# ---- the pruning --------------------------------------------------------------------------------------------------

def test_the_kept_ids_are_the_top_unioned_with_the_corpus():
    def tokenize(texts):
        return [[int(w) for w in t.split()] for t in texts]
    kept, corpus = Q.kept_ids(tokenize, ['3 50 7', '', '42 50'], vocab_size=60, top=5)
    assert kept == [0, 1, 2, 3, 4, 7, 42, 50] and corpus == {3, 7, 42, 50}
    assert Q.kept_ids(tokenize, ['1'], vocab_size=3, top=5)[0] == [0, 1, 2]


def test_the_corpus_texts_are_whole_cards_and_every_label():
    cards, labels = Q.corpus_texts(CORPUS_20)
    assert len(labels) == sum(len(t) for t in embed.labels().values()) == 304
    result = artifacts.build(CORPUS_20, drafts=True)
    records = {b['id']: b for b in result.corpus['entities']['benchmark']}
    rows = result.facets['benchmarks']
    assert len(cards) == len(rows) == 20
    cut = 0
    for row, text in zip(rows, cards):
        identity, rest = embed.card_parts(row, records[row['id']])
        assert text == identity + '\n' + rest                 # the whole card, whatever the document vector keeps
        short = embed.card(row, records[row['id']], budget=60)
        assert text.startswith(short)
        cut += short != text
    assert cut > 10                                           # so a budget would have cut most of them


# ---- the committed files ------------------------------------------------------------------------------------------

def test_the_committed_files_match_their_meta(meta):
    assert meta['artifact'] == 'query-encoder' and meta['format'] == Q.FORMAT and meta['dims'] == embed.DIMS
    assert meta['model']['id'] == embed.MODEL_ID and meta['model']['revision'] == embed.REVISION
    for key, name in (('matrix', Q.MATRIX), ('residual', Q.RESIDUAL), ('tokenizer', Q.TOKENIZER)):
        data = committed(name)
        assert meta['files'][key] == {'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    assert meta['files']['tokenizer']['sha256'] == embed.WEIGHTS[Q.TOKENIZER]     # the pinned file, byte for byte
    assert meta['files']['matrix']['bytes'] == meta['rows'] * meta['dims'] == 4 * meta['files']['residual']['bytes']
    ids = meta['token_ids']
    assert ids == sorted(set(ids)) and ids[:Q.TOP] == list(range(Q.TOP)) and ids[-1] < meta['vocab_size']
    assert len(ids) == len(meta['scales']) == meta['rows'] == Q.TOP + meta['pruning']['corpus_tokens_above_top']


def test_git_reads_both_planes_as_binary():
    """`* text=auto` in .gitattributes: a file is binary to git when a NUL sits in its first 8,000 bytes."""
    for name in (Q.MATRIX, Q.RESIDUAL):
        assert b'\0' in committed(name)[:8000], name


def test_the_fixture_is_200_strings_and_the_pruned_four():
    with open(os.path.join(ROOT, Q.FIXTURE), encoding='ascii') as fh:
        fx = json.load(fh)
    groups = [s['group'] for s in fx['strings']]
    assert {g: groups.count(g) for g in set(groups)} == {'query': 106, 'identity': 34, 'label': 30, 'edge': 30}
    assert [s['text'] for s in fx['strings'] if s['group'] == 'edge'] == Q.EDGE
    assert sorted(p['text'] for p in fx['pruned']) == sorted(set(Q.QUERIES) - {s['text'] for s in fx['strings']})
    assert fx['model']['revision'] == embed.REVISION and fx['tolerance'] == embed.TOLERANCE


# ---- the pinned model, when it is here ----------------------------------------------------------------------------

def _model_here() -> bool:
    try:
        import model2vec  # noqa: F401
    except ImportError:
        return False
    folder = embed.cached()
    return folder is not None and not embed.verify(folder)


@pytest.mark.skipif(not _model_here(), reason='model2vec and the pinned potion-base-8M weights are not here: '
                    'uv run --extra embed python -m tools.build.embed --fetch')
def test_every_committed_file_is_what_the_export_writes():
    assert Q.stale(ROOT, Q.files(ROOT)) == []
