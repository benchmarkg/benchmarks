// site/src/lib/comparability.ts -- P3-S10-T04 (04 S8 "What the UI does with it"; 10 V5; 09 Rule 2, S6.8; 08 S3.2 S5).
// The three comparability states, decided from the build's numbers and never from the page's own reading of them:
//
//   1. comparable            one comparability_key and key_unknown_count 0 on every claim: plotted together, silently;
//   2. possibly-comparable   one key, but unknown material fields on its claims: plotted together behind a persistent
//                            banner naming which material fields are unknown on which claim. Two claims silent about
//                            chain-of-thought produce the same key (an unknown enters the key tuple as "?"), and they
//                            agree only in their ignorance, so the key alone never confirms comparability (04 S8);
//   3. not-comparable        more than one key: the field-by-field diff table instead of a chart, each condition set on
//                            its own, never ordered against another, and the count of claims a restriction to one set
//                            drops always shown (10 V5: "silently dropping data to make a chart look clean is the
//                            exact behaviour this view exists to prevent").
//
// A group is the claims on one benchmark family (its id before any `@`) and one metric, the grouping
// derived/comparability.json is written in (tools/build/comparability.py `pairwise`). The state reads claims.json's own
// `comparability` numbers (P3-S10-T02: the key and key_unknown_count are two numbers, not one); the diff table reads
// derived/comparability.json's rows, because 08 S3.2 S5 has the build compute every diff ("The UI never computes a
// comparability verdict at runtime"). A group above DEFER_ABOVE claims is `deferred` there, with no rows: it is still
// refused, its sets and counts still shown, and the page says the diff is deferred rather than inventing one (08 S3.2:
// "the UI computes the one pair the user actually selected on demand", which is the workbench's, P3-S10-T05).
//
// In a diff row a value is the canonical value the key hashes, JSON null for an answered absence (a field whose
// `*_available` companion is false, 13 S4.5), and UNKNOWN where the claim does not say. The three render differently,
// so an answered "none" is never mistaken for an unknown, nor an unknown for a value.
//
// This module imports nothing at run time, so site/test/comparability.test.mjs loads it as the site does; the pages pass
// it claims.json's rows (src/lib/claims.ts). P3-S10-T05: the workbench's script (islands/workbench/client.ts) runs the same
// decisions in the browser over a selection, so nothing here may need Node outside diffGroups, the one function that
// reads a file: it takes node:fs and node:path from process.getBuiltinModule when it is called, and the UTF-8 order is
// code-point order computed here rather than Buffer's.
import type { ClaimRow } from './claims';

export const UNKNOWN = '?';                   // tools/build/comparability.py UNKNOWN
export const DEFER_ABOVE = 40;                // tools/build/comparability.py DEFER_ABOVE (08 S3.2)
export const DIFF_NAME = 'derived/comparability.json';
export const STATES = ['single', 'comparable', 'possibly-comparable', 'not-comparable'] as const;
export type State = (typeof STATES)[number];
export type Severity = 'material' | 'informative';

// ---- derived/comparability.json ------------------------------------------------------------------------------------

export interface DiffRow { a: string; b: string; field: string; a_val: unknown; b_val: unknown; severity: Severity }
export interface DiffGroup {
  benchmark: string;
  metric: string;
  claims: number;
  keys: number;
  pairs: number;
  diff_status: 'computed' | 'deferred';
  rows: DiffRow[] | null;                     // null exactly when deferred
}

/** The key a group is held under in diffGroups' map. */
export const groupKey = (benchmark: string, metric: string) => `${benchmark}\u0000${metric}`;
/** The benchmark family a claim is grouped under: its benchmark id before any `@` (comparability.py `claim_facts`). */
export const family = (ref: string) => ref.split('@', 1)[0];

/** derived/comparability.json beside claims.json, by group; null when there is no claims.json. The stage writes the two
 *  together (tools/build/claims.py ARTIFACTS), so a claims.json without it throws, as does a preview's read into a
 *  build that is not one. */
export function diffGroups(claims: { dir: string; drafts: boolean } | null): Map<string, DiffGroup> | null {
  if (claims == null) return null;
  const { existsSync, readFileSync } = process.getBuiltinModule('node:fs');
  const { join } = process.getBuiltinModule('node:path');
  const path = join(claims.dir, ...DIFF_NAME.split('/'));
  if (!existsSync(path)) {
    throw new Error(`${path} is missing beside claims.json: the build writes them together (08 S4.2), and without it no `
      + 'comparison can name the fields its claims differ in');
  }
  return parseDiffGroups(JSON.parse(readFileSync(path, 'utf8')), claims.drafts, path);
}

/** diffGroups' reading of the artifact once parsed, with its checks: what the workbench's script calls on the copy it
 *  fetched. `path` names it in an error. */
