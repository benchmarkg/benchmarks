"""The query encoder's static files and its parity fixture (P6-S1-T01; 11 S4 "The embedding decision"; 08 S5.5).

    uv run --extra embed python -m tools.build.query_encoder            # write them
    uv run --extra embed python -m tools.build.query_encoder --check    # exit 1 if a committed one is stale

11 S4: "A model2vec model *is* an embedding matrix: encoding is tokenise, look up rows, mean-pool, normalise." The
document side, tools/build/embed.py (P6-S1-T03), embeds every family's card in Python with the full model; the query
side runs in the browser, site/src/islands/search/encoder.ts, over the files this writes into site/public/embed/, and
must land in the same space, so everything here is embed.py's: the model pin (MODEL_ID at REVISION, the WEIGHTS
sha256s), read from the local Hugging Face cache by embed.encoder() and never from the network; its quantiser; and its
encode call (max_length=None, normalize=True) for the reference vectors. The model card (checked 2026-11-25) is public
and ungated, licence MIT; `--fetch` in embed.py downloads it with no token.

  tokenizer.json              the model's tokenizer, the pinned file byte for byte (WEIGHTS sha256), not pruned:
                              WordPiece splits a word into the longest pieces its vocabulary holds, so a smaller
                              vocabulary would segment words differently and move vectors that never touch a pruned
                              row. Pruning happens after tokenisation, on the rows.
  potion-8m-pruned.i8.bin     the kept rows x 256 int8, row-major, no header: embed.quantise, symmetric, one scale per
                              row, scale = max|v| / 127, v ~ q * float32(scale), each coordinate within scale / 2
  potion-8m-pruned.r2.bin     each coordinate's 2-bit residual, four to a byte, coordinate k of the row-major matrix at
                              bits 2(k mod 4) of byte k div 4: r = floor((v / scale - q + 0.5) * 4) in 0..3, and
                              v ~ float32(scale) * (q + (r - 1.5) / 4), each coordinate within scale / 8
  potion-8m-pruned.meta.json  token_ids (row r is the token token_ids[r]), scales, provenance: emit.serialise's bytes

The pruning (11 S4: "the top ~12k WordPiece tokens unioned with every token occurring in the corpus, mapping the rest
to [UNK]"). potion's tokenizer is bge-base-en-v1.5's, bert-base-uncased's WordPiece vocabulary less its 994 [unused]
slots, 29,528 tokens: five special tokens, 997 single characters (ids 5 to 1,001), then words and ## pieces in the
vocabulary's own order, most frequent first (1,005 is 'in', 2,000 'stay', 5,000 'involving', 11,999 'madras').
The top TOP (12,000) is ids 0 to 11,999. The corpus token set is every id model2vec's own `tokenize` (the model
tokenizer, no special tokens added, [UNK] removed) gives over:

  1. every benchmark family's whole card, embed.card_parts' identity and rest *before* the CARD_TOKENS cut, so a word
     the cut drops from the document vector is still a query word: name, aliases, edition names, tagline, the domain,
     capability and evaluation-method labels, description;
  2. every label of those three vocabularies (taxonomy/domains.yaml, capabilities.yaml, evaluation-methods.yaml), used
     by a card or not, because a query names a term no family carries yet;

over the draft preview corpus, artifacts.build(drafts=True), as scripts/preview_corpus.py builds it: every committed
benchmark that passes tier 1, since no entry is published yet (05 S4) and the published corpus has no tokens. On main
at 201f8811 (2026-11-25): 325 families and 304 labels give 7,656 distinct ids, 2,834 of them at or above TOP, so
14,834 rows. A token with no row is dropped from the mean, as model2vec drops [UNK]. When a draft adds a word, --check
fails until this is re-run, and until then the encoder drops that word (pruned tokens are the fixture's `pruned` group).

Why the residual plane. The ledger's done_when is "within 1e-3 on every fixture string", and which 1e-3 is an open
question for the maintainer (raised in #278): the maximum absolute difference of any component, or 1 - cosine. For
unit vectors the first is the stricter (max |a - b| <= 1e-3 bounds 1 - cos at 256 x 1e-6 / 2 = 1.3e-4), so
test/encoder.parity.test.mjs asserts it. int8 alone cannot meet it: a coordinate is off by up to scale / 2, and
potion's rows put up to 68% of their norm in one coordinate (median 24%), so a normalised single token is off by up
to 2.8e-3 (over all 29,528 rows), and a mean of several, whose rounding noise is no longer bounded by one step,
no better: over the fixture, int8 alone measures max |a - b| 1.9e-3 at worst, 186 of the 200 strings over 1e-3, but
1 - cos only 7.2e-5. The 2-bit residual brings the step to scale / 4 (ten bits in all) for a quarter of the int8
bytes, and measures 5.0e-4 and 5.3e-6. If the maintainer settles on the cosine reading, the .r2.bin is dropped and
the encoder reads the int8 plane alone (encoder.ts dequantises without it). The figures are the test's, printed by
every run (2026-11-25).

What it costs, on disk and brotli-compressed at quality 11: the int8 plane 3,797,504 bytes (3,342,267), the residual
949,376 (949,381: two-bit codes do not compress), the meta 240,836 (79,230), the tokenizer 683,666 (152,003); 4.52 MB
on the wire in all, 3.57 MB without the residual, against the 3.5 MB 11 S4 asks 08 S8 to budget for the whole
semantic tier, document vectors included. 11 S4 sized ~12k rows at ~3 MB; the union with the corpus is 14,834.

The fixture, site/test/fixtures/encoder-parity.json: 200 strings, each with the ids model2vec tokenizes it to and its
reference vector, the full unpruned model's encode (embed.Potion.encode, the document side's own call), as base64
little-endian float32:

  query     106  the QUERIES written for this fixture, the kind of thing 11 S4 has a visitor type ("find me benchmarks
                 about protein folding"), across the taxonomy's families; the four whose tokens a pruned row would
                 drop are the `pruned` group instead (below)
  identity   34  names, aliases and edition names of draft families, as they are written
  label      30  every tenth label of the three vocabularies, in file order
  edge       30  what the tokenizer must reproduce: case, accents, punctuation, digits, CJK in and out of the Basic
                 Multilingual Plane, Greek final sigma, control and format characters, special-token text, a word
                 over max_input_chars_per_word, nothing to pool at all, and one string over 512 tokens

Every one of the 200 has every token in a kept row (the export refuses otherwise), so its only difference from the
reference is the quantiser's. The `pruned` group holds the four queries that do drop a token, each with its full
reference, `pruned_ref` (model2vec itself over the matrix with every unkept row zeroed, which drops them, since the
mean is normalised), and the cosine between the two: what pruning costs, stated rather than hidden (0.80 for
'climate model projections' without 'projections', 0.87, 0.89 and 0.91 for the other three).

Determinism: the matrix and its meta are a function of the pinned weights, the corpus and TOP; the fixture of the
weights and the strings below. Two runs write the same bytes, which is what --check compares.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools.build import embed  # noqa: E402
from tools.build.emit import serialise  # noqa: E402

TOP = 12000
LEVELS = 4                                                   # the residual's 2 bits
FORMAT = 1
OUT = os.path.join('site', 'public', 'embed')
TOKENIZER, MATRIX, RESIDUAL, META = ('tokenizer.json', 'potion-8m-pruned.i8.bin', 'potion-8m-pruned.r2.bin',
                                     'potion-8m-pruned.meta.json')
FIXTURE = os.path.join('site', 'test', 'fixtures', 'encoder-parity.json')
RUN = 'uv run --extra embed python -m tools.build.query_encoder'

QUERIES = [
    'find me benchmarks about protein folding', 'protein structure prediction from sequence',
    'benchmarks for code generation with unit tests',
    'repository-level software engineering tasks from real GitHub issues',
    'multilingual machine translation evaluation', 'translation for low resource languages',
    'math word problems for grade school', 'competition mathematics olympiad problems',
    'formal theorem proving in Lean',
    'long context retrieval over entire books', 'needle in a haystack test',
    'web browsing agents that complete tasks on real websites', 'agents that use tools and call APIs',
    'computer use agents operating a desktop GUI', 'autonomous driving planning in simulation',
    'robot manipulation with a gripper', 'humanoid locomotion control',
    'medical question answering like the USMLE exam',
    'clinical diagnosis from patient notes', 'radiology report generation from chest x-rays',
    'speech recognition word error rate', 'text to speech naturalness', 'music generation quality',
    'weather forecasting with machine learning', 'climate model projections', 'satellite imagery and remote sensing',
    'molecular property prediction', 'retrosynthesis planning for organic chemistry',
    'crystal structure prediction for materials discovery', 'drug target interaction', 'single cell gene expression',
    'genomic variant effect prediction', 'jailbreak robustness of language models',
    'prompt injection attacks against agents', 'measuring sycophancy', 'truthfulness and hallucination',
    'bias and fairness across demographic groups', 'dangerous capability evaluations for biosecurity',
    'deceptive behaviour and scheming', 'reading comprehension questions about a passage',
    'commonsense reasoning about everyday situations', 'logical deduction puzzles', 'theory of mind false belief tasks',
    'spatial reasoning from images', 'chart and diagram understanding', 'visual question answering on natural images',
    'video understanding with temporal questions', 'document OCR and handwriting recognition',
    'image generation judged by human preference', 'text to video generation', '3D reconstruction from multiple views',
    'object detection on COCO', 'semantic segmentation of street scenes', 'board games like chess and go',
    'poker and imperfect information games', 'Atari video game playing', 'real time strategy games like StarCraft',
    'abstract reasoning puzzles like ARC', 'general intelligence test batteries compared with humans',
    'multi-subject knowledge exam with multiple choice questions', 'open preference arena with Elo ratings',
    'summarization of news articles', 'dialogue and chat assistant quality',
    'instruction following with verifiable constraints', 'creative writing graded by a rubric',
    'information extraction from scientific papers', 'legal reasoning over contracts',
    'financial analysis of company filings', 'forecasting future events with prediction markets',
    'economically valuable tasks done by professionals', 'tutoring students in education',
    'CAD model generation for mechanical parts', 'circuit design and electronic design automation',
    'data science notebooks with pandas', 'machine learning engineering on Kaggle competitions',
    'code performance optimization', 'bug repair benchmarks', 'competitive programming contests',
    'SQL query generation from natural language', 'cybersecurity capture the flag challenges',
    'multi agent cooperation and negotiation', 'long horizon tasks that take humans hours',
    'research agents that reproduce papers', 'fluid dynamics surrogate models', 'particle physics jet tagging',
    'quantum chemistry energies', 'astronomy and cosmology data', 'earthquake and flood hazard prediction',
    'species identification from camera traps', 'crop yield prediction in agriculture', 'energy grid optimization',
    'brain decoding from fMRI', 'calibration and uncertainty of model predictions',
    'adversarial robustness to perturbations', 'continual learning without forgetting',
    'sample efficient learning from few examples', 'benchmarks released after 2024 with open access data',
    'contamination resistant evaluation with a private test set', 'human expert evaluation of answers',
    'model graded judge with pairwise comparisons', 'exact match accuracy on short answers',
    'episodic return in reinforcement learning environments', 'wet lab validation of designed proteins',
    'sim to real transfer for robots', 'tactile sensing for dexterous hands', 'drone navigation',
    'audio event detection in sound clips', 'bird sound classification', 'speaker verification',
    'speech translation between languages',
]

IDENTITY = [
    'A2RL Drone Championship', 'Aider polyglot benchmark', 'In-Context Scheming Evaluations', 'BALROG',
    'BIG-Bench Hard', 'BuildingsBench', 'CAMELYON17', 'CHiME Challenge', 'ControlArena', 'CVDP', 'DL3DV-10K',
    'F1TENTH Autonomous Racing',
    'ForecastBench', 'GPQA', 'ICDAR 2015 Incidental Scene Text', 'JetClass', 'LHC Olympics 2020', 'MathTutorBench',
    'Meta-World', 'MMLU-Pro', 'OmniDocBench', 'safe-control-gym', 'Video-MME',
    # aliases
    'Stanford Question Answering Dataset', 'Task of Fictitious Unlearning', 'Comprehensive Verilog Design Problems',
    'GPQA diamond', 'WorkArena++', 'Holistic Evaluation of Audio Representations',
    # edition names
    'Season 1 (A2RL x DCL), ADNEC Marina Hall, Abu Dhabi, 11-12 April 2025',
    'SQuAD 2.0 (SQuADRUn in the ACL version of its paper)',
    'NAVSIM v2 (devkit v2.0 to v2.2; navhard_two_stage, the EPDMS and pseudo-simulation), CoRL 2025',
    'The Third Perception Test Challenge (ICCV 2025)', 'Embedded Systems Week 2016, Pittsburgh (the first race)',
]

EDGE = [
    '',                                                      # nothing at all: the zero vector
    ' \t\n \u3000 ',                                         # whitespace only, an ideographic space among it
    '\U0001f9ec\U0001f52c',                                  # two emoji, each [UNK], removed: the zero vector
    'a' * 101 + ' protein',                                  # a word over max_input_chars_per_word is one [UNK]
    'PROTEIN Folding',                                       # lowercased
    'Montr\u00e9al fa\u00e7ade na\u00efve caf\u00e9',        # accents stripped
    'x\u0301y e\u0300',                                      # combining marks already decomposed, stripped
    '\u0130stanbul \u00c5NGSTR\u00d6M',                        # a dotted capital I, a ring, an umlaut
    '\u0391.\u03a3 \u039f.\u03a3. \u03a3.\u0391',              # a word-final capital sigma: sigma, per character
    '\u0386.\u0388.\u03a3',                                    # the same, accents stripped (Greek ## pieces are pruned)
    '\u65e5\u672c\u8a9e\u306e\u8cea\u554f\u5fdc\u7b54',      # CJK in the BMP, padded with spaces
    '\U00020000abc def',                                     # CJK outside the BMP, padded too (encoder.ts)
    'x\u0000y\u200bz\u00adw\u0085v',                         # NUL, zero-width space, soft hyphen, NEL: removed
    '\ufeffbom nbsp\u00a0here tab\there line\u2028sep',      # BOM removed, other spaces split
    'GPT-4o vs. o1-preview (2024)',                          # punctuation and digits split
    'SWE-bench_Verified@v1.2',
    'http://example.invalid/path?q=1&r=2',
    "don't can't won't",
    '\u201equotes\u201c \u00abguillemets\u00bb \u2014 dash',
    '\ufb01le \ufb02ow',                                      # ligatures, both in the vocabulary
    '\uff46\uff55\uff4c\uff4c\uff57\uff49\uff44\uff54\uff48 \uff21\uff22\uff23',  # fullwidth: no NFKC, [UNK]
    'x\u00b2 + y\u00b3 \u00bd',                              # superscripts and a vulgar fraction
    'math \u2211 \u222b \u221a \u2264 \u2265',
    '\u0661\u0662\u0663 \u0664\u0665\u0666',                 # Arabic-Indic digits
    '[MASK] the [CLS] token',                                # special tokens matched in the raw text, kept
    '[mask] lower',                                          # not a special token: case-sensitive, so [ mask ]
    'protein protein protein',                               # a repeated token
    'q',                                                     # one character
    'ProteinGym',                                            # one word, several pieces
    ' '.join(IDENTITY * 3),                                  # 693 tokens, over 512: nothing truncates
]

PRUNED_NOTE = ('the QUERIES that drop a token a pruned row would hold; pruned_ref is model2vec over the matrix with '
               'every unkept row zeroed')


class ExportError(Exception):
    """The export would write something wrong; the message says why."""


# ---- the pruning --------------------------------------------------------------------------------------------------

def corpus_texts(root: str) -> tuple[list[str], list[str]]:
    """(every family's whole card, every label of the three vocabularies) over the draft preview corpus."""
    from tools.build import artifacts
    result = artifacts.build(root, drafts=True)
    records = {b['id']: b for b in result.corpus['entities']['benchmark']}
    cards = ['\n'.join(embed.card_parts(row, records[row['id']])) for row in result.facets['benchmarks']]
    return cards, [label for terms in embed.labels().values() for label in terms.values()]


def kept_ids(tokenize, texts: list[str], vocab_size: int, top: int = TOP) -> tuple[list[int], set[int]]:
    """(the kept token ids ascending, the corpus token set): ids below `top` and every id `tokenize` gives `texts`."""
    corpus: set[int] = set()
    for ids in tokenize(texts):
        corpus.update(ids)
    return sorted(set(range(min(top, vocab_size))) | corpus), corpus


# ---- the residual -------------------------------------------------------------------------------------------------

def residual(rows: np.ndarray, q: np.ndarray, scales: list[float]) -> np.ndarray:
    """Each coordinate's 2-bit residual code, 0..3: where v / scale sits in [q - 0.5, q + 0.5], in quarters."""
    s = np.asarray(scales, dtype=np.float64).astype(np.float32).astype(np.float64).reshape(-1, 1)
    t = np.asarray(rows, dtype=np.float64) / np.where(s > 0, s, 1.0) - q
    return np.clip(np.floor((t + 0.5) * LEVELS), 0, LEVELS - 1).astype(np.uint8)


def pack(codes: np.ndarray) -> bytes:
    """Four codes a byte, the first in the low bits."""
    c = codes.reshape(-1, 4).astype(np.uint8)
    return (c[:, 0] | (c[:, 1] << 2) | (c[:, 2] << 4) | (c[:, 3] << 6)).astype(np.uint8).tobytes()


def dequantise(q: np.ndarray, scales: list[float], codes: np.ndarray | None = None) -> np.ndarray:
    """What encoder.ts computes: float32(scale) * (q + (r - 1.5) / 4), or q * float32(scale) without the residual."""
    s = np.asarray(scales, dtype=np.float64).astype(np.float32).reshape(-1, 1)
    if codes is None:
        return q.astype(np.float32) * s
    return (s * (q.astype(np.float32) + (codes.astype(np.float32) - 1.5) / LEVELS)).astype(np.float32)


# ---- the export ---------------------------------------------------------------------------------------------------

def b64(v: np.ndarray) -> str:
    return base64.b64encode(np.asarray(v, dtype='<f4').tobytes()).decode('ascii')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def files(root: str, potion=None) -> dict[str, bytes]:
    """Every file this writes, path relative to `root` -> bytes. Raises ExportError rather than write a fixture string
    that drops a token, or a binary git could take for text."""
    potion = potion or embed.encoder()
    model = potion.model
    folder = embed.cached()
    with open(os.path.join(folder, TOKENIZER), 'rb') as fh:
        tokenizer = fh.read()
    if sha256(tokenizer) != embed.WEIGHTS[TOKENIZER]:
        raise ExportError('%s does not hash to its pin' % TOKENIZER)
    full = np.asarray(model.embedding, dtype=np.float32)
    vocab_size, dims = full.shape
    cards, labels = corpus_texts(root)
    kept, corpus = kept_ids(model.tokenize, cards + labels, vocab_size)
    rows = full[kept]
    q, scales = embed.quantise(rows)
    codes = residual(rows, q, scales)
    matrix, packed = q.tobytes(order='C'), pack(codes)
    for name, data in ((MATRIX, matrix), (RESIDUAL, packed)):
        # .gitattributes says `* text=auto`: git stores a file as binary when its first 8,000 bytes hold a NUL
        if b'\0' not in data[:8000]:
            raise ExportError('%s has no NUL in its first 8,000 bytes, so git would treat it as text' % name)
    meta = {
        'artifact': 'query-encoder', 'format': FORMAT, 'model': dict(potion.identity), 'vocab_size': vocab_size,
        'unk_token_id': model.unk_token_id, 'rows': len(kept), 'dims': dims, 'token_ids': kept, 'scales': scales,
        'quantization': {'scheme': 'int8, symmetric, one scale per row: scale = max|v| / %d' % embed.QMAX,
                         'qmax': embed.QMAX, 'dequantize': 'v[i][k] = q[i][k] * float32(scales[i])',
                         'residual': {'bits': 2, 'layout': 'code of coordinate k (row-major) at bits 2*(k % 4) of '
                                                           'byte floor(k / 4)',
                                      'dequantize': 'v[i][k] = float32(scales[i]) * (q[i][k] + (r[i][k] - 1.5) / 4)'}},
        'pruning': {'top': TOP, 'corpus': 'every token of every family card, uncut, in the draft preview corpus, and '
                                          'of every domain, capability and evaluation-method label',
                    'families': len(cards), 'labels': len(labels), 'corpus_tokens': len(corpus),
                    'corpus_tokens_above_top': len([i for i in corpus if i >= TOP]),
                    'corpus_tokens_sha256': sha256(','.join(map(str, sorted(corpus))).encode('ascii'))},
        'files': {'matrix': {'file': MATRIX, 'bytes': len(matrix), 'sha256': sha256(matrix)},
                  'residual': {'file': RESIDUAL, 'bytes': len(packed), 'sha256': sha256(packed)},
                  'tokenizer': {'file': TOKENIZER, 'bytes': len(tokenizer), 'sha256': sha256(tokenizer)}},
    }
    out = {os.path.join(OUT, TOKENIZER): tokenizer, os.path.join(OUT, MATRIX): matrix,
           os.path.join(OUT, RESIDUAL): packed, os.path.join(OUT, META): serialise(meta)}
    out[FIXTURE] = fixture(potion, set(kept), full)
    return out


def fixture(potion, kept: set[int], full: np.ndarray) -> bytes:
    """encoder-parity.json: one string a line, ASCII-escaped, so every control and invisible character shows."""
    from model2vec import StaticModel
    from tokenizers import Tokenizer
    model = potion.model
    labels = [label for terms in embed.labels().values() for label in terms.values()]
    groups = [('query', QUERIES), ('identity', IDENTITY), ('label', labels[::10][:30]), ('edge', EDGE)]
    texts = [t for _, ts in groups for t in ts]
    ids = model.tokenize(texts)
    refs = potion.encode(texts)
    strings, pruned_texts = [], []
    for (group, ts) in groups:
        for t in ts:
            k = len(strings) + len(pruned_texts)
            if any(i not in kept for i in ids[k]):
                if group != 'query':
                    raise ExportError('the %s string %r has a token with no kept row' % (group, t))
                pruned_texts.append((t, ids[k], refs[k]))
                continue
            strings.append({'group': group, 'text': t, 'ids': ids[k], 'ref': b64(refs[k])})
    if len(strings) != 200:
        raise ExportError('%d fixture strings, not 200' % len(strings))
    zeroed = full.copy()
    zeroed[[i for i in range(len(full)) if i not in kept]] = 0
    pruned_model = StaticModel(vectors=zeroed, tokenizer=Tokenizer.from_str(model.tokenizer.to_str()),
                               normalize=True, max_length=None)
    pruned = []
    for t, tids, ref in pruned_texts:
        pref = pruned_model.encode([t], max_length=None, normalize=True, use_multiprocessing=False,
                                   show_progress_bar=False)[0]
        pruned.append({'text': t, 'ids': tids, 'dropped': [i for i in tids if i not in kept], 'ref': b64(ref),
                       'pruned_ref': b64(pref),
                       'cosine': round(float(np.dot(ref.astype(np.float64), pref.astype(np.float64))), 6)})
    head = {'about': 'P6-S1-T01: written by tools/build/query_encoder.py (%s); the reference is %s@%s through %s, '
                     'max_length None, normalized; ref is base64 little-endian float32' % (
                         RUN, embed.MODEL_ID, embed.REVISION[:12], potion.identity['library']),
            'model': dict(potion.identity), 'tolerance': embed.TOLERANCE, 'pruned_note': PRUNED_NOTE}
    lines = ['{']
    lines += ['%s: %s,' % (json.dumps(k), json.dumps(v, sort_keys=True)) for k, v in sorted(head.items())]
    for key, items in (('pruned', pruned), ('strings', strings)):
        lines.append('%s: [' % json.dumps(key))
        lines += ['  %s%s' % (json.dumps(x, sort_keys=True), ',' if n < len(items) - 1 else '')
                  for n, x in enumerate(items)]
        lines.append('],' if key == 'pruned' else ']')
    lines.append('}')
    return ('\n'.join(lines) + '\n').encode('ascii')


def stale(root: str, out: dict[str, bytes]) -> list[str]:
    """Every file in `out` whose committed bytes differ."""
    bad = []
    for path, data in sorted(out.items()):
        full = os.path.join(root, path)
        if not os.path.exists(full):
            bad.append('%s is missing' % path)
            continue
        with open(full, 'rb') as fh:
            if fh.read() != data:
                bad.append('%s is stale' % path)
    return bad


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--check', action='store_true', help='write nothing; exit 1 if a committed file is stale')
    a = p.parse_args(argv)
    try:
        out = files(ROOT)
    except (embed.EmbedError, ExportError) as e:
        print('query_encoder: %s' % e, file=sys.stderr)
        return 1
    if a.check:
        bad = stale(ROOT, out)
        for line in bad:
            print('query_encoder: %s; regenerate with %s' % (line, RUN), file=sys.stderr)
        if not bad:
            print('query_encoder: %d files current' % len(out))
        return 1 if bad else 0
    for path, data in sorted(out.items()):
        full = os.path.join(ROOT, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as fh:
            fh.write(data)
        print('query_encoder: wrote %s (%d bytes)' % (path, len(data)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
