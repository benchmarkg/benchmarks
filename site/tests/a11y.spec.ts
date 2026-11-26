// site/tests/a11y.spec.ts -- P2-S8-T03 (09 S8, S13 "Axe / Pa11y over a fixed page sample"; 14 Phase 2 exit criterion 8).
// The accessibility harness: axe-core and pa11y at WCAG 2.2 AA over the eight archetype pages, each in four modes --
// light, dark, forced-colors and prefers-contrast: more -- over the draft preview playwright.config.ts serves:
//
//   cd site && npx playwright test tests/a11y.spec.ts
//   cd site && npm run test:a11y -- /benchmarks/   only the routes named: an archetype's against its baseline, any other
//                                                  built route against none (test/a11y/run.mjs)
//
// Done when: "The harness runs axe-core and pa11y over all eight archetypes in light, dark, forced-colors and
// prefers-contrast more, and fails the job on any violation. Driving the count to zero is P2-S8-T09."
//
// test/a11y/archetypes.json names the eight, one fixed page each, and the four modes. Each page is opened twice in one
// Chromium, the one Playwright installs: by Playwright, for axe-core (@axe-core/playwright), and by pa11y, through the
// puppeteer pa11y itself depends on, connected to that same browser over the DevTools protocol, so pa11y needs no browser
// of its own (the root package.json tells puppeteer never to download one). Both pages are put in the mode by emulation
// and held to it: a page whose media queries do not answer as the mode says fails, as does a page that is not its
// archetype (its family's fallback element, scripts/route_fallback_map.json, and anything the archetype `requires`), an
// axe run that passed no rule and a pa11y run whose runner never reached the page.
//
// What fails the job: a violation either tool reports that test/a11y/baseline.json does not list for that archetype and
// mode. The baseline is the audit of 2026-11-26, the violations the pages had when the harness was first run, so the job
// is red on a regression from the day the harness lands rather than red on every pull request until P2-S8-T09 has fixed
// them all. It only shrinks: a listed violation no longer found fails until it is taken out, and a listed violation the
// baseline on the base branch does not list fails, so a pull request cannot add one (the base is UAIBI_A11Y_BASE, else
// origin/$GITHUB_BASE_REF, else origin/main). A violation is listed by tool, rule and the element it is on, as that
// element's tag and classes: one defect repeated down a list is one entry, and neither the data on the page, nor its
// order, nor the build's scoping attributes move it. Each run writes its full findings -- every node, its selector,
// HTML, message and help link -- to a11y.json in the test's output directory and prints one line of counts: P2-S8-T09's
// work list.
//
// The failure case is checked as a failure: the landing page is served again with an image that has no text alternative,
// in each mode, and the gate must report it as new, from axe and from pa11y both; a listed violation no page has any
// more, and one the base branch does not list, must be reported too.
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createServer, type AddressInfo } from 'node:net';
import { fileURLToPath } from 'node:url';
import { AxeBuilder } from '@axe-core/playwright';
import { chromium, expect, test as base, type Browser } from '@playwright/test';
import { builtRoutes, loadGroups, routeRegExp } from '../../scripts/route_groups.mjs';

const require = createRequire(import.meta.url);
const pa11y = require('pa11y');
// the puppeteer pa11y resolves for itself, so the browser pa11y is handed is driven by the client it was written for
const puppeteer = createRequire(require.resolve('pa11y'))('puppeteer');

