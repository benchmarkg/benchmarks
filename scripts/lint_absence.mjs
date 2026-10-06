#!/usr/bin/env node
// scripts/lint_absence.mjs -- P2-S2-T04. The absence rule of 09-design-system.md S13 and S11.2.
//
//   node scripts/lint_absence.mjs               # lint site/src/components/; exit 1 on any finding
//   node scripts/lint_absence.mjs PATH...       # lint these files or directories instead
//
// A missing value is a fact with a name -- not reported, not recorded, not applicable, unknown (09 S11.2) --
// rendered by <Absent>, never an empty string, a dash or nothing. So under components/ this fails on:
//   filler     `v || ''`, `v ?? ''`, `v ?? '—'` and the same with any filler a reader would take for a
//              value or a blank: '', ' ', '-', '–', '—', '?', 'n/a', 'N/A', 'NA', 'none', 'null'
//   guard      a truthiness-guarded value render: `{v && <b>{v}</b>}` or `{v ? <b>{v}</b> : ...}` or
//              `{v ? v : ...}`. A 0, a 0.0 or an empty string is a value, and the guard hides it; test
//              `v != null` (or `v === undefined`) and render <Absent> for the other branch
// Comments are not read. A guard on something that is not then rendered as content -- `{open && <Panel/>}`, or
// `{reason && <Marker reason={reason} />}`, which passes it on as an attribute -- is fine.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const DEFAULT = join(ROOT, 'site', 'src', 'components');
const EXTS = new Set(['.astro', '.tsx', '.jsx', '.ts', '.js', '.mjs']);
const FILLERS = ['', ' ', '-', '–', '—', '?', 'n/a', 'N/A', 'NA', 'none', 'null'];
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const FILLER = new RegExp(`(\\|\\||\\?\\?)\\s*(["'\`])(${FILLERS.map(esc).join('|')})\\2`, 'g');
const PATH = String.raw`[A-Za-z_$][\w$]*(?:\??\.[A-Za-z_$][\w$]*|\[\d+\])*`;
// `{` then a value path then && or a ternary ? (not ?. or ??), and not a comparison
const GUARD = new RegExp(String.raw`\{\s*(${PATH})\s*(&&|\?(?![?.]))`, 'g');

const lineOf = (text, index) => text.slice(0, index).split('\n').length;
const blank = (m) => m.replace(/[^\n]/g, ' ');

/** The text with comments blanked out (positions kept), so a pattern in a comment is not read. */
export function code(text) {
  return text.replace(/<!--[\s\S]*?-->/g, blank).replace(/\/\*[\s\S]*?\*\//g, blank)
    .replace(/(^|[^:'"`\\])\/\/[^\n]*/g, (m, p) => p + ' '.repeat(m.length - p.length));
}

/** From the `{` at `open`, the index of its matching `}` (strings skipped), or the end of the text. */
function close(text, open) {
  let depth = 0;
  for (let i = open; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"' || ch === "'" || ch === '`') {
      const end = text.indexOf(ch, i + 1);
      if (end > 0 && !text.slice(i, end).includes('\n')) { i = end; continue; }
    }
    if (ch === '{') depth++;
    else if (ch === '}' && --depth === 0) return i;
  }
  return text.length;
}

export function lintText(text) {
  const src = code(text);
  const out = [];
  for (const m of src.matchAll(FILLER)) {
    out.push({ rule: 'filler', index: m.index, msg: `${m[0]} renders a missing value as ${m[3] ? `'${m[3]}'` : 'nothing'}: use <Absent> with its phrase (09 S11.2)` });
  }
  for (const m of src.matchAll(GUARD)) {
    const [whole, value, op] = m;
    const body = src.slice(m.index + whole.length, close(src, m.index));
    // rendered as content: {v} or {v.x}, not passed on as an attribute (reason={reason} is not a render)
    const rendered = new RegExp(String.raw`(?<!=\s*)\{\s*${esc(value)}(?![\w$])`).test(body);
    const ternaryItself = op !== '&&' && new RegExp(String.raw`^\s*${esc(value)}(?![\w$])\s*:`).test(body);
    if (rendered || ternaryItself) {
      out.push({ rule: 'guard', index: m.index, msg: `{${value} ${op} ...} hides a 0 or an empty value: test ${value} != null and render <Absent> otherwise` });
    }
  }
  return out.sort((a, b) => a.index - b.index).map((f) => ({ ...f, line: lineOf(text, f.index) }));
}

export function* walk(target) {
  if (statSync(target).isFile()) { yield target; return; }
  for (const name of readdirSync(target).sort()) {
    if (name === 'node_modules' || name.startsWith('.')) continue;
    yield* walk(join(target, name));
  }
}

export function lint(targets) {
  const out = [];
  for (const t of targets) {
    for (const f of walk(t)) {
      if (!EXTS.has(extname(f)) || f.endsWith('.d.ts')) continue;
      out.push(...lintText(readFileSync(f, 'utf8')).map((x) => ({ ...x, file: f })));
    }
  }
  return out;
}

function main(argv) {
  const targets = argv.length ? argv.map((p) => resolve(p)) : [DEFAULT];
  for (const t of targets) {
    if (!existsSync(t)) { console.error(`lint_absence: ${t} does not exist`); return 2; }
  }
  const found = lint(targets);
  for (const f of found) console.error(`${relative(ROOT, f.file).split(sep).join('/')}:${f.line}: [${f.rule}] ${f.msg}`);
  console.log(`lint_absence: ${found.length} finding(s) in ${targets.map((t) => relative(ROOT, t).split(sep).join('/') || '.').join(', ')}`);
  return found.length ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) process.exitCode = main(process.argv.slice(2));
