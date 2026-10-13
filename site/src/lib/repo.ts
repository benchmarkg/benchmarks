// site/src/lib/repo.ts -- P2-S2-T06. Where the catalogue's files live, for the links that cite them at a commit.
export const REPO = 'https://github.com/benchmarkg/benchmarks';

/** A file at a commit: the permalink 09 S6.5 and S6.13 cite. */
export const blobAt = (sha: string, path: string) => `${REPO}/blob/${sha}/${path}`;
export const rawAt = (sha: string, path: string) => `${REPO}/raw/${sha}/${path}`;
export const editOnMain = (path: string) => `${REPO}/edit/main/${path}`;

/** The correction issue form (.github/ISSUE_TEMPLATE/correction.yml, P2-S6-T02), pre-filled through its field ids:
 *  `entity` and, beside a field, `field` -- both plain text inputs, because a query parameter is only known to
 *  prefill an input or a textarea; dropdown prefill is unverified (P2-S6-T05). {entity_id} is substituted. */
export const CORRECTION_FORM = `${REPO}/issues/new?template=correction.yml&entity={entity_id}&title=Correction%3A+{entity_id}`;

/** The correction form for one entity, and for one of its fields when `field` names it (as its YAML path, for
 *  example data.access), with a title that says which. */
export function correctionHref(entity_id: string, field?: string): string {
  const q = new URLSearchParams({ template: 'correction.yml', entity: entity_id });
  if (field != null) q.set('field', field);
  q.set('title', `Correction: ${entity_id}${field != null ? ` (${field})` : ''}`);
  return `${REPO}/issues/new?${q.toString()}`;
}

export function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (m, k) => (k in values ? encodeURIComponent(values[k]) : m));
}

/** A commit SHA: 7 to 40 lowercase hex characters. A permalink at anything else is not a permalink. */
export function sha(s: string): string {
  if (!/^[0-9a-f]{7,40}$/.test(s)) throw new Error(`${JSON.stringify(s)} is not a commit SHA`);
  return s;
}