export function parseDiffGroups(doc: unknown, drafts: boolean, path: string): Map<string, DiffGroup> {
  const raw = doc as {
    artifact: string; format: number; unknown: string; defer_above: number; groups: DiffGroup[]; drafts?: boolean;
  };
  if (raw.artifact !== 'comparability' || raw.format !== 1 || raw.unknown !== UNKNOWN || raw.defer_above !== DEFER_ABOVE) {
    throw new Error(`${path} is not format 1 of the comparability artifact with unknown "${UNKNOWN}" and defer_above ${DEFER_ABOVE}`);
  }
  if ((raw.drafts === true) !== drafts) {
    throw new Error(`${path} and the claims.json beside it are not one build: one is a draft preview's and the other is not`);
  }
  const out = new Map<string, DiffGroup>();
  for (const g of raw.groups) {
    if ((g.diff_status === 'deferred') !== (g.rows == null) || (g.diff_status === 'deferred') !== (g.claims > DEFER_ABOVE)) {
      throw new Error(`${path}: group (${g.benchmark}, ${g.metric}) of ${g.claims} claims is ${g.diff_status} with ${g.rows == null ? 'no' : 'its'} rows`);
    }
    out.set(groupKey(g.benchmark, g.metric), g);
  }
  return out;
}

// ---- the state of a group ------------------------------------------------------------------------------------------

/** One condition set: the claims of a group that share one comparability_key. One key is one key tuple, so every claim
 *  in a set has the same material values and the same unknown fields; a set whose rows disagree on either throws. */
export interface ConditionSet {
  label: string;                              // A, B, ...: the largest set first
  key: string;
  rows: ClaimRow[];                           // in the order the page gave them
  unknown_fields: string[];                   // the material fields unknown on its claims
  state: Exclude<State, 'not-comparable'>;    // a set is one key: single, comparable or possibly-comparable
}

/** A diff table cell: a value as text, an answered absence, or the unknown marker. */
export type Cell = { kind: 'value'; text: string } | { kind: 'none' } | { kind: 'unknown' };
export interface DiffField { field: string; values: Cell[] }   // one cell per set, in set order

export interface Comparison {
  benchmark: string;                          // the family id
  metric: string;
  id: string;                                 // an id for the page: cmp-<metric>
  state: State;
  total: number;                              // every claims.json claim of the group: the denominator of every count
  sets: ConditionSet[];
  diff_status: 'computed' | 'deferred';
  diff: DiffField[];                          // state 3, computed: every material field that differs between sets
  restrict: { label: string; keeps: number; drops: number } | null;   // state 3: restricting to the largest set
}

/** A..Z, then AA..: a set's label from its index. */
export function setLabel(i: number): string {
  let s = '';
  for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  return s;
}

/** UTF-8 byte order, which is code-point order (comparability.py sorts by `.encode('utf-8')`). */
export function utf8(a: string, b: string): number {
  const x = Array.from(a, (c) => c.codePointAt(0)!);
  const y = Array.from(b, (c) => c.codePointAt(0)!);
  for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1;
  return x.length === y.length ? 0 : x.length < y.length ? -1 : 1;
}

/** The state of claims sharing one key: one claim compares with nothing; unknowns make it possibly comparable. */
function setState(rows: ClaimRow[], unknown: string[]): ConditionSet['state'] {
  if (rows.length < 2) return 'single';
  return unknown.length > 0 ? 'possibly-comparable' : 'comparable';
}

/** The condition sets of `rows` (one group), largest first, ties by the smallest claim id in UTF-8 order. */
export function conditionSets(rows: ClaimRow[]): ConditionSet[] {
  const byKey = new Map<string, ClaimRow[]>();
  for (const r of rows) {
    const k = r.comparability.comparability_key;
    byKey.set(k, [...(byKey.get(k) ?? []), r]);
  }
  const first = (rs: ClaimRow[]) => rs.map((r) => r.claim.id).sort(utf8)[0];
  return [...byKey.entries()]
    .sort(([, a], [, b]) => b.length - a.length || utf8(first(a), first(b)))
    .map(([key, rs], i) => {
      const unknown = [...rs[0].comparability.unknown_fields];
      for (const r of rs) {
        const c = r.comparability;
        if (c.key_unknown_count !== c.unknown_fields.length) {
          throw new Error(`${r.claim.id}: key_unknown_count ${c.key_unknown_count} but ${c.unknown_fields.length} unknown field(s)`);
        }
        if (c.unknown_fields.join('\u0000') !== unknown.join('\u0000')) {
          throw new Error(`${r.claim.id} shares key ${key} with ${rs[0].claim.id} but not its unknown fields: one key is one key tuple`);
        }
      }
      return { label: setLabel(i), key, rows: rs, unknown_fields: unknown, state: setState(rs, unknown) };
    });
}

