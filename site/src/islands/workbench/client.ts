// site/src/islands/workbench/client.ts -- P3-S10-T05 (10 V5; 08 S4.1, S4.3). The Comparison Workbench's script: the
// selection in the address, applied to the table components/Workbench.astro rendered at build time.
//
// On entering the page it loads claims.json and derived/comparability.json, then corpus.json, each by the content-hashed
// URL the page names (08 S4.3's order for the workbench; S4.1: corpus.json loads lazily "on entering the Workbench",
// and no other view loads it). corpus.json is the index a pasted id is checked against: every benchmark and system the
// build publishes, those with no curated claim included, which claims.json alone cannot name. Before applying anything
// it checks that the claims it fetched are the ones the table was rendered from, claim by claim and key by key, and
// derived/comparability.json's groups against them (lib/workbench.ts `view` runs compare() over every whole group), and
// applies nothing if not: the build's table stays, with the reason.
//
// The address is the state. A selection, a pasted list (ids=, rewritten to its canonical b= and sys= in place) or a
// restriction (k=) is read on load; every control is a link or a GET form, so changing the selection is navigating to
// its URL and the history is the reader's. The table is re-composed through lib/workbench.ts `view`, the function the
// build rendered with: the claim blocks are the build's own, moved into their cells (so a number is drawn by one
// component, ProvenanceDetails, whichever side composed the table), their set labels rewritten; the column banners are
// built here in ComparabilityBanner's markup and words, from the Comparison lib/comparability.ts returns.
//
// No chart library: 10 V5's parallel-coordinates plot is not built (Workbench.astro says why), so this script is the
// route's whole JavaScript beside the theme toggle.
import { parseDiffGroups, unknownsOn, DEFER_ABOVE, type Cell, type Comparison } from '../../lib/comparability.ts';
import {
  cellKey, columnNote, columnState, compareHref, constrains, encode, pasted, plural, readQuery, resolve, restrictTo, restrictedNote, slug,
  spansNote, summary, systemOf, unrestrict, view, type Column, type Ignored, type Index, type View,
} from '../../lib/workbench.ts';
import type { ClaimRow } from '../../lib/claims';

type Kid = Node | string | null | undefined | false;
function h(tag: string, attrs: Record<string, string | number | null | undefined> = {}, ...kids: (Kid | Kid[])[]): HTMLElement {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, String(v));
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
  return el;
}
const code = (s: string) => h('code', {}, s);

async function json(href: string): Promise<any> {
  const res = await fetch(href);
  if (!res.ok) throw new Error(`${href} answered HTTP ${res.status}`);
  return res.json();
}

const root = document.querySelector<HTMLElement>('[data-workbench]');
if (root != null) void main(root);

