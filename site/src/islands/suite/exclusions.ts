// site/src/islands/suite/exclusions.ts -- P6-S4-T03 (11 S2 F2 "How it is wrong" 2 and 3, and "Made visible"; 10 V10
// "Failure mode to avoid"; 02 S11's implication table). The Suite Builder's hard exclusion rules. An entry whose licence
// forbids the suite's use, or that is deprecated, superseded or known-contaminated, is left out of the suite by code,
// from the entry's structured fields -- "hard code filters with a visible 'excluded N entries because...' panel, not
// model judgement" -- and the panel names every entry left out and the rule that fired on it.
//
// The rules, in the order the panel names them, and the fields each reads (schema/benchmark.py; the terms are
// taxonomy/lifecycle.yaml's and taxonomy/data-properties.yaml's):
//
//   licence-incompatible  data.dataset_licence and execution.code_licence, the two the entry's licence is derived from
//                         (ADR-0024). It fires when either text limits use to non-commercial, research or academic use
//                         and the suite is screened for any use, or limits use to a stated purpose. The texts are SPDX
//                         ids or curated prose, read by the patterns below; the reason quotes the text that fired
//   deprecated            lifecycle `deprecated` (the maintainer advises against use), or `retracted` (the maintainer has
//                         formally withdrawn it, the stronger state)
//   superseded            lifecycle `superseded`, or a non-empty lineage.superseded_by, which 11 F2 names as a field the
//                         builder needs; the reason names the successors
//   known-contaminated    data.contamination_risk `high` or `confirmed`, the two values 02 S11 calls "known-contaminated"
//                         (each requires a contamination_evidence source, and the reason counts them), or lifecycle
//                         `contaminated`, which 02 S11 makes require one of the two
//
// What no rule reads, and the gaps that leaves, stated rather than filled:
//   - The suite's use. 10's filter grammar (lib/filter-url.ts) has no key for it, so /suite/?b=... cannot say that a suite
//     is for non-commercial research, and the page screens every basket for any use, commercial use included: the one
//     reading under which nothing the suite keeps can be forbidden by its licence. screen() takes the use as an argument,
//     so a key in the grammar, which is a maintainer's decision, is a single argument here.
//   - data.access. Who can run an entry (a private test server, a signed agreement, an invitation) is what the suite
//     manifest is to say (10 V10, "The export is honest about runnability"), not a licence term forbidding a use.
//   - data.upstream_licences and data.records_licence (prose about an entry's constituents, and the terms of its
//     evaluation records), and a version's own superseded_by: the basket holds benchmark ids, not versions.
//   - An entry with no licence curated, or whose terms the patterns do not recognise, cannot be read by the licence rule.
//     It is not excluded, and the panel names it, so that silence is not read as clearance (10 V10: "A total that
//     silently omits two entries is worse than no total").
//
// The one seam. screen() is the only place the rules are applied. islands/SuiteBuilder.tsx screens its basket, whatever
// put the entries there -- the Add buttons, a ?b= link, the Atlas's selection, this browser's kept basket -- and renders
// what is kept as the suite and what is not in its Excluded panel. The AI accelerator (11 F2; P6-S5) fills a starting
// basket (10 V10, "an accelerator that fills a starting basket from a need statement"), so its proposal reaches the page
// as basket ids, by lib/suite-basket.ts added() or a ?b= link, and is screened by this same call over the same table;
// nothing it narrates may present an entry screen() excluded, and a Worker that narrows the retrieved set before the model
// sees it calls screen() too. test/suite.exclusions.test.mjs calls it as both paths do. The analysis panels (P6-S4-T02)
// and the manifest (P6-S4-T04) are to read `kept`.
//
// Build time and run time. factTable() runs in pages/suite/index.astro over the full records, which the browser never
// loads, and keeps only the entries a rule can fire on or the licence rule cannot read; the island receives that table
// as a prop and imports screen() and the panel's wording only, so the patterns cost the route's 80 KB nothing.

/** The rules, in the order the panel names them, each with the word it is named by. */
export const RULES = [
  ['licence', 'licence-incompatible'],
  ['deprecated', 'deprecated'],
  ['superseded', 'superseded'],
  ['contaminated', 'known-contaminated'],
] as const;

export type RuleId = (typeof RULES)[number][0];

/** What a suite is screened for: `any` use, commercial use included (the page's), or non-commercial research only. */
export type Use = 'any' | 'non-commercial';

/** How a licence text limits use: to non-commercial, research or academic use, or to a stated purpose. */
export type Limit = 'non-commercial' | 'purpose';

/** A licence text that limits use, with the field (or fields, when both say the same) it was read from. */
export interface Terms { field: string; text: string; limit: Limit }