/** One value as the diff table shows it (comparability.py `canonicalise`'s shapes). */
export function cell(v: unknown): Cell {
  if (v === UNKNOWN) return { kind: 'unknown' };
  if (v === null || v === undefined) return { kind: 'none' };
  return { kind: 'value', text: text(v) };
}
function text(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(text).join(', ')}]`;
  if (v !== null && typeof v === 'object') {
    // a mapping's unset keys are left out, as the drill-down shows conditions (ProvenanceDetails `show`)
    return Object.entries(v as Record<string, unknown>).filter(([, x]) => x != null).map(([k, x]) => `${k} ${text(x)}`).join(', ') || '{}';
  }
  return String(v);
}
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** The field-by-field table of a computed group's material differences: one row per field that differs between any two
 *  of its sets, one cell per set. Every set has a value for every such field (a field that differs somewhere differs
 *  from each set in some pair), and the rows of one set agree, or this throws. */
function diffTable(sets: ConditionSet[], rows: DiffRow[]): DiffField[] {
  const NOTHING = Symbol('nothing');
  const setOf = new Map(sets.flatMap((s, i) => s.rows.map((r) => [r.claim.id, i] as const)));
  const fields = new Map<string, unknown[]>();
  for (const r of rows) {
    if (r.severity !== 'material') continue;
    const values = fields.get(r.field) ?? sets.map(() => NOTHING);
    for (const [id, v] of [[r.a, r.a_val], [r.b, r.b_val]] as const) {
      const i = setOf.get(id);
      if (i === undefined) throw new Error(`derived/comparability.json names ${id}, which is not a claim of this group`);
      if (values[i] !== NOTHING && !same(values[i], v)) {
        throw new Error(`set ${sets[i].label} has two values for ${r.field}: one key is one set of material values`);
      }
      values[i] = v;
    }
    fields.set(r.field, values);
  }
  return [...fields.entries()].sort(([a], [b]) => utf8(a, b)).map(([field, values]) => {
    const missing = values.findIndex((v) => v === NOTHING);
    if (missing >= 0) throw new Error(`no value of ${field} for set ${sets[missing].label}`);
    return { field, values: values.map(cell) };
  });
}

/** The comparison of one group's rows, which claims.json holds and the page orders. `group` is derived/comparability.json's
 *  for the same (benchmark, metric) and must count the same claims and keys. */
export function compare(rows: ClaimRow[], group: DiffGroup | undefined): Comparison {
  if (rows.length === 0) throw new Error('compare: a comparison of no claims');
  const benchmark = family(rows[0].claim.benchmark);
  const metric = rows[0].claim.metric;
  for (const r of rows) {
    if (family(r.claim.benchmark) !== benchmark || r.claim.metric !== metric) {
      throw new Error(`compare: ${r.claim.id} is not on (${benchmark}, ${metric})`);
    }
  }
  const sets = conditionSets(rows);
  if (group == null || group.claims !== rows.length || group.keys !== sets.length) {
    throw new Error(`derived/comparability.json ${group == null ? 'has no group' : `counts ${group.claims} claim(s) in ${group.keys} key(s)`} for `
      + `(${benchmark}, ${metric}), where claims.json has ${rows.length} in ${sets.length}: they are not one build's`);
  }
  const refused = sets.length > 1;
  const diff = refused && group.rows != null ? diffTable(sets, group.rows) : [];
  if (refused && group.diff_status === 'computed' && diff.length === 0) {
    throw new Error(`(${benchmark}, ${metric}) spans ${sets.length} keys, but its diff names no material field (09 S6.8: name exactly which)`);
  }
  return {
    benchmark, metric, id: `cmp-${metric}`, total: rows.length, sets, diff_status: group.diff_status, diff,
    state: refused ? 'not-comparable' : sets[0].state,
    restrict: refused ? { label: sets[0].label, keeps: sets[0].rows.length, drops: rows.length - sets[0].rows.length } : null,
  };
}

/** Every group of `rows` (claims.json's, on one page), in metric-id order, each its rows in the order given. */
export function comparisons(rows: ClaimRow[], groups: Map<string, DiffGroup> | null): Comparison[] {
  const by = new Map<string, ClaimRow[]>();
  for (const r of rows) {
    const k = groupKey(family(r.claim.benchmark), r.claim.metric);
    by.set(k, [...(by.get(k) ?? []), r]);
  }
  return [...by.entries()].sort(([a], [b]) => utf8(a, b)).map(([k, rs]) => compare(rs, groups?.get(k)));
}

/** The claims of a set with an unknown material field, each with the fields: what the state-2 banner names. */
export function unknownsOn(set: ConditionSet): { claim: string; system: string; fields: string[] }[] {
  return set.rows.filter((r) => r.comparability.unknown_fields.length > 0)
    .map((r) => ({ claim: r.claim.id, system: r.claim.system, fields: [...r.comparability.unknown_fields] }));
}
