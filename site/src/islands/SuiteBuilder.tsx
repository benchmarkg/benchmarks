// site/src/islands/SuiteBuilder.tsx -- P6-S4-T01 (10 V10 "Form", "Two words, used precisely throughout", "Basket
// persistence"; 10 "Filter state encoding"; 09 S8.1, S8.4). The V10 Suite Builder at /suite/: a three-pane working
// surface, pages/suite/index.astro mounting it with facets.json's content-hashed URL and the browse rail's vocabularies.
//
//   Find benchmarks   the filter/search pane: a search box over names, aliases and ids (lib/suite-basket.ts answers),
//                     the Atlas's four facet controls (domain, capability, evaluation method, lifecycle) with live
//                     counts (lib/browse-view.ts tally), and the results, each with its Add or Remove
//   Basket            the working selection: each entry with its Remove, the add-from-lasso and add-from-cell entry
//                     points, the working link and its copy button, and this browser's kept basket, offered, never applied
//   Analysis          the four computed panels' places (coverage, redundancy, cost and runtime, not covered), and the
//                     suite manifest, set apart from the basket
//
// The URL is the source of truth. Everything the page shows is decoded from the query string by lib/filter-url.ts, the
// basket as 10's `b` key beside the filter pane's d, c, em, lc and q, and every change is written back in canonical form:
// pushState for the basket and the facets, so Back steps through them, replaceState for each keystroke of the search. So
// a basket round-trips through its link alone, with no server state and nothing read from storage: tests/suite-basket.
// spec.ts opens a link in a browser context that has never seen the page. localStorage only mirrors it, and is read once,
// to offer what it kept (lib/suite-basket.ts says when it is written). An id the link names that the index does not have
// is left out of the basket and named in a visible "ignored filter: b=..." notice (10 "Filter state encoding").
//
// The basket is never the citable object (10 V10, "the failure mode to avoid is a UI that pretends a scratch selection
// and a citable export are the same thing"). The basket pane says it is a working selection and not citable, its link is
// labelled a working link and says it is not a citation, and the suite manifest -- what a basket exports, and what is to
// be cited -- is its own section in the analysis pane, drawn differently (a solid rule where the basket's is dashed), with
// the index commit an export would pin. Exporting it is not built (`bench suite`, P6-S4-T04, writes suite.yaml), and the
// section says so rather than offering a button that does nothing. Nothing on the page is labelled a permalink or "cite".
//
// The four panels are computed in JavaScript from structured fields, never by a model (10 V10); P6-S4-T02 computes them
// (islands/suite/panels.ts), and until then each place says it is not computed yet. The hard exclusion filters and their
// "excluded N entries because ..." panel are P6-S4-T03's.
//
// The entry points (10 V10's sketch: "+ from lasso (V1)", "+ from cell (V2)"):
//   from lasso   the Atlas's selection toolbar links to /suite/?b=<its ids> (islands/AtlasSelection.tsx), and this pane
//                links to the Atlas. Following that link from here first mirrors the basket to this browser, so when the
//                Atlas's link brings a selection back, the entries kept here are offered for adding to it
//   from cell    the Coverage Map (10 V2, /coverage/) is not built on this branch (P4-S3-T01 builds it), so the entry
//                point says so, without a link. Its brush is to link lib/suite-basket.ts suiteHref(the cell's ids)
//
// Without JavaScript (08 S8.3; 09 S8.6) the page as sent is the server's: the panes' headings, the basket's note that the
// basket lives in the address and needs JavaScript to be read, the analysis places and the manifest section, and, in the
// filter pane, this island's children -- the server-rendered directory of every benchmark by domain family, each linking
// its page, which scripts/route_fallback_map.json holds the route to. The static suite report a ?b= link renders without
// JavaScript is P6-S4-T07's (pages/suite/report.astro). Once facets.json is in, the live results replace the directory in
// place (an Astro <astro-slot>, which React mounts once and drops), so the page never holds two lists.
//
// Announcements: one status region, polite (09 S8.4), saying the basket's new size after each change; the filter's counts
// are not announced, the results being the page's to read, not news.
//
// The route's JavaScript is held to 10's V10 row, 80 KB (scripts/route_groups.json): React's runtime and this island,
// with lib/browse-view.ts's bitset tally. No other library.
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { decode, encode, ignoredNotice, type FilterState, type Ignored } from '../lib/filter-url.ts';
import {
  buildIndex, chips, cleared, readFacets, tally, unapplied, vocabularies, type FacetRow, type Index, type RailGroup,
  type RailKey,
} from '../lib/browse-view.ts';
import { added, answers, basketOf, offer, removed, store, stored, suiteHref, withBasket, withIds } from '../lib/suite-basket.ts';