/** What the rules read of one entry. An entry is in the table only where a rule can fire on it or the licence rule
 *  cannot read it; a field is present only where it bears on a rule. */
export interface Facts {
  lifecycle?: string;        // deprecated, retracted, superseded or contaminated
  successors?: string[];     // lineage.superseded_by
  risk?: string;             // data.contamination_risk, high or confirmed
  evidence?: number;         // with risk: how many contamination_evidence items the entry carries
  terms?: Terms[];           // the licence texts that limit use
  unread?: true;             // no licence curated, or terms the patterns do not recognise
}

export type FactTable = Record<string, Facts>;

/** One rule fired on one entry: the field it read and what that field holds. */
export interface Fired { rule: RuleId; field: string; value: string; limit?: Limit; evidence?: number }

/** A basket screened: the suite, what was excluded and why, and what the licence rule could not read. */
export interface Screened {
  kept: string[];                                // the suite: the entries no rule fired on, in the order given
  excluded: { id: string; fired: Fired[] }[];    // the others, each with every rule that fired on it, in RULES order
  unread: string[];                              // of `kept`, the entries whose licence the rule could not read
}

/** The one seam (module header): `ids` screened by the hard rules over `table`, for `use`. Pure, and reads nothing but
 *  its arguments: the same ids, however they were gathered, give the same answer. */
export function screen(ids: readonly string[], table: FactTable, use: Use = 'any'): Screened {
  const out: Screened = { kept: [], excluded: [], unread: [] };
  for (const id of ids) {
    const f = Object.prototype.hasOwnProperty.call(table, id) ? table[id] : undefined;
    const fired: Fired[] = [];
    if (f != null) {
      const lc = f.lifecycle;
      for (const t of f.terms ?? []) {
        if (use === 'any' || t.limit === 'purpose') fired.push({ rule: 'licence', field: t.field, value: t.text, limit: t.limit });
      }
      if (lc === 'deprecated' || lc === 'retracted') fired.push({ rule: 'deprecated', field: 'lifecycle', value: lc });
      if (lc === 'superseded') fired.push({ rule: 'superseded', field: 'lifecycle', value: lc });
      if (f.successors != null && f.successors.length > 0) fired.push({ rule: 'superseded', field: 'lineage.superseded_by', value: f.successors.join(', ') });
      if (lc === 'contaminated') fired.push({ rule: 'contaminated', field: 'lifecycle', value: lc });
      if (f.risk != null) fired.push({ rule: 'contaminated', field: 'data.contamination_risk', value: f.risk, evidence: f.evidence ?? 0 });
    }
    if (fired.length > 0) out.excluded.push({ id, fired });
    else {
      out.kept.push(id);
      if (f?.unread) out.unread.push(id);
    }
  }
  return out;
}

// ---- the panel's wording ----------------------------------------------------------------------------------------

const LABEL = Object.fromEntries(RULES) as Record<RuleId, string>;

/** The word a rule is named by in the panel. */
export const label = (rule: RuleId) => LABEL[rule];

const entries = (n: number) => `${n} ${n === 1 ? 'entry' : 'entries'}`;

/** The panel's first line: "Excluded N of M entries because: <rule> (k), ...", each rule with the number of entries it
 *  fired on, or that none is excluded. */
export function summary(s: Screened): string {
  const n = s.excluded.length;
  if (n === 0) return s.kept.length === 0 ? 'The basket is empty, so nothing is excluded.' : `No entry is excluded: no rule fires on the ${entries(s.kept.length)} of the basket.`;
  const by = RULES.map(([id, word]) => [word, s.excluded.filter((e) => e.fired.some((f) => f.rule === id)).length] as const).filter(([, k]) => k > 0);
  return `Excluded ${n} of ${entries(n + s.kept.length)} because: ${by.map(([word, k]) => `${word} (${k})`).join(', ')}.`;
}

const LIFECYCLE: Record<string, string> = {
  deprecated: 'the maintainer advises against use',
  retracted: 'the maintainer has withdrawn it',
  superseded: 'a later benchmark has replaced it',
  contaminated: 'evidenced training-data leakage compromises it',
};

/** Why one rule fired: the field it read, what the field holds, and what that means; `nameOf` turns a successor's id
 *  into its name. */
export function why(f: Fired, nameOf: (id: string) => string = (id) => id): string {
  if (f.rule === 'licence') {
    return `${f.field}: “${f.value}”, ${f.limit === 'purpose' ? 'which limits use to a stated purpose' : 'which allows non-commercial use only, and the suite is screened for any use'}`;
  }
  if (f.field === 'lineage.superseded_by') return `lineage.superseded_by: ${f.value.split(', ').map(nameOf).join(', ')}`;
  if (f.field === 'data.contamination_risk') return `data.contamination_risk: ${f.value}, on ${f.evidence} evidence ${f.evidence === 1 ? 'source' : 'sources'}`;
  return `lifecycle: ${f.value}, ${LIFECYCLE[f.value]}`;
}

