// site/src/lib/browse-view.ts -- P2-S4-T04 (10 V11 "The filter panel", "Filter state encoding"; 09 S6.10, S8.4; 12
// S5.3). The V11 browse view's logic, pure and DOM-free: the facet rail's groups and the filter keys they answer to,
// facets.json's rows matched against a selection, every term's count recomputed on every change, the applied-filter
// chips, the filter empty-state's most constraining filter, the one sentence the status region announces, and the
// curation-confidence indicator's scope. islands/FacetPanel.tsx renders what this computes, and test/browse-view.test.mjs
// drives it under Node, which loads it as it is, stripping the types.
//
// The rail. One group per term key of 10's filter grammar (lib/filter-url.ts TERM_KEYS) that names a taxonomy
// vocabulary: d, c, em, s, lc, acc, mt, sp, ct, rt. `b` is the Suite Builder's basket, not a facet. A field the grammar
// gives no key (refresh, data provenance, contamination risk, the ceiling anchor, activity, maintenance status,
// independence flags, reproducibility blockers, harness availability) has no group, because a selection lives in the
// query string and a group whose state could not be written there would make a link that does not reproduce the view;
// giving one a key is a change to 10's grammar first. Every term of a group's vocabulary is in it, whatever its count:
// "zero-count terms are shown and disabled, never hidden" (10 V11).
//
// Matching. "AND across facets, OR within a facet" (08 S5.7). facets.json (tools/build/emit.py, format 2) writes a flat
// facet's values as the term id, or `{field}:{id}` for an id the facet defines in more than one field (execution's
// wet-lab is a compute tier and a reproducibility blocker), so a term matches either spelling: exactly one of the two can
// occur for any term, and which one is the emitter's business. The domain group matches a family against a row's
// `domain` and a subdomain against its `subdomain` (domain.primary). Secondary domains are not in facets.json (emit.py
// says why), so the filter is on the primary domain; the single-facet /browse/domain/ pages list secondaries apart.
//
// Counting. A term's count is the number of rows that carry it and match every OTHER group's selection: what the
// results would hold if that term were its group's only selection. So the counts of a group with a selection still show
// what each of its other terms would add. The sets are P2-S4-T02's bitset index (lib/facet-index.ts, 08 S5.7):
// buildIndex() builds facets.json's value bitsets once, in result order, and gives each rail term the union of its
// spellings' sets; tally() ORs a group's selected terms, ANDs the groups and the year range, and counts every term within
// the set constrain() gives its group, so a change is word-wise ANDs and popcounts, not a pass over the rows.
// test/perf/facet-filter.bench.mjs holds it to 08 S8.1's filter budget at 1,500 and 5,000 rows.
//
// What the view applies. The rail's term keys, and `yr` (release year, inclusive; a row with no year is outside every
// range). The grammar's other keys are kept in the URL and named in a visible "not applied" notice rather than dropped
// or silently ignored: `q` is the search box's (Pagefind, P2-S4-T06/T07), `hr` filters on headroom, which no build
// stage computes yet (every row's is null), `sort` and `ver` have no control here yet, and `b` is the Suite Builder's.
import { buildFacetIndex, constrain, countBoth, members, union, valueSet, within, type Bitset, type FacetIndex } from './facet-index.ts';
import type { FilterState, Ignored, RangeKey, SingleKey, TermKey, Vocabularies } from './filter-url.ts';

// ---- facets.json ------------------------------------------------------------------------------------------

/** The facets.json format this view reads (tools/build/emit.py FORMATS). */
export const FACETS_FORMAT = 2;

/** One facets.json row: 08 S4.2's list, as tools/build/emit.py FACET_ROW writes it. */
export interface FacetRow {
  id: string;
  slug: string;
  name: string;
  aliases: string[];
  domain: string;                       // the family of domain.primary
  subdomain: string;                    // domain.primary
  facets: Record<string, string[]>;     // the seven flat facet arrays, keyed by taxonomy facet name
  year: number | null;
  lifecycle: string;
  verification_max: string | null;
  condition_completeness_max: number | null;
  claim_count: number;
  headroom: number | null;
}

