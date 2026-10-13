// site/test/contribute-links.test.mjs -- P2-S6-T05 (05 S6; 09 S6.14). Every entity page's "Suggest a correction".
//
//   cd site && node --test test/contribute-links.test.mjs
//
// Done when: "Every entity page carries a correction link whose query string prefills the entity id without
// depending on dropdown prefill behaviour." The test builds the site itself, over the draft preview (no entry is
// published yet, so the published build has no benchmark page to check), into build/site-contribute-test/, then
// reads every benchmark, version, system, organisation and metric page:
//
//   page link    one "Suggest a correction" in the page's Contribute block, opening correction.yml with `entity` = the
//                page's entity id
//   field links  beside each editable field, the same form with `field` = the field's YAML path, whose first segment is
//                a field the entity's record has
//   no dropdown  every prefilled parameter names an input or a textarea of correction.yml, never a dropdown -- and
//                the checker that says so is shown to flag a dropdown on a form that has one
import { before, test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = fileURLToPath(new URL('../', import.meta.url));
const ROOT = join(SITE, '..');
const PREVIEW = join(ROOT, 'build', 'preview');
const OUT = join(ROOT, 'build', 'site-contribute-test');
const FORM = readFileSync(join(ROOT, '.github', 'ISSUE_TEMPLATE', 'correction.yml'), 'utf8');
const REPO_FORM = 'https://github.com/benchmarkg/benchmarks/issues/new';
let corpus;

/** The form's fields by id: `- type: input` then `id: entity` -> { entity: 'input' }. */
export function formFields(yamlText) {
  return Object.fromEntries([...yamlText.matchAll(/- type: (\w+)\n\s+id: ([\w-]+)/g)].map((m) => [m[2], m[1]]));
}

/** What is wrong with a correction href: not the form, not correction.yml, or a parameter that is not a text field. */
export function prefillProblems(href, yamlText = FORM) {
  const url = new URL(href);
  const fields = formFields(yamlText);
  const out = [];
  if (`${url.origin}${url.pathname}` !== REPO_FORM) out.push(`not the issue form: ${href}`);
  if (url.searchParams.get('template') !== 'correction.yml') out.push('not the correction form');
  for (const key of url.searchParams.keys()) {
    if (key === 'template' || key === 'title') continue;
    if (!(key in fields)) out.push(`${key} is no field of the form`);
    else if (!['input', 'textarea'].includes(fields[key])) out.push(`${key} is a ${fields[key]}, whose prefill is unverified`);
  }
  return out;
}

const decode = (s) => s.replace(/&amp;/g, '&');
const links = (html) => [...html.matchAll(/<a\b([^>]*)data-action="correction"([^>]*)>/g)].map((m) => {
  const attrs = m[1] + m[2];
  return { href: decode(/href="([^"]+)"/.exec(attrs)[1]), field: /data-field="([^"]+)"/.exec(attrs)?.[1] ?? null };
});
const html = (...parts) => readFileSync(join(OUT, ...parts, 'index.html'), 'utf8');
const dirs = (...parts) => (existsSync(join(OUT, ...parts)) ? readdirSync(join(OUT, ...parts)) : []);

before(() => {
  const win = process.platform === 'win32';
  // relative to the repository root: on Windows `uv` needs a shell, and a shell splits the root's path at its spaces
  let r = spawnSync('uv', ['run', 'python', 'scripts/preview_corpus.py', '--out', 'build/preview'], { cwd: ROOT, encoding: 'utf8', shell: win });
  assert.equal(r.status, 0, r.stderr);
  r = spawnSync(process.execPath, [join(SITE, 'node_modules', 'astro', 'bin', 'astro.mjs'), 'build', '--outDir', OUT], {
    cwd: SITE, encoding: 'utf8',
    env: { ...process.env, UAIBI_CORPUS: join(PREVIEW, 'corpus.json'), UAIBI_SITE_DRAFTS: '1', ASTRO_TELEMETRY_DISABLED: '1' },
  });
  assert.equal(r.status, 0, (r.stdout ?? '').slice(-3000) + (r.stderr ?? '').slice(-3000));
  corpus = JSON.parse(readFileSync(join(PREVIEW, 'corpus.json'), 'utf8')).entities;
});

test('correction.yml takes the entity and the field in plain text inputs', () => {
  const fields = formFields(FORM);
  assert.equal(fields.entity, 'input');
  assert.equal(fields.field, 'input');
});

test('the prefill checker flags a dropdown, an unknown field and another form', () => {
  const form = `${FORM}\n  - type: dropdown\n    id: facet\n`;
  assert.deepEqual(prefillProblems(`${REPO_FORM}?template=correction.yml&entity=x&field=y&title=t`, form), []);
  assert.deepEqual(prefillProblems(`${REPO_FORM}?template=correction.yml&entity=x&facet=capability`, form),
    ['facet is a dropdown, whose prefill is unverified']);
  assert.deepEqual(prefillProblems(`${REPO_FORM}?template=correction.yml&entity_id=x`), ['entity_id is no field of the form']);
  assert.equal(prefillProblems(`${REPO_FORM}?template=new-benchmark.yml&entity=x`).length, 1);
});

const KINDS = [
  { kind: 'benchmark', dir: 'benchmarks', record: (id) => corpus.benchmark.find((b) => b.id === id) },
  { kind: 'system', dir: 'systems', record: (id) => corpus.system.find((s) => s.id === id) },
  { kind: 'organization', dir: 'orgs', record: (id) => corpus.organization.find((o) => o.id === id) },
  { kind: 'metric', dir: 'metrics', record: (id) => corpus.metric.find((m) => m.id === id) },
];

for (const { kind, dir, record } of KINDS) {
  test(`every ${kind} page: one page link prefilling its id, and field links prefilling real fields`, () => {
    const ids = dirs(dir).filter((d) => existsSync(join(OUT, dir, d, 'index.html')));
    assert.equal(ids.length, corpus[kind].length, `one ${kind} page per record`);
    assert.ok(ids.length > 0);
    for (const id of ids) {
      const all = links(html(dir, id));
      const page = all.filter((l) => l.field == null);
      assert.equal(page.length, 1, `${dir}/${id}: one page-level correction link`);
      assert.equal(new URL(page[0].href).searchParams.get('entity'), id, `${dir}/${id}: the link prefills the entity id`);
      const fields = all.filter((l) => l.field != null);
      assert.ok(fields.length > 0, `${dir}/${id}: a correction link beside its fields`);
      for (const l of [...page, ...fields]) assert.deepEqual(prefillProblems(l.href), [], `${dir}/${id}`);
      for (const l of fields) {
        const q = new URL(l.href).searchParams;
        assert.equal(q.get('field'), l.field, `${dir}/${id}: data-field and the prefilled field agree`);
        const owner = q.get('entity') === id ? record(id) : corpus.metric.find((m) => m.id === q.get('entity'));
        assert.ok(owner != null, `${dir}/${id}: ${q.get('entity')} is this entity or a metric it shows`);
        assert.ok(l.field.split('.')[0] in owner, `${dir}/${id}: ${l.field} is a field of ${q.get('entity')}`);
      }
    }
  });
}

test('a benchmark page links the fields a reader is most likely to correct', () => {
  const fields = new Set(links(html('benchmarks', 'swe-bench')).map((l) => l.field));
  for (const f of ['description', 'lifecycle', 'released', 'domain.primary', 'capability', 'evaluation_method', 'data.access',
    'governance.maintainer', 'execution.compute_tier', 'liveness.repo_last_commit', 'lineage']) {
    assert.ok(fields.has(f), `swe-bench links ${f}`);
  }
});

test('a version page corrects its benchmark', () => {
  const versions = dirs('benchmarks').flatMap((b) => dirs('benchmarks', b, 'v').map((v) => [b, v]));
  assert.ok(versions.length > 0);
  for (const [b, v] of versions) {
    const page = links(html('benchmarks', b, 'v', v)).filter((l) => l.field == null);
    assert.equal(page.length, 1);
    assert.equal(new URL(page[0].href).searchParams.get('entity'), b);
  }
});