/** The note under the panel naming the kept entries the licence rule could not read, so that none is taken as cleared. */
export function unreadNote(s: Screened, nameOf: (id: string) => string = (id) => id): string {
  return `The licence rule read ${s.kept.length - s.unread.length} of the ${entries(s.kept.length)} kept. No licence it recognises is curated for ${s.unread.map(nameOf).join(', ')}: kept, not cleared.`;
}

// ---- build time: the fact table ---------------------------------------------------------------------------------

/** The least of a benchmark record the rules read (types/benchmark.d.ts's Benchmark has it). */
export interface Entry {
  id: string;
  lifecycle?: string | null;
  data?: { dataset_licence?: string | null; contamination_risk?: string; contamination_evidence?: readonly unknown[] } | null;
  execution?: { code_licence?: string | null } | null;
  lineage?: { superseded_by?: readonly string[] } | null;
}

// A limit to non-commercial, research or academic use: a Creative Commons NC licence however it is spelt (CC-BY-NC-4.0,
// CC BY-NC-ND, CC-NC-SA) or prose that says so ("non-commercial", "no commercial use", "research use", "academic use",
// "academic research only")
const NON_COMMERCIAL = /\b(?:BY|CC)[- ]NC\b|\bnon-?commercial\b|\bno commercial\b|\b(?:research|academic)(?: research)? use\b|\b(?:research|academic)(?: research)?[- ]only\b/i;
// A limit to a stated purpose: "use only to improve the safety and security of AI systems"
const PURPOSE = /\buse only (?:to|for)\b/i;
// The open licences the corpus names, as SPDX ids or as Creative Commons writes them. A text with none of these and no
// limit (a bare "Terms of Use") is terms the rule does not recognise.
const OPEN = /\b(?:CC0(?:-1\.0)?|CC[- ]BY(?:[- ](?:SA|ND))?(?:[- ]\d\.\d)?|MIT|Apache[- ]2\.0|BSD(?:-[234]-Clause)?|[AL]?GPL-[23]\.0|MPL-2\.0|EUPL-1\.2|AFL-3\.0|ODC-By-1\.0|ODbL-1\.0|CDLA-Permissive-[12]\.0)\b/i;

/** How one licence text reads: a limit on use, open, or terms the patterns do not recognise. */
export function termsOf(text: string): Limit | 'open' | 'unread' {
  if (NON_COMMERCIAL.test(text)) return 'non-commercial';
  if (PURPOSE.test(text)) return 'purpose';
  return OPEN.test(text) ? 'open' : 'unread';
}

/** What the rules read of one record, or null when no rule can fire on it and its licence is read as open. */
export function factsOf(b: Entry): Facts | null {
  const f: Facts = {};
  const lc = b.lifecycle;
  if (lc === 'deprecated' || lc === 'retracted' || lc === 'superseded' || lc === 'contaminated') f.lifecycle = lc;
  const successors = b.lineage?.superseded_by ?? [];
  if (successors.length > 0) f.successors = [...successors];
  const risk = b.data?.contamination_risk;
  if (risk === 'high' || risk === 'confirmed') {
    f.risk = risk;
    f.evidence = (b.data?.contamination_evidence ?? []).length;
  }
  const texts: [string, string | null | undefined][] = [['data.dataset_licence', b.data?.dataset_licence], ['execution.code_licence', b.execution?.code_licence]];
  const read = texts.filter((t): t is [string, string] => t[1] != null && t[1].trim() !== '').map(([field, text]) => ({ field, text, reads: termsOf(text) }));
  const terms: Terms[] = [];
  for (const r of read) {
    if (r.reads !== 'non-commercial' && r.reads !== 'purpose') continue;
    const same = terms.find((t) => t.text === r.text);
    if (same != null) same.field += `, ${r.field}`;
    else terms.push({ field: r.field, text: r.text, limit: r.reads });
  }
  if (terms.length > 0) f.terms = terms;
  else if (read.length === 0 || read.some((r) => r.reads === 'unread')) f.unread = true;
  return Object.keys(f).length > 0 ? f : null;
}

/** The fact table a page hands the island: every record a rule can fire on or the licence rule cannot read, by id. */
export function factTable(records: Iterable<Entry>): FactTable {
  const out: FactTable = {};
  for (const b of records) {
    const f = factsOf(b);
    if (f != null) out[b.id] = f;
  }
  return out;
}
