"""S6, the document embeddings: vectors.i8.bin and vectors.meta.json (P6-S1-T03; 08 S3.2, S4.2, S5.5; 11 S4).

    uv run --extra embed python -m tools.build.embed --fetch      # once: the pinned weights into the Hugging Face cache
    uv run --extra embed bench build --embed --out build/         # build/vectors.i8.bin and build/vectors.meta.json

11 S4 "The embedding decision": static embeddings, client-side, with the *document* vectors "computed in Python at build
time with the full unpruned model for best quality". 08 S3.2 names the model, `potion-base-8M`, whose config gives
`hidden_dim: 256`, and the output, "int8 for transport plus a per-vector scale, dequantised once into a `Float32Array`
at load". This module is that stage; the query side, the pruned matrix and the JS encoder, is P6-S1-T01's.

The model is pinned, not named: MODEL_ID at REVISION, a commit of a public, ungated Hugging Face repository (MIT), and
the sha256 of each file the stage reads (WEIGHTS). The build never touches the network (08 S2): `bench build --embed`
reads the weights from the local Hugging Face cache (HF_HUB_CACHE, by default outside the repository), checks every
hash, and refuses when they are absent, naming the one command that fetches them, `--fetch` above. That command
downloads exactly WEIGHTS at REVISION with no token (`token=False`: never a login, never an accepted licence), and
checks the same hashes. model2vec is the `embed` extra in pyproject.toml, imported only here, only when the stage runs.

The retrieval card (11 S4 "What is actually in each index"). One per benchmark family, never per edition -- "the
cosine similarity between SWE-bench and SWE-bench Verified is approximately 1.0, so a separate vector buys no
discrimination" -- so editions enter as alias strings, and "the family's embedding card includes the edition names so
a semantic query for 'CASP17' still lands on the CASP family". A card is plain lines, with no field labels (a word
every card repeats only pulls every vector toward the same point):

  identity   the facets.json row's `name`, `aliases` and `editions` (emit.edition_names: the lexical index's own
             alias strings), whitespace-folded, each once, in that order. Never cut.
  the rest   the tagline; the domain line, `<family label>: <subdomain label>` and each secondary subdomain's label;
             the capability labels; the evaluation-method labels (taxonomy/*.yaml `label`s, the words a person
             types); the description. Cut at the last whole word that keeps the card within CARD_TOKENS.

CARD_TOKENS is 300, counted by the encoder's own `count`: for potion-base-8M, the WordPiece tokens model2vec pools
(its tokenizer, [UNK] removed). Identity alone may exceed it, and is then the whole card. A token-count prefix at a
whitespace boundary is a prefix of the full text's tokens (BertPreTokenizer splits on whitespace), so the count is
monotonic in the cut and a binary search finds it. Encoding passes `max_length=None`, so model2vec truncates nothing
the card kept.

The matrix. model2vec's mean-pooled vectors, L2-normalised again here in float64 and stored as float32; a card that
pools to the zero vector refuses the build, because every row the loader receives is a unit vector. Rows are in
facets.json `benchmarks` order -- the facet filter's row numbers (08 S5.7), so the cosine loop restricted to the
survivors indexes the same rows -- and the build refuses unless the corpus's benchmarks are exactly those ids.

The quantiser: symmetric int8, one scale per row. scale = max|v| / 127, as a float32 written to the meta as the
shortest decimal that gives it back; q = rint(v / float32(scale)), clipped to [-127, 127], so -128 never occurs and
the row's largest coordinate is +-127. Dequantised, v' = q * float32(scale) -- what the loader computes (11 S4:
"quantise to int8 for transport, then dequantise once into a Float32Array at load"), and what JavaScript's
Math.fround(scale) gives too. A zero scale is a zero row, which the build has already refused. Each coordinate is
off by at most scale / 2.

The tolerance, and what it bounds. The ledger's done_when asks for "dequantised cosine within 1e-3 of the float
matrix". What a per-row int8 scheme guarantees, and what `build` enforces (TOLERANCE), is row fidelity: for every row,
1 - cos(v', v) <= 1e-3. A cosine *between two rows*, or between a float query and a dequantised row, moves by more:
each coordinate's error is up to max|v| / 254, potion's first principal component makes max|v| about 0.35, and a dot
product sums 256 such errors. Measured over the 320 drafts (2026-11-25): row fidelity at worst 1.8e-4; a float query
against the dequantised rows moves by 5.5e-4 on average and 3.6e-3 at worst, row against row 4.5e-3 at worst
(tools/tests/test_embed.py's model test prints the fixture's figures). Only RRF's ranks (08 S5.7) read the cosines, so
this reorders near-ties only; a bound of 1e-3 on every pair needs more than eight bits a coordinate (int16 doubles
vectors.i8.bin), which is a decision for 08 S4.2, not this stage.

What the cards do, measured over the same drafts: 273 of 320 are cut to the budget, and two are over it because their
identity alone is (physionet-challenge, 27 editions, 618 tokens; f1tenth, 35 editions, 333). A query naming an edition
is the lexical leg's to resolve exactly (11 S4: "exact match is what the alias table and BM25 are for"); semantically,
the query "CASP17" alone puts casp third, behind capri and casmi.

The two files, beside the S8 artifacts in --out:

  vectors.i8.bin     rows x 256 signed bytes, row-major, no header: row i is facets.json benchmarks[i]
  vectors.meta.json  {artifact: vectors, format, model: {id, revision, dims, library}, rows, dims, ids, scales,
                      quantization: {scheme, qmax, dequantize, row_cosine_tolerance}, vectors: {file, dtype, layout,
                      bytes, sha256}, index: {artifact, format}, card: {budget, unit, identity, rest}, cards_sha256,
                      drafts (a preview build only)}

`ids` repeats the facets.json order so a loader can refuse a matrix built against another facets.json; `cards_sha256`
hashes every card in order (each card's UTF-8 bytes and a newline), the input this stage is a function of: 08 S3.1
keys S6's cache on the card text, and recomputing only changed cards is left to that cache, because the full stage
takes about two seconds over the 320 drafts, the model's load included. Neither file is in build-manifest.json yet:
tools/build/manifest.py hashes canonical JSON artifacts into /data/, a binary has no canonical JSON form, and how the
semantic tier is fetched and cached is P6-S1-T06's (11 S4: "cached in IndexedDB keyed on the index commit SHA").

No entry is published yet (05 S4), so `bench build --embed` over the repository writes zero rows: an empty
vectors.i8.bin and a meta whose ids are []. The model still has to be present, because the meta names it.

Determinism (08 S6): the cards are a pure function of the corpus, facets.json and the taxonomy; model2vec runs without
multiprocessing; the meta is emit.serialise()'s canonical bytes. Two builds on one machine are byte-identical. Across
machines the float vectors come from numpy's float32 means, whose summation order is numpy's; an int8 coordinate
sitting on a rounding boundary could differ, which is unverified rather than observed.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from importlib import metadata
from typing import Protocol

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools.build.emit import fold, nfc, serialise, taxonomy  # noqa: E402

MODEL_ID = 'minishlab/potion-base-8M'                       # 08 S3.2, S5.5; MIT, public and ungated
REVISION = 'bf8b056651a2c21b8d2565580b8569da283cab23'       # the repository's commit, checked 2026-11-25
WEIGHTS = {                                                  # what the stage reads at REVISION, and its sha256
    'config.json': '2a6ac0e9aaa356a68a5688070db78fc3a464fefe85d2f06a1905ce3718687553',
    'model.safetensors': 'f65d0f325faadc1e121c319e2faa41170d3fa07d8c89abd48ca5358d9a223de2',   # 30,236,760 bytes
    'tokenizer.json': 'e67e803f624fb4d67dea1c730d06e1067e1b14d830e2c2202569e3ef0f70bb50',
}
DIMS = 256                                                   # 08 S5.5: hidden_dim 256, not 384
CARD_TOKENS = 300
QMAX = 127                                                   # symmetric: -128 is never written
TOLERANCE = 1e-3                                             # 1 - cos(dequantised row, float row), every row
FORMAT = 1
BIN, META = 'vectors.i8.bin', 'vectors.meta.json'
FETCH = 'uv run --extra embed python -m tools.build.embed --fetch'
IDENTITY = ('name', 'aliases', 'editions')
REST = ('tagline', 'domain', 'capability', 'evaluation_method', 'description')
WORD = re.compile(r'\S+')


class EmbedError(Exception):
    """The stage cannot run or would write something wrong; the message says why."""


class Encoder(Protocol):
    """What the stage needs from a model: its identity for the meta, a token count and a float32 encoding."""
    identity: dict              # {id, revision, dims, library}
    unit: str                   # what `count` counts, for the meta

    def count(self, text: str) -> int: ...

    def encode(self, texts: list[str]) -> np.ndarray: ...


# ---- the retrieval card -------------------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def labels() -> dict[str, dict[str, str]]:
    """taxonomy file -> {term id: label}, for the three vocabularies a card names."""
    models = taxonomy()
    return {name: {t.id: t.label for t in models[name].terms}
            for name in ('domains.yaml', 'capabilities.yaml', 'evaluation-methods.yaml')}


def pretokens(text: str) -> int:
    """A count with no model: BERT's pre-tokens (a run of word characters, or one other non-space character)."""
    return len(re.findall(r'\w+|[^\w\s]', text))


