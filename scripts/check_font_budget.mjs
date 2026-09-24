#!/usr/bin/env node
// scripts/check_font_budget.mjs -- P2-S2-T05. The font rules of 09-design-system.md S12.1-12.2.
//
//   node scripts/check_font_budget.mjs           # check; exit 1 on any failure
//   node scripts/check_font_budget.mjs --print   # print the measured fallback @font-face blocks
//
// Checks:
//   budget     every face in site/public/fonts/ together <= 120 KB, read as 120,000 bytes (the
//              stricter of the two readings), and every face is really WOFF2
//   preload    at most two faces preloaded, and exactly the sans and the mono, never the
//              condensed -- across site/src/ and, when it exists, every built page in site/dist/;
//              each preload is as="font" type="font/woff2" crossorigin (09 S12.1)
//   swap       every @font-face in site/src/styles/type.css that downloads a file sets
//              font-display: swap, and the file exists
//   measured   each metric-compatible fallback alias carries size-adjust, ascent-override,
//              descent-override and line-gap-override, and each value equals what Capsize's
//              fallback generator computes today from the SHIPPED subset -- so a value copied
//              from anywhere else, or left behind after the subsets change, fails (09 S12.2)
//
// Capsize lives in site/node_modules (devDependencies of site/package.json): run `npm ci` in
// site/ first.
import { createRequire } from 'node:module';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SITE = join(ROOT, 'site');
const FONTS = join(SITE, 'public', 'fonts');
const TYPE_CSS = join(SITE, 'src', 'styles', 'type.css');
const BUDGET_BYTES = 120_000;
const PRELOAD = new Set(['/fonts/plex-sans.woff2', '/fonts/plex-mono.woff2']);
// Each fallback alias of 09 S3.1, the shipped face it stands in for, and the local face under it.
const FALLBACKS = [
  { family: 'Plex Fallback', face: 'plex-sans.woff2', metrics: 'arial' },
  { family: 'Plex Mono Fallback', face: 'plex-mono.woff2', metrics: 'courierNew' },
];

const failures = [];
const fail = (msg) => failures.push(msg);

async function siteImport(spec) {
  const req = createRequire(join(SITE, 'package.json'));
  let path;
  try {
    path = req.resolve(spec);
  } catch {
    console.error(`cannot resolve ${spec} from site/: run \`npm ci\` in site/ first`);
    process.exit(2);
  }
  // The ESM build, when the package has one.
  const esm = path.replace(/\.cjs$/, '.mjs');
  return import(pathToFileURL(existsSync(esm) ? esm : path).href);
}

async function measure() {
  const { fromFile } = await siteImport('@capsizecss/unpack/fs');
  const { createFontStack } = await siteImport('@capsizecss/core');
  const out = [];
  for (const fb of FALLBACKS) {
    const metrics = await fromFile(join(FONTS, fb.face));
    const local = (await siteImport(`@capsizecss/metrics/${fb.metrics}`)).default;
    const [face] = createFontStack([metrics, local], { fontFaceFormat: 'styleObject' }).fontFaces;
    const f = face['@font-face'];
    // Capsize omits an override that equals the local face's own value (Courier New's line gap,
    // for one). Stating it explicitly is harmless and keeps every alias carrying all four, so it
    // is filled in here with Capsize's own formula and rounding.
    const sizeAdjust = parseFloat(f.sizeAdjust ?? '100') / 100;
    const own = (v) => `${parseFloat((v / (metrics.unitsPerEm * sizeAdjust) * 100).toFixed(4))}%`;
    out.push({ ...fb, src: f.src, values: {
      'size-adjust': f.sizeAdjust ?? '100%',
      'ascent-override': f.ascentOverride ?? own(metrics.ascent),
      'descent-override': f.descentOverride ?? own(Math.abs(metrics.descent)),
      'line-gap-override': f.lineGapOverride ?? own(metrics.lineGap) } });
  }
  return out;
}