export interface FacetsDoc {
  artifact: 'facets';
  format: number;
  benchmarks: FacetRow[];
  drafts?: boolean;
}

/** The rows of a fetched facets.json, or the reason it cannot be read by this view. */
export function readFacets(doc: unknown): { rows: FacetRow[]; drafts: boolean } | { error: string } {
  const d = doc as Partial<FacetsDoc> | null;
  if (d == null || typeof d !== 'object' || d.artifact !== 'facets') return { error: 'the file is not the facets artifact' };
  if (d.format !== FACETS_FORMAT) return { error: `facets.json is format ${String(d.format)}, and this view reads format ${FACETS_FORMAT}` };
  if (!Array.isArray(d.benchmarks)) return { error: 'facets.json has no benchmarks list' };
  return { rows: d.benchmarks, drafts: d.drafts === true };
}

// ---- the rail ---------------------------------------------------------------------------------------------

export type RailKey = Exclude<TermKey, 'b'>;

/** A rail group: one term key of 10's grammar, the taxonomy facet whose terms it offers, and, for a facet with several
 *  fields, the field those terms are values of. `facet` is also the facets.json array the group reads. */
export interface RailSpec {
  key: RailKey;
  label: string;
  facet: string;
  field: string | null;
}

/** The rail, in its order: the domain spine first, then what is measured, how, of what, and the record's properties. */
export const RAIL: readonly RailSpec[] = [
  { key: 'd', label: 'Domain', facet: 'domain', field: null },
  { key: 'c', label: 'Capability', facet: 'capability', field: null },
  { key: 'em', label: 'Evaluation method', facet: 'evaluation_method', field: null },
  { key: 's', label: 'Subject under test', facet: 'subject', field: null },
  { key: 'lc', label: 'Lifecycle', facet: 'lifecycle', field: 'lifecycle' },
  { key: 'acc', label: 'Access', facet: 'data_properties', field: 'data.access' },
  { key: 'mt', label: 'Maintainer type', facet: 'governance', field: 'governance.maintainer_type' },
  { key: 'sp', label: 'Submission process', facet: 'governance', field: 'governance.submission_process' },
  { key: 'ct', label: 'Compute tier', facet: 'execution', field: 'execution.compute_tier' },
  { key: 'rt', label: 'Reproducibility tier', facet: 'execution', field: 'execution.reproducibility_tier' },
];

/** The least of a taxonomy term the rail needs (lib/terms.ts TaxTerm carries it). */
export interface TermSource {
  facet: string;
  id: string;
  label: string;
  definition: string;
  field?: string;
  parent?: string | null;
}

export interface RailTerm {
  id: string;
  label: string;
  gloss: string;            // the definition, whitespace-folded: what the hover shows
  parent: string | null;    // a subdomain's family; null otherwise
}

export interface RailGroup extends RailSpec {
  taxonomy: string;         // the /taxonomy/{facet}/ segment (lib/terms.ts facetSegment)
  browse: string;           // the /browse/{segment}/ segment (lib/browse.ts browseSegment)
  terms: RailTerm[];
}

const kebab = (s: string) => s.replace(/_/g, '-');

/** The rail's groups over the taxonomy's terms, in RAIL order and each vocabulary's file order. Throws on a group with
 *  no term, because a rail group that offers nothing means a facet or field was renamed under it. */
export function railGroups(terms: readonly TermSource[]): RailGroup[] {
  return RAIL.map((spec) => {
    const own = terms.filter((t) => t.facet === spec.facet && (spec.field == null || t.field === spec.field));
    if (own.length === 0) {
      throw new Error(`browse rail ${spec.key}: taxonomy/ has no ${spec.facet} term${spec.field != null ? ` of field ${spec.field}` : ''}`);
    }
    return {
      ...spec,
      taxonomy: kebab(spec.facet),
      browse: kebab((spec.field ?? spec.facet).split('.').pop()!),
      terms: own.map((t) => ({ id: t.id, label: t.label, gloss: t.definition.split(/\s+/).join(' ').trim(), parent: t.parent ?? null })),
    };
  });
}

