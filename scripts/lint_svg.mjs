#!/usr/bin/env node
// scripts/lint_svg.mjs -- P2-S2-T04. The 11px floor of 09-design-system.md S3.2 and S13, in built SVG.
//
//   node scripts/lint_svg.mjs [DIR]       # walk DIR (default site/dist/); exit 1 on any text below 11px
//
// "11px is an absolute floor, including inside SVG charts, and a lint check walks the built SVG to enforce it"
// (09 S3.2). Every .svg file and every inline <svg> in an .html file is read, and each <text>, <tspan> and
// <textPath> with any text in it is given the size it renders at:
//
//   - its font-size: the element's style="" over its font-size="" attribute over the last matching rule of a
//     <style> block in the same file (selectors text / tspan / textPath / * / .class / tag.class, the last
//     compound of each selector), else inherited from its parent, else 16px at the root;
//   - in px, pt (4/3 px), unitless (SVG user units, read as px), rem (16px), em and % (of the parent), or a
//     keyword (xx-small 9, x-small 10, small 13, medium 16, ...; smaller / larger divide or multiply by 1.2);
//   - times the scale of every enclosing <svg> that has a viewBox and a width (or height) in px or unitless:
//     a chart drawn at 11 units in a 600-unit viewBox shown 300px wide renders at 5.5px.
//
// A <svg> whose rendered width is not a fixed length (100%, unset, CSS-sized) is read at scale 1, the size it
// is authored at; the report says how many were. A missing DIR is an error: an unbuilt site is not a pass.
// A relative DIR that does not exist from the current directory is looked for in site/ too, where Astro builds
// dist/, so `node scripts/lint_svg.mjs dist/` works from the repository root.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join, relative, resolve, sep, isAbsolute } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SITE = join(ROOT, 'site');
export const FLOOR = 11;
const ROOT_SIZE = 16;
const TEXT = new Set(['text', 'tspan', 'textpath']);
const KEYWORDS = { 'xx-small': 9, 'x-small': 10, small: 13, medium: 16, large: 18, 'x-large': 24, 'xx-large': 32, 'xxx-large': 48 };
const VOID = new Set(['br', 'hr', 'img', 'input', 'meta', 'link', 'area', 'base', 'col', 'embed', 'source', 'track', 'wbr']);

const lineOf = (text, index) => text.slice(0, index).split('\n').length;

/** A font-size value in px, given the parent's size; null when it cannot be read (inherit, var(), calc()). */
export function px(value, parent) {
  const v = String(value).trim().toLowerCase();
  if (v in KEYWORDS) return KEYWORDS[v];
  if (v === 'smaller') return parent / 1.2;
  if (v === 'larger') return parent * 1.2;
  const m = v.match(/^(-?\d*\.?\d+)(px|pt|rem|em|%)?$/);
  if (!m) return null;
  const n = parseFloat(m[1]);
  return { undefined: n, px: n, pt: (n * 4) / 3, rem: n * ROOT_SIZE, em: n * parent, '%': (n / 100) * parent }[m[2]];
}

