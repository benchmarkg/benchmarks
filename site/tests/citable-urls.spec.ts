// site/tests/citable-urls.spec.ts -- P2-S8-T07 (14 Phase 2 Exit criteria, the fifth; 08 S8.3; 10 "The permanent
// citation URL"). Every benchmark has a stable citable URL that renders with JavaScript disabled (the `nojs` project,
// playwright.config.ts):
//
//   cd site && npx playwright test tests/citable-urls.spec.ts --project=nojs
//
// Done when: "All ~320 benchmark URLs resolve and carry their citation metadata with JavaScript off." The subject list is
// data/, not the build: every curated benchmark file, data/benchmarks/<family>/**/*.yaml and never _stubs/ (the files
// schema/stub.py curated_benchmark_files reads), parsed for its id, so a benchmark the build silently drops -- a draft
// that fails tier 1 is left out of the preview without failing it (tools/build/artifacts.py) -- is a URL that answers
// 404 here, not a page nobody asked for. Which of them a build must serve is 05 S4's rule, read from the same files:
//   - a draft preview (scripts/preview_corpus.py, UAIBI_SITE_DRAFTS=1; every page says so in [data-draft-preview]) serves
//     every one of them, drafts included. It is the build this spec runs over, as the other page tests do, because no
//     entry is published yet;
//   - a published build serves those whose curation.verification_status is not ai-drafted-unverified (absent is that
//     default). Today that is none of them, so over a published build each family's walk is skipped, with the reason,
//     rather than passed over an empty list; it covers an entry the day one is promoted.
//
// For each URL, rendered in a browser with scripting off:
//   - it answers 200 at its own path, with no redirect elsewhere;
//   - it has one citation block (CiteThis.astro, 10 V6 section 18) citing that id, not inside a <noscript> (09 S8.6) and
//     visible, once any closed <details> around it is opened by its summary; its permalink is the YAML at a 40-digit
//     commit, at the path the entry was read from in data/ (a page that guessed another path cites a file that is not
//     there), its BibTeX names that commit and its APA line is there;
//   - the commit SHA: the build footer (BuildFooter.astro) prints it, in full in data-commit, the same commit as the
//     permalink's and as the rest of the site's (the landing page's footer, read once per walk);
//   - the release tag: the block's Release line and the footer print the same release (lib/release.ts). Before the first
//     tagged release, which is now (the repository has no v* tag), the line is not blank: it holds the absence token,
//     "not applicable (no tagged release yet)" (09 S6.9: a missing value is a fact with a name), and the footer "no
//     tagged release yet". That absence is checked against git, so a build that lost its tag cannot pass as untagged.
//
// One browser page per family walks the family's URLs; the families run in parallel. A navigation with scripting off is
// what the criterion is about (08 S8.3: the archive crawler, the library harvester, the text browser), its response is
// the 200 that is asserted, and "visible" needs the page's own CSS applied, which plain HTTP plus a DOM parser would not
// give (and the site has no DOM parser among its dependencies). The block is read in one evaluate per page.
//
// The failure case is checked as a failure, as tests/nojs.spec.ts checks its own: a data/ directory made here with an id
// the build does not have is walked and must answer 404; and a real page is served again doctored -- its citation block
// taken out, its release line taken out or left blank, its footer's commit taken out, its permalink at another commit or
// to another file, the block hidden, the whole page inside a <noscript> -- and each must be reported.
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { load } from 'js-yaml';
import { expect, test, type Page } from '@playwright/test';

interface Entry {
  id: string;
  family: string;         // the directory under data/benchmarks/ the file is in
  path: string;           // the file, from the repository root: what the permalink must name
  status: string | null;  // curation.verification_status as written
}
/** The release a page prints: a tag, or null for "no tagged release yet". */
type Release = string | null;
interface Build { preview: boolean; commit: string | null; release: Release | undefined }

