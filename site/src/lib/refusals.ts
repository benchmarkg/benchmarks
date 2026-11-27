// site/src/lib/refusals.ts -- P3-S10-T06 (10 V5 "Beyond the generic key, six categorical refusals"; 04 S8, S9; 08 S3.2
// S5). The six cases 10 V5 names in which a comparison table "produces a confidently wrong number", each decided here,
// beside the comparability key rather than inside it:
//
//   rating-pool           Pool-relative rating compared across snapshots. "Require matching `rating_pool_id` + snapshot
//                         date; otherwise render side by side with no shared axis." Read off the claim's `rating_pool`
//                         (schema/claim.py: a rating claim names one, no other claim may) and its metric's
//                         `requires_pool`. The pool's snapshot_date is not in any artifact the site reads (claims.json
//                         carries the pool id, not the RatingPool record), but schema/entities.py RatingPool makes the
//                         id carry the date ("a pool is a pool at a date"), so one id is one pool at one date and the
//                         date shown is the id's; an id dated to the month shows the month
//   pass-hat-k            Reliability metric averaged across k. "pass^1 and pass^8 are different metrics." Read off the
//                         inlined conditions' `selection_strategy: pass-hat-k` and `k`; a claim under another strategy
//                         beside a pass^k claim is a different metric as well
//   vector-valued         Vector-valued result collapsed. "Render as a small-multiple row ... never a scalar. Honour the
//                         `no_legitimate_aggregate` flag." Read off the benchmark's `no_legitimate_aggregate`, its
//                         `aggregation_policy: none-by-design` (04 S5: "the site refuses to render a single headline number
//                         for the benchmark at all") and the metric's `value_type: vector`; the dimension is the claim's
//                         `subset`. The schema has no field saying which dimensions make up a vector, nor that a metric
//                         is an aggregate over them, so the dimension read is the subset and a claim that names none is
//                         grouped as naming no dimension
//   legality-track        Different leaderboard legality rules. "Treat harness legality as a material condition; the two
//                         leaderboards never merge." Read off the conditions' `eligibility_track` (schema/conditions.py:
//                         "the board a result is listed on (ARC-AGI-3 official vs community)")
//   training-eligibility  Different training-data eligibility. "Group by compliance tier." Read off the conditions'
//                         `training_data_eligibility`, a tier id of the benchmark's `training_data_eligibility_tiers`,
//                         whose label the group carries
//   resolution            Unresolved ground truth. "Show `resolution_status` ... and never plot pending against resolved."
//                         Read off the claim's `resolution_status`, `resolved` when unset (schema/claim.py's default);
//                         every two statuses are kept apart, since a partial score moves as the rest resolves too
//
// A refusal fires on a set of claims (one workbench column's) when its field splits them into two or more groups; a
// claim that does not record the field is a group of its own ("not recorded"), never assumed to share a value (04 S8:
// "`null` in a material field means unknown"). A field no claim of the set records fires nothing: there is no value to
// differ in, and the comparability key's unknown count already says what is unknown. The refusals that fire cut the
// set into parts, one per combination of their groups, and each part is read on its own axis: the workbench draws each
// as a column of its own under one header naming the refusal, with the reason, the groups and what would make the claims
// comparable over the table, so no number is ever read against a number from another part.
//
// The decision reads the build's records only -- claims.json's rows (the claim, its inlined conditions) and corpus.json's
// benchmark and metric entities -- and is a pure function of them, so the build's render and the workbench's script in
// the browser apply the same one (08 S3.2 S5: "The UI never computes a comparability verdict at runtime" that the build
// did not decide): the script checks that its decision over the whole index is the one the page was rendered with before
// it applies a selection. Like lib/comparability.ts, this module imports nothing at run time (Node strips its types in
// site/test/refusals.test.mjs).
//
// What would close the two gaps above. The snapshot date: tools/build/claims.py could inline the RatingPool record a
// rating names (its snapshot_date) in the claims.json row, a build change with no schema change; until then a match on
// the id is a match on the date by the schema's identity rule. The dimensions: a schema field that names the
// dimensions of a vector-valued result (on the Metric or the Benchmark) and marks a metric or claim that aggregates
// over them would let a collapsed scalar be refused on its own; that is a schema/*.py change, not made here.
import type { ClaimRow } from './claims';

export const REFUSALS = ['rating-pool', 'pass-hat-k', 'vector-valued', 'legality-track', 'training-eligibility', 'resolution'] as const;
export type RefusalId = (typeof REFUSALS)[number];