type ModeName = 'light' | 'dark' | 'forced-colors' | 'contrast-more';
interface Mode { colorScheme: 'light' | 'dark'; forcedColors?: 'active'; contrast?: 'more'; what: string }
interface Archetype { name: string; family: string; route: string; requires?: string[]; basis: string }
interface Spec { modes: Record<ModeName, Mode>; standard: { axe: string[]; pa11y: string }; archetypes: Archetype[] }
interface Baseline { recorded: string; known: Record<string, Partial<Record<ModeName, string[]>>> }
interface Fallback { route: string; selector?: string }
/** One element one tool reports against one rule: `shape` is the element's tag and classes, `target` its selector. */
interface Found { tool: 'axe' | 'pa11y'; rule: string; shape: string; target: string; what: string }
interface Tools { browser: Browser; remote: any }

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => JSON.parse(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'));
const SPEC = read('../test/a11y/archetypes.json') as Spec;
const BASELINE = read('../test/a11y/baseline.json') as Baseline;
const MAP = read('../../scripts/route_fallback_map.json') as { families: Fallback[] };
const DIST = fileURLToPath(new URL('../dist', import.meta.url));
const BASELINE_PATH = 'site/test/a11y/baseline.json';

/** The ledger's eight, in its order (P2-S8-T03), and the done-when's four modes. */
const EIGHT = ['landing', 'benchmark-detail', 'taxonomy-term', 'browse', 'atlas', 'methodology', 'search', 'contribute'];
const FOUR: ModeName[] = ['light', 'dark', 'forced-colors', 'contrast-more'];
// pa11y is given the viewport Playwright opens its page at, so both tools read the same layout
const VIEWPORT = { width: 1280, height: 720 };

// ---- the gate, as pure functions ------------------------------------------------------------------------------------

/** An element as the start of its outer HTML says: its tag and classes, sorted. Used when the element cannot be found
 *  again in the page by its selector; null when the snippet is not an element. */
function shapeOf(html: string | null | undefined): string | null {
  const m = /^<([a-zA-Z][\w-]*)\b([^>]*)/.exec((html ?? '').trim());
  if (m == null) return null;
  const c = /\sclass\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))/i.exec(m[2]);
  const classes = (c == null ? '' : c[1] ?? c[2] ?? c[3]).split(/\s+/).filter((x) => x !== '' && !x.startsWith('astro-')).sort();
  return [m[1].toLowerCase(), ...classes].join('.');
}
/** The same, read from the element itself, in the page: [selector] -> [shape | null]. */
const SHAPES = (selectors: string[]) => selectors.map((s) => {
  try {
    const el = s === '' ? null : document.querySelector(s);
    return el == null ? null : [el.tagName.toLowerCase(), ...[...el.classList].filter((x) => !x.startsWith('astro-')).sort()].join('.');
  } catch {
    return null;
  }
});
const keyOf = (f: Found) => `${f.tool} ${f.rule} ${f.shape}`;

/** What fails one archetype in one mode: a violation the baseline does not list, and a listed one no longer found. */
function gateProblems(found: Found[], known: string[]): string[] {
  const keys = new Map<string, Found>();
  for (const f of found) if (!keys.has(keyOf(f))) keys.set(keyOf(f), f);
  const out: string[] = [];
  for (const [k, f] of [...keys].sort(([a], [b]) => (a < b ? -1 : 1))) {
    if (!known.includes(k)) out.push(`new violation: ${k} (${f.what}) at ${f.target}`);
  }
  for (const k of known) {
    if (!keys.has(k)) out.push(`no longer found, so take it out of ${BASELINE_PATH} (it only shrinks): ${k}`);
  }
  return out;
}

/** Every entry of `current` that `previous`, the baseline on the base branch, does not list. */
function grownProblems(current: Baseline, previous: Baseline, ref: string): string[] {
  const out: string[] = [];
  for (const [name, modes] of Object.entries(current.known)) {
    for (const [mode, keys] of Object.entries(modes ?? {})) {
      const before = previous.known[name]?.[mode as ModeName] ?? [];
      for (const k of keys ?? []) if (!before.includes(k)) out.push(`${name} ${mode}: ${k} is not in the baseline on ${ref}; it only shrinks`);
    }
  }
  return out;
}

/** What is wrong with archetypes.json read against the route families, the fallback map and the build. */
function specProblems(spec: Spec, families: { route: string }[], built: string[]): string[] {
  const out: string[] = [];
  const names = spec.archetypes.map((a) => a.name);
  if (JSON.stringify(names) !== JSON.stringify(EIGHT)) out.push(`the archetypes are ${names.join(', ')}, not the eight: ${EIGHT.join(', ')}`);
  if (JSON.stringify(Object.keys(spec.modes)) !== JSON.stringify(FOUR)) out.push(`the modes are ${Object.keys(spec.modes).join(', ')}, not ${FOUR.join(', ')}`);
  for (const a of spec.archetypes) {
    if (!families.some((f) => f.route === a.family)) out.push(`${a.name}: ${a.family} is no route family of scripts/route_groups.json`);
    else if (MAP.families.find((e) => e.route === a.family)?.selector == null) {
      out.push(`${a.name}: ${a.family} has no fallback element in scripts/route_fallback_map.json to know its page by`);
    }
    if (!routeRegExp(a.family).test(a.route)) out.push(`${a.name}: ${a.route} is not a page of ${a.family}`);
    if (!built.includes(a.route)) out.push(`${a.name}: ${a.route} is not built`);
  }
  return out;
}

