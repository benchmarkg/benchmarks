// site/src/islands/SearchBox.tsx -- P2-S4-T07 (10 V11 "Search: three tiers, and the ordering rule matters more than the
// tiers", "Failure mode to avoid", "Without JavaScript"; 09 S6.10, S6.11, S8.4, S8.6, S11.5; 08 S4.3, S5.5). The search
// box at /search/ (pages/search.astro), answered by Pagefind, the lexical tier, on every keystroke.
//
// What the server sends is not this box. pages/search.astro renders the page's working part as plain links -- every
// single-facet browse page and every taxonomy term page the build rendered -- and this island renders nothing on the
// server: a box that cannot answer without JavaScript would be a dead box, and 09 S8.6 rules out the <noscript> block
// that would apologise for it. Once the island hydrates, the box appears above those links and the links stay.
//
// The lexical tier. Pagefind's own browser API, from the bundle S12 writes into dist/pagefind/ (lib/pagefind.ts;
// BUNDLE_URL here), loaded when the box first takes focus or a query arrives in the link (08 S4.2: "on first keystroke in
// the search box", brought forward to focus so the first keystroke does not pay for the load), never on page load. Every
// change of the box's value asks it at once: no debounce, no Enter. An answer that arrives after a later keystroke has
// asked is dropped, so the list on screen always answers the box as it stands or the keystroke just before it, and the
// results stay up while the next answer is on its way rather than blanking on every key. STEP results are read at a
// time, because each one's data() is a fragment fetch; "Show more" reads the next STEP.
//
// The ordering rule (10 V11): "Pagefind answers on every keystroke; the semantic tier loads in the background and, once
// ready, *appends* a block. Semantic search is never on the critical path to a first result." The seam a later tier
// plugs into is LaterTier and addLaterTier(), below: a tier is asked on the same keystroke as Pagefind, beside it and
// never before it, and nothing Pagefind answers waits on it. Its hits render only once Pagefind has answered the same
// query, as a block after the lexical list, without the pages that list already shows; the lexical list is never
// reordered or moved by it. A tier that fails says so in one line (09 S11.5) and the results above it are unchanged.
// No tier is added yet. The semantic tier (P6-S1: the model2vec encoder, P6-S1-T01, and the cosine and fusion step,
// P6-S1-T05, which owns the reciprocal rank fusion at k = 60 10 V11 asks for when both are present) is to call
// addLaterTier() once its opt-in has loaded it; this file imports nothing of it. A pending tier shows nothing yet: 09
// S6.11's skeleton for the semantic tier is that tier's to add, sized to its own block.
//
// The form's submit button (P2-S8-T09; 09 S8.2, WCAG SC 3.2.2, which pa11y's H32.2 holds a form to) asks again for the
// box as it stands, the question a keystroke asks: Enter or the button is an explicit way to ask, and the retry after a
// Pagefind load that failed. Typing still needs neither.
//
// Announcements: one polite status region, debounced at 500 ms (09 S8.4, lib/browse-view.ts ANNOUNCE_MS), and nothing
// live on the result list. The query is kept in the link as `q` (10 "Filter state encoding": "q  free-text query"),
// replaced, not pushed, on each keystroke, so Back leaves the page rather than stepping through the letters, and a link
// carrying ?q= is answered on arrival.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ANNOUNCE_MS } from '../lib/browse-view.ts';

/** Where S12 writes the bundle (lib/pagefind.ts BUNDLE, at the root of dist/): pagefind.js is loaded from here. */
export const BUNDLE_URL = '/pagefind/';
/** Results read and shown at a time: the first answer, and each "Show more". */
export const STEP = 10;

/** One result, of either tier. `type` is the record's `type` filter (tools/build/pagefind_records.py): benchmark,
 *  system, organization, metric or term, or `page` for a crawled narrative page. */
