// site/test/encoder.parity.test.mjs -- P6-S1-T01 (11 S4 "The embedding decision"; 08 S5.5). The query encoder,
// src/islands/search/encoder.ts, loaded by Node as it is (its types stripped), over the files in public/embed/, against
// the Python reference vectors in test/fixtures/encoder-parity.json:
//
//   cd site && npm test -- encoder.parity      # the verify: node --test takes `encoder.parity` as one more file
//                                              # pattern, which matches nothing and is ignored, so this runs every
//                                              # test/*.test.mjs, this file among them (the suite needs a built dist/)
//   cd site && node --test test/encoder.parity.test.mjs                    # this file alone
//
// Done when: "The JS encoder reproduces the Python model2vec vector within 1e-3 on every fixture string." Which 1e-3 is
// the maintainer's open question (#278): the largest absolute difference of any one component, or 1 - cosine. For
// unit vectors the first is the stricter -- a component bound of 1e-3 caps 1 - cosine at 256 x 1e-6 / 2 = 1.3e-4 --
// so that is the one asserted, on every one of the 200 strings, and 1 - cosine is asserted beside it. Every run prints
// the worst case of both, for the shipped stack (int8 rows and the 2-bit residual) and for the int8 rows alone, which
// meet the cosine reading and not the component one: the figures the maintainer's decision needs.
//
// The fixture and the files are tools/build/query_encoder.py's (`uv run --extra embed python -m
// tools.build.query_encoder`, `--check` to compare): the references are the full unpruned potion-base-8M through
// model2vec 0.10.0, the document side's own encode call. Also held: the token ids, exactly, for every string (the
// tokenizer is the part most likely to drift); the four queries that drop a pruned token, against model2vec over the
// pruned matrix, with what pruning costs them printed; the two corrections prenormalise makes, shown to be needed; the
// files' sizes and hashes against their meta and the tokenizer against the model pin; and that the encoder imports
// nothing but @huggingface/tokenizers, at the exact version 08 S5.5 names.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { Tokenizer } from '@huggingface/tokenizers';
import { ENCODER_FORMAT, QueryEncoder, dequantise, prenormalise } from '../src/islands/search/encoder.ts';

const EMBED = new URL('../public/embed/', import.meta.url);
const read = (name) => readFileSync(new URL(name, EMBED));
const META = JSON.parse(read('potion-8m-pruned.meta.json'));
const TOKENIZER = JSON.parse(read('tokenizer.json'));
const I8 = read('potion-8m-pruned.i8.bin');
const R2 = read('potion-8m-pruned.r2.bin');
const FIXTURE = JSON.parse(readFileSync(new URL('./fixtures/encoder-parity.json', import.meta.url), 'utf8'));
const EMBED_PY = readFileSync(new URL('../../tools/build/embed.py', import.meta.url), 'utf8');
const TOL = FIXTURE.tolerance;

const full = new QueryEncoder(TOKENIZER, META, dequantise(META, I8, R2));
const int8 = new QueryEncoder(TOKENIZER, META, dequantise(META, I8));

