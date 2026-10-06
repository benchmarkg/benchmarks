// site/test/lint.test.mjs -- P2-S2-T04. The three JS lint gates of 09-design-system.md S13, proved to fire.
//
//   node --test site/test/lint.test.mjs
//
// DONE WHEN: "Each prohibited pattern fails on a fixture and passes on the real tree." Each fixture under
// test/fixtures/lint/ holds one prohibited pattern and is run through the script's command line, the way CI
// runs it; the clean fixtures hold the look-alikes each rule must not fire on. The real tree is site/src/ for
// lint_tokens, site/src/components/ for lint_absence and the built site/dist/ for lint_svg (skipped, with a
// reason, until `npm run build` has made it).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { px } from '../../scripts/lint_svg.mjs';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const FIX = fileURLToPath(new URL('fixtures/lint/', import.meta.url));
const run = (script, ...args) => {
  const r = spawnSync(process.execPath, [`${ROOT}scripts/${script}`, ...args], { cwd: ROOT, encoding: 'utf8' });
  return { code: r.status, out: r.stdout, err: r.stderr };
};

// ---- lint_tokens ------------------------------------------------------------------------------------------
const TOKENS = {
  'colour-hex.css': ['colour', '#1a2b3c'],
  'colour-function.css': ['colour', 'oklch('],
  'colour-named.css': ['colour', 'red'],
  'font-px.css': ['font-px', '10px'],
  'font-shorthand-px.css': ['font-px', '12px'],
  'outline-none.css': ['outline', 'outline: none'],
  'outline-zero.css': ['outline', 'outline: 0'],
  'domain-family.css': ['domain', 'data-domain-family'],
  'domain-group.css': ['domain', 'data-domain-group'],
  'style-attribute.astro': ['colour', '#000'],
  'react-style.tsx': ['font-px', 'fontSize: 10'],
};
for (const [file, [rule, text]] of Object.entries(TOKENS)) {
  test(`lint_tokens fails ${file} on [${rule}]`, () => {
    const r = run('lint_tokens.mjs', `${FIX}tokens/${file}`);
    assert.equal(r.code, 1, r.out + r.err);
    assert.ok(r.err.includes(`[${rule}]`), r.err);
    assert.ok(r.err.includes(text), r.err);
  });
}

test('lint_tokens reads a React style object for colour as well as size', () => {
  assert.match(run('lint_tokens.mjs', `${FIX}tokens/react-style.tsx`).err, /\[colour\] raw colour '#ff0000'/);
});

test('lint_tokens passes the look-alikes: tokens, system colours, an #id selector, a #fragment, comments', () => {
  for (const f of ['clean.css', 'clean.astro']) {
    const r = run('lint_tokens.mjs', `${FIX}tokens/${f}`);
    assert.equal(r.code, 0, f + ': ' + r.err);
  }
});

test('lint_tokens passes the real tree, skipping the generated tokens.css', () => {
  const r = run('lint_tokens.mjs');
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, /0 finding\(s\) in site\/src/);
});

// ---- lint_absence -----------------------------------------------------------------------------------------
const ABSENCE = {
  'filler-empty.astro': ['filler', "|| ''"],
  'filler-dash.astro': ['filler', "?? '—'"],
  'guard-and.astro': ['guard', '{claim.value && ...}'],
  'guard-ternary.tsx': ['guard', '{score ? ...}'],
};
for (const [file, [rule, text]] of Object.entries(ABSENCE)) {
  test(`lint_absence fails ${file} on [${rule}]`, () => {
    const r = run('lint_absence.mjs', `${FIX}absence/${file}`);
    assert.equal(r.code, 1, r.out + r.err);
    assert.ok(r.err.includes(`[${rule}]`), r.err);
    assert.ok(r.err.includes(text), r.err);
  });
}

test('lint_absence passes null checks, boolean guards and a guard passed on as an attribute', () => {
  const r = run('lint_absence.mjs', `${FIX}absence/clean.astro`);
  assert.equal(r.code, 0, r.err);
});

test('lint_absence passes the real components tree', () => {
  const r = run('lint_absence.mjs');
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, /0 finding\(s\) in site\/src\/components/);
});

// ---- lint_svg ---------------------------------------------------------------------------------------------
test('lint_svg fails every text node under 11px: attribute, viewBox scale, inherited em, inline tspan', () => {
  const r = run('lint_svg.mjs', `${FIX}svg`);
  assert.equal(r.code, 1, r.out + r.err);
  const lines = r.err.trim().split('\n');
  assert.equal(lines.length, 4, r.err);
  assert.ok(lines.some((l) => l.includes('small-attribute.svg') && l.includes('"0.5" renders at 10px')));
  assert.ok(lines.some((l) => l.includes('small-scaled.svg') && l.includes('"physics" renders at 7px')));
  assert.ok(lines.some((l) => l.includes('small-inherited.svg') && l.includes('"nine" renders at 9px')));
  assert.ok(lines.some((l) => l.includes('page/index.html') && l.includes('<tspan> "small" renders at 9px')));
  assert.ok(!r.err.includes('fine') && !r.err.includes('outside an svg'));
});

test('lint_svg passes 11px exactly, empty text and the 16px default', () => {
  const r = run('lint_svg.mjs', `${FIX}svg-clean`);
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, /3 text node\(s\) in 2 file\(s\) .*; 0 below 11px; 1 <svg> read at scale 1/);
});

test('lint_svg refuses a directory that does not exist rather than passing it', () => {
  assert.equal(run('lint_svg.mjs', `${FIX}no-such-dir`).code, 2);
});

test('font sizes resolve in every unit the floor is written in', () => {
  assert.equal(px('11', 16), 11);
  assert.equal(px('11px', 16), 11);
  assert.equal(px('9pt', 16), 12);
  assert.equal(px('0.6875rem', 16), 11);
  assert.equal(px('0.5em', 24), 12);
  assert.equal(px('50%', 20), 10);
  assert.equal(px('x-small', 16), 10);
  assert.equal(px('var(--fs-2xs)', 16), null);
});

const DIST = `${ROOT}site/dist`;
test('lint_svg passes the real built site', { skip: !existsSync(DIST) && 'site/dist/ is not built: run `npm run build` in site/' }, () => {
  const r = run('lint_svg.mjs', 'dist/');            // the task's verify, from the repository root
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, /under site\/dist;/);
});