async function main(root: HTMLElement): Promise<void> {
  const status = root.querySelector<HTMLElement>('[data-wb-status]')!;
  const say = (state: string, text: string) => {
    root.dataset.workbenchLive = state;
    status.textContent = text;
  };
  const { claimsHref, comparabilityHref, corpusHref } = root.dataset;
  if (!claimsHref || !comparabilityHref || !corpusHref) {
    say('unavailable', 'This build ships no content-hashed claims, comparability or corpus artifact, so no selection can be applied: the table is the build\'s, every curated claim.');
    return;
  }
  say('loading', 'Loading the claims, their condition sets and the index, to apply the selection in the address.');
  let claims: { claims: ClaimRow[]; drafts?: boolean };
  let diff: unknown;
  let corpus: { entities: Record<string, { id: string; name?: string }[]> };
  try {
    [claims, diff] = await Promise.all([json(claimsHref), json(comparabilityHref)]);
    corpus = await json(corpusHref);
  } catch (e) {
    say('failed', `The workbench's data did not load (${(e as Error).message}), so no selection is applied: the table is the build's, every curated claim.`);
    return;
  }
  const blocks = new Map([...root.querySelectorAll<HTMLElement>('[data-wb-claim]')].map((el) => [el.dataset.wbClaim!, el]));
  const rows = claims.claims;
  if (rows.length !== blocks.size || rows.some((r) => blocks.get(r.claim.id)?.dataset.key !== r.comparability.comparability_key)) {
    say('failed', 'The claims this page loaded are not the ones its table was built from, so no selection is applied: the table is the build\'s, every curated claim.');
    return;
  }
  const names = (kind: string) => new Map((corpus.entities[kind] ?? []).map((e) => [e.id, e.name ?? e.id]));
  const index: Index = { benchmarks: names('benchmark'), systems: names('system'), metrics: names('metric'), rows };
  let v: View;
  let ignored: Ignored[];
  try {
    const groups = parseDiffGroups(diff, claims.drafts === true, comparabilityHref);
    const r = resolve(readQuery(location.search), index);
    ignored = r.ignored;
    v = view(index, groups, r.selection);
  } catch (e) {
    say('failed', `The selection could not be applied (${(e as Error).message}): the table is the build's, every curated claim.`);
    return;
  }
  const href = compareHref(v.selection);
  if (location.pathname + location.search !== href) history.replaceState(null, '', href + location.hash);
  root.querySelector('[data-wb-static]')?.remove();
  const form = root.querySelector<HTMLFormElement>('[data-wb-form]')!;
  form.querySelector<HTMLTextAreaElement>('textarea[name="ids"]')!.value = pasted(v.selection);
  form.querySelector<HTMLInputElement>('input[name="k"]')!.value = v.selection.k.join(',');
  if (!constrains(v.selection) && ignored.length === 0) {
    say('ready', 'The address selects everything, so the table is every curated claim. Paste ids to narrow it.');
    return;
  }
  render(root, v, ignored, index, blocks);
  say('applied', constrains(v.selection) ? 'The table shows the selection in the address.' : 'The address selects nothing this build has, so the table is every curated claim.');
}

// ---- the view -------------------------------------------------------------------------------------------------------

function render(root: HTMLElement, v: View, ignored: Ignored[], index: Index, blocks: Map<string, HTMLElement>): void {
  const tpl = root.querySelector<HTMLTemplateElement>('template[data-wb-templates]')!;
  const token = (name: 'none' | 'unknown') => tpl.content.querySelector(`[data-wb-t="${name}"]`)!.cloneNode(true) as HTMLElement;
  const name = (kind: 'benchmarks' | 'systems' | 'metrics', id: string) => index[kind].get(id) ?? id;
  const box = root.querySelector<HTMLElement>('[data-workbench-view]')!;
  box.dataset.selection = encode(v.selection);
  box.dataset.claimsTotal = String(v.claims);
  box.dataset.dropped = String(v.dropped);

  const parts: Node[] = [h('p', { class: 'summary', 'data-wb-summary': '' }, summary(v))];
  if (ignored.length > 0) {
    parts.push(h('div', { class: 'ignored', 'data-wb-ignored': '', role: 'note' },
      h('p', {}, `${plural(ignored.length, 'value', 'values')} in the address ${ignored.length === 1 ? 'is' : 'are'} not in this selection:`),
      h('ul', {}, ignored.map((i) => h('li', { 'data-ignored-key': i.key, 'data-ignored-value': i.value }, 'ignored filter: ', code(`${i.key}=${i.value}`), ` (${i.why})`)))));
  }

  const said = v.columns.filter((c) => c.comparison != null && (c.comparison.state === 'not-comparable' || c.restricted.length > 0
    || c.comparison.sets.some((s) => s.state === 'possibly-comparable')));
  const refused = v.columns.filter((c) => c.comparison?.state === 'not-comparable').length;
  const banners = h('section', { class: 'comparability', 'data-wb-banners': '', 'aria-labelledby': 'wb-banners-h' },
    h('h2', { id: 'wb-banners-h' }, 'Comparability ', h('span', { class: 'count' }, `(${refused} of ${v.columns.length} ${v.columns.length === 1 ? 'column spans' : 'columns span'} condition sets)`)));
  if (said.length === 0) banners.append(h('p', { 'data-wb-banners-none': '' }, 'Every column holds claims of one condition set, with no material field unknown on claims shown together.'));
  for (const c of said) banners.append(columnBanners(c, v, name, token));
  parts.push(banners);

  const head = h('tr', {}, h('th', { scope: 'col' }, 'System'), v.columns.map((c) => h('th', { scope: 'col', 'data-col': c.id, 'data-col-state': columnState(c), 'data-claims-total': c.comparison?.total ?? 0 },
    index.benchmarks.has(c.benchmark) ? h('a', { href: `/benchmarks/${c.benchmark}/` }, name('benchmarks', c.benchmark)) : code(c.benchmark),
    c.metric != null && h('span', { class: 'metric' }, name('metrics', c.metric)),
    columnNote(c) != null && h('span', { class: 'note', 'data-col-note': '' }, columnNote(c)!))));
  const body = h('tbody', {}, v.rows.map((r) => h('tr', { 'data-system': r.system, 'data-spans-sets': r.spans },
    h('th', { scope: 'row' }, index.systems.has(r.system) ? h('a', { href: `/systems/${r.system}/` }, name('systems', r.system)) : code(r.system),
      spansNote(r) != null && h('span', { class: 'note', 'data-wb-spans': '' }, spansNote(r)!)),
    v.columns.map((c) => cell(c, r.system, v, blocks, token)))));
  const table = h('table', { 'data-wb-table': '', id: 'wb-table' },
    h('caption', {}, 'Systems by benchmark and metric. Each number carries its verification and how many of its material conditions it states; where a column spans condition sets, each claim says which set it is in.'),
    h('thead', {}, head), body);
  parts.push(h('div', { class: 'scroll', tabindex: 0, role: 'region', 'aria-label': 'The comparison table' }, table));
  box.replaceChildren(...parts);
}

