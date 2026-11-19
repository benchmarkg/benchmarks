// site/src/lib/bench-routes.ts -- P2-S1-T04 (08 S3.4, the --routes-from-diff build mode). BENCH_ROUTES, read by every
// getStaticPaths() in src/pages/, so a preview build renders the routes a diff touches plus the fixed narrative routes.
//
// 08 S3.4: "A small integration reads `BENCH_ROUTES`, a newline-separated list of route paths computed by mapping
// `git diff --name-only <base>...<head>` through the entity-to-route map, and every `getStaticPaths()` filters to that
// list plus the fixed narrative routes. Preview builds then render tens of pages instead of thousands regardless of any
// caching feature, and `main` always renders everything." scripts/routes_from_diff.py writes the list, through
// tools/build/modes.py's map; this is the filter, and every page with a parameter passes its paths through onlyRoutes().
//
//   unset            every route: the default, and what main's build has
//   a build of main  every route, whatever BENCH_ROUTES says: a push to main, its scheduled rebuild or a manual run
//                    (GITHUB_REF on main and GITHUB_EVENT_NAME push, schedule or workflow_dispatch). build-preview.yml
//                    runs on workflow_run, whose GITHUB_REF is main too (08 S7.4), and it does filter: it builds a pull
//                    request's merge commit, not main
//   `*` on a line    every route: the diff touched something every route reads (a taxonomy term, a template)
//   a list           those routes and the fixed narrative routes. A route ending in `/` brings the routes beneath it,
//                    so /benchmarks/{id}/ brings its citation files and its superseded versions; one ending in a file
//                    name is that file. Blank lines are ignored, so an empty list renders the narrative routes alone
//
// The fixed narrative routes (08 S7.5's "Views, narrative pages, feeds | fixed") are every page without a parameter --
// /, /api/, /freshness/, /sources/, /feed/, the feeds, /ns/croissant-benchmark/v1/ -- which has no getStaticPaths() and
// always renders, and the two narrative families that have one, NARRATIVE: /docs/{slug}/ and /feed/{name}.xml.
// tools/build/modes.py holds the same parse and the same main rule for `bench build`'s note, and
// tests/build/test_routes_from_diff.py holds the two to each other. No import, so Node loads this file as the site does.

type Env = Record<string, string | undefined>;

export const EVERYTHING = '*';
export const MAIN_REF = 'refs/heads/main';
export const MAIN_EVENTS: readonly string[] = ['push', 'schedule', 'workflow_dispatch'];
export const NARRATIVE: readonly string[] = ['/docs/', '/feed/'];

/** A route as the filter compares it: rooted, and ending in `/` unless its last segment names a file. */
export function normalise(route: string): string {
  const r = `/${route.trim().replace(/^\/+/, '')}`;
  return r.endsWith('/') || (r.split('/').pop() ?? '').includes('.') ? r : `${r}/`;
}

/** A build of main itself, which renders everything whatever BENCH_ROUTES says. */
export function mainBuild(env: Env = process.env): boolean {
  return env.GITHUB_REF === MAIN_REF && MAIN_EVENTS.includes(env.GITHUB_EVENT_NAME ?? '');
}

/** The routes BENCH_ROUTES restricts this build to, sorted; null when it renders everything. */
export function benchRoutes(env: Env = process.env): string[] | null {
  const text = env.BENCH_ROUTES;
  if (text == null || mainBuild(env)) return null;
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l !== '');
  if (lines.includes(EVERYTHING)) return null;
  return [...new Set(lines.map(normalise))].sort();
}

/** Whether a build restricted to `listed` (null: unrestricted) renders `route`. */
export function rendered(route: string, listed: string[] | null): boolean {
  if (listed == null) return true;
  const r = normalise(route);
  if (NARRATIVE.some((n) => r.startsWith(n))) return true;
  return listed.some((l) => r === l || (l.endsWith('/') && r.startsWith(l)));
}

let announced = false;

/** `paths`, a getStaticPaths() result, filtered to what this build renders; `route` gives each one's URL path. */
export function onlyRoutes<T>(paths: T[], route: (path: T) => string, env: Env = process.env): T[] {
  const listed = benchRoutes(env);
  if (!announced && env.BENCH_ROUTES != null) {
    announced = true;
    console.log(listed == null
      ? `[bench-routes] BENCH_ROUTES is set, and every route renders (${mainBuild(env) ? 'a build of main' : '`*`'})`
      : `[bench-routes] BENCH_ROUTES: ${listed.length} listed route(s) and the fixed narrative routes; every other route is skipped (08 S3.4)`);
  }
  return listed == null ? paths : paths.filter((p) => rendered(route(p), listed));
}