def card_parts(row: dict, record: dict) -> tuple[str, str]:
    """(identity, the rest) of one family's card: a facets.json row and its corpus.json benchmark record."""
    names: list[str] = []
    for n in [row['name'], *row['aliases'], *row['editions']]:
        n = fold(n)
        if n and n not in names:
            names.append(n)
    lab = labels()
    domains, primary = lab['domains.yaml'], record['domain']['primary']
    domain = ['%s: %s' % (domains[primary.split('/')[0]], domains[primary])]
    domain += [domains[s] for s in record['domain']['secondary']]
    rest = [fold(record['tagline']), '; '.join(domain),
            '; '.join(lab['capabilities.yaml'][c] for c in record['capability']),
            '; '.join(lab['evaluation-methods.yaml'][m] for m in record['evaluation_method']),
            fold(record['description'])]
    return '\n'.join(names), '\n'.join(r for r in rest if r)


def card(row: dict, record: dict, count=pretokens, budget: int = CARD_TOKENS) -> str:
    """The card: identity whole, then as much of the rest as keeps `count(card)` within `budget`, cut after a word."""
    identity, rest = card_parts(row, record)
    if not rest:
        return identity
    whole = identity + '\n' + rest
    if count(whole) <= budget:
        return whole
    ends = [m.end() for m in WORD.finditer(rest)]
    # the most words of the rest that fit: count() is monotonic in a cut at a word's end (module docstring), and the
    # whole rest does not fit, so the answer is below len(ends)
    lo, hi = 0, len(ends) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count(identity + '\n' + rest[:ends[mid - 1]]) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return identity + '\n' + rest[:ends[lo - 1]] if lo > 0 else identity


