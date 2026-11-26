// site/src/islands/search/loader.ts -- P6-S1-T06 (11 S4 "First-query latency"; 08 S4.3 "Search (semantic, opt-in)",
// S5.5). The semantic tier's files, loaded off the critical path and cached in IndexedDB keyed on the index commit SHA.
// 11 S4: "The mitigation is therefore a loading policy, not an optimisation, and it is a commitment rather than an
// aspiration." This module is that policy, items 1 to 3; item 4, the budget lines, is P6-S1-T07's to measure.
//
// What it loads. The query encoder's four files in public/embed/ (tools/build/query_encoder.py; islands/search/encoder.ts
// says what each is): its meta first, then the tokenizer, the int8 matrix and, when the meta names one, the 2-bit
// residual. And the document vectors, vectors.meta.json and vectors.i8.bin, which `bench build --embed` writes beside
// the corpus (tools/build/embed.py) and the site publishes at /embed/ when the build has them (pages/embed/[file].ts,
// lib/vectors.ts, which also holds them to the facets.json beside them, since this page loads no facets.json). The
// search page says which builds did (pages/search.astro, data-vectors). A build without them -- the draft preview, whose
// scripts/preview_corpus.py runs no S6 -- still loads the encoder, so loading and caching are the same in every build;
// its stack's `vectors` is null and the tier has nothing to rank.
//
// When (11 S4 item 1: "after first paint and after Pagefind is interactive, inside a requestIdleCallback, never as part
// of page load"). startSemanticTier() waits for three things in turn: a painted frame (a task queued from a
// requestAnimationFrame callback runs after that frame); `after`, the search box's lexicalReady() (islands/SearchBox.tsx),
// which resolves once Pagefind has loaded and initialised, which the box does only when it takes focus or a query
// arrives in the link, so a visit that never uses the box fetches nothing; and an idle callback, with IDLE_TIMEOUT_MS
// as its deadline so a busy page still gets the tier. Safari has no requestIdleCallback; a 1 ms timeout stands in.
//
// It never blocks a keystroke (item 3). Nothing on the lexical path awaits it: the box asks Pagefind on every keystroke,
// and its LaterTier seam never awaits a tier; semanticStack() is for the semantic tier's own search() (P6-S1-T09) to
// await. And it yields: every step of the load is its own idle callback -- parsing the tokenizer, dequantising,
// building the encoder, the cache's read and write -- and the encoder matrix, ~3.8 million values and the one long
// step (11 S4 estimates 15-40 ms), is dequantised SLICE_ROWS rows at a time, yielding to the next idle callback whenever
// the current one's time is spent, so a key pressed mid-load waits on at most one slice.
//
// The cache (item 2: "cached in IndexedDB keyed on the index commit SHA, so it downloads once per build rather than once
// per visit, and a rebuild invalidates it correctly and automatically"). The key is the build's commit, release()'s
// commit_sha (lib/release.ts), the one every page footer prints and S13 holds equal to build-manifest.json's
// index_commit (tools/build/manifest.py); the search page passes it as data-index-commit, and anything but 40 lowercase
// hex digits is refused rather than used as a key. One database, DB_NAME, one store, DB_STORE, holding one record: the
// dequantised stack, as CachedStack -- the tokenizer's text (parsed again at each load, a step 11 S4 counts), the
// encoder meta and its Float32Array, and the document vectors as cosine.ts's Matrix, dequantised with their norms. A
// visit at the same commit reads it and fetches nothing. A visit at another commit finds no record, fetches every file
// again, and replaces the record: the store is cleared in the same transaction, so it never holds two builds' stacks,
// about 16 MB each, 15.2 MB of it the encoder matrix as float32. A record of another CACHE_FORMAT, or whose arrays do
// not match their metas, or that does not build an encoder, is a miss, never an error. Without IndexedDB (a private
// window, a full quota) the stack is fetched every visit and still served.
//
// Every file is checked before it is used or cached: its length and sha256 against what its meta records (the encoder
// meta's `files`; vectors.meta.json's `vectors`), so a partial download, a stale HTTP cache or a file of another build
// is refused rather than cached under this commit. That needs crypto.subtle, a secure context's (https, or localhost);
// elsewhere the tier fails rather than skip the check. The files are fetched with `cache: 'no-cache'`, so a changed
// commit revalidates each one with the server: a file the rebuild did not change comes back as a 304, not a download.
//
// A load that fails says so (state `failed`, and the reason) and is not retried on this page; nothing of it is cached,
// so the next visit tries again. The lexical results are untouched either way.
//
// The module imports nothing at load but types: the encoder (and with it @huggingface/tokenizers) and cosine.ts are
// dynamic imports made once the load starts, so none of it is on the page's critical path either. What this module does
// not do: encode a query or rank (encoder.ts, cosine.ts, fusion.ts), render the semantic block (P6-S1-T09), or measure
// the four cold-start numbers (P6-S1-T07).
import type { EncoderMeta, QueryEncoder } from './encoder.ts';
import type { Matrix, VectorsMeta } from './cosine.ts';

