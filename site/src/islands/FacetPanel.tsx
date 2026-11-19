// site/src/islands/FacetPanel.tsx -- P2-S4-T04 (10 V11 "The filter panel"; 09 S6.2, S6.10, S8.2, S8.4, S10, S11.5;
// 12 S5.3). The V11 browse view at /benchmarks/: a facet rail beside a result list, every count recomputed from
// facets.json on every filter change. pages/benchmarks/index.astro renders it with the rail's vocabulary (taxonomy/,
// read at build time) and facets.json's content-hashed URL, which lib/manifest.ts dataHref() is the only way to name.
// lib/browse-view.ts holds the logic and says what each rule is; this file renders it.
//
// What renders before facets.json arrives is what the server sent: every group and every term, each term a link to its
// single-facet page (/browse/{facet}/{term}/), so the view is a usable route into the catalogue as it stands, and is the
// same markup with JavaScript off. Once the rows load, each term becomes a checkbox with its live count. A term whose
// count is zero is shown and disabled, never hidden, because the gaps are the product; a selected term stays enabled
// whatever its count, so it can always be removed.
//
// The selection lives in the query string in lib/filter-url.ts's canonical form, written on every change (pushState,
// so Back steps through the selections) and read on load and on popstate. A value the link names that no vocabulary
// has is shown in a visible "ignored filter" notice (10 "Filter state encoding"), and a key the view keeps but does not
// apply is named in a notice too, never dropped silently.
//
// Announcements: one status region, polite, debounced at 500 ms (09 S8.4), and nothing live on the result list. The
// first tally is the page arriving, not a change, so it is not announced.
//
// Without a published entry facets.json has no rows: every count is zero, every term disabled, and the result region
// says that nothing is published yet and what that zero does and does not mean, rather than reading as an empty field.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { decode, encode, ignoredNotice, type FilterState, type Ignored } from '../lib/filter-url.ts';
import {
  ANNOUNCE_MS, announcement, browseHref, buildIndex, chips, cleared, confidence, mostConstraining, readFacets, tally,
  termHref, toggle, unapplied, vocabularies, without, type Confidence, type Family, type Index, type RailGroup,
  type RailKey, type RailTerm,
} from '../lib/browse-view.ts';

interface Props {
  facetsHref: string | null;    // lib/manifest.ts dataHref('facets.json'); null when the build wrote no manifest
  groups: RailGroup[];
  families: Family[];
  published: number;            // the published benchmarks the page was built over
}

type Load =
  | { status: 'loading' }
  | { status: 'unavailable' }
  | { status: 'failed'; reason: string }
  | { status: 'ready'; index: Index };

// Open on arrival: the spine and the two facets most sessions start from; a group holding a selection opens too.
const OPEN_FIRST = new Set<RailKey>(['d', 'c', 'em']);
const domId = (key: string, id: string) => `f-${key}-${id.replace(/[^a-z0-9]+/gi, '-')}`;
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function ConfidenceNote({ c }: { c: Confidence }) {
  const thin = 'a short or empty list is not evidence of a thin field';
  let body: ReactNode;
  if (c.scope === 'filtered' && c.families.length === 1) {
    const f = c.families[0];
    body = f.signoff === 'none'
      ? <><strong>Curation confidence for {f.label}: unreviewed.</strong> No domain reviewer has signed off on it yet, so this list is not review-backed, and {thin}.</>
      : <><strong>Curation confidence for {f.label}: signed off ({f.signoff}).</strong></>;
  } else if (c.scope === 'filtered') {
    body = <><strong>Curation confidence:</strong> {c.families.map((f, i) => <span key={f.id}>{i > 0 ? '; ' : ''}{f.label}, {f.signoff === 'none' ? 'unreviewed' : `signed off (${f.signoff})`}</span>)}.{c.state === 'reviewed' ? '' : ` Where a family is unreviewed, ${thin}.`}</>;
  } else if (c.state === 'unreviewed') {
    body = <><strong>Curation confidence: unreviewed.</strong> No domain reviewer has signed off on any of the {c.families.length} domain families yet, so no list here is review-backed, and {thin}.</>;
  } else if (c.state === 'partly-reviewed') {
    body = <><strong>Curation confidence: {c.signed.length} of {c.families.length} domain families signed off.</strong> The other {c.families.length - c.signed.length} are unreviewed, and in them {thin}.</>;
  } else {
    body = <><strong>Curation confidence: every domain family is signed off by a reviewer.</strong></>;
  }
  return <p className="confidence" data-curation-confidence={c.state} data-scope={c.scope}>{body}</p>;
}

interface RowProps {
  g: RailGroup;
  t: RailTerm;
  index: Index | null;
  count: number;
  selected: boolean;
  onToggle: () => void;
}

/** One term: before the rows load, a link to its single-facet page; after, a checkbox with its live count. The
 *  definition shows on hover and focus, with the full one a link away (10 V11). */
