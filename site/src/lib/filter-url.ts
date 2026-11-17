// site/src/lib/filter-url.ts -- P2-S4-T03 (10 "Filter state encoding"). The browse filter's state in the query string,
// canonically ordered "so that one selection always produces exactly one URL": shareable links deduplicate, the
// AI layer's cache can key on the URL, and a URL in a paper resolves to the same view a year later.
//
//   keys sorted alphabetically; values sorted within each key; values comma-joined; an omitted key is no constraint;
//   v=1 is the filter-grammar version. There is no key for the presentation group: it is display-only and orders and
//   bands views, and a user filters by family through `d`. Adding a group key requires an ADR.
//
// Unknown keys are ignored rather than erroring; unknown values are dropped from the state and returned as
// `ignored`, which the view renders as a visible "ignored filter: c=nonexistent-term" notice. "Silent ignoring is how
// a shared link quietly shows the wrong thing." The module is pure: the vocabularies come in as an argument, so the
// browse view passes the terms it filters on and the tests pass their own.

/** The filter-grammar version every canonical URL carries. */
export const GRAMMAR_VERSION = '1';

/** Term-list keys: each value must be a term of the key's vocabulary (10's table). */
export const TERM_KEYS = {
  acc: 'access',
  b: 'basket',
  c: 'capability',
  ct: 'compute_tier',
  d: 'domain',
  em: 'evaluation_method',
  lc: 'lifecycle',
  mt: 'maintainer_type',
  rt: 'reproducibility_tier',
  s: 'subject_under_test',
  sp: 'submission_process',
} as const;

/** Range keys, `min-max`: headroom in [0, 1] and release year. */
export const RANGE_KEYS = { hr: 'headroom', yr: 'release year' } as const;

/** Single-valued keys: the free-text query, the sort key and the verification threshold. */
export const SINGLE_KEYS = { q: 'free-text query', sort: 'sort key', ver: 'verification threshold' } as const;

export type TermKey = keyof typeof TERM_KEYS;
export type RangeKey = keyof typeof RANGE_KEYS;
export type SingleKey = keyof typeof SINGLE_KEYS;
export type FilterKey = TermKey | RangeKey | SingleKey;

/** A selection. An absent or empty key is no constraint. */
export type FilterState = Partial<Record<TermKey, string[]> & Record<RangeKey, string> & Record<SingleKey, string>>;

/** The allowed values per key that has a closed vocabulary; a key absent here is not checked (q, b). */
export type Vocabularies = Partial<Record<TermKey | 'sort' | 'ver', ReadonlySet<string>>>;

export interface Ignored { key: string; value: string }

export interface Decoded { state: FilterState; ignored: Ignored[]; version: string | null }

export const KEYS: readonly FilterKey[] = [
  ...(Object.keys(TERM_KEYS) as TermKey[]),
  ...(Object.keys(RANGE_KEYS) as RangeKey[]),
  ...(Object.keys(SINGLE_KEYS) as SingleKey[]),
].sort();

const isTermKey = (k: string): k is TermKey => Object.prototype.hasOwnProperty.call(TERM_KEYS, k);
const isRangeKey = (k: string): k is RangeKey => Object.prototype.hasOwnProperty.call(RANGE_KEYS, k);
const isSingleKey = (k: string): k is SingleKey => Object.prototype.hasOwnProperty.call(SINGLE_KEYS, k);

// One encoding for every value, so a value is written one way only. The comma is the separator of a term list, so a
// term that held one would be split on the way back; a closed vocabulary has none, and the free-text query is a single
// value, encoded whole.
const enc = (value: string) => encodeURIComponent(value);
const dec = (value: string) => {
  try {
    return decodeURIComponent(value.replace(/\+/g, ' '));
  } catch {
    return null;
  }
};
// Code-point order, not the locale's: canonical form must not depend on who builds the URL.
const byCodePoint = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

const RANGE = /^(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)$/;
// A headroom bound keeps one decimal at least (10's example writes hr=0.0-0.8) and never loses a digit it was given.
const fraction = (n: number) => (Number.isInteger(n * 10) ? n.toFixed(1) : String(n));

/** A range value in canonical form, or null when it is not `min-max` with min <= max inside the key's bounds. */
export function canonicalRange(key: RangeKey, value: string): string | null {
  const m = RANGE.exec(value.trim());
  if (!m) return null;
  const [lo, hi] = [Number(m[1]), Number(m[2])];
  if (!(lo <= hi)) return null;
  if (key === 'hr') return lo >= 0 && hi <= 1 ? `${fraction(lo)}-${fraction(hi)}` : null;
  return Number.isInteger(lo) && Number.isInteger(hi) ? `${lo}-${hi}` : null;
}

/** The canonical query string for a selection, without the leading `?`: one selection, one string. */
export function encode(state: FilterState): string {
  const parts: string[] = [];
  for (const key of KEYS) {
    const raw = state[key];
    if (raw == null) continue;
    if (isTermKey(key)) {
      const values = [...new Set((raw as string[]).map((v) => v.trim()).filter(Boolean))].sort(byCodePoint);
      if (values.length) parts.push(`${key}=${values.map(enc).join(',')}`);
    } else if (isRangeKey(key)) {
      const r = canonicalRange(key, raw as string);
      if (r) parts.push(`${key}=${r}`);
    } else {
      const v = (raw as string).trim().replace(/\s+/g, ' ');
      if (v) parts.push(`${key}=${enc(v)}`);
    }
  }
  return parts.length ? [...parts, `v=${GRAMMAR_VERSION}`].join('&') : '';
}

/** A query string (with or without `?`) to a selection, the values it ignored, and the grammar version it carried. */
export function decode(query: string, vocab: Vocabularies = {}): Decoded {
  const state: FilterState = {};
  const ignored: Ignored[] = [];
  let version: string | null = null;
  for (const pair of query.replace(/^\?/, '').split('&')) {
    if (!pair) continue;
    const eq = pair.indexOf('=');
    const key = dec(eq < 0 ? pair : pair.slice(0, eq));
    const rawValue = eq < 0 ? '' : pair.slice(eq + 1);
    if (key == null) continue;
    if (key === 'v') {
      version = dec(rawValue);
      continue;
    }
    if (isTermKey(key)) {
      const allowed = vocab[key];
      const kept = new Set(state[key] ?? []);
      for (const part of rawValue.split(',')) {
        const value = dec(part)?.trim();
        if (!value) continue;
        if (allowed && !allowed.has(value)) ignored.push({ key, value });
        else kept.add(value);
      }
      if (kept.size) state[key] = [...kept].sort(byCodePoint);
    } else if (isRangeKey(key)) {
      const value = dec(rawValue)?.trim() ?? '';
      const r = canonicalRange(key, value);
      if (r) state[key] = r;
      else if (value) ignored.push({ key, value });
    } else if (isSingleKey(key)) {
      const value = dec(rawValue)?.trim().replace(/\s+/g, ' ') ?? '';
      const allowed = key === 'q' ? undefined : vocab[key];
      if (!value) continue;
      if (allowed && !allowed.has(value)) ignored.push({ key, value });
      else state[key] = value;
    }
    // any other key is ignored, as 10 "Filter state encoding" says: a later grammar may add keys
  }
  return { state, ignored, version };
}

/** The canonical form of any query string: decode, then encode. Idempotent. */
export function canonicalise(query: string, vocab: Vocabularies = {}): string {
  return encode(decode(query, vocab).state);
}

/** The visible notice for an ignored value, in 10's words. */
export function ignoredNotice(i: Ignored): string {
  return `ignored filter: ${i.key}=${i.value}`;
}
