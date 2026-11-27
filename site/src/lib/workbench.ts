// site/src/lib/workbench.ts -- P3-S10-T05 (10 V5; 10 "Filter state encoding"; 08 S3.2 S5, S4.3; 04 S8). The Comparison
// Workbench's selection and the table it gives, pure and DOM-free: components/Workbench.astro renders a view at build
// time, islands/workbench/client.ts renders one in the browser from the address, and test/workbench.test.mjs drives it
// under Node, which loads it as it is, stripping the types.
//
// The selection is 10 V5's "user-assembled N systems x M benchmarks grid", in the query string in 10's canonical form
// (keys sorted, values sorted within a key and comma-joined, an omitted key no constraint, v=1 the grammar version), so
// one selection always produces exactly one URL:
//
//   /compare/?b=mmlu,swe-bench-verified&sys=gpt-5,o3&v=1
//
//   b     benchmark ids: the grammar's basket key, the same benchmark-id list the Suite Builder's basket writes, so a
//         basket opens here as a selection of benchmarks
//   sys   system ids, the other axis. The grammar had no key for systems; this is the one it gains, a term list like b
//   k     comparability keys a restriction keeps: in each column holding claims under one of them, only those claims
//         are shown and the rest are counted as dropped, never silently (10 V5's "Restrict to group A -- drops 14 of 31
//         claims"). A key names its column, since it hashes the benchmark version and the metric (04 S8)
//   ids   the pasted list (10 V5: "or a pasted list of IDs"): benchmark, system and claim ids, separated by spaces,
//         commas, semicolons or new lines, read once and replaced by the b and sys they resolve to (a claim adds its
//         system and its benchmark). It is what the paste form sends; it is never part of a canonical URL
//
// The bare /compare/ constrains nothing, so it is every curated claim: the one selection the build renders, and the page
// as it reads without JavaScript. An id the address names that the build does not have is the grammar's unknown value:
// left out of the selection and returned as `ignored`, which the page shows ("silent ignoring is how a shared link
// quietly shows the wrong thing"); an unknown key is ignored, as 10 says.
//
// The table: one row per system, one column per (benchmark family, metric), the grouping comparability is decided in
// (tools/build/comparability.py `pairwise`), and in each cell the claims of that system in that column. Each column's
// state, condition sets, diff and restriction count come from lib/comparability.ts's compare() over the claims the
// selection keeps, with derived/comparability.json's group cut to the pairs among them (`subgroup`): the build computed
// every pair, so a selection's diff is a subset of the build's rows and nothing is decided here that compare() does not
// decide (08 S3.2 S5: "The UI never computes a comparability verdict at runtime"). A selected benchmark or system with
// no curated claim is a column or row of absent cells, drawn rather than omitted (10 Design stance, rule 3).
//
// P3-S10-T06: each column's categorical refusals (10 V5's six, lib/refusals.ts), decided over the same kept claims,
// from the index's benchmark and metric records (`facts`). A refused column is cut into parts, each drawn as a column of
// its own under one header (`parts`): the comparability key's state stays what compare() says, and a refusal is read
// beside it, never folded into it, since the refusals are 10's "beyond the generic key".
import { compare, family, groupKey, utf8, type Comparison, type DiffGroup } from './comparability.ts';
import { NO_FACTS, refuse, type ColumnRefusal, type Facts } from './refusals.ts';
import type { ClaimRow } from './claims';

/** The workbench's route (10 "Information architecture": /compare/ is V5). */
export const COMPARE_PATH = '/compare/';
/** The filter-grammar version every canonical URL carries (lib/filter-url.ts GRAMMAR_VERSION). */
export const GRAMMAR_VERSION = '1';
export const KEYS = ['b', 'k', 'sys'] as const;
export type Key = (typeof KEYS)[number];

export type Selection = Record<Key, string[]>;
export const EMPTY: Selection = { b: [], k: [], sys: [] };

export interface Ignored { key: string; value: string; why: string }

/** A system id without its version or variant: the row a claim is drawn in (lib/claims.ts baseId). */
export const systemOf = (ref: string) => ref.split('@', 1)[0].split('#', 1)[0];
const sorted = (xs: Iterable<string>) => [...new Set([...xs].map((x) => x.trim()).filter(Boolean))].sort(utf8);

/** The selection in canonical form: each key's values sorted, each once. */
export const canonical = (s: Partial<Selection>): Selection => ({ b: sorted(s.b ?? []), k: sorted(s.k ?? []), sys: sorted(s.sys ?? []) });
/** Whether a selection constrains anything: the bare URL is the whole index. */
export const constrains = (s: Selection) => KEYS.some((k) => s[k].length > 0);

