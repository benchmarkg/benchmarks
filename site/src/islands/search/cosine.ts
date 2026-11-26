// site/src/islands/search/cosine.ts -- P6-S1-T05 (11 S4 "The pipeline", step 2, and "Sizing"; 08 S5.5, S5.7 "The
// fusion order", step 3). The semantic leg of the faceted query pipeline: cosine similarity between a query vector and
// the document matrix, restricted to the facet filter's survivors, as a ranked list for the fusion step
// (islands/search/fusion.ts) to read beside the BM25 leg's (islands/search/lexical.ts).
//
// The matrix is what `bench build --embed` writes (tools/build/embed.py, P6-S1-T03): vectors.i8.bin, rows x dims signed
// bytes, row-major, no header, row i being facets.json benchmarks[i]; and vectors.meta.json, whose `ids` repeat the
// facets.json order, whose `scales` hold one float32 scale a row, written as the shortest decimal that gives it back,
// and whose `vectors.bytes` is the file's length. One row per benchmark family, never per edition (11 S4).
//
// Dequantised once, at load (loadMatrix). 11 S4 and 08 S5.5: "quantise to int8 for transport, then dequantise once into
// a Float32Array at load", because a dot loop over the Int8Array was measured slower than over float32 (V8 does not
// auto-vectorise, and the int-to-float conversions cost more than they save). A coordinate is q x Math.fround(scale),
// the meta's own rule (`v[i][k] = q[i][k] * float32(scales[i])`): an int8 times a float32 is exact in a double (at most
// 7 + 24 significant bits), so the one rounding is the store into the Float32Array, which is what embed.py's float32
// multiply rounds too -- the matrix here is the one the build checked against its tolerance, bit for bit. The loader
// refuses rather than guesses: another artifact or format, a byte count, scale count or id count that disagrees with
// the row count, a scale that is not a positive finite number (embed.py writes none: a zero scale is a zero row, which
// it refuses), and, given the facets.json ids, a matrix built against another facets.json, whose rows would score the
// wrong benchmarks. Fetching the files, checking `vectors.sha256` and caching the result are the loader's
// (islands/search/loader.ts, P6-S1-T06); this module is handed the bytes.
//
// Each row's norm is computed once at load beside it. The build wrote unit rows, but quantisation moves a row's norm by
// up to about 1e-4 (embed.py: row fidelity 1 - cos <= 1e-3), so the score divides by both norms and is the cosine of the
// dequantised row, not a dot product that is almost one.
//
// The loop. No vector library and no index (11 S4 "Sizing": "a flat Float32Array and a hand-written dot-product loop
// answers a query in under a millisecond at our size", 0.61 ms measured at 1,500 x 256). dot() is that loop: one pass,
// coordinates in order, summed in a double, so a score is a pure function of the two vectors. The query is read as
// float32, the encoder's output type (islands/search/encoder.ts, P6-S1-T01, which this module does not need: the query
// vector is an input). A query of the wrong width is refused, because mixing two models' spaces "silently returns
// garbage rather than erroring" (11 S4); a zero query -- a text with no token in the encoder's vocabulary -- has no
// direction, and gives no list rather than a list of NaNs.
//
// The survivors. 08 S5.7 runs the facet filter first and the cosine "restricted to the survivors": only their rows are
// scored, and a row's score does not depend on which others survive. Rows are facets.json row numbers, the same in the
// facet bitsets (lib/facet-index.ts), the BM25 leg and this matrix, which is why loadMatrix checks the ids. The list is
// best first and equal scores go by row (lexical.ts byScore), so it is a pure function of the matrix, the query and the
// survivors; the fusion reads only the scores, and ranks equal ones alike.
import { members, wordsFor, type Bitset } from '../../lib/facet-index.ts';
import { byScore, type Ranked } from './lexical.ts';

/** The vectors.meta.json format this leg reads (tools/build/embed.py FORMAT). */
export const VECTORS_FORMAT = 1;

/** What the leg reads of vectors.meta.json (tools/build/embed.py build()). */
export interface VectorsMeta {
  artifact: string;
  format: number;
  rows: number;
  dims: number;
  ids: readonly string[];
  scales: readonly number[];
  vectors: { bytes: number; sha256?: string };
}

