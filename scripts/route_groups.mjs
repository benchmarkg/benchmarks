#!/usr/bin/env node
// scripts/route_groups.mjs -- P2-S8-T01 (08 S8.1, 10 "Performance budget"). The route groups of scripts/route_groups.json,
// read against a built site as the checks size-limit runs (site/.size-limit.js):
//
//   node scripts/route_groups.mjs [DIST]       # every family, its group, budget and built pages; default: site/dist
//
// Every page of the build (each index.html under dist/) belongs to exactly one family of route_groups.json, or to an
// ignored route. A page that no family claims, or that two claim, throws, so a new route family cannot pass the gate
// unmeasured (10: the gate "also fails when a route in the URL scheme above maps to no row in that table"); and a family
// with no built page throws, unless it is `pending` the task that routes it, because a check over no page has measured
// nothing. Each family then becomes size-limit checks:
//   js "0 B"     every script byte of every page in the family, but 09 S9's pre-paint line, which 09 S9 allows on every
//                page and tests/detail-nojs.spec.ts allows the same way. Counted raw, not gzipped: zero is zero either
//                way, and gzip makes even an empty file 20 bytes. size-limit fails a check that names no file ("missed"),
//                so each names an empty file too, which weighs 0 B
//   js limit     the JavaScript of the family's heaviest page as route_js.mjs finds it, every script, gzip -9 per file (the
//                landing's 40 KB, P2-S4-T08, and the Atlas's 120 KB)
//   js null      the same measurement, printed with no limit; the family's `budget` says why
//   weight       the heaviest page of the family by what a reader downloads for it (08 S8.1 row 3, "including fonts"):
//                the HTML, its stylesheets, scripts and images as their gzip -9 copies, written to the cache, and its
//                fonts (and any raster image) as they are, since a woff2 is compressed already and is not compressed
//                again in transit. Gzipping one anyway would make it a little smaller (plex-sans.woff2: 37,076 bytes,
//                36,819 gzipped), so the raw count is the larger and the honest one. Measured raw, as the sum of those
//                files
// The pre-paint line must be byte-identical on every page, so the one script a 0 KB page may carry is the shared line of
// theme.ts and never a page's own.
//
// Fonts are read from the page's own CSS, its inline <style> blocks and linked stylesheets. A face counts when the page
// preloads it, or when a font-family or font declaration of that CSS names its family (custom properties followed); an
// italic face only when the page also sets something in italic (an em, i, cite, var, dfn or address element, or
// font-style: italic). That is an upper bound: a rule that matches no element still counts its face. Standard library
// only.
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { attrValue, globSafe, localFile, routeScripts } from './route_js.mjs';

export const GROUPS_FILE = fileURLToPath(new URL('route_groups.json', import.meta.url));

/** route_groups.json as {families: [{route, group, title, js, weight?, pending?, budget?, basis}], ignored}. */
export function loadGroups(file = GROUPS_FILE) {
  const doc = JSON.parse(readFileSync(file, 'utf8'));
  const families = [];
  for (const g of doc.groups) {
    for (const f of g.families) {
      if (f.js !== null && typeof f.js !== 'string') throw new Error(`${f.route}: js is a size-limit limit ('0 B', '120 KiB') or null`);
      if (f.js === null && !f.budget) throw new Error(`${f.route}: a family with no JavaScript budget says why, in budget`);
      families.push({ ...f, group: g.group, title: g.title });
    }
  }
  return { families, ignored: doc.ignored ?? [] };
}

/** A family's route as a RegExp over built routes: {name} is one path segment, {...name} one or more. */
export function routeRegExp(route) {
  const body = route.split(/(\{[^}]+\})/).map((part) => {
    if (part.startsWith('{...')) return '[^/]+(?:/[^/]+)*';
    if (part.startsWith('{')) return '[^/]+';
    return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }).join('');
  return new RegExp(`^${body}$`);
}