/** The baseline on `ref`, or null when `ref` has none; throws when `ref` itself is not there to read. */
function baselineAt(ref: string): Baseline | null {
  const git = (...args: string[]) => execFileSync('git', ['-c', 'core.longpaths=true', ...args], { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  git('rev-parse', '--verify', '--quiet', `${ref}^{commit}`);
  try {
    return JSON.parse(git('show', `${ref}:${BASELINE_PATH}`)) as Baseline;
  } catch {
    return null;
  }
}

// ---- the two tools over one page ------------------------------------------------------------------------------------

/** A port nothing listens on now: the DevTools endpoint pa11y's puppeteer connects to. */
const freePort = () => new Promise<number>((resolve, reject) => {
  const server = createServer();
  server.on('error', reject);
  server.listen(0, '127.0.0.1', () => {
    const { port } = server.address() as AddressInfo;
    server.close(() => resolve(port));
  });
});

const test = base.extend<{}, { tools: Tools }>({
  tools: [async ({}, use) => {
    const port = await freePort();
    const browser = await chromium.launch({ args: [`--remote-debugging-port=${port}`] });
    try {
      const remote = await puppeteer.connect({ browserURL: `http://127.0.0.1:${port}`, defaultViewport: null });
      await use({ browser, remote });
      await remote.disconnect();
    } finally {
      await browser.close();
    }
  }, { scope: 'worker' }],
});

const MEDIA = () => ({
  dark: matchMedia('(prefers-color-scheme: dark)').matches,
  forced: matchMedia('(forced-colors: active)').matches,
  more: matchMedia('(prefers-contrast: more)').matches,
});
const expected = (m: Mode) => ({ dark: m.colorScheme === 'dark', forced: m.forcedColors === 'active', more: m.contrast === 'more' });
const archetypeSelectors = (a: Archetype) => [MAP.families.find((e) => e.route === a.family)?.selector ?? '', ...(a.requires ?? [])].filter(Boolean);

interface Audit { found: Found[]; problems: string[]; report: Record<string, unknown> }

/** Audit `route` in `mode` with axe-core and with pa11y. `problems` is what keeps the audit from counting: the page, the
 *  mode or a tool. `doctor` rewrites the page's HTML as served, to both tools. */
async function audit(tools: Tools, baseURL: string, route: string, mode: Mode, selectors: string[], doctor?: (html: string) => string): Promise<Audit> {
  const problems: string[] = [];
  const found: Found[] = [];
  const want = JSON.stringify(expected(mode));

  // axe-core, in a Playwright page
  const context = await tools.browser.newContext({
    baseURL, viewport: VIEWPORT, colorScheme: mode.colorScheme, forcedColors: mode.forcedColors ?? 'none', contrast: mode.contrast ?? 'no-preference',
  });
  let axe;
  try {
    const page = await context.newPage();
    if (doctor) {
      await page.route((u) => u.pathname === route, async (r) => {
        const res = await r.fetch();
        await r.fulfill({ response: res, body: doctor(await res.text()) });
      });
    }
    const res = await page.goto(route, { waitUntil: 'networkidle' });
    if (res?.status() !== 200) problems.push(`${route} answered ${res?.status() ?? 'nothing'}`);
    const media = JSON.stringify(await page.evaluate(MEDIA));
    if (media !== want) problems.push(`axe's page answers its media queries ${media}, not ${want}`);
    // the archetype is known by the page as sent: an island may take its fallback element over once it hydrates
    const sent = res == null ? '' : await res.text();
    const missing = await page.evaluate(([html, sels]) => {
      const doc = new DOMParser().parseFromString(html, 'text/html');
      return sels.filter((s) => doc.querySelector(s) == null);
    }, [sent, selectors] as [string, string[]]);
    for (const s of missing) problems.push(`${route} as sent has nothing matching ${s}`);
    axe = await new AxeBuilder({ page }).withTags(SPEC.standard.axe).analyze();
    if (axe.passes.length === 0) problems.push('axe-core passed no rule: it did not read the page');
    const nodes = axe.violations.flatMap((v) => v.nodes.map((n) => ({ v, n, target: n.target.map(String).join(' >> ') })));
    const shapes = await page.evaluate(SHAPES, nodes.map(({ n }) => (n.target.length === 1 && typeof n.target[0] === 'string' ? n.target[0] : '')));
    nodes.forEach(({ v, n, target }, i) => found.push({ tool: 'axe', rule: v.id, shape: shapes[i] ?? shapeOf(n.html) ?? '(page)', target, what: v.help }));
  } finally {
    await context.close();
  }

  // pa11y, in a page of the same browser, through its own puppeteer
  const page = await tools.remote.newPage();
  let result;
  try {
    await page.emulateMediaFeatures([
      { name: 'prefers-color-scheme', value: mode.colorScheme },
      { name: 'forced-colors', value: mode.forcedColors ?? 'none' },
      { name: 'prefers-contrast', value: mode.contrast ?? 'no-preference' },
    ]);
    if (doctor) {
      await page.setRequestInterception(true);
      page.on('request', async (req: any) => {
        if (req.isNavigationRequest() && new URL(req.url()).pathname === route) {
          await req.respond({ status: 200, contentType: 'text/html; charset=utf-8', body: doctor(await (await fetch(req.url())).text()) });
        } else {
          await req.continue();
        }
      });
    }
    result = await pa11y(new URL(route, baseURL).href, {
      browser: tools.remote, page, viewport: VIEWPORT, standard: SPEC.standard.pa11y, runners: ['htmlcs'], timeout: 90_000,
    });
    const media = JSON.stringify(await page.evaluate(MEDIA));
    if (media !== want) problems.push(`pa11y's page answers its media queries ${media}, not ${want}`);
    if (await page.evaluate(() => typeof (window as any).HTMLCS) !== 'object') problems.push('pa11y\'s runner, HTML_CodeSniffer, never reached the page');
    const shapes = await page.evaluate(SHAPES, result.issues.map((i: any) => i.selector ?? ''));
    result.issues.forEach((i: any, n: number) => found.push({ tool: 'pa11y', rule: i.code, shape: shapes[n] ?? shapeOf(i.context) ?? '(page)', target: i.selector, what: i.message }));
  } finally {
    await page.close();
  }

  const counts = new Map<string, number>();
  for (const f of found) counts.set(keyOf(f), (counts.get(keyOf(f)) ?? 0) + 1);
  const report = {
    route,
    axe: {
      engine: axe.testEngine,
      violations: axe.violations.map((v) => ({ rule: v.id, impact: v.impact, help: v.help, helpUrl: v.helpUrl, nodes: v.nodes.map((n) => ({ target: n.target, html: n.html, summary: n.failureSummary })) })),
    },
    pa11y: { pageUrl: result.pageUrl, standard: SPEC.standard.pa11y, issues: result.issues.map((i: any) => ({ code: i.code, message: i.message, selector: i.selector, context: i.context })) },
    keys: Object.fromEntries([...counts].sort(([a], [b]) => (a < b ? -1 : 1))),
  };
  return { found, problems, report };
}

// ---- the tests --------------------------------------------------------------------------------------------------------

test.describe.configure({ timeout: 180_000 });

/** One page in the four modes, each a test: an archetype against its baseline, any other route against none. */
function auditTests(a: Archetype, known: Baseline['known'][string], title: string) {
  for (const name of FOUR) {
    test(`${title} in ${name}: axe-core and pa11y find no violation the baseline does not list`, async ({ tools }) => {
      const { found, problems, report } = await audit(tools, test.info().project.use.baseURL!, a.route, SPEC.modes[name], archetypeSelectors(a));
      const listed = known[name] ?? [];
      const gate = gateProblems(found, listed);
      writeFileSync(test.info().outputPath('a11y.json'), JSON.stringify({ archetype: a.name, mode: name, ...report, known: listed, gate }, null, 2) + '\n');
      const count = (tool: Found['tool']) => {
        const of = found.filter((f) => f.tool === tool);
        return `${of.length} node(s) over ${new Set(of.map((f) => f.rule)).size} rule(s)`;
      };
      console.log(`a11y ${a.name} ${name}: axe ${count('axe')}, pa11y ${count('pa11y')}; ${Object.keys(report.keys as object).length} distinct, `
        + `${listed.length} in the baseline, ${gate.length} problem(s)`);
      expect(problems).toEqual([]);
      expect(gate).toEqual([]);
    });
  }
}

// `npm run test:a11y -- ROUTE...` (test/a11y/run.mjs) names routes in UAIBI_A11Y_ROUTES: the harness then audits those
// alone, in the four modes, an archetype's route against its baseline and any other built route against none.
const ROUTES = (process.env.UAIBI_A11Y_ROUTES ?? '').split(',').map((r) => r.trim()).filter(Boolean);

if (ROUTES.length > 0) {
  for (const route of ROUTES) {
    const a = SPEC.archetypes.find((x) => x.route === route);
    if (a != null) auditTests(a, BASELINE.known[a.name] ?? {}, `${a.name} (${route})`);
    else auditTests({ name: route, family: '', route, basis: 'named on the command line' }, {}, route);
  }
} else {
  test('the eight archetypes are named, each a built page of a route family the fallback map knows by its element', () => {
    const families = loadGroups().families;
    const built = builtRoutes(DIST);
    expect(specProblems(SPEC, families, built)).toEqual([]);
    // and a wrong archetype is caught: a ninth, a route of another family, an unbuilt page, a family with no element
    const [first] = SPEC.archetypes;
    const broken = { ...SPEC, archetypes: [{ ...first, route: '/nowhere/' }, ...SPEC.archetypes.slice(1), { ...first, name: 'ninth', family: '/claims/{id}/' }] };
    expect(specProblems(broken, families, built)).toEqual([
      `the archetypes are ${[...EIGHT, 'ninth'].join(', ')}, not the eight: ${EIGHT.join(', ')}`,
      'landing: /nowhere/ is not a page of /',
      'landing: /nowhere/ is not built',
      'ninth: /claims/{id}/ has no fallback element in scripts/route_fallback_map.json to know its page by',
      'ninth: / is not a page of /claims/{id}/',
    ]);
  });

  test('the baseline names only archetypes and modes the harness runs, and only shrinks against the base branch', () => {
    expect(BASELINE.recorded).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    for (const [name, modes] of Object.entries(BASELINE.known)) {
      expect(EIGHT, `baseline archetype ${name}`).toContain(name);
      for (const mode of Object.keys(modes ?? {})) expect(FOUR, `baseline mode ${name} ${mode}`).toContain(mode);
    }
    const ref = process.env.UAIBI_A11Y_BASE || (process.env.GITHUB_BASE_REF ? `origin/${process.env.GITHUB_BASE_REF}` : 'origin/main');
    const previous = baselineAt(ref);
    if (previous == null) test.info().annotations.push({ type: 'baseline', description: `${ref} has no ${BASELINE_PATH} yet: this change adds it` });
    else expect(grownProblems(BASELINE, previous, ref)).toEqual([]);
    // the failure case: an entry the base branch does not list
    const landing = { ...BASELINE.known.landing, light: [...(BASELINE.known.landing?.light ?? []), 'axe image-alt img'] };
    expect(grownProblems({ ...BASELINE, known: { ...BASELINE.known, landing } }, BASELINE, 'the base')).toEqual([
      'landing light: axe image-alt img is not in the baseline on the base; it only shrinks',
    ]);
  });

  test('a violation is keyed by the element it is on, and a listed one no longer found fails', () => {
    expect(shapeOf('<span data-absent="not-recorded" class="reason absent" data-astro-cid-x>not recorded</span>')).toBe('span.absent.reason');
    expect(shapeOf('<form role="search"><label for="q">Search th...</form>')).toBe('form');
    expect(shapeOf('a text node')).toBeNull();
    const f: Found = { tool: 'axe', rule: 'color-contrast', shape: 'span.absent', target: 'div:nth-child(4) > dd > .absent', what: 'contrast' };
    // one defect down a list is one entry
    expect(gateProblems([f, { ...f, target: 'div:nth-child(9) > dd > .absent' }], ['axe color-contrast span.absent'])).toEqual([]);
    expect(gateProblems([], ['axe color-contrast span.absent'])).toEqual([
      `no longer found, so take it out of ${BASELINE_PATH} (it only shrinks): axe color-contrast span.absent`,
    ]);
    expect(gateProblems([f], [])).toEqual(['new violation: axe color-contrast span.absent (contrast) at div:nth-child(4) > dd > .absent']);
  });

  test('the gate goes red on a new violation in every mode: an image with no text alternative, found by axe and by pa11y', async ({ tools }) => {
    const landing = SPEC.archetypes.find((a) => a.name === 'landing')!;
    const pixel = '<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" width="24" height="24">';
    const doctor = (html: string) => html.replace(/<main\b[^>]*>/, (m) => m + pixel);
    const baseURL = test.info().project.use.baseURL!;
    for (const name of FOUR) {
      const { found, problems } = await audit(tools, baseURL, landing.route, SPEC.modes[name], archetypeSelectors(landing), doctor);
      expect(problems, name).toEqual([]);
      const red = gateProblems(found, BASELINE.known.landing?.[name] ?? []).join('\n');
      expect(red, name).toMatch(/^new violation: axe image-alt img \(/m);
      expect(red, name).toMatch(/^new violation: pa11y WCAG2AA\.Principle1\.Guideline1_1\.1_1_1\.H37 img \(/m);
    }
  });

  for (const a of SPEC.archetypes) auditTests(a, BASELINE.known[a.name] ?? {}, `${a.name} (${a.route})`);
}