function attrs(s) {
  const out = {};
  for (const m of s.matchAll(/([:\w-]+)\s*=\s*("([^"]*)"|'([^']*)'|([^\s"'>]+))/g)) out[m[1].toLowerCase()] = m[3] ?? m[4] ?? m[5];
  return out;
}

function styleSize(style) {
  const m = (style || '').match(/(?:^|;)\s*font-size\s*:\s*([^;!]+)/i) || (style || '').match(/(?:^|;)\s*font\s*:[^;]*?(\d*\.?\d+(?:px|pt|rem|em|%))/i);
  return m ? m[1].trim() : null;
}

/** The font-size rules of the <style> blocks in a document: [{tag, cls, size}], in order. */
export function styleRules(text) {
  const out = [];
  for (const block of text.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)) {
    const css = block[1].replace(/\/\*[\s\S]*?\*\//g, '');
    for (const r of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const size = styleSize(r[2].replace(/\s+/g, ' '));
      if (!size) continue;
      for (const sel of r[1].split(',')) {
        const last = sel.trim().split(/[\s>+~]+/).pop();
        const m = last.match(/^([a-zA-Z*]+)?((?:\.[\w-]+)*)$/);
        if (m) out.push({ tag: (m[1] || '*').toLowerCase(), cls: m[2] ? m[2].slice(1).split('.') : [], size });
      }
    }
  }
  return out;
}

function ruleSize(rules, tag, classes) {
  let size = null;
  for (const r of rules) {
    if ((r.tag === '*' || r.tag === tag) && r.cls.every((c) => classes.includes(c)) && (r.tag !== '*' || r.cls.length)) size = r.size;
    else if (r.tag === '*' && !r.cls.length) size = r.size;
  }
  return size;
}

function scaleOf(a) {
  const vb = (a.viewbox || '').trim().split(/[\s,]+/).map(Number);
  if (vb.length !== 4 || !(vb[2] > 0) || !(vb[3] > 0)) return { scale: 1, fixed: true };
  for (const [dim, i] of [['width', 2], ['height', 3]]) {
    const m = (a[dim] || '').trim().match(/^(\d*\.?\d+)(px)?$/);
    if (m) return { scale: parseFloat(m[1]) / vb[i], fixed: true };
  }
  return { scale: 1, fixed: false };
}

/** Every text node in the SVG of one document: [{index, size, content, tag}], size in rendered px. A text node is a
 *  run of characters between tags whose innermost open element is a <text>, <tspan> or <textPath>. */
export function texts(doc, isSvg) {
  const rules = styleRules(doc);
  const out = [];
  let unscaled = 0;
  const stack = [];          // the open elements inside the outermost <svg>: {tag, size, scale}
  const re = /<!--[\s\S]*?-->|<(\/?)([a-zA-Z][\w:-]*)((?:"[^"]*"|'[^']*'|[^'">])*?)(\/?)>/g;
  let last = 0;
  let m;
  while ((m = re.exec(doc))) {
    const top = stack[stack.length - 1];
    const run = doc.slice(last, m.index);
    if (top && TEXT.has(top.tag) && run.trim()) out.push({ index: last, size: top.size * top.scale, content: run, tag: top.tag });
    last = re.lastIndex;
    if (m[0].startsWith('<!--')) continue;
    const [, closing, rawTag, attrText, selfClose] = m;
    const tag = rawTag.toLowerCase();
    if (!stack.length && !(isSvg || tag === 'svg')) continue;          // HTML outside any <svg>
    if (closing) {
      const at = stack.map((n) => n.tag).lastIndexOf(tag);
      if (at >= 0) stack.length = at;
      continue;
    }
    if (tag === 'style' || tag === 'script') {
      const end = doc.toLowerCase().indexOf(`</${tag}`, re.lastIndex);
      if (end >= 0) re.lastIndex = last = end;
      continue;
    }
    const a = attrs(attrText);
    const parent = top || { size: ROOT_SIZE, scale: 1 };
    let scale = parent.scale;
    if (tag === 'svg') {
      const s = scaleOf(a);
      scale *= s.scale;
      if (!s.fixed) unscaled++;
    }
    const classes = (a.class || '').split(/\s+/).filter(Boolean);
    const declared = styleSize(a.style) ?? a['font-size'] ?? ruleSize(rules, tag, classes);
    const read = declared == null ? null : px(declared, parent.size);
    if (!selfClose && !VOID.has(tag)) stack.push({ tag, size: read ?? parent.size, scale });
  }
  return { texts: out, unscaled };
}

export function lintDocument(doc, isSvg) {
  const { texts: found, unscaled } = texts(doc, isSvg);
  const bad = found.filter((t) => t.size < FLOOR - 1e-9).map((t) => ({
    index: t.index, line: lineOf(doc, t.index),
    msg: `<${t.tag}> "${t.content.trim().slice(0, 40)}" renders at ${+t.size.toFixed(2)}px, under the ${FLOOR}px floor (09 S3.2)`,
  }));
  return { bad, checked: found.length, unscaled };
}

export function* walk(target) {
  if (statSync(target).isFile()) { yield target; return; }
  for (const name of readdirSync(target).sort()) {
    if (name === 'node_modules' || name.startsWith('.')) continue;
    yield* walk(join(target, name));
  }
}

export function lint(dir) {
  const result = { bad: [], files: 0, checked: 0, unscaled: 0 };
  for (const f of walk(dir)) {
    const ext = extname(f).toLowerCase();
    if (ext !== '.svg' && ext !== '.html') continue;
    const doc = readFileSync(f, 'utf8');
    if (ext === '.html' && !/<svg\b/i.test(doc)) continue;
    const r = lintDocument(doc, ext === '.svg');
    result.files++;
    result.checked += r.checked;
    result.unscaled += r.unscaled;
    result.bad.push(...r.bad.map((b) => ({ ...b, file: f })));
  }
  return result;
}

export function locate(arg, cwd = process.cwd()) {
  const p = arg || join(SITE, 'dist');
  if (isAbsolute(p)) return p;
  const here = resolve(cwd, p);
  return existsSync(here) || !existsSync(resolve(SITE, p)) ? here : resolve(SITE, p);
}

function main(argv) {
  const dir = locate(argv[0]);
  if (!existsSync(dir)) { console.error(`lint_svg: ${dir} does not exist: build the site first (cd site && npm run build)`); return 2; }
  const r = lint(dir);
  for (const b of r.bad) console.error(`${relative(ROOT, b.file).split(sep).join('/')}:${b.line}: ${b.msg}`);
  console.log(`lint_svg: ${r.checked} text node(s) in ${r.files} file(s) with SVG under ${relative(ROOT, dir).split(sep).join('/')}; `
    + `${r.bad.length} below ${FLOOR}px; ${r.unscaled} <svg> read at scale 1 (no fixed width)`);
  return r.bad.length ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) process.exitCode = main(process.argv.slice(2));