/** Every page of the build in `dist`, as its route ('/', '/atlas/', '/benchmarks/mmlu/'), sorted. An .html file that
 *  is not an index.html throws: route_js.mjs reads a route's page as <route>index.html, and the site builds no other. */
export function builtRoutes(dist) {
  if (!existsSync(join(dist, 'index.html'))) throw new Error(`${dist} holds no built site: build it first (cd site && npm run build)`);
  const out = [];
  const walk = (dir, parts) => {
    for (const d of readdirSync(dir, { withFileTypes: true })) {
      if (d.isDirectory()) walk(join(dir, d.name), [...parts, d.name]);
      else if (d.name === 'index.html') out.push('/' + parts.map((p) => p + '/').join(''));
      else if (d.name.endsWith('.html')) throw new Error(`${[...parts, d.name].join('/')}: a page that is not <route>/index.html`);
    }
  };
  walk(dist, []);
  return out.sort();
}

/** Each family with its built pages, [{...family, pages}]. Throws on a page that no family (and no ignored route) claims,
 *  on one that two claim, and on a family that has no page and is not pending. */
export function assignPages({ families, ignored }, routes) {
  const rows = families.map((f) => ({ ...f, re: routeRegExp(f.route), pages: [] }));
  const skip = ignored.map((i) => routeRegExp(i.route));
  const unclaimed = [];
  for (const r of routes) {
    if (skip.some((re) => re.test(r))) continue;
    const hit = rows.filter((f) => f.re.test(r));
    if (hit.length > 1) throw new Error(`${r} is claimed by ${hit.map((f) => f.route).join(' and ')}: a page has one family`);
    if (hit.length === 0) unclaimed.push(r);
    else hit[0].pages.push(r);
  }
  if (unclaimed.length > 0) {
    throw new Error(`no family in scripts/route_groups.json claims ${unclaimed.length} built page(s), so no budget gates them: `
      + `${unclaimed.slice(0, 5).join(', ')}${unclaimed.length > 5 ? ', ...' : ''}; give the route family a row`);
  }
  const empty = rows.filter((f) => f.pages.length === 0 && !f.pending);
  if (empty.length > 0) {
    throw new Error(`no page was built for ${empty.map((f) => f.route).join(', ')}, so the gate would measure nothing: build the site `
      + 'over the draft preview (scripts/preview_corpus.py, UAIBI_CORPUS, UAIBI_SITE_DRAFTS=1), or mark the family pending the task that routes it');
  }
  return rows.map(({ re, ...f }) => f);
}

