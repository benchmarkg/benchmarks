#!/usr/bin/env node
// scripts/route_js.mjs -- P2-S4-T08 (08 S8.1, 10 "Performance budget"). The JavaScript one built route ships, as files,
// so size-limit can measure it (site/.size-limit.js):
//
//   node scripts/route_js.mjs [ROUTE...]       # print each route's scripts and their gzipped bytes; default: /
//                                               # (a route may drop its leading slash, atlas/, which Git Bash would
//                                               # otherwise rewrite into a Windows path)
//
// 10's budgets are per route ("JS shipped"), and size-limit measures files, so a route's JavaScript is read from its built
// page, site/dist/<route>index.html, the way a browser would find it:
//   external   every <script src>, <link rel="modulepreload"> and island (<astro-island component-url, renderer-url,
//              before-hydration-url>) the page names, and every chunk those import, statically or by a literal dynamic
//              import(), transitively: everything the route can load, an upper bound rather than first paint only
//   inline     every inline <script> the browser runs -- 09 S9's pre-paint theme line among them -- and not a data block
//              (application/ld+json, application/json, importmap), which no browser runs
// What the route fetches as data (facets.json for the browse view; nothing for the landing, 08 S4.3) is not JavaScript and
// is not here: 10's JS budgets are counted over the data column, not with it.
//
// A local script this cannot find in dist/ throws, so a page that names a missing chunk fails the measurement rather than
// measuring less. Standard library only.
import { existsSync, readFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { dirname, join, posix, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const DATA_TYPES = new Set(['application/ld+json', 'application/json', 'importmap', 'speculationrules']);
const attr = (attrs, name) => new RegExp(`\\b${name}\\s*=\\s*("([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i').exec(attrs);
const value = (m) => (m == null ? null : m[2] ?? m[3] ?? m[4]);
// a chunk's relative imports in Vite's minified ESM: `import{a}from"./x.js"`, `import"./x.js"`, `export*from"./x.js"`,
// `import("./x.js")`
const IMPORTS = /(?:\bfrom\s*|\bimport\s*\(?\s*)(["'`])(\.{1,2}\/[^"'`]+?\.js)\1/g;

/** The built page of `route` ('/', '/atlas/') under `dist`. */
export function pagePath(dist, route) {
  const r = route.replace(/^\/+/, '');
  return join(dist, ...r.split('/').filter(Boolean), 'index.html');
}

/** {page, external: [absolute paths, sorted], inline: [script bodies, in page order]} for `route` of the build in `dist`. */
export function routeScripts(dist, route) {
  const page = pagePath(dist, route);
  if (!existsSync(page)) throw new Error(`${page} is missing: build the site first (cd site && npm run build)`);
  const html = readFileSync(page, 'utf8').replace(/<!--[\s\S]*?-->/g, '');
  const roots = new Set();
  const inline = [];
  const local = (url, from) => {
    if (url == null || /^[a-z]+:|^\/\//i.test(url)) return;               // another origin, or a data: URL
    const path = url.startsWith('/') ? join(dist, ...url.split(/[?#]/)[0].split('/').filter(Boolean)) : resolve(dirname(from), url);
    if (!existsSync(path)) throw new Error(`${relative(dist, from) || from} names ${url}, which is not in ${dist}`);
    roots.add(path);
  };
  for (const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
    const [, attrs, body] = m;
    const src = value(attr(attrs, 'src'));
    if (src != null) local(src, page);
    else if (!DATA_TYPES.has((value(attr(attrs, 'type')) ?? '').toLowerCase()) && body.trim() !== '') inline.push(body);
  }
  for (const m of html.matchAll(/<link\b([^>]*)>/gi)) {
    if (/\bmodulepreload\b/i.test(value(attr(m[1], 'rel')) ?? '')) local(value(attr(m[1], 'href')), page);
  }
  for (const m of html.matchAll(/<astro-island\b([^>]*)>/gi)) {
    for (const name of ['component-url', 'renderer-url', 'before-hydration-url']) local(value(attr(m[1], name)), page);
  }
  const seen = new Set();
  const queue = [...roots];
  while (queue.length > 0) {
    const file = queue.shift();
    if (seen.has(file)) continue;
    seen.add(file);
    for (const m of readFileSync(file, 'utf8').matchAll(IMPORTS)) {
      const dep = resolve(dirname(file), m[2]);
      if (!existsSync(dep)) throw new Error(`${relative(dist, file)} imports ${m[2]}, which is not in ${dist}`);
      queue.push(dep);
    }
  }
  return { page, external: [...seen].sort(), inline };
}

/** A path as a size-limit `path` entry: relative to `from`, with forward slashes, and refused when it holds a glob
 *  metacharacter, which size-limit would read as a pattern (Vite's chunk names never do). */
export function globSafe(path, from) {
  const rel = relative(from, path).split('\\').join(posix.sep);
  if (/[*?[\]{}()!]/.test(rel)) throw new Error(`${rel} holds a glob metacharacter; size-limit cannot name it as a path`);
  return rel;
}

const gz = (buf) => gzipSync(buf, { level: 9 }).length;

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const dist = join(fileURLToPath(new URL('..', import.meta.url)), 'site', 'dist');
  for (const route of process.argv.length > 2 ? process.argv.slice(2) : ['/']) {
    const { external, inline } = routeScripts(dist, route);
    let total = 0;
    console.log(route);
    for (const f of external) {
      const n = gz(readFileSync(f));
      total += n;
      console.log(`  ${String(n).padStart(8)} B gz  ${relative(dist, f).split('\\').join('/')}`);
    }
    inline.forEach((body, i) => {
      const n = gz(Buffer.from(body));
      total += n;
      console.log(`  ${String(n).padStart(8)} B gz  inline script ${i + 1}`);
    });
    console.log(`  ${String(total).padStart(8)} B gz  in all (${(total / 1024).toFixed(1)} KB)`);
  }
}
