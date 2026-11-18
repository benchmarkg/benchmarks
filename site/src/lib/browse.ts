// site/src/lib/browse.ts -- P2-S4-T01 (10 V11 "Without JavaScript", "Information architecture"; 08 S8.3, S7.5). The
// single-facet browse pages, /browse/{facet}/{term}/: one per value a single filter can take, each a complete index
// of the published benchmarks that carry it. They are the no-JS route into the catalogue for crawlers, archives and
// text browsers. Multi-term combinations need JavaScript, by decision: "a single-facet page is a browsable index, a
// five-facet intersection is a query" (10 V11), and 08 S8.3 declines the intersection route family
// (/browse/domain/{d}/capability/{c}/) because it would cost hundreds to thousands of pages from the 20,000-file cap.
//
// The URL's facet is the field a filter constrains. 10 spells the routes /browse/domain/{family}/{subdomain}/,
// /browse/capability/{term}/, /browse/evaluation-method/{term}/, /browse/lifecycle/{term}/, /browse/access/{term}/ and
// /browse/org/{id}/, and its filter grammar filters on `acc` (access), not on "data properties". So a facet with
// one field browses under the facet (domain, capability, evaluation-method, subject, ceiling-anchor-type,
// maintenance-status), and a facet with several fields browses each field under the field's own name: data
// properties' access, refresh, data-provenance and contamination-risk; lifecycle's lifecycle and activity;
// governance's maintainer-type, submission-process and independence-flags; execution's compute-tier,
// reproducibility-tier, reproducibility-blockers and harness-availability. Every page is then one value of one field.
// Execution's `wet-lab` is two pages, a compute tier and a reproducibility blocker, because it is two terms (9c).
// This is the spelling the detail page's chips already link (views/BenchmarkDetail.astro).
//
// Which values get a page. Every term of every facet vocabulary in taxonomy/ (lib/terms.ts reads them), whether or not
// a published benchmark carries it. A term with no member gets a page that says so, because "the gaps are the product"
// (10 V11), and every /taxonomy/ term page links its browse page. A derived term (maintenance_status, computed from
// observable signals that no build stage derives yet) gets a page saying its members are derived and not listed.
// Organisations get /browse/org/{id}/ only if they are published and governance.maintainers names them on a published
// benchmark. An organisation's value set is the corpus's, not a closed vocabulary's, so one that maintains nothing has
// no gap to show, and its profile is /orgs/{id}/. Over an empty corpus (no entry is published yet) that is one page
// per vocabulary term, each in its empty state, and no organisation page.
//
// Membership is terms.ts members(), the rule the /taxonomy/ term pages list members by, so the two never disagree. A
// domain page keeps the benchmarks whose primary domain it is apart from those holding it as a secondary domain.
//
// terms.ts is imported with its extension so that Node can load this module as it is, stripping the types itself, and
// test/browse-routes.test.mjs can call browsePages() on records of its own.
import { facetFiles, members, type TaxTerm } from './terms.ts';
import type { Benchmark } from '../types/benchmark';
import type { Organization } from '../types/organization';

/** The segment a term browses under: the last part of its `field`, or its facet, in kebab case (data.access -> access,
 *  evaluation_method -> evaluation-method). */
export const browseSegment = (t: Pick<TaxTerm, 'facet' | 'field'>) => (t.field ?? t.facet).split('.').pop()!.replace(/_/g, '-');
export const browseHref = (t: Pick<TaxTerm, 'facet' | 'field' | 'id'>) => `/browse/${browseSegment(t)}/${t.id}/`;

/** /browse/org/{id}/: the benchmarks an organisation maintains (10 V11). */
export const ORG_SEGMENT = 'org';
export const orgBrowseHref = (id: string) => `/browse/${ORG_SEGMENT}/${id}/`;