/** One cell: the build's claim blocks for it, each told its set, then what the restriction dropped, or the absence. */
function cell(c: Column, system: string, v: View, blocks: Map<string, HTMLElement>, token: (n: 'none') => HTMLElement): HTMLElement {
  const td = h('td', { 'data-col': c.id });
  const many = c.comparison?.state === 'not-comparable';
  const list = v.cells.get(cellKey(c.id, system)) ?? [];
  for (const row of list) {
    const block = blocks.get(row.claim.id)!;
    const label = c.setOf.get(row.claim.id)!;
    block.dataset.set = label;
    block.dataset.setState = c.comparison!.sets.find((s) => s.label === label)!.state;
    let tag = block.querySelector<HTMLElement>(':scope > [data-set-label]');
    if (many) {
      if (tag == null) {
        tag = h('span', { class: 'set', 'data-set-label': '' });
        block.prepend(tag);
      }
      tag.textContent = `Set ${label}`;
    } else tag?.remove();
    td.append(block);
  }
  const dropped = c.dropped.filter((d) => systemOf(d.claim.system) === system).length;
  if (dropped > 0) td.append(h('span', { class: 'dropped', 'data-wb-dropped': dropped }, `${dropped} dropped by the restriction`));
  if (list.length === 0 && dropped === 0) td.append(token('none'));
  return td;
}