/** The document matrix, dequantised: row i's coordinates are data[i * dims .. (i + 1) * dims), and norms[i] its norm. */
export interface Matrix {
  rows: number;
  dims: number;
  ids: readonly string[];
  data: Float32Array;
  norms: Float64Array;
}

const bytesOf = (b: ArrayBuffer | ArrayBufferView): Int8Array =>
  (ArrayBuffer.isView(b) ? new Int8Array(b.buffer, b.byteOffset, b.byteLength) : new Int8Array(b));

/** vectors.i8.bin and vectors.meta.json as one matrix, dequantised once into a Float32Array (module docstring). Given
 *  `facetIds`, the ids of the loaded facets.json in its order, refuses a matrix built against any other. */
export function loadMatrix(meta: VectorsMeta, bin: ArrayBuffer | ArrayBufferView, facetIds?: readonly string[]): Matrix {
  if (meta.artifact !== 'vectors') throw new Error(`the meta is the ${String(meta.artifact)} artifact, not vectors`);
  if (meta.format !== VECTORS_FORMAT) throw new Error(`vectors.meta.json is format ${String(meta.format)}, and this leg reads format ${VECTORS_FORMAT}`);
  const { rows, dims, ids, scales } = meta;
  if (!Number.isInteger(rows) || rows < 0 || !Number.isInteger(dims) || dims <= 0) throw new Error(`a ${rows} x ${dims} matrix`);
  if (ids.length !== rows || scales.length !== rows) throw new Error(`${rows} rows, ${ids.length} ids, ${scales.length} scales`);
  const q = bytesOf(bin);
  if (q.length !== rows * dims || meta.vectors.bytes !== q.length) {
    throw new Error(`vectors.i8.bin is ${q.length} bytes; ${rows} x ${dims} is ${rows * dims} and the meta says ${meta.vectors.bytes}`);
  }
  if (facetIds != null && (facetIds.length !== rows || facetIds.some((id, i) => id !== ids[i]))) {
    throw new Error('the matrix was built against another facets.json: its ids are not the loaded rows in their order');
  }
  const data = new Float32Array(rows * dims);
  const norms = new Float64Array(rows);
  for (let i = 0; i < rows; i++) {
    const s = Math.fround(scales[i]);
    if (!(Number.isFinite(s) && s > 0)) throw new Error(`row ${i} (${ids[i]}) has the scale ${String(scales[i])}`);
    const base = i * dims;
    let squares = 0;
    for (let k = 0; k < dims; k++) {
      data[base + k] = q[base + k] * s;
      squares += data[base + k] * data[base + k];       // the stored float32, not the double that was assigned
    }
    norms[i] = Math.sqrt(squares);
  }
  return { rows, dims, ids, data, norms };
}

/** The hand-rolled loop: the dot product of a[offset .. offset + n) and b[0 .. n), coordinates in order, summed in a
 *  double. */
export function dot(a: Float32Array, offset: number, b: Float32Array, n: number): number {
  let s = 0;
  for (let k = 0; k < n; k++) s += a[offset + k] * b[k];
  return s;
}

/** The survivors' rows ranked by cosine similarity to `query`, best first, equal scores by row; every row when
 *  `survivors` is not given, and none for a zero query. Throws on a query whose width is not the matrix's, a coordinate
 *  that is not finite, or a survivor set over another number of rows. */
export function cosine(m: Matrix, query: ArrayLike<number>, survivors?: Bitset): Ranked[] {
  if (query.length !== m.dims) throw new Error(`the query has ${query.length} dimensions and the matrix ${m.dims}`);
  const q = Float32Array.from(query);
  if (!q.every(Number.isFinite)) throw new Error('the query has a coordinate that is not finite');
  const qn = Math.sqrt(dot(q, 0, q, m.dims));
  if (qn === 0) return [];
  let rows: number[];
  if (survivors == null) rows = Array.from({ length: m.rows }, (_, i) => i);
  else {
    if (survivors.length !== wordsFor(m.rows)) throw new Error(`a survivor set of ${survivors.length} words, over a matrix of ${m.rows} rows`);
    rows = members(survivors);
    if (rows.length > 0 && rows[rows.length - 1] >= m.rows) throw new Error(`survivor ${rows[rows.length - 1]} is past the matrix's ${m.rows} rows`);
  }
  return rows.map((row) => ({ row, score: dot(m.data, row * m.dims, q, m.dims) / (qn * m.norms[row]) })).sort(byScore);
}
