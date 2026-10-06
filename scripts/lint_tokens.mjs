#!/usr/bin/env node
// scripts/lint_tokens.mjs -- P2-S2-T04. The token rules of 09-design-system.md S13, S3.2 and S4.2.
//
//   node scripts/lint_tokens.mjs                 # lint site/src/; exit 1 on any finding
//   node scripts/lint_tokens.mjs PATH...         # lint these files or directories instead
//
// Fails on (09 S13, "lint_tokens.mjs"):
//   colour     a raw colour literal outside tokens.css: a hex colour, a colour function (rgb(), hsl(),
//              oklch(), lab(), color() ...), or a named colour on a colour property. A colour is a
//              token in design/tokens.yaml, used as var(--c-...). Allowed: currentColor, transparent,
//              the CSS-wide keywords, and the CSS system colours forced-colors mode needs
//   font-px    a px font size: font-size or the font shorthand in px, or a React fontSize in px or a
//              bare number (React reads that as px). Sizes are rem tokens (09 S3.2, SC 1.4.4)
//   outline    outline: none / outline: 0 / outline-style: none (09 S7: focus must stay visible)
//   domain     a rule keyed on [data-domain-family] or [data-domain-group] that sets color, background,
//              background-color, fill or stroke: domain family is never encoded by hue (09 S4.2, D4)
//
// What is read: CSS files whole; in .astro files the <style> blocks, style="..." attributes and the
// script's string literals; in .ts/.tsx/.js/.jsx/.mjs the string literals and style objects. Skipped:
// site/src/styles/tokens.css and site/src/lib/tokens.json (the generated tokens themselves), *.d.ts
// (generated types), and anything that is not one of those extensions. Comments are not read.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const DEFAULT = join(ROOT, 'site', 'src');
const SKIP = new Set([join(ROOT, 'site', 'src', 'styles', 'tokens.css'), join(ROOT, 'site', 'src', 'lib', 'tokens.json')]);
const EXTS = new Set(['.css', '.astro', '.ts', '.tsx', '.js', '.jsx', '.mjs']);

// CSS Color 4 named colours. `transparent` and `currentcolor` are allowed, so they are not here.
export const NAMED = new Set(('aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue '
  + 'blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue '
  + 'darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid '
  + 'darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink '
  + 'deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold '
  + 'goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush '
  + 'lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey '
  + 'lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime '
  + 'limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen '
  + 'mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin '
  + 'navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise '
  + 'palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue '
  + 'saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow '
  + 'springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen').split(' '));