const REPO = fileURLToPath(new URL('../..', import.meta.url));
const DATA = join(REPO, 'data', 'benchmarks');
const STUBS = '_stubs';                                   // never published (schema/stub.py, 07 S2.4)
const DRAFT = 'ai-drafted-unverified';                    // 05 S4: never published; also the model's default
const PERMALINK = /^https:\/\/github\.com\/[^/]+\/[^/]+\/blob\/([0-9a-f]{40})\/(data\/benchmarks\/.+\.yaml)$/;
const NO_TAG = 'no tagged release yet';                   // BuildFooter.astro and CiteThis.astro's absence reason

/** Every curated benchmark under `root` (a data/benchmarks/ directory), in path order: its id from the file. */
function entriesIn(root: string): Entry[] {
  const files = (readdirSync(root, { recursive: true }) as string[])
    .map((p) => p.split(sep).join('/'))
    .filter((p) => p.endsWith('.yaml') && p.split('/')[0] !== STUBS && p.includes('/'))
    .sort();
  return files.map((rel) => {
    const doc = load(readFileSync(join(root, rel), 'utf8'), { filename: rel }) as
      { id?: unknown; curation?: { verification_status?: unknown } } | null;
    const status = doc?.curation?.verification_status;
    return { id: String(doc?.id), family: rel.split('/')[0], path: `data/benchmarks/${rel}`,
      status: typeof status === 'string' ? status : null };
  });
}

/** The entries a build must serve: a draft preview, every one; a published build, those 05 S4 publishes. */
const expected = (entries: Entry[], preview: boolean) => (preview ? entries : entries.filter((e) => (e.status ?? DRAFT) !== DRAFT));
const routeOf = (id: string) => `/benchmarks/${id}/`;

const ENTRIES = entriesIn(DATA);
const FAMILIES = [...new Set(ENTRIES.map((e) => e.family))];

/** What the page, as a browser with scripting off built it, shows of its citation, read in the page in one pass. */
function readCitation() {
  const text = (n: Element | null | undefined) => (n?.textContent ?? '').replace(/\s+/g, ' ').trim();
  const blocks = [...document.querySelectorAll('section.cite')];
  const cite = blocks[0];
  const line = cite?.querySelector('[data-release-tag]');
  const footer = document.querySelector('[data-build-footer]');
  const commit = footer?.querySelector('[data-commit]');
  const release = footer?.querySelector('[data-release]');
  return {
    blocks: blocks.length,
    cites: cite?.getAttribute('data-cite') ?? null,
    citeNoscript: cite?.closest('noscript') != null,
    permalink: cite?.querySelector('a[href*="/blob/"]')?.getAttribute('href') ?? null,
    bibtex: text(cite?.querySelector('pre code')),
    apa: text(cite?.querySelector('.apa')),
    line: line == null ? null : { code: line.querySelector('code') != null ? text(line.querySelector('code')) : null,
      absent: line.querySelector('[data-absent="not-applicable"]') != null ? text(line.querySelector('[data-absent]')) : null },
    footer: footer == null ? null : {
      noscript: footer.closest('noscript') != null,
      commit: commit?.getAttribute('data-commit') ?? null,
      shown: text(commit),
      release: release == null ? null : { code: release.tagName === 'CODE', text: text(release) },
    },
    preview: document.querySelector('[data-draft-preview]') != null,
  };
}
type Facts = ReturnType<typeof readCitation>;

/** The release the block's Release line prints, or a problem with it. */
function lineRelease(line: Facts['line']): { release?: Release; problem?: string } {
  if (line == null) return { problem: 'its citation block has no Release line ([data-release-tag])' };
  if (line.code != null && /^v[0-9]/.test(line.code)) return { release: line.code };
  if (line.code != null) return { problem: `its Release line names ${JSON.stringify(line.code)}, not a v* release tag` };
  if (line.absent != null && line.absent.includes(NO_TAG)) return { release: null };
  return { problem: `its Release line is blank: neither a tag nor the absence token "${NO_TAG}" (09 S6.9)` };
}

/** The release the footer prints, or a problem with it. */
function footerRelease(r: { code: boolean; text: string } | null): { release?: Release; problem?: string } {
  if (r == null) return { problem: 'its footer prints no release ([data-release])' };
  if (r.code && /^v[0-9]/.test(r.text)) return { release: r.text };
  if (!r.code && r.text === NO_TAG) return { release: null };
  return { problem: `its footer's release reads ${JSON.stringify(r.text)}, neither a v* tag nor "${NO_TAG}"` };
}