/** The canonical query string, without the `?`; empty for the selection that constrains nothing. */
export function encode(s: Partial<Selection>): string {
  const c = canonical(s);
  const parts = KEYS.filter((k) => c[k].length > 0).map((k) => `${k}=${c[k].map(encodeURIComponent).join(',')}`);
  return parts.length > 0 ? [...parts, `v=${GRAMMAR_VERSION}`].join('&') : '';
}
/** The link to a selection. */
export function compareHref(s: Partial<Selection>): string {
  const q = encode(s);
  return q.length > 0 ? `${COMPARE_PATH}?${q}` : COMPARE_PATH;
}

const dec = (v: string) => {
  try {
    return decodeURIComponent(v.replace(/\+/g, ' '));
  } catch {
    return null;
  }
};

/** A query string as it was written: each key's values, the pasted ids, the grammar version, before any is checked. */
export interface Query { b: string[]; k: string[]; sys: string[]; ids: string[]; version: string | null }

export function readQuery(search: string): Query {
  const q: Query = { b: [], k: [], sys: [], ids: [], version: null };
  for (const pair of search.replace(/^\?/, '').split('&')) {
    if (!pair) continue;
    const eq = pair.indexOf('=');
    const key = dec(eq < 0 ? pair : pair.slice(0, eq));
    const raw = eq < 0 ? '' : pair.slice(eq + 1);
    if (key === 'v') q.version = dec(raw);
    else if (key === 'ids') q.ids.push(...(dec(raw) ?? '').split(/[\s,;]+/).filter(Boolean));
    else if (key === 'b' || key === 'k' || key === 'sys') {
      for (const part of raw.split(',')) {
        const v = dec(part)?.trim();
        if (v) q[key].push(v);
      }
    }
    // any other key is ignored (10 "Filter state encoding": a later grammar may add keys)
  }
  return q;
}

/** What a selection is checked against: every benchmark and system the build publishes, by id with its name, and
 *  claims.json's rows. The server passes the content collections; the browser, corpus.json's entities. */
export interface Index {
  benchmarks: Map<string, string>;
  systems: Map<string, string>;
  metrics: Map<string, string>;
  rows: ClaimRow[];
  facts?: Facts;                      // the benchmark and metric records the refusals read (P3-S10-T06); none when omitted
}

/** The selection a query names, in canonical form, and every value it names that this build does not have. */
export function resolve(q: Query, index: Index): { selection: Selection; ignored: Ignored[] } {
  const claimed = { b: new Set(index.rows.map((r) => family(r.claim.benchmark))), sys: new Set(index.rows.map((r) => systemOf(r.claim.system))) };
  const isBench = (id: string) => index.benchmarks.has(id) || claimed.b.has(id);
  const isSystem = (id: string) => index.systems.has(id) || claimed.sys.has(id);
  const keys = new Set(index.rows.map((r) => r.comparability.comparability_key));
  const claims = new Map(index.rows.map((r) => [r.claim.id, r]));
  const out: Selection = { b: [], k: [], sys: [] };
  const ignored: Ignored[] = [];
  for (const v of q.b) (isBench(family(v)) ? out.b.push(family(v)) : ignored.push({ key: 'b', value: v, why: 'no benchmark has this id in this build' }));
  for (const v of q.sys) (isSystem(systemOf(v)) ? out.sys.push(systemOf(v)) : ignored.push({ key: 'sys', value: v, why: 'no system has this id in this build' }));
  for (const v of q.k) (keys.has(v) ? out.k.push(v) : ignored.push({ key: 'k', value: v, why: 'no curated claim in this build has this comparability key' }));
  for (const v of q.ids) {
    const c = claims.get(v);
    if (c != null) {
      out.b.push(family(c.claim.benchmark));
      out.sys.push(systemOf(c.claim.system));
    } else if (isBench(family(v))) out.b.push(family(v));
    else if (isSystem(systemOf(v))) out.sys.push(systemOf(v));
    else ignored.push({ key: 'ids', value: v, why: 'not a benchmark, system or curated claim id in this build' });
  }
  if (q.version != null && q.version !== GRAMMAR_VERSION) {
    ignored.push({ key: 'v', value: q.version, why: `this page reads version ${GRAMMAR_VERSION} of the grammar` });
  }
  return { selection: canonical(out), ignored };
}

// ---- the table ------------------------------------------------------------------------------------------------------

/** A group of derived/comparability.json cut to `kept`, some of its claims: their count, their keys and the build's rows
 *  for the pairs among them. A deferred group stays deferred: the build computed no pair of it to cut. */