interface Props {
  facetsHref: string | null;    // lib/manifest.ts dataHref('facets.json'); null when the build wrote no manifest
  groups: RailGroup[];          // the browse rail's vocabularies, definitions left out
  commit: string;               // the commit this build read the index at, which an exported manifest pins (lib/release.ts)
  children?: ReactNode;         // pages/suite/index.astro: the directory of every benchmark, as the server rendered it
}

type Load =
  | { status: 'loading' }
  | { status: 'unavailable' }
  | { status: 'failed'; reason: string }
  | { status: 'ready'; index: Index };

/** The rail keys the filter pane offers a control for: the Atlas's four (islands/Atlas.tsx CONTROLS). */
const CONTROLS: readonly RailKey[] = ['d', 'c', 'em', 'lc'];

/** The analysis pane's four computed panels (10 V10), in its order, with what each will show. */
const PANELS = [
  { id: 'coverage', title: 'Coverage', what: 'Where the entries sit on the domain and capability matrix, every family row shown, empty ones included.' },
  { id: 'redundancy', title: 'Redundancy', what: 'Pairs that share a subdomain and capability, or carry a sourced correlation above 0.8, with the source.' },
  { id: 'cost', title: 'Cost and runtime', what: 'The estimate ranges of cost and runtime summed, naming every entry with no estimate curated.' },
  { id: 'not-covered', title: 'Not covered', what: 'The capabilities and domains the basket measures nothing of.' },
];

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
/** This browser's storage, or null where reading it throws (a private window, blocked site data). */
const local = () => {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};
/** A group's terms in the select's order: for the domain, each family followed by its subdomains (as the Atlas's). */
const ordered = (g: RailGroup) => (g.key !== 'd' ? g.terms
  : g.terms.filter((t) => t.parent == null).flatMap((f) => [f, ...g.terms.filter((t) => t.parent === f.id)]));