export const termHref = (g: Pick<RailGroup, 'taxonomy'>, id: string) => `/taxonomy/${g.taxonomy}/${id}/`;
export const browseHref = (g: Pick<RailGroup, 'browse'>, id: string) => `/browse/${g.browse}/${id}/`;

/** decode()'s vocabularies: each rail key takes its group's term ids, and nothing else. */
export function vocabularies(groups: readonly RailGroup[]): Vocabularies {
  return Object.fromEntries(groups.map((g) => [g.key, new Set(g.terms.map((t) => t.id))]));
}

// ---- the index and the tally ------------------------------------------------------------------------------

export interface Index {
  groups: RailGroup[];
  rows: FacetRow[];             // in result order: name, then id; a row's bit in every set is its place here
  facets: FacetIndex;           // lib/facet-index.ts over `rows`
  terms: Map<string, Bitset>[]; // per group: term id -> the rows carrying it; a term no row carries is absent
}

const byName = (a: FacetRow, b: FacetRow) => a.name.localeCompare(b.name, 'en') || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);

/** The rows sorted for display, the facet index over them, and per group each term's rows, built once on load. A
 *  term's rows are its spellings' (module docstring, "Matching"): a domain term is a row's family or its subdomain,
 *  any other term its bare id or `{field}:{id}` in its facet's array. */
export function buildIndex(groups: RailGroup[], rows: readonly FacetRow[]): Index {
  const sorted = [...rows].sort(byName);
  const facets = buildFacetIndex(sorted);
  const terms = groups.map((g) => {
    const out = new Map<string, Bitset>();
    for (const t of g.terms) {
      const spelt = (g.key === 'd'
        ? [valueSet(facets, 'domain', t.id), valueSet(facets, 'subdomain', t.id)]
        : [valueSet(facets, g.facet, t.id), g.field != null ? valueSet(facets, g.facet, `${g.field}:${t.id}`) : undefined]
      ).filter((s): s is Bitset => s != null);
      if (spelt.length > 0) out.set(t.id, spelt.length === 1 ? spelt[0] : union(facets.words, spelt));
    }
    return out;
  });
  return { groups, rows: sorted, facets, terms };
}

export interface Tally {
  total: number;
  matches: number[];                  // row indexes into index.rows, in result order
  counts: Map<string, number>[];      // per group: term id -> count; a term no row carries is absent (0)
}

function yearRange(state: FilterState): [number, number] | null {
  if (state.yr == null) return null;
  const m = /^(-?\d+)-(-?\d+)$/.exec(state.yr);
  return m ? [Number(m[1]), Number(m[2])] : null;
}

/** The selection's results and every term's count, over the bitsets (module docstring, "Counting"). */
export function tally(index: Index, state: FilterState): Tally {
  const { facets, terms } = index;
  const yr = yearRange(state);
  const base = yr == null ? facets.all : within(facets.ranges.year, facets.words, yr[0], yr[1]);
  const unions = index.groups.map((g, gi) => {
    const sel = state[g.key] ?? [];
    return sel.length === 0 ? null : union(facets.words, sel.map((id) => terms[gi].get(id)));
  });
  const { all, others } = constrain(base, unions);
  const counts = terms.map((byTerm, gi) => {
    const m = new Map<string, number>();
    for (const [id, rows] of byTerm) {
      const n = countBoth(rows, others[gi]);
      if (n > 0) m.set(id, n);
    }
    return m;
  });
  const matches = members(all);
  return { total: matches.length, matches, counts };
}

// ---- the selection ------------------------------------------------------------------------------------------

/** The selection with `value` of term key `key` added, or removed when it is there. */
export function toggle(state: FilterState, key: RailKey, value: string): FilterState {
  const now = state[key] ?? [];
  const next = now.includes(value) ? now.filter((v) => v !== value) : [...now, value];
  const out: FilterState = { ...state };
  if (next.length > 0) out[key] = next;
  else delete out[key];
  return out;
}