# ---- the quantiser ------------------------------------------------------------------------------------------------

def shortest(x: np.float32) -> float:
    """What the meta writes for a float32 scale: the float64 of the shortest decimal that gives `x` back through
    float64 (as JSON.parse then Math.fround does), else, should that double rounding miss, `x` exactly."""
    x = np.float32(x)
    s = float(np.format_float_positional(x, unique=True, trim='-'))
    return s if np.float32(s) == x else float(x)


def quantise(matrix: np.ndarray) -> tuple[np.ndarray, list[float]]:
    """(int8 rows, scales): row i dequantises to q[i] * float32(scales[i]), each coordinate within scales[i] / 2."""
    m = np.asarray(matrix, dtype=np.float32)
    peak = np.abs(m).max(axis=1) if m.size else np.zeros(len(m), dtype=np.float32)
    scales = [shortest(p / np.float32(QMAX)) for p in peak]
    s32 = np.asarray(scales, dtype=np.float64).astype(np.float32).reshape(-1, 1)
    q = np.zeros(m.shape, dtype=np.int8)
    live = s32[:, 0] > 0
    q[live] = np.clip(np.rint(m[live] / s32[live]), -QMAX, QMAX).astype(np.int8)
    return q, scales


def dequantise(q: np.ndarray, scales: list[float]) -> np.ndarray:
    """What the loader computes: q * float32(scale), row by row, in float32."""
    return q.astype(np.float32) * np.asarray(scales, dtype=np.float64).astype(np.float32).reshape(-1, 1)