const COLOUR_PROPS = /^(color|background(-color)?|border(-(top|right|bottom|left|block|inline)(-(start|end))?)?(-color)?|outline(-color)?|fill|stroke|box-shadow|text-shadow|text-decoration(-color)?|caret-color|accent-color|column-rule(-color)?|stop-color|flood-color|lighting-color|scrollbar-color)$/;
const HEX = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])/;
const FUNC = /\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(/i;
const DOMAIN = /\[\s*data-domain-(?:family|group)\b/;
const DOMAIN_PROPS = new Set(['color', 'background', 'background-color', 'fill', 'stroke']);

const stripCssComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
const lineOf = (text, index) => text.slice(0, index).split('\n').length;

/** Every colour literal in one CSS value, given its property ('' when unknown). */
export function colourLiterals(prop, value) {
  const v = value.replace(/var\([^)]*\)/g, ' ').replace(/url\([^)]*\)/g, ' ').replace(/(["'])(?:(?!\1).)*\1/g, ' ');
  const out = [];
  const hex = v.match(HEX);
  if (hex) out.push(hex[0]);
  const fn = v.match(FUNC);
  if (fn) out.push(fn[0] + '...)');
  if (COLOUR_PROPS.test(prop)) {
    for (const word of v.toLowerCase().match(/[a-z]+/g) || []) if (NAMED.has(word)) out.push(word);
  }
  return out;
}

/** The leaf rules of a stylesheet: {selector, decls: [{prop, value, index}]}, with @media and nesting walked. */
export function rules(css, offset = 0) {
  const text = stripCssComments(css);
  const out = [];
  const stack = [];
  let start = 0;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '{') {
      stack.push({ selector: text.slice(start, i).trim().split(/;/).pop().trim(), body: i + 1, nested: false });
      if (stack.length > 1) stack[stack.length - 2].nested = true;
      start = i + 1;
    } else if (ch === '}') {
      const block = stack.pop();
      if (block) {
        const body = text.slice(block.body, i);
        const selector = [...stack.map((b) => b.selector), block.selector].filter((s) => !s.startsWith('@')).join(' ');
        const decls = [];
        let at = block.body;
        for (const part of body.split(';')) {
          const m = part.match(/^\s*([-\w]+)\s*:([\s\S]*)$/);
          if (m && !part.includes('{') && !part.includes('}')) decls.push({ prop: m[1].toLowerCase(), value: m[2].trim(), index: offset + at });
          at += part.length + 1;
        }
        if (!block.selector.startsWith('@font-face')) out.push({ selector, decls });
      }
      start = i + 1;
    }
  }
  return out;
}

function lintDecl(prop, value) {
  const found = [];
  for (const lit of colourLiterals(prop, value)) found.push(['colour', `raw colour ${lit} in ${prop}: use a var(--c-*) token`]);
  if ((prop === 'font-size' || prop === 'font') && /\d(?:\.\d+)?px\b/.test(value)) {
    found.push(['font-px', `px font size in ${prop}: ${value} (rem only, 09 S3.2)`]);
  }
  if ((prop === 'outline' && /^(none|0)(\s|$|!)/.test(value)) || (prop === 'outline-style' && /^none\b/.test(value))) {
    found.push(['outline', `${prop}: ${value} (focus must stay visible)`]);
  }
  return found;
}

/** Findings for one stylesheet's text. `base` is the stylesheet's offset in its file, for line numbers. */
export function lintCss(css, base = 0) {
  const out = [];
  for (const r of rules(css, base)) {
    const keyed = DOMAIN.test(r.selector);
    for (const d of r.decls) {
      for (const [rule, msg] of lintDecl(d.prop, d.value)) out.push({ rule, index: d.index, msg });
      if (keyed && DOMAIN_PROPS.has(d.prop)) {
        out.push({ rule: 'domain', index: d.index, msg: `${r.selector} sets ${d.prop}: domain family is never a colour (09 S4.2)` });
      }
    }
  }
  return out;
}

/** Findings for script text: string literals that are colour literals, and style-object font sizes and outlines. */
export function lintScript(code, base = 0) {
  const out = [];
  const src = code.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' ')).replace(/(^|[^:'"`\\])\/\/[^\n]*/g, (m, p) => p + ' '.repeat(m.length - p.length));
  for (const m of src.matchAll(/(["'`])((?:\\.|(?!\1)[^\\\n])*)\1/g)) {
    const s = m[2].trim();
    if (HEX.test(s) && new RegExp('^' + HEX.source + '$').test(s)) out.push({ rule: 'colour', index: base + m.index, msg: `raw colour '${s}': read it from tokens.json or use var(--c-*)` });
    else if (/^(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(.*\)$/i.test(s)) out.push({ rule: 'colour', index: base + m.index, msg: `raw colour '${s}'` });
    else if (/[;{]|^[-\w]+\s*:/.test(s)) {                        // an inline style string: 'color: #fff; font-size: 12px'
      for (const part of s.split(';')) {
        const d = part.match(/^\s*([-\w]+)\s*:\s*(.+)$/);
        if (d) for (const [rule, msg] of lintDecl(d[1].toLowerCase(), d[2].trim())) out.push({ rule, index: base + m.index, msg });
      }
    }
  }
  for (const m of src.matchAll(/\bfontSize\s*:\s*(?:(\d+(?:\.\d+)?)\s*[,}\n]|(["'`])\s*\d+(?:\.\d+)?px\s*\2)/g)) {
    out.push({ rule: 'font-px', index: base + m.index, msg: `${m[0].replace(/[,}\n]$/, '').trim()}: React reads a number as px; use a rem token` });
  }
  for (const m of src.matchAll(/\boutline(Style)?\s*:\s*(["'`])\s*(none|0)\s*\2/g)) {
    out.push({ rule: 'outline', index: base + m.index, msg: `${m[0]} (focus must stay visible)` });
  }
  for (const m of src.matchAll(/\b(color|background(?:Color)?|fill|stroke|borderColor|outlineColor)\s*:\s*(["'`])([a-z]+)\2/gi)) {
    if (NAMED.has(m[3].toLowerCase())) out.push({ rule: 'colour', index: base + m.index, msg: `raw colour '${m[3]}' in ${m[1]}` });
  }
  return out;
}

/** Findings for an .astro file: frontmatter script, <style> blocks, <script> blocks, style="..." attributes. */
export function lintAstro(text) {
  const out = [];
  const fm = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (fm) out.push(...lintScript(fm[1], text.indexOf(fm[1])));
  for (const m of text.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)) out.push(...lintCss(m[1], m.index + m[0].indexOf(m[1])));
  for (const m of text.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) out.push(...lintScript(m[1], m.index + m[0].indexOf(m[1])));
  const body = fm ? fm.index + fm[0].length : 0;
  for (const m of text.slice(body).matchAll(/\sstyle\s*=\s*(["'])([\s\S]*?)\1/g)) {
    out.push(...lintCss(`x{${m[2]}}`, body + m.index).map((f) => ({ ...f, index: body + m.index })));
  }
  return out;
}

export function lintFile(path) {
  const text = readFileSync(path, 'utf8');
  const ext = extname(path);
  const found = ext === '.css' ? lintCss(text) : ext === '.astro' ? lintAstro(text) : lintScript(text);
  return found.map((f) => ({ ...f, file: path, line: lineOf(text, f.index) }));
}

export function* walk(target) {
  const st = statSync(target);
  if (st.isFile()) { yield target; return; }
  for (const name of readdirSync(target).sort()) {
    if (name === 'node_modules' || name.startsWith('.')) continue;
    yield* walk(join(target, name));
  }
}

export function lint(targets) {
  const out = [];
  for (const t of targets) {
    for (const f of walk(t)) {
      if (SKIP.has(resolve(f)) || f.endsWith('.d.ts') || !EXTS.has(extname(f))) continue;
      out.push(...lintFile(f));
    }
  }
  return out;
}

function main(argv) {
  const targets = argv.length ? argv.map((p) => resolve(p)) : [DEFAULT];
  for (const t of targets) {
    if (!existsSync(t)) { console.error(`lint_tokens: ${t} does not exist`); return 2; }
  }
  const found = lint(targets);
  for (const f of found) console.error(`${relative(ROOT, f.file).split(sep).join('/')}:${f.line}: [${f.rule}] ${f.msg}`);
  console.log(`lint_tokens: ${found.length} finding(s) in ${targets.map((t) => relative(ROOT, t).split(sep).join('/') || '.').join(', ')}`);
  return found.length ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) process.exitCode = main(process.argv.slice(2));