/** The selection without one applied filter: a term, or the whole year range. */
export function without(state: FilterState, chip: Pick<Chip, 'key' | 'value'>): FilterState {
  if (chip.key === 'yr') {
    const out: FilterState = { ...state };
    delete out.yr;
    return out;
  }
  return toggle(state, chip.key, chip.value);
}

/** The selection with every applied filter removed; the keys this view does not apply are kept. */
export function cleared(state: FilterState, groups: readonly RailGroup[]): FilterState {
  const out: FilterState = { ...state };
  for (const g of groups) delete out[g.key];
  delete out.yr;
  return out;
}

export interface Chip {
  key: RailKey | 'yr';
  value: string;
  group: string;            // the group's label: "Capability"
  label: string;            // the term's label, or the range as written
}

/** One chip per applied filter, in rail order and each key's canonical value order, then the year range. */
export function chips(groups: readonly RailGroup[], state: FilterState): Chip[] {
  const out: Chip[] = [];
  for (const g of groups) {
    const labels = new Map(g.terms.map((t) => [t.id, t.label]));
    for (const v of [...(state[g.key] ?? [])].sort()) out.push({ key: g.key, value: v, group: g.label, label: labels.get(v) ?? v });
  }
  if (state.yr != null) out.push({ key: 'yr', value: state.yr, group: 'Release year', label: state.yr.replace('-', '–') });
  return out;
}

/** The keys of 10's grammar present in the selection that this view keeps but does not apply (module docstring). */
export const UNAPPLIED: readonly (RangeKey | SingleKey | 'b')[] = ['b', 'hr', 'q', 'sort', 'ver'];

export function unapplied(state: FilterState): Ignored[] {
  const out: Ignored[] = [];
  for (const key of UNAPPLIED) {
    const v = state[key];
    if (v == null) continue;
    for (const value of Array.isArray(v) ? v : [v]) out.push({ key, value });
  }
  return out;
}

/** The filter empty-state's offer (09 S6.10): the applied filter whose removal returns the most results, and how many. */
export function mostConstraining(index: Index, state: FilterState): { chip: Chip; results: number } | null {
  let best: { chip: Chip; results: number } | null = null;
  for (const chip of chips(index.groups, state)) {
    const results = tally(index, without(state, chip)).total;
    if (best == null || results > best.results) best = { chip, results };
  }
  return best;
}

// ---- what the view says ---------------------------------------------------------------------------------------

/** The status region's one sentence (09 S8.4: "312 benchmarks match"). */
export function announcement(total: number): string {
  if (total === 0) return 'No benchmark matches';
  return total === 1 ? '1 benchmark matches' : `${total} benchmarks match`;
}

/** The status region's debounce, 09 S8.4. */
export const ANNOUNCE_MS = 500;

export type Signoff = 'none' | 'generalist' | 'domain-expert';
export interface Family {
  id: string;
  label: string;
  signoff: Signoff;
}

export interface Confidence {
  scope: 'all' | 'filtered';
  families: Family[];         // the families in scope, in taxonomy order
  signed: Family[];           // of those, the ones a reviewer has signed off
  state: 'unreviewed' | 'partly-reviewed' | 'reviewed';
}

/** The curation-confidence indicator's scope: the families the domain filter touches (a subdomain's family counts),
 *  or every family when the domain is unfiltered. The indicator reads each family's reviewer sign-off, 12 S5.3's
 *  reviewer_signoff term and 14 Phase 1's honest gate (lib/vocab.ts signoff()), as the browse pages do. */
export function confidence(families: readonly Family[], state: FilterState): Confidence {
  const touched = new Set((state.d ?? []).map((v) => v.split('/')[0]));
  const scope = touched.size > 0 ? 'filtered' : 'all';
  const inScope = scope === 'all' ? [...families] : families.filter((f) => touched.has(f.id));
  const signed = inScope.filter((f) => f.signoff !== 'none');
  return {
    scope, families: inScope, signed,
    state: signed.length === 0 ? 'unreviewed' : signed.length === inScope.length ? 'reviewed' : 'partly-reviewed',
  };
}
