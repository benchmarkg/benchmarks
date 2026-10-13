// site/worker/redirects.ts -- P2-S3-T08 (04 S3; 08 S7.2). The tombstone 301s: a published citation to a merged id's
// page keeps resolving, to the page of the id it merged into.
//
// The table is site/worker/redirects.json, which tools/build/redirects.py writes from data/tombstones/ (chains
// collapsed, so one hop). The Worker that imports this (site/worker/index.ts, the deploy task's) runs on an asset
// miss -- a tombstoned id has no page, so its path is exactly a miss -- and never first: 08 S7.2 keeps
// run_worker_first off every citable path. The rest of the path after the id is kept, so /benchmarks/{old}/v/{ver}/
// lands on /benchmarks/{new}/v/{ver}/, and so is the query string.
import TABLE from './redirects.json' with { type: 'json' };

export interface Redirect {
  from: string;     // '/benchmarks/{old}/'
  to: string;       // '/benchmarks/{new}/'
  status: 301;
}
export interface RedirectTable {
  artifact: 'redirects';
  format: number;
  redirects: Redirect[];
}

/** The 301 for a request URL, or null when no tombstone covers its path. `/benchmarks/old` (no trailing slash)
 *  is the same page as `/benchmarks/old/`. */
export function redirect(url: URL, table: RedirectTable = TABLE as RedirectTable): Response | null {
  const path = url.pathname.endsWith('/') ? url.pathname : `${url.pathname}/`;
  for (const r of table.redirects) {
    if (path.startsWith(r.from)) {
      const rest = url.pathname.length > r.from.length ? url.pathname.slice(r.from.length) : '';
      const location = new URL(r.to + rest + url.search, url);
      return new Response(null, { status: r.status, headers: { Location: location.toString() } });
    }
  }
  return null;
}