/** What a refusal reads off a benchmark and a metric: corpus.json's entities, the content collections' data. */
export interface BenchmarkFacts {
  name?: string | null;
  no_legitimate_aggregate?: boolean | null;
  aggregation_policy?: string | null;
  training_data_eligibility_tiers?: { id: string; label?: string | null }[] | null;
}
export interface MetricFacts { value_type?: string | null; requires_pool?: boolean | null }
export interface Facts { benchmarks: Map<string, BenchmarkFacts>; metrics: Map<string, MetricFacts> }
export const NO_FACTS: Facts = { benchmarks: new Map(), metrics: new Map() };

/** One value of a refusal's field among the claims: its claims, in the order given. */
export interface Group { id: string; label: string; claims: string[] }
export interface Refusal {
  id: RefusalId;
  name: string;               // which refusal: 10 V5's situation
  field: string;              // the record field it reads
  why: string;                // why these claims, read together, would give a wrong number
  requires: string;           // what would make them comparable
  groups: Group[];            // two or more
}
/** The claims that agree on every refusal's field: read on their own axis, never against another part's. */
export interface Part { id: string; label: string; groups: string[]; claims: string[] }
export interface ColumnRefusal {
  refusals: Refusal[];        // in REFUSALS order
  parts: Part[];
  partOf: Map<string, string>;  // claim id -> part id
}

/** A group's value as the refusal reads it: an id, a label, and where it sorts (recorded values first). */
interface Value { id: string; label: string; order: [number, number | string] }
interface Ctx { benchmark: string; facts: BenchmarkFacts | undefined; metric: MetricFacts | undefined }
interface Rule {
  id: RefusalId;
  name: string;
  field: string;
  requires: string;
  applies(rows: ClaimRow[], ctx: Ctx): boolean;
  value(row: ClaimRow, ctx: Ctx): Value;
  why(groups: Group[], rows: ClaimRow[], ctx: Ctx): string;
}

/** The id of a group of claims that do not record the field. */
export const NOT_RECORDED = '~not-recorded';
const unrecorded = (what: string): Value => ({ id: NOT_RECORDED, label: `${what} not recorded`, order: [1, 0] });
const recorded = (id: string, label: string, order: number | string = id): Value => ({ id, label, order: [0, order] });
const cond = (r: ClaimRow, f: string): unknown => (r.conditions as Record<string, unknown> | null | undefined)?.[f] ?? null;
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
const listed = (gs: Group[]) => gs.map((g) => `${g.label} (${plural(g.claims.length, 'claim', 'claims')})`).join('; ');

/** The snapshot a pool id carries: schema/entities.py RatingPool requires it to end in its date, YYYY-MM or YYYY-MM-DD. */
export function poolDate(pool: string): string | null {
  return /-(\d{4}-\d{2}(?:-\d{2})?)$/.exec(pool)?.[1] ?? null;
}
const RESOLUTION_ORDER = ['resolved', 'partial', 'pending'];