export interface Member {
  benchmark: Benchmark;
  secondary: boolean;           // a domain page only: the domain is one of its secondaries, not its primary
}
export interface Neighbour {
  term: TaxTerm;
  count: number | null;         // benchmarks on its page; null for a derived term
}
export interface TermPage {
  kind: 'term';
  segment: string;
  term: TaxTerm;
  members: Member[] | null;     // null: a derived term, whose members are computed and never curated
  parent: TaxTerm | null;       // a subdomain's family
  families: Neighbour[];        // a domain page: the families, which head the spine
  children: Neighbour[];        // a domain page: its family's subdomains
  siblings: Neighbour[];        // any other page: every term of its segment, itself included
}
export interface OrgPage {
  kind: 'org';
  segment: typeof ORG_SEGMENT;
  org: Organization;
  members: Member[];
}
export type BrowsePage = TermPage | OrgPage;

const byName = (a: Member, b: Member) => a.benchmark.name.localeCompare(b.benchmark.name, 'en') || (a.benchmark.id < b.benchmark.id ? -1 : 1);

/** Every browse page over `benchmarks` and `organizations` (the published corpus), in taxonomy file and term order,
 *  then the organisations by id. Throws when two vocabularies would share a URL, so a page can never mean two things. */
export function browsePages(benchmarks: Benchmark[], organizations: Organization[], root?: string): BrowsePage[] {
  const terms = facetFiles(root).flatMap((f) => f.terms);
  const owner = new Map<string, string>();      // segment -> the facet and field it browses
  for (const t of terms) {
    const seg = browseSegment(t);
    const what = `${t.facet}${t.field != null ? ` field ${t.field}` : ''}`;
    if (seg === ORG_SEGMENT) throw new Error(`taxonomy ${what} browses under /browse/${seg}/, which is the organisation route`);
    if (owner.has(seg) && owner.get(seg) !== what) {
      throw new Error(`/browse/${seg}/ would hold two vocabularies: ${owner.get(seg)} and ${what}`);
    }
    owner.set(seg, what);
  }
  const listed = new Map(terms.map((t) => {
    const m = members(t, benchmarks);
    return [`${browseSegment(t)}/${t.id}`, m == null ? null : [...m].sort(byName)] as const;
  }));
  if (listed.size !== terms.length) throw new Error('two terms of one browse segment share an id, so one URL would name both');
  const count = (t: TaxTerm) => listed.get(`${browseSegment(t)}/${t.id}`)?.length ?? null;
  const neighbour = (t: TaxTerm): Neighbour => ({ term: t, count: count(t) });
  const domain = terms.filter((t) => t.facet === 'domain');
  const families = domain.filter((t) => t.parent == null).map(neighbour);

  const pages: BrowsePage[] = terms.map((t) => {
    const seg = browseSegment(t);
    const isDomain = t.facet === 'domain';
    const family = isDomain ? (t.parent ?? t.id) : null;
    return {
      kind: 'term', segment: seg, term: t, members: listed.get(`${seg}/${t.id}`) ?? null,
      parent: isDomain && t.parent != null ? domain.find((d) => d.id === t.parent) ?? null : null,
      families: isDomain ? families : [],
      children: isDomain ? domain.filter((d) => d.parent === family).map(neighbour) : [],
      siblings: isDomain ? [] : terms.filter((s) => browseSegment(s) === seg).map(neighbour),
    };
  });
  for (const org of [...organizations].sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))) {
    const maintained = benchmarks.filter((b) => (b.governance?.maintainers ?? []).includes(org.id))
      .map((b) => ({ benchmark: b, secondary: false })).sort(byName);
    if (maintained.length > 0) pages.push({ kind: 'org', segment: ORG_SEGMENT, org, members: maintained });
  }
  return pages;
}

/** The page's URL path below /browse/, as getStaticPaths' params: { facet, term }, `term` carrying a domain id's
 *  family (/browse/domain/code/repository-scale-se/). */
export const browseParams = (p: BrowsePage) => ({ facet: p.segment, term: p.kind === 'term' ? p.term.id : p.org.id });