/** A column's section of banners: ComparabilityBanner's two kinds, in its markup and words, and the restriction count. */
function columnBanners(c: Column, v: View, name: (k: 'benchmarks' | 'systems' | 'metrics', id: string) => string,
  token: (n: 'unknown') => HTMLElement): HTMLElement {
  const g = c.comparison!;
  const id = `wb-${slug(c.id)}`;
  const refused = g.state === 'not-comparable';
  const sec = h('section', { class: 'column-banners', 'data-wb-col-banners': c.id, 'aria-labelledby': `${id}-h` },
    h('h3', { id: `${id}-h` }, `${name('benchmarks', c.benchmark)} · ${name('metrics', c.metric!)} `, code(c.metric!)));
  if (refused && g.restrict != null) sec.append(differ(g, `${id}-diff`, c, v, token));
  for (const s of g.sets.filter((x) => x.state === 'possibly-comparable')) {
    const bid = `${id}-set-${s.label.toLowerCase()}-unknown`;
    const unknowns = unknownsOn(s);
    const fields = [...new Set(unknowns.flatMap((u) => u.fields))].sort();
    const H = refused ? 'h5' : 'h4';
    sec.append(h('div', { 'data-set-banner': s.label }, h('section', { class: 'wb-banner', 'data-comparability-unknown': '', 'data-key': s.key, role: 'region', 'aria-labelledby': `${bid}-heading` },
      h(H, { class: 'title', id: `${bid}-heading` }, h('span', { 'aria-hidden': 'true' }, '?'),
        ` Possibly comparable: ${plural(unknowns.length, 'claim shares', 'claims share')} one condition set, with ${plural(fields.length, 'material field', 'material fields')} unknown`),
      h('p', {}, 'The shared comparability key confirms only the fields these claims state. A material field none of them states is unknown on each, so they agree on it only in what they leave unknown:'),
      h('table', { 'data-unknowns': '' },
        h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Claim'), h('th', { scope: 'col' }, 'Unknown material fields'))),
        h('tbody', {}, unknowns.map((u) => h('tr', { 'data-unknown-claim': u.claim },
          h('th', { scope: 'row' }, `${name('systems', systemOf(u.system))} `, code(u.claim)),
          h('td', {}, u.fields.flatMap((f, i) => [h('code', { 'data-unknown-field': f }, f), i < u.fields.length - 1 ? ', ' : null])))))))));
  }
  if (c.restricted.length > 0) {
    sec.append(h('p', { class: 'restricted', 'data-wb-restricted': '', 'data-dropped': c.dropped.length }, `${restrictedNote(c)} `,
      h('a', { href: compareHref(unrestrict(v.selection, c)) }, 'Show them')));
  }
  return sec;
}

/** ComparabilityBanner kind="differ", built here: the field-by-field table instead of one chart, and the two ways on. */
function differ(g: Comparison, id: string, c: Column, v: View, token: (n: 'unknown') => HTMLElement): HTMLElement {
  const r = g.restrict!;
  const value = (x: Cell) => (x.kind === 'value' ? x.text : x.kind === 'none' ? h('span', { class: 'none' }, 'none') : token('unknown'));
  const whole = c.whole;
  return h('section', { class: 'wb-banner', 'data-comparability': '', 'data-diff-status': g.diff_status, role: 'region', 'aria-labelledby': `${id}-heading` },
    h('h4', { class: 'title', id: `${id}-heading` }, h('span', { 'aria-hidden': 'true' }, '≠'), ` These results were produced under ${g.sets.length} different condition sets`),
    g.diff_status === 'computed'
      ? [h('p', {}, `They differ in ${plural(g.diff.length, 'material field', 'material fields')}, so they are not drawn as one chart:`),
        h('div', { class: 'scroll', tabindex: 0, role: 'region', 'aria-label': 'Material fields that differ between the condition sets' },
          h('table', { 'data-diff': '' },
            h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Field'), g.sets.map((s) => h('th', { scope: 'col', 'data-set-col': s.label }, `Set ${s.label} `, h('span', { class: 'n' }, `(${plural(s.rows.length, 'claim', 'claims')})`))))),
            h('tbody', {}, g.diff.map((d) => h('tr', { 'data-diff-field': d.field }, h('th', { scope: 'row' }, code(d.field)),
              d.values.map((x) => h('td', { 'data-cell': x.kind }, value(x))))))))]
      : h('p', { 'data-diff-deferred': '' }, `The build computes a field-by-field diff for a group of ${DEFER_ABOVE} claims or fewer (08 S3.2), and this one holds ${plural(whole, 'claim', 'claims')}, so the fields these sets differ in are not computed, and they are not drawn as one chart. The sets: `,
        g.sets.map((s, i) => h('span', { 'data-set-col': s.label }, `Set ${s.label} (${plural(s.rows.length, 'claim', 'claims')})${i < g.sets.length - 1 ? ', ' : '.'}`))),
    h('p', { class: 'actions' },
      h('a', { href: compareHref(restrictTo(v.selection, g.sets[0].key)), 'data-action': 'restrict', 'data-dropped': r.drops }, `Restrict to Set ${r.label}, one condition set (${r.drops} of ${plural(g.total, 'claim', 'claims')} dropped)`),
      ' ',
      h('a', { href: '#wb-table', 'data-action': 'proceed' }, 'Proceed with every affected cell flagged')));
}