const RULES: Rule[] = [
  {
    id: 'rating-pool',
    name: 'Pool-relative ratings from different rating pools',
    field: 'rating_pool',
    requires: 'ratings fitted in one rating pool at one snapshot date: the same rating_pool, whose id carries its snapshot date (a pool is a pool at a date, 04 S9).',
    applies: (rows, ctx) => ctx.metric?.requires_pool === true || rows.some((r) => r.claim.claim_type === 'rating' || r.claim.rating_pool != null),
    value: (r) => {
      const pool = r.claim.rating_pool;
      if (pool == null) return unrecorded('rating pool');
      const date = poolDate(pool);
      return recorded(pool, `${pool}, snapshot ${date ?? 'undated'}`, `${date ?? ''} ${pool}`);
    },
    why: (gs, rows) => `${plural(rows.length, 'rating comes', 'ratings come')} from ${gs.length} rating pools: ${listed(gs)}. A rating is relative to the pool it was fitted in, and it moves when a different system joins the pool, so a rating is never read against one from another pool or another snapshot.`,
  },
  {
    id: 'pass-hat-k',
    name: 'A reliability metric across different k',
    field: 'conditions.selection_strategy, conditions.k',
    requires: 'claims under pass^k with the same k: selection_strategy pass-hat-k and one value of k.',
    applies: (rows) => rows.some((r) => cond(r, 'selection_strategy') === 'pass-hat-k'),
    value: (r) => {
      const s = cond(r, 'selection_strategy');
      const k = cond(r, 'k');
      if (s === 'pass-hat-k') return k == null ? { id: 'pass-hat-k', label: 'pass^k, k not recorded', order: [0, Number.MAX_SAFE_INTEGER] } : recorded(`pass-hat-k@${k}`, `pass^${k}`, Number(k));
      return s == null ? unrecorded('selection strategy') : { id: String(s), label: `not pass^k: ${s}`, order: [0, `~${s}`] };
    },
    why: (gs) => `pass^k is the share of tasks solved in every one of k trials, a reliability metric: pass^1 and pass^8 are different metrics, and an average or a ranking across k is a number nobody measured. These claims are under ${gs.length} settings: ${listed(gs)}.`,
  },
  {
    id: 'vector-valued',
    name: 'A vector-valued result collapsed onto one axis',
    field: 'subset',
    requires: 'claims on one dimension of the result: the same subset, each dimension read in its own column, never combined into one score.',
    applies: (_rows, ctx) => ctx.facts?.no_legitimate_aggregate === true || ctx.facts?.aggregation_policy === 'none-by-design' || ctx.metric?.value_type === 'vector',
    value: (r) => (r.claim.subset == null ? unrecorded('dimension (subset)') : recorded(r.claim.subset, r.claim.subset)),
    why: (gs, _rows, ctx) => {
      const name = ctx.facts?.name ?? ctx.benchmark;
      const basis = ctx.facts?.no_legitimate_aggregate === true ? 'records that no aggregate of its results is legitimate (no_legitimate_aggregate)'
        : ctx.facts?.aggregation_policy === 'none-by-design' ? 'publishes no aggregate by design (aggregation_policy none-by-design)'
          : 'is scored with a vector-valued metric (value_type vector)';
      return `${name} ${basis}: its result is one number per dimension, read as a small-multiple row and never collapsed into one scalar or onto one axis. This column holds ${gs.length} dimensions: ${listed(gs)}.`;
    },
  },
  {
    id: 'legality-track',
    name: 'Different leaderboard legality rules',
    field: 'conditions.eligibility_track',
    requires: 'claims listed under one eligibility track: the same eligibility_track.',
    applies: (rows) => rows.some((r) => cond(r, 'eligibility_track') != null),
    value: (r) => {
      const t = cond(r, 'eligibility_track');
      return t == null ? unrecorded('eligibility track') : recorded(String(t), `track ${t}`);
    },
    why: (gs) => `An eligibility track is a leaderboard with its own legality rules (10 V5's example: ARC-AGI-3's official board admits unmodified general-purpose API systems, its community board permits harnesses), so the track is a material condition and two tracks never merge. These claims are listed under ${gs.length}: ${listed(gs)}.`,
  },
  {
    id: 'training-eligibility',
    name: 'Different training-data eligibility',
    field: 'conditions.training_data_eligibility',
    requires: 'claims under one training-data tier: the same training_data_eligibility, a tier the benchmark declares in training_data_eligibility_tiers.',
    applies: (rows) => rows.some((r) => cond(r, 'training_data_eligibility') != null),
    value: (r, ctx) => {
      const t = cond(r, 'training_data_eligibility');
      if (t == null) return unrecorded('training-data tier');
      const tier = (ctx.facts?.training_data_eligibility_tiers ?? []).find((x) => x.id === t);
      return recorded(String(t), tier?.label != null && tier.label !== '' ? `tier ${tier.label} (${t})` : `tier ${t}`);
    },
    why: (gs) => `A training-data tier restricts what a model was allowed to train on, a comparability key on the training side, so claims are grouped by tier and never ranked across tiers. These claims are under ${gs.length} tiers: ${listed(gs)}.`,
  },
  {
    id: 'resolution',
    name: 'Unresolved ground truth',
    field: 'resolution_status',
    requires: 'claims of one resolution_status: a pending or partial claim is compared with others once it has resolved.',
    applies: () => true,
    value: (r) => {
      const s = r.claim.resolution_status ?? 'resolved';
      return recorded(s, `resolution_status ${s}`, RESOLUTION_ORDER.indexOf(s));
    },
    why: (gs) => `A pending or partial claim is scored against answers that do not all exist yet, and its number moves as they resolve, so pending is never plotted against resolved, nor partial against either. These claims are ${listed(gs)}.`,
  },
];

const byOrder = (a: Value, b: Value) => {
  if (a.order[0] !== b.order[0]) return a.order[0] - b.order[0];
  const [x, y] = [a.order[1], b.order[1]];
  if (typeof x === 'number' && typeof y === 'number' && x !== y) return x - y;
  const [s, t] = [String(x), String(y)];
  return s < t ? -1 : s > t ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
};