/** Where the site serves the tier's files: public/embed/, and the document vectors beside them (pages/embed/[file].ts). */
export const EMBED_URL = '/embed/';
/** The encoder's meta, which names the other three files with their lengths and sha256s (tools/build/query_encoder.py). */
export const ENCODER_META = 'potion-8m-pruned.meta.json';
/** The document vectors (tools/build/embed.py BIN, META). */
export const VECTORS_META = 'vectors.meta.json';
export const VECTORS_BIN = 'vectors.i8.bin';
/** The IndexedDB database and its one object store, whose one record is keyed on the index commit SHA. */
export const DB_NAME = 'uaibi-semantic-tier';
export const DB_STORE = 'stack';
/** CachedStack's layout. Changing the layout changes this, and every record of another format is a miss. */
export const CACHE_FORMAT = 1;
/** Encoder rows dequantised between two looks at the idle deadline: 131,072 values, about a millisecond. */
export const SLICE_ROWS = 512;
/** requestIdleCallback's timeout: how long a page that is never idle defers each step of the load. */
export const IDLE_TIMEOUT_MS = 2000;

const COMMIT = /^[0-9a-f]{40}$/;

/** What the page tells the loader (pages/search.astro, on its [data-semantic-tier] element). */
export interface SemanticConfig {
  commit: string;              // the index commit SHA: the cache key
  vectors: boolean;            // whether this build ships the document vectors
  base?: string;               // EMBED_URL unless given
}

/** waiting: started, not yet past first paint, Pagefind and an idle callback. loading: reading the cache or the network. */
export type SemanticState = 'waiting' | 'loading' | 'ready' | 'failed';

/** The loaded tier: the query encoder, and the document vectors when the build shipped them. */
export interface SemanticStack {
  commit: string;
  source: 'network' | 'cache';
  encoder: QueryEncoder;
  vectors: Matrix | null;
}

/** The IndexedDB record: the dequantised stack at one commit. */
export interface CachedStack {
  format: number;
  commit: string;
  tokenizer: string;                                          // tokenizer.json's text
  encoder: { meta: EncoderMeta; matrix: Float32Array };       // the matrix dequantised (encoder.ts dequantise)
  vectors: Matrix | null;                                     // dequantised, with the norms (cosine.ts loadMatrix)
}

/** Where the stack is cached: get() a record by commit, put() one in place of every other. */
export interface StackStore {
  get(commit: string): Promise<unknown>;
  put(record: CachedStack): Promise<void>;
}

/** What an idle callback is handed: how long it may run. */
export interface Deadline {
  timeRemaining(): number;
}

/** What the load needs from its host: the browser's in browserDeps(), a test's in test/semantic-loader.test.mjs. */
export interface LoaderDeps {
  fetch: (url: string, init?: RequestInit) => Promise<Response>;
  store: StackStore | null;                                   // null: no cache, fetch every visit
  idle: () => Promise<Deadline>;
  sha256: (bytes: Uint8Array) => Promise<string>;             // lowercase hex
}