export default function SuiteBuilder({ facetsHref, groups, commit, children }: Props) {
  const [load, setLoad] = useState<Load>(facetsHref == null ? { status: 'unavailable' } : { status: 'loading' });
  const [state, setState] = useState<FilterState>({});
  const [ignored, setIgnored] = useState<Ignored[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [kept, setKept] = useState<string[]>([]);       // the basket this browser kept, read once, on arrival
  const [said, setSaid] = useState('');
  const index = load.status === 'ready' ? load.index : null;
  // the vocabularies the query string is read with: the rail's terms, and once the index is in, its ids for `b`
  const vocab = useMemo(() => (index == null ? vocabularies(groups) : withIds(vocabularies(groups), index.rows.map((r) => r.id))), [groups, index]);

  useEffect(() => {
    setHydrated(true);
    setKept(stored(local()));
  }, []);

  // the page's state: from the query string on load, again once the index can say which ids it has, and on Back/Forward
  useEffect(() => {
    const read = () => {
      const d = decode(window.location.search, vocab);
      setState(d.state);
      setIgnored(d.ignored);
    };
    read();
    window.addEventListener('popstate', read);
    return () => window.removeEventListener('popstate', read);
  }, [vocab]);

  // the rows: facets.json, once, by its hashed URL
  useEffect(() => {
    if (facetsHref == null) return;
    let live = true;
    fetch(facetsHref)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return readFacets(await res.json());
      })
      .then((got) => {
        if (live) setLoad('error' in got ? { status: 'failed', reason: got.error } : { status: 'ready', index: buildIndex(groups, got.rows) });
      })
      .catch((e: unknown) => {
        if (live) setLoad({ status: 'failed', reason: e instanceof Error ? e.message : String(e) });
      });
    return () => {
      live = false;
    };
  }, [facetsHref, groups]);

  const basket = basketOf(state);
  const rows = useMemo(() => new Map<string, FacetRow>((index?.rows ?? []).map((r) => [r.id, r])), [index]);
  const counted = useMemo(() => (index != null ? tally(index, state) : null), [index, state]);
  const results = useMemo(() => (index == null || counted == null ? []
    : counted.matches.map((i) => index.rows[i]).filter((r) => answers(r, state.q))), [index, counted, state.q]);

  /** Write `next` to the page and to the URL, canonical; `push` adds a history entry, so Back undoes it. */
  const write = (next: FilterState, push: boolean) => {
    setState(next);
    setIgnored([]);
    const q = encode(next);
    const url = `${window.location.pathname}${q.length > 0 ? `?${q}` : ''}`;
    if (push) window.history.pushState(null, '', url);
    else window.history.replaceState(null, '', url);
  };
  /** A change to the basket: to the URL, mirrored to this browser, and its new size said once (09 S8.4). */
  const edit = (next: FilterState) => {
    write(next, true);
    const n = basketOf(next).length;
    store(local(), basketOf(next));
    setSaid(`${plural(n, 'benchmark', 'benchmarks')} in the basket`);
  };

  const dLabels = new Map((groups.find((g) => g.key === 'd')?.terms ?? []).map((t) => [t.id, t.label] as const));
  const nameOf = (id: string) => rows.get(id)?.name ?? id;
  const whereOf = (r: FacetRow) => `${dLabels.get(r.domain) ?? r.domain} › ${dLabels.get(r.subdomain) ?? r.subdomain}`;
  const inBasket = new Set(basket);
  const filterIgnored = ignored.filter((i) => i.key !== 'b');
  const basketIgnored = ignored.filter((i) => i.key === 'b');
  const kept0 = offer(kept, basket).filter((id) => index == null || rows.has(id));
  const applied = chips(groups, state);
  const notApplied = unapplied(state).filter((k) => k.key !== 'b' && k.key !== 'q');
  const link = hydrated ? new URL(suiteHref(basket), window.location.origin).href : suiteHref(basket);

  // ---- the filter/search pane -------------------------------------------------------------------------------------
  const control = (k: RailKey) => {
    const gi = groups.findIndex((g) => g.key === k);
    if (gi < 0 || counted == null) return null;
    const g = groups[gi];
    const chosen = state[k] ?? [];
    const value = chosen.length === 1 ? chosen[0] : chosen.length > 1 ? '*' : '';
    return (
      <label key={k} className="control">
        <span className="label">{g.label}</span>
        <select data-control={k} value={value} onChange={(e) => {
          const v = e.currentTarget.value;
          const next: FilterState = { ...state };
          if (v === '') delete next[k];
          else next[k] = [v];
          write(next, true);
        }}>
          <option value="">Any</option>
          {chosen.length > 1 ? <option value="*" disabled>{plural(chosen.length, 'term', 'terms')} from the link</option> : null}
          {ordered(g).map((t) => {
            const n = counted.counts[gi].get(t.id) ?? 0;
            return <option key={t.id} value={t.id} disabled={n === 0 && !chosen.includes(t.id)}>{k === 'd' && t.parent != null ? '  ' : ''}{t.label} ({n})</option>;
          })}
        </select>
      </label>
    );
  };

  let find: ReactNode;
  if (index == null) {
    find = (
      <>
        {load.status === 'unavailable'
          ? <p className="notice" data-find-state="unavailable">This build has no filter index (facets.json), so the list cannot be searched or added from here.</p>
          : load.status === 'failed'
            ? <p className="notice" data-find-state="failed">The filter index could not be read ({load.reason}), so the list cannot be searched or added from here.</p>
            : null}
        {children}
      </>
    );
  } else {
    const searched = (state.q ?? '').trim() !== '';
    const filtered = applied.length > 0 || searched;
    find = (
      <>
        <div className="controls">
          <label className="control search">
            <span className="label">Search names, aliases and ids</span>
            <input type="search" data-control="q" value={state.q ?? ''} onChange={(e) => write({ ...state, q: e.currentTarget.value }, false)} />
          </label>
          {CONTROLS.map(control)}
        </div>
        <div className="applied">
          <p className="count" data-count>{filtered ? `${results.length} of ${index.rows.length} benchmarks match` : plural(index.rows.length, 'benchmark', 'benchmarks')}</p>
          {filtered
            ? <button type="button" className="clear" onClick={() => {
                const next = cleared(state, groups);
                delete next.q;
                write(next, true);
              }}>Clear filters</button>
            : null}
        </div>
        {filterIgnored.length > 0
          ? <div className="notice" data-ignored>
              <p>The link names {filterIgnored.length === 1 ? 'a value' : 'values'} this index does not have, left out of the filter:</p>
              <ul>{filterIgnored.map((i) => <li key={`${i.key}=${i.value}`}><code>{ignoredNotice(i)}</code></li>)}</ul>
            </div>
          : null}
        {notApplied.length > 0
          ? <p className="notice" data-unapplied>Kept in the link but not applied here: {notApplied.map((k, i) => <span key={`${k.key}=${k.value}`}>{i > 0 ? ', ' : ''}<code>{k.key}={k.value}</code></span>)}.</p>
          : null}
        {index.rows.length === 0
          ? <p className="none" data-empty="unpublished">No benchmark is published yet, so there is nothing to add. An entry is published only once a person has verified it.</p>
          : results.length === 0
            ? <p className="none" data-empty="filter">No benchmark matches {applied.length + (searched ? 1 : 0) > 1 ? 'all of these filters' : 'this filter'}.</p>
            : (
              <ul className="results" data-suite-results>
                {results.map((r) => {
                  const has = inBasket.has(r.id);
                  return (
                    <li key={r.id} data-result={r.id} data-in-basket={has ? '' : undefined}>
                      <span className="what"><a href={`/benchmarks/${r.id}/`}>{r.name}</a> <span className="meta">{whereOf(r)}</span></span>
                      <button type="button" className="add" onClick={() => edit(has ? removed(state, r.id) : added(state, [r.id]))}>
                        {has ? 'Remove' : 'Add'}<span className="visually-hidden"> {r.name} {has ? 'from' : 'to'} the basket</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
      </>
    );
  }

  // ---- the basket ---------------------------------------------------------------------------------------------------
  const entries = [...basket].sort((a, b) => nameOf(a).localeCompare(nameOf(b), 'en') || (a < b ? -1 : 1));
  let held: ReactNode;
  if (!hydrated) {
    held = (
      <p className="hint" data-suite-nojs>The basket is kept in this page's address, as <code>?b=</code> and the benchmarks' ids, and is read and edited by JavaScript, which has not run here. Without it this page cannot show the basket a link names; every benchmark is listed under Find benchmarks, each linking its page.</p>
    );
  } else {
    held = (
      <>
        {kept0.length > 0
          ? <div className="notice" data-suite-offer={kept0.join(' ')}>
              <p>{basket.length === 0
                ? `This browser kept a basket of ${plural(kept0.length, 'benchmark', 'benchmarks')} from an earlier visit. This link names an empty one.`
                : `This browser kept ${plural(kept0.length, 'more benchmark', 'more benchmarks')} from an earlier basket that this link does not name.`}</p>
              <p className="actions">
                <button type="button" onClick={() => edit(added(state, kept0))}>{basket.length === 0 ? 'Restore them' : 'Add them'}</button>
                <button type="button" onClick={() => setKept([])}>Dismiss</button>
              </p>
            </div>
          : null}
        {basketIgnored.length > 0
          ? <div className="notice" data-ignored="b">
              <p>The link names {basketIgnored.length === 1 ? 'an entry' : 'entries'} this index does not have, left out of the basket:</p>
              <ul>{basketIgnored.map((i) => <li key={i.value}><code>{ignoredNotice(i)}</code></li>)}</ul>
            </div>
          : null}
        {entries.length > 0
          ? <ul className="entries" data-basket-entries>
              {entries.map((id) => {
                const r = rows.get(id);
                return (
                  <li key={id} data-basket-entry={id}>
                    <span className="what">{r != null ? <a href={`/benchmarks/${id}/`}>{r.name}</a> : <code>{id}</code>}{r != null ? <> <span className="meta">{whereOf(r)}</span></> : null}</span>
                    <button type="button" className="remove" onClick={() => edit(removed(state, id))}>
                      <span aria-hidden="true">×</span><span className="visually-hidden">Remove {nameOf(id)} from the basket</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          : <p className="none" data-empty="basket">The basket is empty. Add benchmarks from the list, or from a selection on the Atlas.</p>}
        {entries.length > 1 ? <p className="actions"><button type="button" className="clear" onClick={() => edit(withBasket(state, []))}>Empty the basket</button></p> : null}
        <div className="link" data-suite-link-box>
          <label htmlFor="suite-link">Working link to this basket</label>
          <span className="link-row">
            <input id="suite-link" type="text" readOnly value={link} data-suite-link onFocus={(e) => e.currentTarget.select()} />
            <button type="button" onClick={() => {
              Promise.resolve()
                .then(() => navigator.clipboard.writeText(link))
                .then(() => setSaid('Working link copied'), () => setSaid('The link could not be copied: select it and copy it'));
            }}>Copy link</button>
          </span>
          <p className="hint">It reopens this selection in any browser, with nothing stored on a server. It is not a citation: a basket changes while it is edited, and what its entries say is whatever the index holds when the link is opened.</p>
        </div>
      </>
    );
  }

  return (
    <div className="suite-builder" data-suite-builder data-state={hydrated ? load.status : 'server'} data-basket={basket.join(' ')}>
      <section className="pane find" aria-labelledby="suite-find-h" data-suite-find>
        <h2 id="suite-find-h">Find benchmarks</h2>
        {find}
      </section>

      <section className="pane basket" aria-labelledby="suite-basket-h" data-suite-basket data-citable="no">
        <h2 id="suite-basket-h">Basket {hydrated ? <span className="count">({basket.length})</span> : null}</h2>
        <p className="scratch" data-scratch>Working selection, not citable</p>
        {held}
        <ul className="entry-points" aria-label="Add from another view">
          <li data-entry-point="lasso">
            <a href="/atlas/" onClick={() => store(local(), basket)}>+ from lasso (Atlas)</a>
            <span className="hint"> Select benchmarks on the map, then follow its “Add to suite basket” link; what this basket holds is offered back for adding.</span>
          </li>
          <li data-entry-point="cell" data-not-built>
            <span>+ from cell (Coverage Map)</span>
            <span className="hint"> Not built yet: the Coverage Map has no page.</span>
          </li>
        </ul>
      </section>

      <section className="pane analysis" aria-labelledby="suite-analysis-h" data-suite-analysis>
        <h2 id="suite-analysis-h">Analysis</h2>
        <p className="hint">Computed in the browser from the entries' structured fields, never by a model.</p>
        {PANELS.map((p) => (
          <section key={p.id} className="panel" data-panel={p.id} aria-labelledby={`suite-panel-${p.id}`}>
            <h3 id={`suite-panel-${p.id}`}>{p.title}</h3>
            <p className="what">{p.what}</p>
            <p className="not-built" data-not-built>Not computed yet.</p>
          </section>
        ))}
        <section className="manifest" data-suite-manifest data-citable="yes" aria-labelledby="suite-manifest-h">
          <h3 id="suite-manifest-h">Suite manifest, the citable export</h3>
          <p>A basket is a scratch selection, and its link is not a record of anything. What a suite is cited by is the manifest a basket exports: a <code>suite.yaml</code> with each entry's id and version pin, the index commit it was read at (this page: <code data-suite-commit>{commit}</code>), and the recommended conditions for each entry.</p>
          <p className="not-built" data-not-built>Exporting the manifest is not built yet, so nothing on this page is citable.</p>
        </section>
      </section>

      <p role="status" className="visually-hidden" data-suite-status>{said}</p>
    </div>
  );
}