export interface Hit {
  url: string;
  title: string;
  type: string;
  excerpt: string;          // Pagefind's, with <mark> around the matched words; empty when a tier has none
}

/** What a reader is told each kind of result is. */
export const TYPE_LABEL: Readonly<Record<string, string>> = {
  benchmark: 'Benchmark', system: 'System', organization: 'Organization', metric: 'Metric', term: 'Taxonomy term', page: 'Page',
};

// ---- the lexical tier: Pagefind's browser API, the part used here ------------------------------------------

interface PagefindData {
  url: string;
  meta?: Record<string, string>;
  excerpt?: string;
  filters?: Record<string, string[]>;
}
interface PagefindResult {
  id: string;
  data(): Promise<PagefindData>;
}
interface Pagefind {
  init(): Promise<void>;
  search(term: string): Promise<{ results: PagefindResult[] } | null>;
}

let loading: Promise<Pagefind> | null = null;

/** Pagefind, loaded once per page; a load that fails is forgotten, so the next keystroke tries again. */
function lexicalTier(): Promise<Pagefind> {
  if (loading == null) {
    const url = `${BUNDLE_URL}pagefind.js`;    // a variable, so the bundler leaves the build's own file to the browser
    const load = (import(/* @vite-ignore */ url) as Promise<Pagefind>).then(async (pf) => {
      await pf.init();
      return pf;
    });
    loading = load;
    load.catch(() => {
      if (loading === load) loading = null;
    });
  }
  return loading;
}

async function read(r: PagefindResult): Promise<Hit> {
  const d = await r.data();
  return { url: d.url, title: d.meta?.title ?? d.url, type: d.filters?.type?.[0] ?? 'page', excerpt: d.excerpt ?? '' };
}

const ENTITY: Readonly<Record<string, string>> = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'", '#x27': "'" };

/** An excerpt as text runs, each marked or not. Only <mark> is markup; everything else is text, rendered as text,
 *  so a record's words can never become HTML on this page. */