/** A file as a meta records it: the encoder meta's `files` entries; vectors.meta.json's `vectors`. */
interface FileRecord {
  file?: string;
  bytes: number;
  sha256?: string;
}

/** The encoder meta's `files` block (tools/build/query_encoder.py), which EncoderMeta does not declare. */
interface EncoderFiles {
  tokenizer: FileRecord;
  matrix: FileRecord;
  residual?: FileRecord;
}

const reason = (e: unknown) => (e instanceof Error ? e.message : String(e));

// ---- the load -----------------------------------------------------------------------------------------------

/** The stack for `config`: from `deps.store` when it holds a valid record at this commit, else from the network, checked
 *  file by file, dequantised and then cached. Throws when the commit is not a commit SHA or a file fails its check. */
export async function loadStack(config: SemanticConfig, deps: LoaderDeps): Promise<SemanticStack> {
  if (!COMMIT.test(config.commit)) throw new Error(`no index commit to key the cache on (got ${JSON.stringify(config.commit)})`);
  const enc = await import('./encoder.ts');

  // a visit at the same commit: the cached stack, and no fetch
  let raw: unknown = null;
  if (deps.store != null) {
    await deps.idle();
    raw = await deps.store.get(config.commit).catch(() => null);
  }
  const hit = cachedRecord(raw, config);
  if (hit != null) {
    try {
      await deps.idle();
      const tokenizer = JSON.parse(hit.tokenizer) as object;
      await deps.idle();
      const encoder = new enc.QueryEncoder(tokenizer, hit.encoder.meta, hit.encoder.matrix);
      return { commit: config.commit, source: 'cache', encoder, vectors: hit.vectors };
    } catch {
      // a record that does not build an encoder is a miss: fetched again, and replaced below
    }
  }

  // the network: the encoder meta, then every file it names and the vectors, each checked before it is used
  const base = config.base ?? EMBED_URL;
  const get = async (name: string): Promise<Response> => {
    const res = await deps.fetch(base + name, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`);
    return res;
  };
  const bytesOf = async (name: string, rec: FileRecord): Promise<Uint8Array> => {
    const b = new Uint8Array(await (await get(name)).arrayBuffer());
    if (b.byteLength !== rec.bytes) throw new Error(`${name} is ${b.byteLength} bytes, and its meta says ${rec.bytes}`);
    if (rec.sha256 != null) {
      const got = await deps.sha256(b);
      if (got !== rec.sha256) throw new Error(`${name} has the sha256 ${got}, and its meta says ${rec.sha256}`);
    }
    return b;
  };
  const meta = (await (await get(ENCODER_META)).json()) as EncoderMeta & { files?: EncoderFiles };
  if (meta.artifact !== 'query-encoder' || meta.format !== enc.ENCODER_FORMAT || meta.files == null) {
    throw new Error(`${ENCODER_META} is not a query-encoder meta of format ${enc.ENCODER_FORMAT}`);
  }
  const { files } = meta;
  const named = (r: FileRecord | undefined, what: string): FileRecord & { file: string } => {
    if (r == null || typeof r.file !== 'string' || !/^[\w.-]+$/.test(r.file)) throw new Error(`${ENCODER_META} names no ${what} file`);
    return r as FileRecord & { file: string };
  };
  const tokenizerFile = named(files.tokenizer, 'tokenizer');
  const matrixFile = named(files.matrix, 'matrix');
  const residualFile = files.residual == null ? null : named(files.residual, 'residual');
  const vectorsLoad = config.vectors
    ? get(VECTORS_META).then(async (res) => {
        const vmeta = (await res.json()) as VectorsMeta;
        if (vmeta.vectors == null) throw new Error(`${VECTORS_META} records no vectors file`);
        return { vmeta, bin: await bytesOf(VECTORS_BIN, vmeta.vectors) };
      })
    : Promise.resolve(null);
  const [tokenizerBytes, i8, r2, vectorsFiles] = await Promise.all([
    bytesOf(tokenizerFile.file, tokenizerFile),
    bytesOf(matrixFile.file, matrixFile),
    residualFile == null ? Promise.resolve(null) : bytesOf(residualFile.file, residualFile),
    vectorsLoad,
  ]);

  await deps.idle();
  const tokenizerText = new TextDecoder().decode(tokenizerBytes);
  const tokenizer = JSON.parse(tokenizerText) as object;
  const matrix = await dequantiseSliced(enc.dequantise, meta, i8, r2, deps.idle);
  let vectors: Matrix | null = null;
  if (vectorsFiles != null) {
    await deps.idle();
    vectors = (await import('./cosine.ts')).loadMatrix(vectorsFiles.vmeta, vectorsFiles.bin);
  }
  await deps.idle();
  const encoder = new enc.QueryEncoder(tokenizer, meta, matrix);

  // cached only once it has built an encoder; a store that cannot take it leaves the stack served, uncached
  if (deps.store != null) {
    await deps.idle();
    const record: CachedStack = { format: CACHE_FORMAT, commit: config.commit, tokenizer: tokenizerText, encoder: { meta, matrix }, vectors };
    await deps.store.put(record).catch(() => undefined);
  }
  return { commit: config.commit, source: 'network', encoder, vectors };
}

/** `raw` as a record of this commit and format whose arrays match their metas, or null: anything else is a miss. */
export function cachedRecord(raw: unknown, config: SemanticConfig): CachedStack | null {
  if (raw == null || typeof raw !== 'object') return null;
  const r = raw as Partial<CachedStack>;
  if (r.format !== CACHE_FORMAT || r.commit !== config.commit || typeof r.tokenizer !== 'string') return null;
  const e = r.encoder;
  if (e == null || e.meta == null || !(e.matrix instanceof Float32Array) || e.matrix.length !== e.meta.rows * e.meta.dims) return null;
  const v = r.vectors;
  if (v === undefined || (v === null) === config.vectors) return null;      // a build with vectors has a record with them
  if (v != null && !(v.data instanceof Float32Array && v.norms instanceof Float64Array && Array.isArray(v.ids)
    && v.ids.length === v.rows && v.norms.length === v.rows && v.data.length === v.rows * v.dims)) return null;
  return r as CachedStack;
}

/** encoder.ts dequantise() over the whole matrix, SLICE_ROWS rows at a time, yielding to `idle` whenever the current
 *  deadline is spent: the same values as one call, since each row's are computed from that row alone. */
export async function dequantiseSliced(
  dequantise: (meta: EncoderMeta, i8: Uint8Array, r2?: Uint8Array) => Float32Array,
  meta: EncoderMeta, i8: Uint8Array, r2: Uint8Array | null, idle: () => Promise<Deadline>,
): Promise<Float32Array> {
  const { rows, dims } = meta;
  if (dims % 4 !== 0 || i8.byteLength !== rows * dims) return dequantise(meta, i8, r2 ?? undefined);   // let it refuse
  const out = new Float32Array(rows * dims);
  let deadline = await idle();
  for (let a = 0; a < rows; a += SLICE_ROWS) {
    const b = Math.min(rows, a + SLICE_ROWS);
    const part = { ...meta, rows: b - a, scales: meta.scales.slice(a, b) };
    out.set(dequantise(part, i8.subarray(a * dims, b * dims), r2?.subarray((a * dims) / 4, (b * dims) / 4)), a * dims);
    if (b < rows && deadline.timeRemaining() < 1) deadline = await idle();
  }
  return out;
}

// ---- the browser: IndexedDB, idle callbacks, the schedule ----------------------------------------------------

/** The IndexedDB store: database DB_NAME, store DB_STORE, out-of-line keys (the commit). put() clears the store and adds
 *  the record in one transaction, so it holds one build's stack at most. */
export function idbStore(name: string = DB_NAME): StackStore {
  const open = () => new Promise<IDBDatabase>((resolve, reject) => {
    const req = indexedDB.open(name, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(DB_STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error(`IndexedDB would not open ${name}`));
    req.onblocked = () => reject(new Error(`IndexedDB ${name} is held open by another tab at an older version`));
  });
  const run = async <T>(mode: IDBTransactionMode, body: (s: IDBObjectStore) => IDBRequest<T> | null): Promise<T | undefined> => {
    const db = await open();
    try {
      return await new Promise<T | undefined>((resolve, reject) => {
        const tx = db.transaction(DB_STORE, mode);
        const req = body(tx.objectStore(DB_STORE));
        tx.oncomplete = () => resolve(req?.result);
        tx.onerror = () => reject(tx.error ?? new Error('IndexedDB transaction failed'));
        tx.onabort = () => reject(tx.error ?? new Error('IndexedDB transaction aborted'));
      });
    } finally {
      db.close();
    }
  };
  return {
    get: (commit) => run('readonly', (s) => s.get(commit)),
    put: async (record) => {
      await run('readwrite', (s) => {
        s.clear();
        s.put(record, record.commit);
        return null;
      });
    },
  };
}

/** The next idle callback, or a 1 ms timeout where there is none (Safari), with an 8 ms budget. */
export function idleCallback(): Promise<Deadline> {
  return new Promise((resolve) => {
    if (typeof requestIdleCallback === 'function') requestIdleCallback(resolve, { timeout: IDLE_TIMEOUT_MS });
    else {
      const end = performance.now() + 9;
      setTimeout(() => resolve({ timeRemaining: () => Math.max(0, end - performance.now()) }), 1);
    }
  });
}

/** The browser's: fetch, IndexedDB when there is one, idle callbacks, and crypto.subtle's SHA-256. */
export function browserDeps(): LoaderDeps {
  let store: StackStore | null = null;
  try {
    if (typeof indexedDB !== 'undefined') store = idbStore();
  } catch {
    store = null;
  }
  return {
    fetch: (url, init) => fetch(url, init),
    store,
    idle: idleCallback,
    sha256: async (bytes) => {
      if (globalThis.crypto?.subtle == null) throw new Error('no crypto.subtle to check the files with: the tier needs a secure context');
      const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes as Uint8Array<ArrayBuffer>));
      return Array.from(digest, (b) => b.toString(16).padStart(2, '0')).join('');
    },
  };
}

/** Resolves after a frame has been painted: a task queued from a requestAnimationFrame callback runs after its frame. */
const painted = () => new Promise<void>((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0)));

let started: Promise<SemanticStack> | null = null;

/** Starts the tier once per page: after first paint, after `after` (the box's lexicalReady()), in an idle callback.
 *  `onState` hears every state, with the stack once ready and the error if it fails. A later call returns the first
 *  call's promise. */
export function startSemanticTier(
  config: SemanticConfig,
  after: Promise<unknown>,
  onState: (state: SemanticState, detail?: SemanticStack | Error) => void = () => undefined,
  deps: LoaderDeps = browserDeps(),
): Promise<SemanticStack> {
  if (started != null) return started;
  onState('waiting');
  const load = (async () => {
    await painted();
    await after;
    await deps.idle();
    onState('loading');
    return loadStack(config, deps);
  })();
  started = load;
  load.then((s) => onState('ready', s), (e: unknown) => onState('failed', e instanceof Error ? e : new Error(reason(e))));
  return load;
}

/** The tier, once started: the promise its search() awaits (P6-S1-T09). null on a page that has not started it. */
export const semanticStack = (): Promise<SemanticStack> | null => started;

/** Starts the tier from the page's [data-semantic-tier] element (pages/search.astro), which carries the config as
 *  data-index-commit and data-vectors, and mirrors the state onto it: data-state, data-source once ready, and
 *  data-failure, the reason, if it fails. */
export function mountSemanticTier(el: HTMLElement, after: Promise<unknown>): Promise<SemanticStack> {
  const config: SemanticConfig = { commit: el.dataset.indexCommit ?? '', vectors: el.dataset.vectors === 'shipped' };
  return startSemanticTier(config, after, (state, detail) => {
    el.dataset.state = state;
    if (state === 'ready' && detail != null && !(detail instanceof Error)) el.dataset.source = detail.source;
    if (state === 'failed' && detail instanceof Error) el.dataset.failure = detail.message;
  });
}
