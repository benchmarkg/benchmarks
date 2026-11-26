// site/src/islands/search/encoder.ts -- P6-S1-T01 (11 S4 "The embedding decision"; 08 S5.5). The query side of the
// dense leg: a static model2vec encoder, so a query is embedded in the browser, offline, into the space of the document
// vectors tools/build/embed.py writes (vectors.i8.bin). 11 S4: "A model2vec model *is* an embedding matrix: encoding is
// tokenise, look up rows, mean-pool, normalise. There is no transformer to run." This module is those four steps over
// the files tools/build/query_encoder.py writes into public/embed/, and nothing else: fetching them, caching the
// dequantised matrix in IndexedDB and when to do it are the loader's (islands/search/loader.ts, P6-S1-T06).
//
//   tokenizer.json              potion-base-8M's own tokenizer, unpruned: WordPiece + BertNormalizer (bge-base-en)
//   potion-8m-pruned.i8.bin     the kept rows, int8, one scale per row (embed.py's quantiser)
//   potion-8m-pruned.r2.bin     each coordinate's 2-bit residual; optional (below)
//   potion-8m-pruned.meta.json  which token each row is, the scales, the model pin
//
// Tokenise. @huggingface/tokenizers 0.2.0 (pure JS, no dependency) runs the model's tokenizer.json as model2vec runs it
// in Python: no special tokens added, and [UNK] removed from the ids, because model2vec removes it before pooling. Two
// places where the JS library and the Rust tokenizers crate model2vec calls disagree are corrected before the text
// reaches it (prenormalise): JavaScript's toLowerCase applies the Final_Sigma rule, so a word-final capital sigma
// becomes final sigma (U+03C2) where Rust's per-character lowercase gives sigma (U+03C3); and the library pads CJK
// ideographs with spaces by UTF-16 unit, which misses those outside the Basic Multilingual Plane that Rust pads (the
// ranges below, as Rust's normaliser has them, U+2B820-U+2B91F excluded). Checked on 2026-11-25 by feeding every
// Unicode code point, between two letters, through both: 53,786 of the 1,112,064 differed, and with these two
// corrections 618 still do, characters Unicode assigned or recategorised in recent versions (61D, 890-891, 2E43-2E4F,
// 1E000-1E02A, ...), on which the Rust crate's category tables and V8's ICU disagree. No fixture string holds one.
//
// Look up. A row exists only for the kept tokens: ids 0 to 11,999 and every token of the draft corpus's cards and the
// taxonomy's labels (query_encoder.py says how that set is drawn). A token with no row is dropped from the mean, as
// [UNK] is -- 11 S4's "mapping the rest to [UNK]" -- so a query word outside the corpus and the top 12k loses its say:
// the fixture's four such queries keep a cosine of 0.80 to 0.91 to their unpruned vectors. Most ## pieces of non-Latin
// scripts sit above id 29,000 and are pruned, so a Greek or Cyrillic word keeps little more than its first letter.
//
// Mean-pool and normalise as model2vec does: the mean of the rows, divided by its norm; a query with no row to pool
// (empty, or every token unknown) is the zero vector, as model2vec returns it, and scores 0 against every document.
//
// The matrix is dequantised once, into a Float32Array (11 S4: "quantise to int8 for transport, then dequantise once
// into a Float32Array at load"), as scale x (q + (r - 1.5) / 4) with the residual and q x scale without it. The
// residual is what holds the parity test's stricter reading of 1e-3, the largest difference of any one component from
// the Python vector; int8 alone holds 1 - cosine within 1e-3 but not that (test/encoder.parity.test.mjs prints both).
import { Tokenizer } from '@huggingface/tokenizers';

/** potion-8m-pruned.meta.json, as tools/build/query_encoder.py writes it (format 1). */
export interface EncoderMeta {
  artifact: 'query-encoder';
  format: number;
  model: { id: string; revision: string; dims: number; library: string };
  vocab_size: number;
  unk_token_id: number;
  rows: number;
  dims: number;
  token_ids: readonly number[];
  scales: readonly number[];
}

export const ENCODER_FORMAT = 1;