export function excerptParts(excerpt: string): { text: string; mark: boolean }[] {
  const out: { text: string; mark: boolean }[] = [];
  let mark = false;
  for (const part of excerpt.split(/(<\/?mark>)/)) {
    if (part === '<mark>') mark = true;
    else if (part === '</mark>') mark = false;
    else if (part !== '') out.push({ text: part.replace(/&(amp|lt|gt|quot|#39|#x27);/g, (_, k: string) => ENTITY[k]), mark });
  }
  return out;
}

// ---- the seam for a later tier ------------------------------------------------------------------------------

/** A search tier slower than Pagefind: 10 V11's tier 3, the semantic tier P6-S1 builds. */
export interface LaterTier {
  id: string;               // 'semantic'
  name: string;             // what the one-line notice calls it when it fails: 'Semantic search'
  heading: string;          // its block's heading: 10 V11's "Related benchmarks you did not type the words for"
  /** Its hits for `query`, best first, whenever they come. `signal` aborts when a later keystroke has asked. */
  search(query: string, signal: AbortSignal): Promise<Hit[]>;
}

const tiers: LaterTier[] = [];
const listeners = new Set<() => void>();

/** Adds a later tier to every search box on the page, from the next keystroke on; returns its removal. */
export function addLaterTier(tier: LaterTier): () => void {
  if (tiers.some((t) => t.id === tier.id)) throw new Error(`a later search tier "${tier.id}" is already added`);
  tiers.push(tier);
  listeners.forEach((f) => f());
  return () => {
    const i = tiers.indexOf(tier);
    if (i >= 0) tiers.splice(i, 1);
    listeners.forEach((f) => f());
  };
}

// ---- the island ---------------------------------------------------------------------------------------------

/** static: as the server sent it, no box. idle: hydrated, Pagefind not asked for yet. loading, ready, failed: Pagefind. */
type Status = 'static' | 'idle' | 'loading' | 'ready' | 'failed';

interface Answer {
  query: string;
  results: PagefindResult[];    // every match, best first
  hits: Hit[];                  // the first of them, read
}
interface Later {
  query: string;
  status: 'pending' | 'done' | 'failed';
  hits: Hit[];
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
const reason = (e: unknown) => (e instanceof Error ? e.message : String(e));

function Excerpt({ text }: { text: string }) {
  if (text === '') return null;
  return <p className="excerpt">{excerptParts(text).map((p, i) => (p.mark ? <mark key={i}>{p.text}</mark> : <span key={i}>{p.text}</span>))}</p>;
}

function HitRow({ h }: { h: Hit }) {
  return (
    <li data-url={h.url} data-type={h.type}>
      <a href={h.url}>{h.title}</a> <span className="kind">{TYPE_LABEL[h.type] ?? h.type}</span>
      <Excerpt text={h.excerpt} />
    </li>
  );
}

export default function SearchBox() {
  const [status, setStatus] = useState<Status>('static');
  const [failure, setFailure] = useState('');
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [later, setLater] = useState<Record<string, Later>>({});
  const [, setTierVersion] = useState(0);
  const [said, setSaid] = useState('');
  const asked = useRef(0);
  const abort = useRef<AbortController | null>(null);

  const fail = (e: unknown) => {
    setStatus('failed');
    setFailure(reason(e));
  };

  const warm = () => {
    setStatus((s) => (s === 'idle' ? 'loading' : s));
    lexicalTier().then(() => setStatus((s) => (s === 'loading' || s === 'failed' ? 'ready' : s)), fail);
  };

  const remember = (q: string) => {
    const params = new URLSearchParams(window.location.search);
    if (q === '') params.delete('q');
    else params.set('q', q);
    const s = params.toString();
    window.history.replaceState(window.history.state, '', `${window.location.pathname}${s === '' ? '' : `?${s}`}${window.location.hash}`);
  };

  /** One keystroke's question, to Pagefind and, beside it, to every later tier. */
  const ask = (q: string) => {
    const n = ++asked.current;
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    remember(q);
    if (q.trim() === '') {
      setAnswer(null);
      setLater({});
      return;
    }
    lexicalTier()
      .then(async (pf) => {
        const found = await pf.search(q);
        if (n !== asked.current) return;                    // a later keystroke has asked since
        const results = found?.results ?? [];
        const hits = await Promise.all(results.slice(0, STEP).map(read));
        if (n !== asked.current) return;
        setStatus('ready');
        setAnswer({ query: q, results, hits });
      })
      .catch((e: unknown) => {
        if (n === asked.current) fail(e);
      });
    // the later tiers: asked now, beside Pagefind, and never awaited by it
    const asking = [...tiers];
    setLater(Object.fromEntries(asking.map((t) => [t.id, { query: q, status: 'pending', hits: [] }])));
    for (const t of asking) {
      Promise.resolve()
        .then(() => t.search(q, ctl.signal))
        .then(
          (hits) => {
            if (n === asked.current) setLater((l) => ({ ...l, [t.id]: { query: q, status: 'done', hits } }));
          },
          () => {
            if (n === asked.current) setLater((l) => ({ ...l, [t.id]: { query: q, status: 'failed', hits: [] } }));
          },
        );
    }
  };

  // hydrated: the box exists from here on, and a query in the link is answered on arrival
  useEffect(() => {
    setStatus('idle');
    const q = new URLSearchParams(window.location.search).get('q') ?? '';
    if (q.trim() !== '') {
      setQuery(q);
      warm();
      ask(q);
    }
    const onTiers = () => setTierVersion((v) => v + 1);
    listeners.add(onTiers);
    return () => {
      listeners.delete(onTiers);
      abort.current?.abort();
    };
  }, []);

  // one polite announcement per settled answer (09 S8.4)
  const total = answer?.results.length ?? null;
  useEffect(() => {
    if (answer == null) {
      setSaid('');
      return;
    }
    const text = total === 0 ? `No result for “${answer.query}”` : `${plural(total ?? 0, 'result', 'results')} for “${answer.query}”`;
    const timer = window.setTimeout(() => setSaid(text), ANNOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [answer?.query, total]);

  const more = async () => {
    const a = answer;
    if (a == null) return;
    try {
      const next = await Promise.all(a.results.slice(a.hits.length, a.hits.length + STEP).map(read));
      setAnswer((cur) => (cur === a ? { ...cur, hits: [...cur.hits, ...next] } : cur));
    } catch (e) {
      fail(e);
    }
  };

  if (status === 'static') return <div className="search-box" data-search-box data-state="static" />;

  const pending = Object.entries(later).filter(([, l]) => l.status === 'pending').map(([id]) => id);
  const shown = new Set((answer?.hits ?? []).map((h) => h.url));
  let body: ReactNode = null;
  if (answer != null) {
    body = answer.results.length === 0
      ? <p className="empty" data-empty="search">No page in the index matches “{answer.query}”. The index holds the published entries, the taxonomy and the pages about the index, so an entry that is not published is not found. Try fewer or shorter words, or browse by facet below.</p>
      : <>
          <ol className="hits" data-tier="lexical">{answer.hits.map((h) => <HitRow key={h.url} h={h} />)}</ol>
          <p className="count">
            Showing {answer.hits.length} of {plural(answer.results.length, 'result', 'results')}.
            {answer.hits.length < answer.results.length
              ? <> <button type="button" className="more" onClick={more}>Show {Math.min(STEP, answer.results.length - answer.hits.length)} more</button></>
              : null}
          </p>
        </>;
  }
  // a later tier's block: only beside Pagefind's answer to the same query, after it, without what it already shows
  const blocks = answer == null ? [] : tiers.map((t) => {
    const l = later[t.id];
    if (l == null || l.query !== answer.query || l.status === 'pending') return null;
    if (l.status === 'failed') {
      return <p key={t.id} className="tier-note" data-tier-failed={t.id}>{t.name} is unavailable: the results above are the word-match results, unchanged.</p>;
    }
    const extra = l.hits.filter((h) => !shown.has(h.url));
    if (extra.length === 0) return null;
    return (
      <section key={t.id} className="later" data-tier={t.id} aria-labelledby={`search-tier-${t.id}`}>
        <h3 id={`search-tier-${t.id}`}>{t.heading}</h3>
        <ol className="hits">{extra.map((h) => <HitRow key={h.url} h={h} />)}</ol>
      </section>
    );
  });

  return (
    <div className="search-box" data-search-box data-state={status}>
      <form role="search" className="search-form" onSubmit={(e) => {
        e.preventDefault();
        ask(query);
      }}>
        <label htmlFor="search-q">Search the index</label>
        <div className="field">
          <input id="search-q" type="search" name="q" value={query} autoComplete="off" spellCheck={false}
            aria-describedby="search-scope" aria-controls="search-results" onFocus={warm}
            onChange={(e) => {
              setQuery(e.target.value);
              ask(e.target.value);
            }} />
          <button type="submit">Search</button>
        </div>
        <p id="search-scope" className="scope">Benchmarks, systems, organizations, metrics, taxonomy terms and the pages about the index. Results appear as you type.</p>
      </form>
      {status === 'failed'
        ? <p className="notice" data-search-failed>The search index could not be loaded ({failure}), so the box cannot answer. Every entry is still reachable from the facet links below.</p>
        : null}
      <p role="status" className="visually-hidden" data-search-status>{said}</p>
      <section id="search-results" className="search-results" aria-label="Search results" data-search-results
        data-answered={answer?.query} data-later-pending={pending.length > 0 ? pending.join(' ') : undefined}>
        {body}
        {blocks}
      </section>
    </div>
  );
}