export function subgroup(g: DiffGroup, kept: ClaimRow[]): DiffGroup {
  const ids = new Set(kept.map((r) => r.claim.id));
  const per = new Map<string, number>();
  for (const r of kept) per.set(r.comparability.comparability_key, (per.get(r.comparability.comparability_key) ?? 0) + 1);
  const n = kept.length;
  const pairs = (n * (n - 1)) / 2 - [...per.values()].reduce((a, k) => a + (k * (k - 1)) / 2, 0);
  return { ...g, claims: n, keys: per.size, pairs, rows: g.rows == null ? null : g.rows.filter((d) => ids.has(d.a) && ids.has(d.b)) };
}

export interface Column {
  id: string;                         // `${benchmark}|${metric}`, or `${benchmark}|` for a benchmark with no claim
  benchmark: string;                  // the family id
  metric: string | null;              // null: a selected benchmark with no curated claim
  comparison: Comparison | null;      // over the claims the selection keeps; null with no claim
  whole: number;                      // the claims the build's group holds, whatever the selection
  restricted: string[];               // the `k` keys restricting this column
  dropped: ClaimRow[];                // the claims the restriction takes out, counted on the page
  setOf: Map<string, string>;         // claim id -> its condition set's label
  refusal: ColumnRefusal | null;      // its categorical refusals over the claims kept, null when none fires (P3-S10-T06)
}
export interface Row { system: string; spans: number }   // spans: columns where its claims are one of several sets
export interface View {
  selection: Selection;
  rows: Row[];
  columns: Column[];
  cells: Map<string, ClaimRow[]>;     // cellKey(column, system) -> its claims, by set label then claim id
  claims: number;                     // in the table
  dropped: number;                    // taken out by the restriction
}

export const cellKey = (column: string, system: string) => `${column}\u0000${system}`;
export const columnId = (benchmark: string, metric: string | null) => `${benchmark}|${metric ?? ''}`;
const byName = (names: Map<string, string>) => (a: string, b: string) =>
  utf8((names.get(a) ?? a).toLowerCase(), (names.get(b) ?? b).toLowerCase()) || utf8(a, b);

/** The table a selection gives over claims.json's rows and derived/comparability.json's groups. Every claim the selection
 *  keeps is in exactly one cell, and every claim a restriction takes out is in its column's `dropped`. */
export function view(index: Index, groups: Map<string, DiffGroup> | null, selection: Selection): View {
  const s = canonical(selection);
  const inB = (b: string) => s.b.length === 0 || s.b.includes(b);
  const inS = (x: string) => s.sys.length === 0 || s.sys.includes(x);
  const whole = new Map<string, ClaimRow[]>();
  for (const r of index.rows) {
    const k = groupKey(family(r.claim.benchmark), r.claim.metric);
    whole.set(k, [...(whole.get(k) ?? []), r]);
  }
  const columns: Column[] = [];
  const cells = new Map<string, ClaimRow[]>();
  const systems = new Set(s.sys);
  for (const [k, all] of whole) {
    const benchmark = family(all[0].claim.benchmark);
    const metric = all[0].claim.metric;
    const picked = all.filter((r) => inB(benchmark) && inS(systemOf(r.claim.system)));
    if (picked.length === 0) continue;
    const g = groups?.get(k);
    compare(all, g);                  // the build's group holds exactly these claims, or this throws: not one build's
    const restricted = [...new Set(picked.map((r) => r.comparability.comparability_key))].filter((key) => s.k.includes(key)).sort(utf8);
    const kept = restricted.length > 0 ? picked.filter((r) => restricted.includes(r.comparability.comparability_key)) : picked;
    const comparison = compare(kept, subgroup(g!, kept));
    const id = columnId(benchmark, metric);
    const setOf = new Map(comparison.sets.flatMap((set) => set.rows.map((r) => [r.claim.id, set.label] as const)));
    columns.push({ id, benchmark, metric, comparison, whole: all.length, restricted, dropped: picked.filter((r) => !kept.includes(r)), setOf,
      refusal: refuse(kept, index.facts ?? NO_FACTS) });
    for (const r of picked) systems.add(systemOf(r.claim.system));
    for (const r of kept) {
      const ck = cellKey(id, systemOf(r.claim.system));
      cells.set(ck, [...(cells.get(ck) ?? []), r]);
    }
  }
  for (const b of s.b) {
    if (!columns.some((c) => c.benchmark === b)) {
      columns.push({ id: columnId(b, null), benchmark: b, metric: null, comparison: null, whole: 0, restricted: [], dropped: [], setOf: new Map(), refusal: null });
    }
  }
  const bench = byName(index.benchmarks);
  columns.sort((a, b) => bench(a.benchmark, b.benchmark) || utf8(a.metric ?? '', b.metric ?? ''));
  for (const c of columns) {
    for (const sys of systems) {
      const list = cells.get(cellKey(c.id, sys));
      if (list != null) list.sort((x, y) => utf8(c.setOf.get(x.claim.id)!, c.setOf.get(y.claim.id)!) || utf8(x.claim.id, y.claim.id));
    }
  }
  const rows = [...systems].sort(byName(index.systems)).map((system) => ({
    system,
    spans: columns.filter((c) => c.comparison?.state === 'not-comparable' && cells.has(cellKey(c.id, system))).length,
  }));
  return {
    selection: s, rows, columns, cells,
    claims: columns.reduce((n, c) => n + (c.comparison?.total ?? 0), 0),
    dropped: columns.reduce((n, c) => n + c.dropped.length, 0),
  };
}