/** The refusals that fire on `rows`, the claims of one (benchmark family, metric) column, and the parts they cut it
 *  into; null when none fires. `facts` are the benchmark's and the metric's records. */
export function refuse(rows: ClaimRow[], facts: Facts = NO_FACTS): ColumnRefusal | null {
  if (rows.length < 2) return null;
  const benchmark = rows[0].claim.benchmark.split('@', 1)[0];
  const ctx: Ctx = { benchmark, facts: facts.benchmarks.get(benchmark), metric: facts.metrics.get(rows[0].claim.metric) };
  const refusals: Refusal[] = [];
  const values = new Map<RefusalId, Map<string, Value>>();       // refusal -> claim id -> its value
  for (const rule of RULES) {
    if (!rule.applies(rows, ctx)) continue;
    const of = new Map(rows.map((r) => [r.claim.id, rule.value(r, ctx)] as const));
    const distinct = [...new Map([...of.values()].map((v) => [v.id, v])).values()].sort(byOrder);
    if (distinct.length < 2) continue;
    const groups = distinct.map((v) => ({ id: v.id, label: v.label, claims: rows.filter((r) => of.get(r.claim.id)!.id === v.id).map((r) => r.claim.id) }));
    refusals.push({ id: rule.id, name: rule.name, field: rule.field, why: rule.why(groups, rows, ctx), requires: rule.requires, groups });
    values.set(rule.id, of);
  }
  if (refusals.length === 0) return null;
  // the parts: one per combination of groups the claims hold, ordered by each refusal's group order in turn
  const rank = new Map(refusals.map((f) => [f.id, new Map(f.groups.map((g, i) => [g.id, i]))]));
  const parts = new Map<string, { part: Part; at: number[] }>();
  const partOf = new Map<string, string>();
  for (const r of rows) {
    const gs = refusals.map((f) => values.get(f.id)!.get(r.claim.id)!);
    const id = refusals.map((f, i) => `${f.id}=${gs[i].id}`).join('&');
    const p = parts.get(id) ?? {
      part: { id, label: gs.map((g) => g.label).join(' · '), groups: gs.map((g) => g.id), claims: [] },
      at: refusals.map((f, i) => rank.get(f.id)!.get(gs[i].id)!),
    };
    p.part.claims.push(r.claim.id);
    parts.set(id, p);
    partOf.set(r.claim.id, id);
  }
  const ordered = [...parts.values()].sort((a, b) => {
    for (let i = 0; i < a.at.length; i++) if (a.at[i] !== b.at[i]) return a.at[i] - b.at[i];
    return 0;
  }).map((p) => p.part);
  return { refusals, parts: ordered, partOf };
}

/** A refusal decision as one string, what the page's header carries and the script checks its own decision against. */
export function signature(r: ColumnRefusal | null): string {
  return r == null ? '' : `${r.refusals.map((f) => f.id).join(' ')} | ${r.parts.map((p) => p.id).join(' ; ')}`;
}

/** The note in a refused column's header: which refusals, so the header never reads as one axis. */
export const refusalNote = (r: ColumnRefusal) => `⊘ Refused: ${r.refusals.map((f) => f.name.charAt(0).toLowerCase() + f.name.slice(1)).join('; ')}`;
/** What the table does with a refused column, under its refusals. */
export const partsNote = (r: ColumnRefusal) =>
  `In the table this column is cut into ${r.parts.length} parts, one per ${r.refusals.length === 1 ? 'group' : 'combination of groups'}, each its own column: no number in one part is read against a number in another.`;

/** The facts of corpus.json's (or the content collections') benchmark and metric records, by id: the server passes the
 *  collections, the browser corpus.json's entities, which are the same records (src/content.config.ts loads them). */
export function factsOf(benchmarks: Iterable<{ id: string } & BenchmarkFacts>, metrics: Iterable<{ id: string } & MetricFacts>): Facts {
  return {
    benchmarks: new Map([...benchmarks].map((b) => [b.id, {
      name: b.name ?? null, no_legitimate_aggregate: b.no_legitimate_aggregate ?? null, aggregation_policy: b.aggregation_policy ?? null,
      training_data_eligibility_tiers: (b.training_data_eligibility_tiers ?? []).map((t) => ({ id: t.id, label: t.label ?? null })),
    }])),
    metrics: new Map([...metrics].map((m) => [m.id, { value_type: m.value_type ?? null, requires_pool: m.requires_pool ?? null }])),
  };
}