function fontFaceBlocks(css) {
  const blocks = [];
  const re = /@font-face\s*\{([^}]*)\}/g;
  let m;
  while ((m = re.exec(css.replace(/\/\*[\s\S]*?\*\//g, '')))) {
    const props = {};
    for (const decl of m[1].split(';')) {
      const i = decl.indexOf(':');
      if (i > 0) props[decl.slice(0, i).trim().toLowerCase()] = decl.slice(i + 1).trim();
    }
    blocks.push(props);
  }
  return blocks;
}

const unquote = (s) => (s || '').replace(/^['"]|['"]$/g, '');

function walk(dir, exts) {
  if (!existsSync(dir)) return [];
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p, exts));
    else if (exts.some((e) => name.endsWith(e))) out.push(p);
  }
  return out.sort();
}

function checkBudget() {
  const faces = readdirSync(FONTS).filter((f) => f.endsWith('.woff2')).sort();
  if (!faces.length) fail('no .woff2 faces in site/public/fonts/');
  let total = 0;
  for (const f of faces) {
    const buf = readFileSync(join(FONTS, f));
    if (buf.subarray(0, 4).toString('latin1') !== 'wOF2') fail(`${f} is not WOFF2`);
    total += buf.length;
    console.log(`  ${f.padEnd(24)} ${String(buf.length).padStart(7)} bytes`);
  }
  console.log(`  ${'total'.padEnd(24)} ${String(total).padStart(7)} bytes of ${BUDGET_BYTES}`);
  if (total > BUDGET_BYTES) fail(`faces total ${total} bytes, over the ${BUDGET_BYTES}-byte budget`);
}

function checkPreloads() {
  const files = [...walk(join(SITE, 'src'), ['.astro', '.html', '.jsx', '.tsx']),
                 ...walk(join(SITE, 'dist'), ['.html'])];
  const all = new Set();
  for (const file of files) {
    const text = readFileSync(file, 'utf8');
    const here = new Set();
    for (const [tag] of text.matchAll(/<link\b[^>]*>/gi)) {
      if (!/\brel\s*=\s*["']?preload/i.test(tag) || !/\bas\s*=\s*["']?font/i.test(tag)) continue;
      const href = (tag.match(/\bhref\s*=\s*["']([^"']+)["']/i) || [])[1];
      const where = relative(ROOT, file).split(sep).join('/');
      if (!/\btype\s*=\s*["']font\/woff2["']/i.test(tag)) fail(`${where}: preload ${href} lacks type="font/woff2"`);
      if (!/\bcrossorigin\b/i.test(tag)) fail(`${where}: preload ${href} lacks crossorigin`);
      if (/condensed/i.test(href || '')) fail(`${where}: preloads the condensed face (${href})`);
      here.add(href);
      all.add(href);
    }
    if (here.size > 2) fail(`${relative(ROOT, file).split(sep).join('/')} preloads ${here.size} faces: ${[...here].join(', ')}`);
  }
  const want = [...PRELOAD].sort().join(', ');
  const got = [...all].sort().join(', ');
  console.log(`  preloaded: ${got || '(none)'}`);
  if (got !== want) fail(`preloaded faces are [${got}], want exactly [${want}]`);
}

async function checkTypeCss() {
  if (!existsSync(TYPE_CSS)) return fail('site/src/styles/type.css is missing');
  const blocks = fontFaceBlocks(readFileSync(TYPE_CSS, 'utf8'));
  for (const b of blocks) {
    const urls = [...(b.src || '').matchAll(/url\(\s*['"]?([^'")]+)['"]?\s*\)/g)].map((m) => m[1]);
    if (!urls.length) continue;
    const fam = unquote(b['font-family']);
    if (b['font-display'] !== 'swap') fail(`@font-face ${fam}: font-display is ${b['font-display'] ?? 'unset'}, want swap`);
    for (const u of urls) {
      if (!u.startsWith('/fonts/') || !existsSync(join(FONTS, u.slice('/fonts/'.length)))) {
        fail(`@font-face ${fam}: ${u} is not a shipped face in site/public/fonts/`);
      }
    }
  }
  for (const m of await measure()) {
    const b = blocks.find((x) => unquote(x['font-family']) === m.family);
    if (!b) { fail(`type.css has no @font-face for "${m.family}"`); continue; }
    if (/url\(/.test(b.src || '')) fail(`"${m.family}" must be local-only, it downloads a file`);
    for (const [prop, want] of Object.entries(m.values)) {
      if (b[prop] !== want) {
        fail(`"${m.family}" ${prop} is ${b[prop] ?? 'unset'}; measured from ${m.face} it is ${want}` +
             ' (run with --print)');
      }
    }
    console.log(`  ${m.family}: ${Object.entries(m.values).map(([k, v]) => `${k} ${v}`).join(', ')}`);
  }
}

if (process.argv.includes('--print')) {
  for (const m of await measure()) {
    console.log(`/* Measured by scripts/check_font_budget.mjs from site/public/fonts/${m.face}` +
                ` against @capsizecss/metrics/${m.metrics}. */`);
    console.log(`@font-face {\n  font-family: "${m.family}";\n  src: ${m.src};`);
    for (const [k, v] of Object.entries(m.values)) console.log(`  ${k}: ${v};`);
    console.log('}');
  }
  process.exit(0);
}

console.log('budget');
checkBudget();
console.log('preload');
checkPreloads();
console.log('type.css');
await checkTypeCss();
for (const f of failures) console.log(`FAIL ${f}`);
console.log(failures.length ? `${failures.length} failure(s)` : 'font budget ok');
process.exit(failures.length ? 1 : 0);