/** What keeps `e`'s page, read as `f`, from being citable in `build`; [] when nothing does. */
function citationProblems(e: Entry, f: Facts, visible: boolean, build: Build): string[] {
  const at = routeOf(e.id);
  const out: string[] = [];
  const link = PERMALINK.exec(f.permalink ?? '');
  if (f.blocks === 0) out.push(`${at}: no citation block (section.cite) with JavaScript off`);
  else {
    if (f.blocks > 1) out.push(`${at}: ${f.blocks} citation blocks, for one entry`);
    if (f.cites !== e.id) out.push(`${at}: its citation block cites ${f.cites}, not ${e.id}`);
    if (f.citeNoscript) out.push(`${at}: its citation block is inside a <noscript>: the page as sent is the citable thing (09 S8.6)`);
    else if (!visible) out.push(`${at}: its citation block is in the page but not visible`);
    if (link == null) out.push(`${at}: its citation block has no permalink at a 40-digit commit (it has ${f.permalink})`);
    else {
      if (link[2] !== e.path) out.push(`${at}: its permalink names ${link[2]}, not ${e.path}, the file the entry is read from`);
      if (!f.bibtex.startsWith('@misc{') || !f.bibtex.includes(`at commit ${link[1]}`)) out.push(`${at}: its BibTeX does not cite commit ${link[1]}`);
    }
    if (f.apa === '') out.push(`${at}: its citation block has no APA line`);
  }
  const line: { release?: Release; problem?: string } = f.blocks === 0 ? {} : lineRelease(f.line);
  if (line.problem != null) out.push(`${at}: ${line.problem}`);
  if (f.footer == null) return [...out, `${at}: no build footer ([data-build-footer]), so no commit SHA or release`];
  if (f.footer.noscript) out.push(`${at}: its build footer is inside a <noscript>`);
  const commit = f.footer.commit;
  if (commit == null || !/^[0-9a-f]{40}$/.test(commit)) out.push(`${at}: its footer names no 40-digit commit SHA (data-commit is ${commit})`);
  else {
    if (!commit.startsWith(f.footer.shown) || f.footer.shown.length < 7) out.push(`${at}: its footer shows ${f.footer.shown}, not commit ${commit}`);
    if (link != null && link[1] !== commit) out.push(`${at}: its citation block cites commit ${link[1]}, its footer ${commit}`);
    if (build.commit != null && commit !== build.commit) out.push(`${at}: built from commit ${commit}, the rest of the site from ${build.commit}`);
  }
  const foot = footerRelease(f.footer.release);
  if (foot.problem != null) out.push(`${at}: ${foot.problem}`);
  if (line.release !== undefined && foot.release !== undefined && line.release !== foot.release) {
    out.push(`${at}: its Release line says ${line.release ?? NO_TAG}, its footer ${foot.release ?? NO_TAG}`);
  }
  if (foot.release !== undefined && build.release !== undefined && foot.release !== build.release) {
    out.push(`${at}: its release is ${foot.release ?? NO_TAG}, the rest of the site's ${build.release ?? NO_TAG}`);
  }
  if (f.preview !== build.preview) out.push(`${at}: ${f.preview ? 'says' : 'does not say'} it is a draft preview, unlike the rest of the site`);
  return out;
}

/** Request `e`'s URL with JavaScript off and say what keeps it from being citable; [] when nothing does. */
async function pageProblems(page: Page, e: Entry, build: Build): Promise<string[]> {
  const route = routeOf(e.id);
  const res = await page.goto(route);
  if (res == null || res.status() !== 200) {
    return [`${route} answered ${res?.status() ?? 'nothing'} with JavaScript off: ${e.path} has no citable page in this build`];
  }
  const at = new URL(page.url()).pathname;
  if (at !== route) return [`${route} went on to ${at}: a citable URL answers at its own path`];
  const facts = await page.evaluate(readCitation);
  const block = page.locator('section.cite').first();
  // a closed <details> around it is opened the way a reader opens it: its summary, natively, with no script
  for (let open = 0; facts.blocks > 0 && open < 8 && !(await block.isVisible()); open++) {
    const closed = block.locator('xpath=ancestor::details[not(@open)][1]');
    if ((await closed.count()) === 0) break;
    await closed.locator(':scope > summary').click();
  }
  return citationProblems(e, facts, facts.blocks > 0 && (await block.isVisible()), build);
}