def row_cosines(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """cos(a[i], b[i]) for every row, in float64."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    return (a * b).sum(axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))


def unit_rows(matrix: np.ndarray) -> np.ndarray:
    m = np.asarray(matrix, dtype=np.float64)
    return (m / np.linalg.norm(m, axis=1, keepdims=True)).astype(np.float32)


# ---- the stage ----------------------------------------------------------------------------------------------------

@dataclass
class Vectors:
    ids: list[str]
    cards: list[str]
    matrix: np.ndarray          # float32, unit rows: what was quantised
    q: np.ndarray               # int8, rows x dims
    scales: list[float]
    meta: dict


def build(corpus: dict, facets: dict, encoder: Encoder) -> Vectors:
    """One unit vector per benchmark family, in facets.json order, quantised; raises EmbedError rather than write a
    matrix that does not match its facets.json, its model or the tolerance."""
    rows = facets['benchmarks']
    ids = [r['id'] for r in rows]
    records = {b['id']: b for b in corpus['entities']['benchmark']}
    if len(set(ids)) != len(ids) or set(ids) != set(records):
        raise EmbedError('facets.json and corpus.json disagree on the benchmarks: %s only in facets.json, %s only in '
                         'corpus.json, %d id(s) repeated' % (sorted(set(ids) - set(records)) or 'none',
                                                             sorted(set(records) - set(ids)) or 'none',
                                                             len(ids) - len(set(ids))))
    dims = encoder.identity['dims']
    cards = [card(r, records[r['id']], encoder.count) for r in rows]
    raw = np.asarray(encoder.encode(cards), dtype=np.float32) if cards else np.zeros((0, dims), dtype=np.float32)
    if raw.shape != (len(cards), dims):
        raise EmbedError('%s encoded %d card(s) to shape %s, not (%d, %d)'
                         % (encoder.identity['id'], len(cards), raw.shape, len(cards), dims))
    zero = [i for i, n in zip(ids, np.linalg.norm(raw.astype(np.float64), axis=1)) if not n > 0]
    if zero:
        raise EmbedError('%s pools to the zero vector (no token of its card is in the vocabulary)' % ', '.join(zero))
    matrix = unit_rows(raw)
    q, scales = quantise(matrix)
    if len(ids):
        worst = float((1.0 - row_cosines(dequantise(q, scales), matrix)).max())
        if worst > TOLERANCE:
            raise EmbedError('a dequantised row is at 1 - cos %.2e from its float row, past the %.0e tolerance'
                             % (worst, TOLERANCE))
    data = q.tobytes(order='C')
    meta = nfc({
        'artifact': 'vectors', 'format': FORMAT, 'model': dict(encoder.identity),
        'rows': len(ids), 'dims': dims, 'ids': ids, 'scales': scales,
        'quantization': {'scheme': 'int8, symmetric, one scale per row: scale = max|v| / %d' % QMAX, 'qmax': QMAX,
                         'dequantize': 'v[i][k] = q[i][k] * float32(scales[i])', 'row_cosine_tolerance': TOLERANCE},
        'vectors': {'file': BIN, 'dtype': 'int8', 'layout': 'row-major, rows x dims, no header', 'bytes': len(data),
                    'sha256': hashlib.sha256(data).hexdigest()},
        'index': {'artifact': 'facets.json', 'format': facets['format']},
        'card': {'budget': CARD_TOKENS, 'unit': encoder.unit, 'identity': list(IDENTITY), 'rest': list(REST)},
        'cards_sha256': hashlib.sha256(b''.join(c.encode('utf-8') + b'\n' for c in cards)).hexdigest(),
        **({'drafts': True} if corpus.get('drafts') else {})})
    return Vectors(ids, cards, matrix, q, scales, meta)


def write(vectors: Vectors, out_dir: str) -> list[str]:
    """out_dir/vectors.i8.bin and out_dir/vectors.meta.json; returns their paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = [os.path.join(out_dir, BIN), os.path.join(out_dir, META)]
    for path, data in zip(paths, (vectors.q.tobytes(order='C'), serialise(vectors.meta))):
        with open(path, 'wb') as fh:
            fh.write(data)
    return paths


# ---- the model ----------------------------------------------------------------------------------------------------

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def verify(folder: str) -> list[str]:
    """Every WEIGHTS file that is missing from `folder` or does not hash to its pin."""
    bad = []
    for name, digest in sorted(WEIGHTS.items()):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            bad.append('%s is missing' % name)
        elif sha256_file(path) != digest:
            bad.append('%s does not hash to its pinned sha256 %s' % (name, digest))
    return bad


def cached() -> str | None:
    """The local snapshot folder of MODEL_ID at REVISION, read without the network; None when it is absent."""
    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub.errors import LocalEntryNotFoundError
    except ImportError:
        return None
    try:
        return snapshot_download(MODEL_ID, revision=REVISION, allow_patterns=sorted(WEIGHTS), token=False,
                                 local_files_only=True)
    except (LocalEntryNotFoundError, FileNotFoundError, OSError):
        return None


def fetch() -> str:
    """Download WEIGHTS at REVISION into the Hugging Face cache, with no token, and check them; the folder."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError as e:
        raise EmbedError('model2vec and huggingface_hub are the `embed` extra: %s' % FETCH) from e
    folder = snapshot_download(MODEL_ID, revision=REVISION, allow_patterns=sorted(WEIGHTS), token=False)
    bad = verify(folder)
    if bad:
        raise EmbedError('%s@%s in %s: %s' % (MODEL_ID, REVISION, folder, '; '.join(bad)))
    return folder


class Potion:
    """potion-base-8M through model2vec, loaded from a local folder (never the hub), its hashes checked first."""

    unit = 'WordPiece tokens of the model tokenizer, [UNK] removed: what model2vec pools'

    def __init__(self, folder: str):
        bad = verify(folder)
        if bad:
            raise EmbedError('%s@%s in %s: %s' % (MODEL_ID, REVISION, folder, '; '.join(bad)))
        from model2vec import StaticModel
        self.model = StaticModel.from_pretrained(folder, max_length=None)    # an existing path: no download
        self.identity = {'id': MODEL_ID, 'revision': REVISION, 'dims': int(self.model.dim),
                         'library': 'model2vec %s' % metadata.version('model2vec')}
        if self.identity['dims'] != DIMS:
            raise EmbedError('%s has %d dims, not the %d 08 S5.5 sizes everything for'
                             % (MODEL_ID, self.identity['dims'], DIMS))

    def count(self, text: str) -> int:
        return len(self.model.tokenize([text])[0])

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(list(texts), max_length=None, normalize=True, use_multiprocessing=False,
                                 show_progress_bar=False)


def encoder() -> Potion:
    """The pinned model from the local cache, or EmbedError naming the command that fetches it. Never the network."""
    try:
        import model2vec  # noqa: F401
    except ImportError as e:
        raise EmbedError('`bench build --embed` needs the `embed` extra (model2vec): uv run --extra embed bench build '
                         '--embed') from e
    folder = cached()
    if folder is None or verify(folder):
        raise EmbedError('%s@%s is not in the local Hugging Face cache (the build never fetches, 08 S2); fetch it '
                         'once, about 30 MB, with no token: %s' % (MODEL_ID, REVISION[:12], FETCH))
    return Potion(folder)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--fetch', action='store_true',
                   help='download %s at %s into the Hugging Face cache, with no token' % (MODEL_ID, REVISION[:12]))
    a = p.parse_args(argv)
    try:
        folder = fetch() if a.fetch else cached()
    except EmbedError as e:
        print('embed: %s' % e, file=sys.stderr)
        return 1
    if folder is None:
        print('embed: %s@%s is not cached; %s' % (MODEL_ID, REVISION[:12], FETCH))
        return 1
    bad = verify(folder)
    print('embed: %s@%s in %s: %s' % (MODEL_ID, REVISION[:12], folder, '; '.join(bad) or 'every file matches its pin'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