/** The CJK ideographs outside the BMP that the Rust normaliser pads with spaces and the JS library does not. */
const ASTRAL_CJK = /[\u{20000}-\u{2A6DF}\u{2A700}-\u{2B81F}\u{2B920}-\u{2CEAF}\u{2F800}-\u{2FA1F}]/gu;

/** The text as the library must see it to tokenise as the Rust tokenizers crate does (module header, "Tokenise"). */
export const prenormalise = (text: string): string => text.replace(/\u03A3/g, '\u03C3').replace(ASTRAL_CJK, ' $& ');

/** The rows x dims matrix the int8 plane and its scales give, refined by the 2-bit residual plane when it is given. */
export function dequantise(meta: EncoderMeta, i8: Uint8Array, r2?: Uint8Array): Float32Array {
  const { rows, dims, scales } = meta;
  const n = rows * dims;
  if (i8.byteLength !== n) throw new Error(`the int8 plane is ${i8.byteLength} bytes, not ${rows} x ${dims}`);
  if (r2 && r2.byteLength !== n / 4) throw new Error(`the residual plane is ${r2.byteLength} bytes, not ${n / 4}`);
  if (scales.length !== rows) throw new Error(`${scales.length} scales for ${rows} rows`);
  const q = new Int8Array(i8.buffer, i8.byteOffset, n);
  const out = new Float32Array(n);
  for (let row = 0; row < rows; row++) {
    const scale = Math.fround(scales[row]);
    for (let k = row * dims, end = k + dims; k < end; k++) {
      const r = r2 ? (r2[k >> 2] >> ((k & 3) << 1)) & 3 : 1.5;
      out[k] = scale * (q[k] + (r - 1.5) / 4);
    }
  }
  return out;
}

export class QueryEncoder {
  readonly dims: number;
  private readonly tokenizer: Tokenizer;
  private readonly unk: number;
  private readonly matrix: Float32Array;
  private readonly rowOf: Int32Array;          // token id -> its row, or -1 when pruned

  /** `tokenizer` is the parsed tokenizer.json; `matrix` is dequantise()'s, or the loader's cached copy of it. */
  constructor(tokenizer: object, meta: EncoderMeta, matrix: Float32Array) {
    if (meta.artifact !== 'query-encoder' || meta.format !== ENCODER_FORMAT) {
      throw new Error(`not a query-encoder meta of format ${ENCODER_FORMAT}`);
    }
    if (matrix.length !== meta.rows * meta.dims) throw new Error('the matrix does not match its meta');
    this.tokenizer = new Tokenizer(tokenizer, {});
    this.dims = meta.dims;
    this.unk = meta.unk_token_id;
    this.matrix = matrix;
    this.rowOf = new Int32Array(meta.vocab_size).fill(-1);
    meta.token_ids.forEach((id, row) => { this.rowOf[id] = row; });
  }

  /** The ids model2vec pools in Python: the model's tokenizer, no special tokens added, [UNK] removed. */
  tokenize(text: string): number[] {
    return this.tokenizer.encode(prenormalise(text), { add_special_tokens: false }).ids.filter((id) => id !== this.unk);
  }

  /** The tokens of `text` that have no row, and so are dropped from the mean. */
  pruned(text: string): number[] {
    return this.tokenize(text).filter((id) => this.rowOf[id] < 0);
  }

  /** The unit query vector: the mean of the rows of the text's tokens, normalised; zeros when no token has a row. */
  encode(text: string): Float32Array {
    const { dims, matrix, rowOf } = this;
    const sum = new Float64Array(dims);
    let count = 0;
    for (const id of this.tokenize(text)) {
      const row = rowOf[id];
      if (row < 0) continue;
      for (let k = 0, at = row * dims; k < dims; k++) sum[k] += matrix[at + k];
      count++;
    }
    const out = new Float32Array(dims);
    if (count === 0) return out;
    let norm = 0;
    for (let k = 0; k < dims; k++) norm += (sum[k] / count) ** 2;
    norm = Math.sqrt(norm);
    if (norm > 0) for (let k = 0; k < dims; k++) out[k] = sum[k] / count / norm;
    return out;
  }
}