/** A cell's claims as the table draws them: one list per part of a refused column, in part order, or the one list. */
export function cellParts(c: Column, list: ClaimRow[]): ClaimRow[][] {
  if (c.refusal == null) return [list];
  return c.refusal.parts.map((p) => list.filter((r) => c.refusal!.partOf.get(r.claim.id) === p.id));
}

/** The selection restricted to the condition set `key` in its column: what a banner's restrict control links to. */
export const restrictTo = (s: Selection, key: string): Selection => canonical({ ...s, k: [...s.k, key] });
/** The selection with column `c`'s restriction lifted: every claim it dropped back in its cell. */
export const unrestrict = (s: Selection, c: Column): Selection => canonical({ ...s, k: s.k.filter((k) => !c.restricted.includes(k)) });
/** A selection as the paste box shows it: its benchmark and system ids, one list. */
export const pasted = (s: Selection) => [...s.b, ...s.sys].join(' ');

// ---- the words, one set for the build's render and the browser's -----------------------------------------------------

export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
/** An id fit for an HTML id attribute. */
export const slug = (id: string) => id.replace(/[^A-Za-z0-9_-]+/g, '-');

export const TABLE_CAPTION = 'Systems by benchmark and metric. Each number carries its verification and how many of its material conditions it '
  + 'states; where a column spans condition sets, each claim says which set it is in; a refused column is cut into parts, each its own column.';
/** What the refusals section says when no column of the view is refused (lib/refusals.ts's six, in its order). */
export const REFUSALS_NONE = 'No column holds ratings from two rating pools, pass^k under two values of k, two dimensions of a vector-valued '
  + 'result, two eligibility tracks, two training-data tiers or two resolution states.';

/** What the table is a view of (10 "Progressive disclosure": every view states what it is a view of). */
export function summary(v: View): string {
  const refused = v.columns.filter((c) => c.comparison?.state === 'not-comparable').length;
  const categorical = v.columns.filter((c) => c.refusal != null).length;
  const benchmarks = new Set(v.columns.map((c) => c.benchmark)).size;
  const what = constrains(v.selection) ? 'The selection in this address' : 'Every curated claim in this build, the bare address constraining nothing';
  return `${what}: ${plural(v.claims, 'claim', 'claims')}, ${plural(v.rows.length, 'system', 'systems')} by ${plural(v.columns.length, 'column', 'columns')} `
    + `on ${plural(benchmarks, 'benchmark', 'benchmarks')}. ${refused === 0 ? 'No column' : plural(refused, 'column', 'columns')} `
    + `${refused === 1 ? 'spans' : 'span'} more than one condition set${v.dropped > 0 ? `; ${plural(v.dropped, 'claim is', 'claims are')} dropped by a restriction to one set, counted where it applies` : ''}.`
    + (categorical > 0 ? ` ${plural(categorical, 'column is', 'columns are')} refused outright, and cut into parts that are never read against each other.` : '');
}

/** A column's state as its header carries it: its comparison's, or `no-claim` for a selected benchmark with none. */
export const columnState = (c: Column) => (c.comparison == null ? 'no-claim' : c.comparison.state);

/** The note in a column's header: how many condition sets it spans, or what it leaves unknown. */
export function columnNote(c: Column): string | null {
  const g = c.comparison;
  if (g == null) return 'no curated claim';
  if (g.state === 'not-comparable') return `≠ ${g.sets.length} condition sets`;
  if (g.state === 'possibly-comparable') return '? unknown conditions';
  return null;
}

/** The note in a row's header when its claims are, in some column, one of several condition sets: the rows 10 V5's
 *  parallel-coordinates plot dashes. */
export const spansNote = (r: Row) => (r.spans > 0 ? `≠ one of several condition sets in ${plural(r.spans, 'column', 'columns')}` : null);

/** A restricted column's count of what the restriction drops. */
export const restrictedNote = (c: Column) =>
  `Restricted to one condition set: ${c.dropped.length} of ${plural(c.dropped.length + (c.comparison?.total ?? 0), 'claim', 'claims')} dropped.`;