/** A base64 little-endian float32 vector, copied so its offset is aligned. */
function vec(b64) {
  const b = Buffer.from(b64, 'base64');
  return new Float32Array(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
}

/** [largest |a - b| of any component, 1 - cosine]; two zero vectors are the same vector. */
function gap(a, b) {
  let max = 0, dot = 0, na = 0, nb = 0;
  for (let k = 0; k < a.length; k++) {
    max = Math.max(max, Math.abs(a[k] - b[k]));
    dot += a[k] * b[k];
    na += a[k] * a[k];
    nb += b[k] * b[k];
  }
  const cos = na === 0 || nb === 0 ? (na === nb ? 1 : 0) : dot / Math.sqrt(na * nb);
  return [max, 1 - cos];
}

/** The worst of both readings over the fixture strings for one encoder, and how many strings break each. */
function worst(encoder) {
  const w = { max: 0, maxText: '', cos: 0, cosText: '', overMax: 0, overCos: 0 };
  for (const s of FIXTURE.strings) {
    const [max, cos] = gap(encoder.encode(s.text), vec(s.ref));
    if (max > w.max) Object.assign(w, { max, maxText: s.text });
    if (cos > w.cos) Object.assign(w, { cos, cosText: s.text });
    w.overMax += max > TOL;
    w.overCos += cos > TOL;
  }
  return w;
}

const quote = (text) => JSON.stringify(text.slice(0, 50));
const say = (w) => `max |a - b| ${w.max.toExponential(2)} (${quote(w.maxText)}), ${w.overMax} of `
  + `${FIXTURE.strings.length} over ${TOL}; 1 - cos ${w.cos.toExponential(2)} (${quote(w.cosText)}), ${w.overCos} over`;

// ---- the files --------------------------------------------------------------------------------------------------

test('encoder.parity: the files are what their meta says, and the tokenizer is the pinned one', () => {
  assert.equal(META.artifact, 'query-encoder');
  assert.equal(META.format, ENCODER_FORMAT);
  assert.equal(META.dims, 256);
  assert.equal(META.model.id, 'minishlab/potion-base-8M');
  assert.equal(META.model.library, 'model2vec 0.10.0');
  assert.ok(EMBED_PY.includes(`REVISION = '${META.model.revision}'`), 'the revision tools/build/embed.py pins');
  for (const [file, data] of [['matrix', I8], ['residual', R2], ['tokenizer', read('tokenizer.json')]]) {
    assert.equal(data.byteLength, META.files[file].bytes, file);
    assert.equal(createHash('sha256').update(data).digest('hex'), META.files[file].sha256, file);
  }
  const pinned = /'tokenizer\.json': '([0-9a-f]{64})'/.exec(EMBED_PY)[1];
  assert.equal(META.files.tokenizer.sha256, pinned, 'byte for byte the file embed.py checks the model by');
  assert.equal(I8.byteLength, META.rows * META.dims);
  assert.equal(R2.byteLength, META.rows * META.dims / 4);
  assert.equal(META.scales.length, META.rows);
  assert.ok(META.scales.every((s) => Number.isFinite(s) && s > 0));
  const ids = META.token_ids;
  assert.equal(ids.length, META.rows);
  assert.ok(ids.every((id) => Number.isInteger(id) && id >= 0 && id < META.vocab_size));
  assert.ok(ids.every((id, i) => i === 0 || id > ids[i - 1]), 'ascending, each once');
  assert.deepEqual(ids.slice(0, META.pruning.top), [...Array(META.pruning.top).keys()], 'the top ids, every one');
  assert.equal(ids.length, META.pruning.top + META.pruning.corpus_tokens_above_top);
  assert.equal(META.vocab_size, Object.keys(TOKENIZER.model.vocab).length);
  assert.equal(TOKENIZER.model.vocab['[UNK]'], META.unk_token_id);
});

test('encoder.parity: dequantise refuses a wrong-sized plane; the residual moves a value 3/8 step at most', () => {
  assert.throws(() => dequantise(META, I8.subarray(1)), /int8 plane/);
  assert.throws(() => dequantise(META, I8, R2.subarray(1)), /residual plane/);
  const a = dequantise(META, I8, R2), b = dequantise(META, I8);
  for (let row = 0; row < META.rows; row += 97) {
    const scale = Math.fround(META.scales[row]);
    for (let k = row * META.dims; k < (row + 1) * META.dims; k++) {
      // (r - 1.5) / 4 is at most 3/8 of a step; each float32 value is rounded by up to an ulp
      assert.ok(Math.abs(a[k] - b[k]) <= scale * 0.375 + (Math.abs(a[k]) + Math.abs(b[k])) * 2 ** -23);
    }
  }
});

// ---- the fixture ------------------------------------------------------------------------------------------------

test('encoder.parity: the fixture is 200 strings in four groups, each with its ids and a 256-float reference', () => {
  const count = {};
  for (const s of FIXTURE.strings) count[s.group] = (count[s.group] ?? 0) + 1;
  assert.deepEqual(count, { query: 106, identity: 34, label: 30, edge: 30 });
  assert.equal(FIXTURE.strings.length, 200);
  assert.equal(FIXTURE.pruned.length, 4);
  for (const s of [...FIXTURE.strings, ...FIXTURE.pruned]) assert.equal(vec(s.ref).length, 256, s.text);
  assert.equal(TOL, 1e-3);
  assert.equal(FIXTURE.model.revision, META.model.revision);
});

test('encoder.parity: every fixture string tokenises to the ids model2vec pools', () => {
  for (const s of [...FIXTURE.strings, ...FIXTURE.pruned]) {
    assert.deepEqual(full.tokenize(s.text), s.ids, JSON.stringify(s.text));
  }
  const long = FIXTURE.strings.at(-1);
  assert.ok(long.ids.length > 512, 'one string is over 512 tokens, and nothing truncates it');
});

test('encoder.parity: every fixture string within 1e-3 of the Python vector, under both readings', (t) => {
  for (const s of FIXTURE.strings) {
    const [max, cos] = gap(full.encode(s.text), vec(s.ref));
    assert.ok(max <= TOL, `max |a - b| ${max.toExponential(2)} > ${TOL}: ${JSON.stringify(s.text)}`);
    assert.ok(cos <= TOL, `1 - cos ${cos.toExponential(2)} > ${TOL}: ${JSON.stringify(s.text)}`);
  }
  const shipped = worst(full), alone = worst(int8);
  t.diagnostic(`int8 + 2-bit residual: ${say(shipped)}`);
  t.diagnostic(`int8 alone:            ${say(alone)}`);
  // the cosine reading is the fallback the module headers offer the maintainer: it must hold for int8 alone
  assert.equal(alone.overCos, 0);
});

test('encoder.parity: a query vector is a unit vector, or zeros when nothing is left to pool', () => {
  for (const s of FIXTURE.strings) {
    const v = full.encode(s.text);
    const norm = Math.sqrt(v.reduce((a, x) => a + x * x, 0));
    if (s.ids.length === 0) assert.equal(norm, 0, JSON.stringify(s.text));
    else assert.ok(Math.abs(norm - 1) < 1e-6, JSON.stringify(s.text));
  }
  assert.ok(FIXTURE.strings.filter((s) => s.ids.length === 0).length >= 3, 'empty, whitespace and unknown-only');
});

test('encoder.parity: a pruned token is dropped, as model2vec drops [UNK], and what that costs is stated', (t) => {
  for (const p of FIXTURE.pruned) {
    assert.deepEqual(full.pruned(p.text), p.dropped, p.text);
    assert.ok(p.dropped.length > 0);
    const v = full.encode(p.text);
    const [max] = gap(v, vec(p.pruned_ref));
    assert.ok(max <= TOL, `${p.text}: ${max.toExponential(2)} from model2vec over the pruned matrix`);
    const [, cos] = gap(v, vec(p.ref));
    assert.ok(Math.abs(1 - cos - p.cosine) < TOL, p.text);
    t.diagnostic(`${JSON.stringify(p.text)}: cosine ${(1 - cos).toFixed(4)} to the unpruned vector`);
  }
  for (const s of FIXTURE.strings) assert.deepEqual(full.pruned(s.text), [], JSON.stringify(s.text));
});

test('encoder.parity: prenormalise makes the two corrections the library needs, and no other change', () => {
  const raw = new Tokenizer(TOKENIZER, {});
  const ids = (text) => raw.encode(text, { add_special_tokens: false }).ids.filter((id) => id !== META.unk_token_id);
  const sigma = String.fromCodePoint(0x3a3);
  const touched = FIXTURE.strings.filter((s) => prenormalise(s.text) !== s.text);
  assert.deepEqual(touched.map((s) => s.group), ['edge', 'edge', 'edge'], 'two capital sigma strings, one astral CJK');
  assert.equal(touched.filter((s) => s.text.includes(sigma)).length, 2);
  assert.equal(touched.filter((s) => [...s.text].some((c) => c.codePointAt(0) >= 0x20000)).length, 1);
  for (const s of touched) {
    assert.notDeepEqual(ids(s.text), s.ids, `without prenormalise ${JSON.stringify(s.text)} tokenises otherwise`);
    assert.deepEqual(ids(prenormalise(s.text)), s.ids);
  }
});

test('encoder.parity: the encoder imports @huggingface/tokenizers alone, at the version 08 S5.5 names', () => {
  const src = readFileSync(new URL('../src/islands/search/encoder.ts', import.meta.url), 'utf8');
  assert.deepEqual([...src.matchAll(/^import .* from '([^']+)';$/gm)].map((m) => m[1]), ['@huggingface/tokenizers']);
  const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
  assert.equal(pkg.dependencies['@huggingface/tokenizers'], '0.2.0');
  const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
  const entry = lock.packages['node_modules/@huggingface/tokenizers'];
  assert.equal(entry.version, '0.2.0');
  assert.equal(entry.dependencies, undefined, 'no dependency of its own');
});