const FACE = /@font-face\s*\{([^}]*)\}/gi;
const ITALIC_ELEMENT = /<(?:em|i|cite|var|dfn|address)\b/i;
const unquote = (s) => s.trim().replace(/^(["'])(.*)\1$/, '$2');

/** The @font-face rules of `css` that download a file: [{family, style, url}]. */
export function fontFaces(css) {
  const out = [];
  for (const m of css.matchAll(FACE)) {
    const family = /font-family\s*:\s*([^;]+)/i.exec(m[1]);
    const url = /url\(\s*(["']?)([^"')]+)\1\s*\)/i.exec(m[1]);
    const style = /font-style\s*:\s*([^;]+)/i.exec(m[1]);
    if (family && url) out.push({ family: unquote(family[1]), style: style ? style[1].trim().toLowerCase() : 'normal', url: url[2] });
  }
  return out;
}

/** The font families `css` sets on anything, lower-cased: each family a font-family or font declaration names outside
 *  @font-face, a var(--x) followed to every value --x is given. */
export function usedFamilies(css) {
  const body = css.replace(FACE, '');
  const vars = new Map();
  for (const m of body.matchAll(/(--[\w-]+)\s*:\s*([^;}]+)/g)) vars.set(m[1], [...(vars.get(m[1]) ?? []), m[2]]);
  const expand = (v, depth) => (depth > 8 ? v : v.replace(/var\(\s*(--[\w-]+)\s*(?:,([^)]*))?\)/g,
    (_, name, fallback) => (vars.get(name) ?? [fallback ?? '']).map((x) => expand(x, depth + 1)).join(',')));
  const names = new Set();
  for (const m of body.matchAll(/(?:^|[;{\s])font(?:-family)?\s*:\s*([^;}]+)/gi)) {
    for (const item of expand(m[1], 0).split(',')) {
      const quoted = /(["'])([^"']+)\1\s*$/.exec(item.trim());
      names.add((quoted ? quoted[2] : item.trim()).toLowerCase());
    }
  }
  return names;
}

/** What a reader downloads for `route` of the build in `dist`: the page, its stylesheets, images and scripts, and the fonts
 *  it can use, as absolute paths. */
export function pageFiles(dist, route) {
  const { page, external } = routeScripts(dist, route);
  const html = readFileSync(page, 'utf8').replace(/<!--[\s\S]*?-->/g, '');
  const files = new Set([page, ...external]);
  const sheets = [...html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style\s*>/gi)].map((m) => ({ css: m[1], from: page }));
  for (const m of html.matchAll(/<link\b([^>]*)>/gi)) {
    const rel = (attrValue(m[1], 'rel') ?? '').toLowerCase().split(/\s+/);
    const file = rel.includes('stylesheet') || (rel.includes('preload') && attrValue(m[1], 'as') === 'font')
      ? localFile(dist, page, attrValue(m[1], 'href')) : null;
    if (file == null) continue;
    files.add(file);
    if (rel.includes('stylesheet')) sheets.push({ css: readFileSync(file, 'utf8'), from: file });
  }
  for (const m of html.matchAll(/<img\b([^>]*)>/gi)) {
    const file = localFile(dist, page, attrValue(m[1], 'src'));
    if (file != null) files.add(file);
  }
  const css = sheets.map((s) => s.css).join('\n');
  const used = usedFamilies(css);
  const italic = ITALIC_ELEMENT.test(html) || /font-style\s*:\s*(?:italic|oblique)/i.test(css.replace(FACE, ''));
  for (const { css: text, from } of sheets) {
    for (const face of fontFaces(text)) {
      if (!used.has(face.family.toLowerCase()) || (face.style !== 'normal' && !italic)) continue;
      const file = localFile(dist, from, face.url);
      if (file != null) files.add(file);
    }
  }
  return [...files].sort();
}

/** A file's gzip -9 size, as @size-limit/file measures it. */
export const gzipBytes = (file) => gzipSync(readFileSync(file), { level: 9 }).length;
/** The files a page's weight counts as they are: fonts and raster images, compressed already and not again in transit. */
export const SENT_AS_IS = /\.(?:woff2?|png|jpe?g|gif|webp|avif)$/i;

/** size-limit's checks for every family of route_groups.json over the build in `dist`. The inline scripts they measure,
 *  and the empty file, are written to `cache` (emptied first); every path is relative to `from`, site/. */
export function sizeLimitChecks({ dist, cache, from, groups = loadGroups() }) {
  const families = assignPages(groups, builtRoutes(dist));
  rmSync(cache, { recursive: true, force: true });
  mkdirSync(cache, { recursive: true });
  const none = join(cache, 'no-javascript.js');
  writeFileSync(none, '');
  let written = 0;
  const write = (body) => {
    const file = join(cache, `inline-${++written}.js`);
    writeFileSync(file, body);
    return file;
  };
  const paths = (files) => files.map((f) => globSafe(f, from));
  const prepaint = new Map();                       // pre-paint body -> a route that carries it
  const scripts = new Map();
  const scriptsOf = (route) => {
    if (!scripts.has(route)) {
      const s = routeScripts(dist, route);
      if (s.prepaint != null && !prepaint.has(s.prepaint)) prepaint.set(s.prepaint, route);
      scripts.set(route, s);
    }
    return scripts.get(route);
  };
  const gz = new Map();                             // file -> gzip -9 bytes: the stylesheets and chunks recur on every page
  const gzipped = (file) => {
    if (!gz.has(file)) gz.set(file, gzipBytes(file));
    return gz.get(file);
  };
  const delivered = (file) => (SENT_AS_IS.test(file) ? statSync(file).size : gzipped(file));
  const heaviest = (pages, filesOf, size) => pages
    .map((route) => { const files = filesOf(route); return { route, files, bytes: files.reduce((n, f) => n + size(f), 0) }; })
    .reduce((a, b) => (b.bytes > a.bytes ? b : a));
  const checks = [];
  for (const f of families) {
    const n = f.pages.length;
    const label = `${f.group}: ${f.route}`;
    const of = n === 1 ? '' : `, the heaviest of ${n} pages`;
    if (n === 0) {
      checks.push({ name: `${label} JavaScript: no page built yet, ${f.pending} routes it`, path: paths([none]), brotli: false, limit: f.js });
      continue;
    }
    if (f.js === '0 B') {
      const files = new Set();
      const bodies = new Set();
      for (const route of f.pages) {
        const { external, inline, prepaint: line } = scriptsOf(route);
        external.forEach((x) => files.add(x));
        const rest = [...inline];
        if (line != null) rest.splice(rest.indexOf(line), 1);
        rest.forEach((b) => bodies.add(b));
      }
      checks.push({
        name: `${label} JavaScript on ${n === 1 ? 'its page' : `all ${n} pages`}, raw bytes, 09 S9's pre-paint line allowed`,
        path: paths([none, ...[...files].sort(), ...[...bodies].map(write)]), brotli: false, limit: f.js,
      });
    } else {
      const top = heaviest(f.pages, (route) => {
        const { external, inline } = scriptsOf(route);
        return [...external, ...inline.map(write)];
      }, gzipped);
      // a page with no script at all names the empty file, raw: gzip would weigh it 20 bytes
      const measured = top.files.length > 0 ? { path: paths(top.files), gzip: true } : { path: paths([none]), brotli: false };
      const check = { name: `${label} JavaScript, gzip -9${of}${n === 1 ? '' : ` (${top.route})`}`, ...measured };
      if (f.js === null) check.name += ': no budget yet (scripts/route_groups.json says why)';
      else check.limit = f.js;
      checks.push(check);
    }
    if (f.weight) {
      const top = heaviest(f.pages, (route) => pageFiles(dist, route), delivered);
      const sent = top.files.map((file) => {
        if (SENT_AS_IS.test(file)) return file;
        const copy = join(cache, `weight-${++written}-${basename(file)}.gz`);
        writeFileSync(copy, gzipSync(readFileSync(file), { level: 9 }));
        return copy;
      });
      checks.push({
        name: `${label} page weight: HTML, CSS, scripts and images gzip -9, fonts as sent${of}${n === 1 ? '' : ` (${top.route})`}`,
        path: paths(sent), brotli: false, limit: f.weight,
      });
    }
  }
  if (prepaint.size > 1) {
    throw new Error(`the pre-paint line differs between pages (${[...prepaint.values()].join(', ')}): 09 S9 allows the one line `
      + 'theme.ts writes, the same on every page');
  }
  return checks;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const dist = process.argv[2] ?? join(dirname(fileURLToPath(import.meta.url)), '..', 'site', 'dist');
  for (const f of assignPages(loadGroups(), builtRoutes(dist))) {
    const budget = [f.js === null ? 'JS not budgeted' : `JS ${f.js}`, f.weight ? `weight ${f.weight}` : null].filter(Boolean).join(', ');
    const pages = f.pages.length > 0 ? `${f.pages.length} page${f.pages.length === 1 ? '' : 's'}` : `no page yet (${f.pending})`;
    console.log(`${f.group.padEnd(12)} ${f.route.padEnd(32)} ${budget.padEnd(28)} ${pages}`);
  }
}
