// site/src/lib/repo.ts -- P2-S2-T06. Where the catalogue's files live, for the links that cite them at a commit.
export const REPO = 'https://github.com/benchmarkg/benchmarks';

/** A file at a commit: the permalink 09 S6.5 and S6.13 cite. */
export const blobAt = (sha: string, path: string) => `${REPO}/blob/${sha}/${path}`;
export const rawAt = (sha: string, path: string) => `${REPO}/raw/${sha}/${path}`;
export const editOnMain = (path: string) => `${REPO}/edit/main/${path}`;

/** The correction issue form (.github/ISSUE_TEMPLATE/correction.yml, from the task "Author the five issue forms"),
 *  pre-filled through its field ids. {entity_id} and {entity_kind} are substituted. */
export const CORRECTION_FORM = `${REPO}/issues/new?template=correction.yml&entity_id={entity_id}&entity_kind={entity_kind}`
  + '&title=Correction%3A+{entity_id}';

export function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (m, k) => (k in values ? encodeURIComponent(values[k]) : m));
}

/** A commit SHA: 7 to 40 lowercase hex characters. A permalink at anything else is not a permalink. */
export function sha(s: string): string {
  if (!/^[0-9a-f]{7,40}$/.test(s)) throw new Error(`${JSON.stringify(s)} is not a commit SHA`);
  return s;
}