/** The build as the landing page tells it, with JavaScript off: preview or published, its commit and its release. */
async function buildOf(page: Page): Promise<Build> {
  const res = await page.goto('/');
  expect(res?.status(), 'the landing page answers').toBe(200);
  const f = await page.evaluate(readCitation);
  const commit = f.footer?.commit ?? null;
  return { preview: f.preview, commit: commit != null && /^[0-9a-f]{40}$/.test(commit) ? commit : null,
    release: footerRelease(f.footer?.release ?? null).release };
}

/** The newest v* tag at or before `commit`, as lib/release.ts asks git for it; null when there is none. */
function gitTag(commit: string): string | null {
  try {
    return execFileSync('git', ['describe', '--tags', '--abbrev=0', '--match', 'v[0-9]*', commit],
      { cwd: REPO, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim() || null;
  } catch {
    return null;
  }
}

/** From now on, serve `route` to `page` as `body` instead of the page the server built. */
const serve = (page: Page, route: string, body: string) =>
  page.route((u) => u.pathname === route, (r) => r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body }));

test('the nojs project runs this spec, with JavaScript off', () => {
  expect(test.info().project.name).toBe('nojs');
  expect(test.info().project.use.javaScriptEnabled).toBe(false);
});

test('the subject list is data/: every curated benchmark file once, by its id, never a stub', () => {
  expect(ENTRIES.length, 'data/benchmarks/ holds curated entries').toBeGreaterThan(0);
  for (const e of ENTRIES) expect(e.id, e.path).toMatch(/^[a-z0-9][a-z0-9-]*$/);
  const ids = ENTRIES.map((e) => e.id);
  expect(ids.filter((id, i) => ids.indexOf(id) !== i), 'one URL per entry').toEqual([]);
  test.info().annotations.push({ type: 'subjects', description: `${ENTRIES.length} benchmark(s) in ${FAMILIES.length} families` });
  // the same reader over a data/benchmarks/ made here: a stub is left out, a file is found however deep it is
  const root = mkdtempSync(join(tmpdir(), 'citable-urls-'));
  try {
    const put = (rel: string, text: string) => {
      mkdirSync(join(root, ...rel.split('/').slice(0, -1)), { recursive: true });
      writeFileSync(join(root, ...rel.split('/')), text);
    };
    put('code/drafted.yaml', 'id: drafted\ncuration:\n  verification_status: ai-drafted-unverified\n');
    put('code/no-status.yaml', 'id: no-status\n');
    put('vision/sub/reviewed.yaml', 'id: reviewed\ncuration:\n  verification_status: curator-reviewed\n');
    put(`${STUBS}/stubbed.yaml`, 'id: stubbed\ncuration:\n  verification_status: unreviewed\n');
    const got = entriesIn(root);
    expect(got.map((e) => [e.id, e.family, e.path])).toEqual([
      ['drafted', 'code', 'data/benchmarks/code/drafted.yaml'],
      ['no-status', 'code', 'data/benchmarks/code/no-status.yaml'],
      ['reviewed', 'vision', 'data/benchmarks/vision/sub/reviewed.yaml'],
    ]);
    // what each build must serve: a preview every entry; a published build only what 05 S4 publishes
    expect(expected(got, true).map((e) => e.id)).toEqual(['drafted', 'no-status', 'reviewed']);
    expect(expected(got, false).map((e) => e.id)).toEqual(['reviewed']);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('the release line tells the truth: "no tagged release yet" only while git has no release tag at the commit', async ({ page }) => {
  const build = await buildOf(page);
  expect(build.commit, 'the landing page footer names the commit').not.toBeNull();
  expect(build.release, "the landing page footer's release").not.toBeUndefined();
  const tag = gitTag(build.commit!);
  if (build.release === null) expect(tag, `the repository tags ${tag} at or before ${build.commit}`).toBeNull();
  else expect(build.release).toMatch(/^v[0-9]/);
  test.info().annotations.push({ type: 'release', description: `${build.release ?? NO_TAG} at ${build.commit}` });
});

for (const family of FAMILIES) {
  const entries = ENTRIES.filter((e) => e.family === family);
  test(`data/benchmarks/${family}/: each benchmark's URL answers 200 with JavaScript off and carries its citation block, commit SHA and release`, async ({ page }) => {
    const build = await buildOf(page);
    const want = expected(entries, build.preview);
    test.skip(want.length === 0, `a published build, and none of the ${entries.length} entries of data/benchmarks/${family}/ is `
      + `published (05 S4: each is ${DRAFT}); the draft preview is the build with their pages`);
    test.setTimeout(30_000 + want.length * 3_000);
    const problems: string[] = [];
    for (const e of want) problems.push(...(await pageProblems(page, e, build)));
    expect(problems).toEqual([]);
    test.info().annotations.push({ type: 'checked', description: `${want.length} URL(s)` });
  });
}

test('a benchmark in data/ that the build does not have fails: its URL answers 404', async ({ page }) => {
  const build = await buildOf(page);
  const root = mkdtempSync(join(tmpdir(), 'citable-urls-'));
  try {
    mkdirSync(join(root, 'code'));
    writeFileSync(join(root, 'code', 'not-in-this-build.yaml'), `id: not-in-this-build\ncuration:\n  verification_status: curator-reviewed\n`);
    const [dropped] = expected(entriesIn(root), build.preview);
    expect(await pageProblems(page, dropped, build)).toEqual([
      '/benchmarks/not-in-this-build/ answered 404 with JavaScript off: data/benchmarks/code/not-in-this-build.yaml has no citable page in this build',
    ]);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('a page whose citation, commit or release is missing, wrong or hidden fails', async ({ page, context }) => {
  const build = await buildOf(page);
  const pages = expected(ENTRIES, build.preview);
  test.skip(pages.length === 0, 'a published build with no entry published: there is no page to doctor');
  const e = pages.find((x) => x.id === 'swe-bench') ?? pages[0];
  expect(await pageProblems(page, e, build), 'the page as built').toEqual([]);
  const route = routeOf(e.id);
  const cases: [string, () => void, RegExp][] = [
    ['the citation block taken out', () => document.querySelector('section.cite')!.remove(), /no citation block/],
    ['its Release line taken out', () => document.querySelector('section.cite [data-release-tag]')!.remove(), /has no Release line/],
    ['its Release line left blank', () => document.querySelector('section.cite [data-release-tag]')!.replaceChildren(), /Release line is blank/],
    ["the footer's commit taken out", () => document.querySelector('[data-build-footer] [data-commit]')!.removeAttribute('data-commit'),
      /footer names no 40-digit commit SHA/],
    ['the permalink at another commit', () => {
      const a = document.querySelector('section.cite a[href*="/blob/"]')!;
      a.setAttribute('href', a.getAttribute('href')!.replace(/\/blob\/[0-9a-f]{40}\//, `/blob/${'0'.repeat(40)}/`));
    }, /cites commit 0{40}, its footer [0-9a-f]{40}/],
    ['the permalink to another file', () => {
      const a = document.querySelector('section.cite a[href*="/blob/"]')!;
      a.setAttribute('href', a.getAttribute('href')!.replace(/data\/benchmarks\/.+$/, 'data/benchmarks/elsewhere/x.yaml'));
    }, /its permalink names data\/benchmarks\/elsewhere\/x\.yaml, not /],
    ['the citation block hidden', () => document.querySelector('section.cite')!.setAttribute('hidden', ''), /not visible/],
    ['the page inside a <noscript>', () => {
      const n = document.createElement('noscript');
      n.append(...document.body.childNodes);
      document.body.append(n);
    }, /citation block is inside a <noscript>/],
  ];
  for (const [what, doctor, want] of cases) {
    const p = await context.newPage();
    await p.goto(route);
    await p.evaluate(doctor);
    await serve(p, route, await p.content());
    expect((await pageProblems(p, e, build)).join('\n'), what).toMatch(want);
    await p.close();
  }
});