function TermRow({ g, t, index, count, selected, onToggle }: RowProps) {
  const id = domId(g.key, t.id);
  return (
    <div className="row">
      {index != null
        ? <>
            <input type="checkbox" id={id} checked={selected} disabled={count === 0 && !selected} onChange={onToggle} aria-describedby={`${id}-gloss`} />
            <label htmlFor={id}>{t.label} <span className="n">{count}</span></label>
          </>
        : <a href={browseHref(g, t.id)} aria-describedby={`${id}-gloss`}>{t.label}</a>}
      <div className="gloss"><p id={`${id}-gloss`}>{t.gloss}</p><a href={termHref(g, t.id)}>Full definition</a></div>
    </div>
  );
}

export default function FacetPanel({ facetsHref, groups, families, published }: Props) {
  const vocab = useMemo(() => vocabularies(groups), [groups]);
  const [state, setState] = useState<FilterState>({});
  const [ignored, setIgnored] = useState<Ignored[]>([]);
  const [load, setLoad] = useState<Load>(facetsHref == null ? { status: 'unavailable' } : { status: 'loading' });
  const [opened, setOpened] = useState<Record<string, boolean>>({});
  const [hush, setHush] = useState(false);
  const [said, setSaid] = useState('');
  const settled = useRef<string | null>(null);

  // the selection: from the query string on load and on Back/Forward
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

  // Escape hides an open definition wherever focus is, until the pointer or focus next moves in the rail (SC 1.4.13)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setHush(true);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

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
        if (!live) return;
        setLoad('error' in got ? { status: 'failed', reason: got.error } : { status: 'ready', index: buildIndex(groups, got.rows) });
      })
      .catch((e: unknown) => {
        if (live) setLoad({ status: 'failed', reason: e instanceof Error ? e.message : String(e) });
      });
    return () => {
      live = false;
    };
  }, [facetsHref, groups]);

  const index = load.status === 'ready' ? load.index : null;
  const counted = useMemo(() => (index != null ? tally(index, state) : null), [index, state]);
  const key = encode(state);

  // one polite announcement per settled change, 500 ms after the last one (09 S8.4)
  useEffect(() => {
    if (counted == null) return;
    if (settled.current == null) {
      settled.current = key;
      return;
    }
    if (settled.current === key) return;
    const timer = window.setTimeout(() => {
      settled.current = key;
      setSaid(announcement(counted.total));
    }, ANNOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [key, counted]);

  const apply = (next: FilterState) => {
    setState(next);
    setIgnored([]);
    const q = encode(next);
    window.history.pushState(null, '', `${window.location.pathname}${q.length > 0 ? `?${q}` : ''}`);
  };

  const applied = chips(groups, state);
  const kept = unapplied(state);
  const scope = confidence(families, state);
  const countOf = (gi: number, id: string) => counted?.counts[gi].get(id) ?? 0;
  const isOpen = (k: string, first: boolean) => opened[k] ?? first;
  const onToggleOpen = (k: string) => (e: { currentTarget: HTMLDetailsElement }) => {
    const open = e.currentTarget.open;
    setOpened((o) => (o[k] === open ? o : { ...o, [k]: open }));
  };
  const domain = groups.findIndex((g) => g.key === 'd');
  const labelOf = new Map(domain >= 0 ? groups[domain].terms.map((t) => [t.id, t.label] as const) : []);

  const row = (g: RailGroup, gi: number, t: RailTerm) => {
    const selected = (state[g.key] ?? []).includes(t.id);
    const count = countOf(gi, t.id);
    return {
      selected, count,
      props: {
        'data-term': t.id,
        'data-count': index != null ? count : undefined,
        'data-zero': index != null && count === 0 ? '' : undefined,
        'data-selected': selected ? '' : undefined,
      },
      node: <TermRow g={g} t={t} index={index} count={count} selected={selected} onToggle={() => apply(toggle(state, g.key, t.id))} />,
    };
  };

  const groupBody = (g: RailGroup, gi: number) => {
    if (g.key !== 'd') {
      return <ul className="terms">{g.terms.map((t) => {
        const r = row(g, gi, t);
        return <li key={t.id} className="term" {...r.props}>{r.node}</li>;
      })}</ul>;
    }
    const fams = g.terms.filter((t) => t.parent == null);
    return <ul className="terms">{fams.map((f) => {
      const r = row(g, gi, f);
      const subs = g.terms.filter((t) => t.parent === f.id);
      const within = subs.some((s) => (state.d ?? []).includes(s.id));
      return (
        <li key={f.id} className="term family" {...r.props}>
          {r.node}
          {subs.length > 0
            ? <details className="subdomains" open={isOpen(`d:${f.id}`, within)} onToggle={onToggleOpen(`d:${f.id}`)}>
                <summary>{plural(subs.length, 'subdomain', 'subdomains')}</summary>
                <ul className="terms">{subs.map((s) => {
                  const sr = row(g, gi, s);
                  return <li key={s.id} className="term" {...sr.props}>{sr.node}</li>;
                })}</ul>
              </details>
            : null}
        </li>
      );
    })}</ul>;
  };

  const best = index != null && counted != null && counted.total === 0 && index.rows.length > 0 ? mostConstraining(index, state) : null;

  let results: ReactNode;
  if (load.status === 'loading') {
    results = <p className="lede" data-browse-state="loading">{published === 0 ? 'No benchmark is published yet.' : `The index lists ${plural(published, 'published benchmark', 'published benchmarks')}.`} Each term in the panel opens the page of every benchmark that carries it, and choosing terms here combines them.</p>;
  } else if (load.status === 'unavailable') {
    results = <p className="lede" data-browse-state="unavailable">This build has no filter index (facets.json), so terms cannot be combined here. Each term in the panel opens the page of every benchmark that carries it.</p>;
  } else if (load.status === 'failed') {
    results = <p className="lede" data-browse-state="failed">The filter index could not be read ({load.reason}), so terms cannot be combined here. Each term in the panel opens the page of every benchmark that carries it.</p>;
  } else if (load.index.rows.length === 0) {
    results = (
      <div className="empty" data-empty="unpublished" data-browse-state="ready">
        <p>No benchmark is published yet, so every count in the panel is zero and every term is disabled. A zero here says nothing about the field: an entry is published only once a person has verified it. Each term's definition shows when you point at it or focus it, with a link to the full one.</p>
      </div>
    );
  } else if (counted != null && counted.total === 0) {
    results = (
      <div className="empty" data-empty="filter" data-browse-state="ready">
        <p>
          {applied.length > 1
            ? <>No benchmark matches all {applied.length} filters. Each filter narrows the results further.</>
            : <>No benchmark matches this filter.</>}
          {best != null
            ? <> <button type="button" className="drop" onClick={() => apply(without(state, best.chip))}>Remove {best.chip.group}: {best.chip.label}</button> to see {best.results}.</>
            : null}
        </p>
      </div>
    );
  } else {
    results = (
      <ol className="results" data-browse-state="ready">
        {(counted?.matches ?? []).map((ri) => {
          const r = load.index.rows[ri];
          return (
            <li key={r.id} data-id={r.id}>
              <a href={`/benchmarks/${r.id}/`}>{r.name}</a>{' '}
              <span className="meta">{labelOf.get(r.subdomain) ?? r.subdomain} · {r.year != null ? r.year : 'release year not recorded'}</span>
            </li>
          );
        })}
      </ol>
    );
  }

  return (
    <div className="facet-panel" data-browse-view data-state={load.status}>
      <a className="skip" href="#browse-results">Skip the filters</a>
      <aside className="rail" aria-labelledby="browse-filters" data-hush={hush ? '' : undefined}
        onFocus={() => setHush(false)} onPointerOver={() => setHush(false)}>
        <h2 id="browse-filters">Filters</h2>
        <ConfidenceNote c={scope} />
        {groups.map((g, gi) => {
          const chosen = (state[g.key] ?? []).length;
          const size = g.key === 'd' ? plural(g.terms.filter((t) => t.parent == null).length, 'family', 'families') : plural(g.terms.length, 'term', 'terms');
          return (
            <details key={g.key} className="group" data-group={g.key} open={isOpen(g.key, OPEN_FIRST.has(g.key) || chosen > 0)} onToggle={onToggleOpen(g.key)}>
              <summary><span className="label">{g.label}</span> <span className="n">{chosen > 0 ? `${chosen} selected` : size}</span></summary>
              {groupBody(g, gi)}
            </details>
          );
        })}
      </aside>
      <section className="list" id="browse-results" aria-labelledby="browse-results-h" tabIndex={-1}>
        <h2 id="browse-results-h">Benchmarks <span className="count">({index != null && counted != null ? `${counted.total} of ${index.rows.length}` : `${published} published`})</span></h2>
        <div className="applied" role="group" aria-label="Applied filters">
          {applied.length > 0
            ? <ul className="chips">{applied.map((c) => (
                <li key={`${c.key}=${c.value}`}>
                  <button type="button" className="chip" data-state="filter-active" data-chip={`${c.key}=${c.value}`} onClick={() => apply(without(state, c))}>
                    <span className="group">{c.group}:</span> {c.label} <span className="remove" aria-hidden="true">×</span><span className="visually-hidden"> (remove filter)</span>
                  </button>
                </li>
              ))}</ul>
            : <p className="none">No filter applied.</p>}
          {applied.length > 1 ? <button type="button" className="clear" onClick={() => apply(cleared(state, groups))}>Clear all filters</button> : null}
        </div>
        {ignored.length > 0
          ? <div className="notice" data-ignored>
              <p>The link names {ignored.length === 1 ? 'a value' : 'values'} this index does not have, left out of the selection:</p>
              <ul>{ignored.map((i) => <li key={`${i.key}=${i.value}`}><code>{ignoredNotice(i)}</code></li>)}</ul>
            </div>
          : null}
        {kept.length > 0
          ? <p className="notice" data-unapplied>Kept in the link but not applied in this view: {kept.map((k, i) => <span key={`${k.key}=${k.value}`}>{i > 0 ? ', ' : ''}<code>{k.key}={k.value}</code></span>)}.</p>
          : null}
        <p role="status" className="visually-hidden" data-filter-status>{said}</p>
        {results}
      </section>
    </div>
  );
}
