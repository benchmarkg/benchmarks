// site/src/islands/Atlas.tsx -- P2-S5-T02 (10 V1; 08 S4.3, S5.2; 09 S4.2, S4.3, S7.6, S8.2). The Atlas, the hero view at
// /atlas/: every benchmark a node, placed by the build. pages/atlas.astro mounts it client:visible with atlas.json's and
// facets.json's content-hashed URLs (lib/manifest.ts dataHref, the only way a page names a /data/ file), the browse rail's
// vocabularies for the filter, each benchmark's tagline for the hover card, and the two themes' palettes (tokens.json's
// hex, resolved at build time, so the route ships 18 colours rather than the token file). lib/atlas.ts holds the rules;
// this file draws them.
//
// sigma@3.0.3 renders a graphology@0.26.0 graph whose x, y and size are atlas.json's x, y and r, set once when the graph is
// built: no layout runs here, and none of sigma's (it has none). Both libraries, and the node program they draw with
// (lib/atlas-program.ts: a ring and a fill level), are imported after hydration, so the server render and the first
// paint ship none of them. sigma draws in positions units (itemSizesReference) against a camera whose bounding box is
// fixed to the presentation groups' outer circles, so a node's place in sigma's own frame depends on atlas.json alone.
//
// A filter is the browse view's grammar and the browse view's tally over facets.json (lib/browse-view.ts): the same
// query string, canonical on every change, read on load and on Back. It changes the nodeReducer's input and nothing
// else, so it re-paints: non-matching nodes drop to --c-ink-faint and lose their labels, matching ones rise to --c-ink.
// Then the camera, never a node, moves to fit the matching set; a filter that matches nothing leaves the camera where it
// is. The camera moves in lib/atlas.ts FIT_MS with an ease-out, instantly under prefers-reduced-motion, and not at all
// on load: a link that carries a filter opens already fitted (09 S7.6).
//
// Hover shows a tagline card (name, tagline, primary domain, lifecycle, headroom, adoption: 10 V1 "Interactions"). A
// click opens the summary panel beside the map, in a column the layout always reserves, so opening it resizes nothing
// and the camera keeps its place; "Open the full page" is the canonical URL.
//
// Behind the WebGL canvases, which carry no meaning a screen reader could use (aria-hidden; 09 S8.2 makes the family
// index the readable form of the map, P2-S5-T03), a 2D canvas draws what sigma does not: the group and family regions'
// hairline outlines and permanent labels (10 V1), and the edges, lineage solid and a sourced correlation dashed. A
// family the domain filter names alone takes --c-emphasis on its outline (09 S4.2 (d)).
//
// The family index (P2-S5-T03; 10 V1 "Without JavaScript", "And it is also the legend"; 09 S4.2, S8.2). The page passes
// components/AtlasIndex.astro as this island's children: the grouped list of the build's atlas.json, server-rendered
// inside the canvas container (`.frame`), beside the stage the canvas is drawn on. It is the map's legend, its no-JS
// form and its screen-reader linearisation, and the canvas is aria-hidden because it is a picture of that list. The
// children are static HTML to React (Astro's <astro-slot>, which React mounts once and never re-renders), so on
// hydration they are hydrated as they stand: no second copy is rendered. Once the map is drawn the island takes that
// list over in place -- the inert list as sent becomes the live one, its data-atlas-index "island", its toggles enabled,
// its items under a roving tabindex -- rather than shipping code to render the list again: the list is replaced on
// hydration by its live self, and the page never holds two. If the map cannot be drawn (atlas.json unreadable, no
// WebGL, nothing published), the list stays as sent, the fallback, its toggles disabled because there is no map for
// them to act on.
//
// lib/roving-tabindex.ts gives the live list 09 S8.2's keys, through the frame's own keydown handler (React delegates
// events from the static children like any others): Tab between families (the clusters), Up and Down within one, Enter
// opens the benchmark's page, Space selects it -- its summary opens in the panel and its node is drawn on top, as a
// click on it does; Escape or the panel's Close lets it go -- and Space on a family's toggle presses it.
//
// A family's toggle is that family's domain filter, the one the filter bar's Domain control sets: pressed, the link
// reads d=<family>, the family's nodes stay in ink and every other node drops to --c-ink-faint, the family's outline
// takes --c-emphasis and the camera may fit it (10 V1: "Selecting a row emphasises that family on the map and dims the
// rest"; 09 S4.2 (d), one family at a time), and nothing moves a node; pressed again, the domain filter is cleared. So
// the legend, the filter bar and the link can never disagree about which family is emphasised, and the highlight costs
// no code of its own: a toggle is pressed exactly when the filter emphasises its family, and its aria-pressed is written
// to the list from the island's state. "/" in the list focuses search: /atlas/ has no search box (the site-wide one,
// islands/SearchBox.tsx, P2-S4-T07, is /search/'s), so it goes to the filter bar's first control, the Domain filter, the
// one way this page has to find benchmarks on the map. The seam is the `search` callback handed to onKey() below: when
// the Atlas gets the search 10 V1 describes ("Search highlights in place"), that callback returns its box instead.
//
// The root element carries `atlasProbe`, so a test can read what the canvas draws without reading pixels: sigma's renderer
// and graphology's graph themselves (positions, sigma's display data, viewport coordinates, the labels drawn, the
// camera). The readers that turn them into plain values are the tests' own (tests/atlas.spec.ts, atlas-a11y.spec.ts),
// rather than shipped to every reader of the page: the Atlas's JavaScript is held to 08 S8.1's 120 KB. A test reads
// them and never writes them; nothing in the page does either.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { NodeDisplayData } from 'sigma/types';
import type { FillData } from '../lib/atlas-program.ts';
import { current, onThemeChange, type Theme } from '../lib/theme.ts';
import { decode, encode, ignoredNotice, type FilterState, type Ignored } from '../lib/filter-url.ts';
import {
  ANNOUNCE_MS, announcement, buildIndex, chips, cleared, readFacets, tally, vocabularies, without, type FacetRow,
  type Index, type RailGroup, type RailKey,
} from '../lib/browse-view.ts';
import {
  FIT_MS, HOME, box, fitState, matching, paint, readAtlas, standing, type AtlasDoc, type AtlasNode, type CameraState,
  type Palette,
} from '../lib/atlas.ts';
import { onKey } from '../lib/roving-tabindex.ts';

interface Props {
  atlasHref: string | null;     // lib/manifest.ts dataHref('atlas.json'); null when the build wrote none
  facetsHref: string | null;    // dataHref('facets.json'), for the filter
  groups: RailGroup[];          // the browse rail's vocabularies, definitions left out
  taglines: Record<string, string>;
  palettes: Record<Theme, Palette>;   // lib/atlas.ts palette() of each theme, from tokens.json at build time
  children?: ReactNode;               // components/AtlasIndex.astro: the family index as the server rendered it
}

type Load =
  | { status: 'loading' }
  | { status: 'unavailable' }
  | { status: 'failed'; reason: string }
  | { status: 'ready'; atlas: AtlasDoc; index: Index | null; facetsError: string | null };

/** The rail keys the filter bar offers a control for; every rail key in the link is applied (lib/browse-view.ts). */
const CONTROLS: readonly RailKey[] = ['d', 'c', 'em', 'lc'];
const QUIET = new Set(['loading', 'unavailable', 'failed', 'empty']);   // states in which nothing is announced

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

// The map's libraries, fetched once, from the moment the data is asked for, so the two downloads overlap.
let libraries: Promise<[typeof import('sigma'), typeof import('graphology'), typeof import('../lib/atlas-program.ts')]> | null = null;
const loadLibraries = () => (libraries ??= Promise.all([import('sigma'), import('graphology'), import('../lib/atlas-program.ts')]));
/** A group's terms in the select's order: for the domain, each family followed by its subdomains. */
const ordered = (g: RailGroup) => (g.key !== 'd' ? g.terms
  : g.terms.filter((t) => t.parent == null).flatMap((f) => [f, ...g.terms.filter((t) => t.parent === f.id)]));
const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** A rem token (`--fs-xs`) in CSS pixels: canvas text is sized in pixels, from the tokens and the reader's root size. */
function remPx(token: string): number {
  const root = getComputedStyle(document.documentElement);
  return parseFloat(root.getPropertyValue(token)) * parseFloat(root.fontSize);
}

/** The ∅ token and its phrase, as components/Absent.astro renders it (09 S6.9, S11.2). */
function NotRecorded({ what }: { what: string }) {
  return <span className="absent" data-absent="not-recorded"><span className="glyph" aria-hidden="true">∅</span> not recorded <span className="reason">({what})</span></span>;
}

function headroomText(h: number | null): ReactNode {
  if (h == null) return <NotRecorded what="headroom" />;
  const pct = `${Math.round(h * 100)}%`;
  return h > 1 ? <>▲ {pct}, past the stated ceiling</> : <>{pct} consumed</>;
}

interface Hover { id: string; x: number; y: number; r: number; width: number }

// What the canvas draws, for tests: sigma's renderer and graphology's graph, read and never written.
export interface AtlasProbe {
  renderer: InstanceType<typeof import('sigma').default>;
  graph: InstanceType<typeof import('graphology').default>;
}

export default function Atlas({ atlasHref, facetsHref, groups, taglines, palettes, children }: Props) {
  const vocab = useMemo(() => vocabularies(groups), [groups]);
  const [load, setLoad] = useState<Load>(atlasHref == null ? { status: 'unavailable' } : { status: 'loading' });
  const [state, setState] = useState<FilterState>({});
  const [ignored, setIgnored] = useState<Ignored[]>([]);
  const [theme, setTheme] = useState<Theme | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [drawn, setDrawn] = useState(false);
  const [drawError, setDrawError] = useState<string | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [said, setSaid] = useState('');
  const root = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLDivElement>(null);
  const settled = useRef<string | null>(null);
  // what the reducer and the region layer read, so a filter or a theme re-paints without rebuilding anything
  const view = useRef<{ palette: Palette | null; matching: Set<string> | null; selected: string | null; emphasis: string | null }>(
    { palette: null, matching: null, selected: null, emphasis: null });
  const map = useRef<{ refresh(): void; fit(ids: string[] | null, animate: boolean): void; setLabelColour(c: string): void } | null>(null);
  const fitted = useRef<string | null>(null);

  useEffect(() => {
    setHydrated(true);
    setTheme(current());
    return onThemeChange(setTheme);
  }, []);

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

  // Escape closes the panel
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelected(null);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  // the data: atlas.json and facets.json, once each, by their hashed URLs. The map draws without facets.json; it then
  // cannot be filtered, and says so.
  useEffect(() => {
    if (atlasHref == null) return;
    let live = true;
    loadLibraries().catch(() => {});                     // a failure is the map's to report, when it mounts
    const json = (href: string) => fetch(href).then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<unknown>;
    });
    const facets: Promise<{ rows: FacetRow[] } | { error: string }> = facetsHref == null
      ? Promise.resolve({ error: 'this build has no facets.json' })
      : json(facetsHref).then(readFacets, (e: unknown) => ({ error: e instanceof Error ? e.message : String(e) }));
    Promise.all([json(atlasHref).then(readAtlas), facets])
      .then(([a, f]) => {
        if (!live) return;
        if ('error' in a) setLoad({ status: 'failed', reason: a.error });
        else setLoad({ status: 'ready', atlas: a.atlas, index: 'error' in f ? null : buildIndex(groups, f.rows), facetsError: 'error' in f ? f.error : null });
      })
      .catch((e: unknown) => {
        if (live) setLoad({ status: 'failed', reason: e instanceof Error ? e.message : String(e) });
      });
    return () => {
      live = false;
    };
  }, [atlasHref, facetsHref, groups]);

  const atlas = load.status === 'ready' ? load.atlas : null;
  const index = load.status === 'ready' ? load.index : null;
  const nodes = useMemo(() => new Map((atlas?.nodes ?? []).map((n) => [n.id, n] as const)), [atlas]);
  const counted = useMemo(() => (index != null ? tally(index, state) : null), [index, state]);
  const matched = useMemo(() => (index != null ? matching(index, state) : null), [index, state]);
  const key = encode(state);
  const pal = theme != null ? palettes[theme] : null;
  // one family named alone by the domain filter is emphasised on the map (09 S4.2 (d): one at a time, never several)
  const emphasis = useMemo(() => {
    const fams = new Set((state.d ?? []).map((v) => v.split('/')[0]));
    return fams.size === 1 ? [...fams][0] : null;
  }, [state.d]);

  // ---- the map: sigma over graphology, mounted once the data is in ------------------------------------------------
  useEffect(() => {
    const el = frame.current;
    if (atlas == null || atlas.nodes.length === 0 || el == null) return;
    let live = true;
    let kill = () => {};
    (async () => {
      const [{ default: Sigma }, { default: Graph }, { default: FillNodeProgram }] = await loadLibraries();
      if (!live) return;
      const graph = new Graph();
      for (const n of atlas.nodes) graph.addNode(n.id, { x: n.x, y: n.y, size: n.r, label: n.label, type: 'fill' });
      const font = getComputedStyle(document.documentElement).getPropertyValue('--font-sans').trim();
      const labelPx = remPx('--fs-xs');
      const groupPx = remPx('--fs-sm');
      const renderer = new Sigma(graph, el, {
        allowInvalidContainer: true,
        itemSizesReference: 'positions',          // r is in atlas.json's units, as x and y are
        zoomToSizeRatioFunction: (ratio) => ratio,
        defaultNodeType: 'fill',
        nodeProgramClasses: { fill: FillNodeProgram },
        renderEdgeLabels: false,
        enableEdgeEvents: false,
        zIndex: true,
        labelFont: font,
        labelSize: labelPx,
        labelWeight: '400',
        labelColor: { color: (view.current.palette ?? palettes[current()]).ink },
        labelRenderedSizeThreshold: 6,
        defaultDrawNodeHover: () => {},          // the hover card is HTML
        minCameraRatio: 0.04,
        maxCameraRatio: 1.5,
        stagePadding: Math.ceil(groupPx * 2.5),   // room for the group labels above the outer circles
        nodeReducer: (id, data) => {
          const v = view.current;
          const n = nodes.get(id);
          if (n == null || v.palette == null) return data;
          const p = paint(n, v.palette, standing(v.matching, id));
          const out: Partial<NodeDisplayData> & FillData = {
            ...data, color: p.fill, ring: p.ring, empty: p.empty, level: p.level, label: p.label, zIndex: p.zIndex,
            highlighted: id === v.selected,
          };
          return out;
        },
      });
      // sigma's frame is the outer circles of the presentation groups, fixed: what is filtered never changes it
      const outer = atlas.regions.filter((r) => r.level === 'group');
      const ring = outer.length > 0 ? outer : atlas.nodes;
      renderer.setCustomBBox({
        x: [Math.min(...ring.map((r) => r.x - r.r)), Math.max(...ring.map((r) => r.x + r.r))],
        y: [Math.min(...ring.map((r) => r.y - r.r)), Math.max(...ring.map((r) => r.y + r.r))],
      });

      // the regions and edges, beneath every sigma layer
      const layer = renderer.createCanvas('regions', { beforeLayer: 'edges' });
      layer.setAttribute('aria-hidden', 'true');
      const ctx = layer.getContext('2d')!;
      const toV = (x: number, y: number) => renderer.graphToViewport({ x, y });
      const radiusPx = (x: number, y: number, r: number) => {
        const c = toV(x, y), e = toV(x + r, y);
        return Math.hypot(e.x - c.x, e.y - c.y);
      };
      const drawLayer = () => {
        const p = view.current.palette;
        if (p == null) return;
        const { width, height } = renderer.getDimensions();
        const dpr = window.devicePixelRatio || 1;
        if (layer.width !== Math.round(width * dpr) || layer.height !== Math.round(height * dpr)) {
          layer.width = Math.round(width * dpr);
          layer.height = Math.round(height * dpr);
        }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, width, height);
        const m = view.current.matching;
        for (const e of atlas.edges) {
          const a = nodes.get(e.from), b = nodes.get(e.to);
          if (a == null || b == null) continue;
          const pa = toV(a.x, a.y), pb = toV(b.x, b.y);
          const on = m == null || (m.has(a.id) && m.has(b.id));
          ctx.beginPath();
          ctx.setLineDash(e.kind === 'correlates_with' ? [4, 3] : []);
          ctx.lineWidth = 1;
          ctx.strokeStyle = on ? p.borderStrong : p.border;
          ctx.moveTo(pa.x, pa.y);
          ctx.lineTo(pb.x, pb.y);
          ctx.stroke();
        }
        ctx.setLineDash([]);
        const circles = atlas.regions.map((r) => ({ r, c: toV(r.x, r.y), rad: radiusPx(r.x, r.y, r.r), emph: r.level === 'family' && r.id === view.current.emphasis }));
        for (const { c, rad, emph } of circles) {
          ctx.beginPath();
          ctx.arc(c.x, c.y, rad, 0, 2 * Math.PI);
          ctx.lineWidth = emph ? 2 : 1;
          ctx.strokeStyle = emph ? p.emphasis : p.border;
          ctx.stroke();
        }
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        for (const { r, c, rad, emph } of circles) {
          // A group's label always shows, above its circle, and never carries a count (10 V1). A family's sits on its
          // circle's rim where the circle is wide enough for it, never shrunk (09 S4.2 (b)); the family index has the rest.
          const group = r.level === 'group';
          ctx.font = group ? `600 ${groupPx}px ${font}` : `400 ${labelPx}px ${font}`;
          const w = ctx.measureText(r.label).width;
          if (!group && w > rad * 1.9) continue;
          const y = group ? c.y - rad - groupPx : c.y - rad;
          if (!group) {
            ctx.fillStyle = p.bg;
            ctx.fillRect(c.x - w / 2 - 3, y - labelPx / 2 - 1, w + 6, labelPx + 2);
          }
          ctx.fillStyle = group ? p.muted : emph ? p.emphasis : p.ink;
          ctx.fillText(r.label, c.x, y);
        }
      };
      renderer.on('afterRender', drawLayer);
      renderer.resize(true);

      renderer.on('enterNode', ({ node }) => {
        const d = renderer.getNodeDisplayData(node)!;
        const at = renderer.framedGraphToViewport(d);
        el.classList.add('pointing');
        setHover({ id: node, x: at.x, y: at.y, r: renderer.scaleSize(d.size), width: renderer.getDimensions().width });
      });
      renderer.on('leaveNode', () => {
        el.classList.remove('pointing');
        setHover(null);
      });
      renderer.on('clickNode', ({ node }) => setSelected(node));
      renderer.getCamera().on('updated', () => setHover(null));

      map.current = {
        refresh: () => renderer.refresh(),
        setLabelColour: (c: string) => renderer.setSetting('labelColor', { color: c }),
        fit: (ids, animate) => {
          const camera = renderer.getCamera();
          const { width, height } = renderer.getDimensions();
          let target: CameraState | null = { ...HOME };
          if (ids != null) {
            const b = box(ids.map((id) => {
              const n = nodes.get(id)!;
              const at = toV(n.x, n.y);
              return { x: at.x, y: at.y, r: radiusPx(n.x, n.y, n.r) };
            }));
            target = b == null ? null : fitState(b, camera.getState(), width, height, (pt) => renderer.viewportToFramedGraph(pt));
          }
          if (target == null) return;                                   // nothing matches: the camera stays
          if (animate && !reducedMotion()) camera.animate(target, { duration: FIT_MS, easing: 'quadraticOut' });
          else camera.setState(target);
        },
      };
      (root.current as unknown as { atlasProbe: AtlasProbe }).atlasProbe = { renderer, graph };
      kill = () => {
        map.current = null;
        renderer.kill();
      };
      setDrawn(true);
    })().catch((e: unknown) => {
      if (live) setDrawError(e instanceof Error ? e.message : String(e));
    });
    return () => {
      live = false;
      kill();
    };
  }, [atlas, nodes]);

  // a filter, a theme or a selection re-paints; a filter also moves the camera, never a node
  useEffect(() => {
    view.current = { palette: pal, matching: matched, selected, emphasis };
    const m = map.current;
    if (m == null || !drawn) return;
    if (pal != null) m.setLabelColour(pal.ink);
    m.refresh();
  }, [pal, matched, selected, emphasis, drawn]);

  // The family index, as the server sent it (components/AtlasIndex.astro). Once the map is drawn the island takes it
  // over in place: the first time, each family's toggle -- its first item -- becomes its one Tab stop and every link
  // leaves the Tab order (lib/roving-tabindex.ts moves the stop from there); every time, the toggles are live and the
  // pressed one is the family the filter emphasises. Until then, and for good if the map cannot be drawn, it is the
  // inert list as sent.
  useEffect(() => {
    const l = root.current?.querySelector<HTMLElement>('[data-atlas-index]');
    if (!drawn || l == null) return;
    for (const el of l.querySelectorAll<HTMLElement>('[data-roving-item]')) {
      const f = el.dataset.highlight;
      if (l.dataset.atlasIndex !== 'island') el.tabIndex = f ? 0 : -1;
      if (f) {
        (el as HTMLButtonElement).disabled = false;
        el.ariaPressed = String(f === emphasis);
      }
    }
    l.dataset.atlasIndex = 'island';
  }, [drawn, emphasis]);

  useEffect(() => {
    const m = map.current;
    if (m == null || !drawn || index == null) return;
    if (fitted.current === key) return;
    const first = fitted.current == null;
    fitted.current = key;
    if (first && matched == null) return;                     // nothing to fit on arrival: the whole map is the view
    m.fit(matched == null ? null : [...matched], !first);       // a link's filter opens fitted, without animation
  }, [key, matched, drawn, index]);

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

  const labelOf = (k: RailKey, id: string) => groups.find((g) => g.key === k)?.terms.find((t) => t.id === id)?.label ?? id;
  const applied = chips(groups, state);
  const status = drawError != null ? 'failed' : load.status === 'ready' ? (load.atlas.nodes.length === 0 ? 'empty' : drawn ? 'drawn' : 'loading') : load.status;

  // ---- the filter bar ---------------------------------------------------------------------------------------------
  const control = (k: RailKey) => {
    const gi = groups.findIndex((g) => g.key === k);
    if (gi < 0 || index == null || counted == null) return null;
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
          apply(next);
        }}>
          <option value="">Any</option>
          {chosen.length > 1 ? <option value="*" disabled>{plural(chosen.length, 'term', 'terms')} from the link</option> : null}
          {ordered(g).map((t) => {
            const n = counted.counts[gi].get(t.id) ?? 0;
            const sub = k === 'd' && t.parent != null;
            return <option key={t.id} value={t.id} disabled={n === 0 && !chosen.includes(t.id)}>{sub ? '  ' : ''}{t.label} ({n})</option>;
          })}
        </select>
      </label>
    );
  };

  let filters: ReactNode = null;
  if (hydrated && load.status === 'ready' && load.atlas.nodes.length > 0) {
    filters = index == null
      ? <p className="notice" data-filter-unavailable>The filter index could not be read ({load.facetsError}), so the map cannot be filtered here.</p>
      : (
        <div className="filters" role="group" aria-label="Filter the map">
          <div className="controls">{CONTROLS.map(control)}</div>
          <div className="applied">
            <p className="count" data-count>{matched == null
              ? `${plural(index.rows.length, 'benchmark', 'benchmarks')}, none filtered out`
              : `${matched.size} of ${index.rows.length} benchmarks match`}</p>
            {applied.length > 0
              ? <ul className="chips">{applied.map((c) => (
                  <li key={`${c.key}=${c.value}`}>
                    <button type="button" className="chip" data-chip={`${c.key}=${c.value}`} onClick={() => apply(without(state, c))}>
                      <span className="group">{c.group}:</span> {c.label} <span className="remove" aria-hidden="true">×</span><span className="visually-hidden"> (remove filter)</span>
                    </button>
                  </li>))}</ul>
              : null}
            {applied.length > 1 ? <button type="button" className="clear" onClick={() => apply(cleared(state, groups))}>Clear all filters</button> : null}
          </div>
          {ignored.length > 0
            ? <div className="notice" data-ignored>
                <p>The link names {ignored.length === 1 ? 'a value' : 'values'} this index does not have, left out of the selection:</p>
                <ul>{ignored.map((i) => <li key={`${i.key}=${i.value}`}><code>{ignoredNotice(i)}</code></li>)}</ul>
              </div>
            : null}
          {matched != null && matched.size === 0
            ? <p className="notice" data-empty="filter">No benchmark matches {applied.length > 1 ? `all ${applied.length} filters` : 'this filter'}; every node is dimmed and the map stays where it was.</p>
            : null}
        </div>
      );
  }

  // ---- what the frame says when there is no map to draw -------------------------------------------------------
  let note: ReactNode = null;
  if (status === 'unavailable') note = <p className="fallback" data-atlas-note="unavailable">This build has no atlas.json, so there is no map to draw. Every benchmark is in the <a href="/benchmarks/">browse view</a>.</p>;
  else if (status === 'failed') note = <p className="fallback" data-atlas-note="failed">The map could not be drawn ({drawError ?? (load.status === 'failed' ? load.reason : '')}). Every benchmark is in the <a href="/benchmarks/">browse view</a>.</p>;
  else if (status === 'empty') note = <p className="fallback" data-atlas-note="empty">No benchmark is published yet, so the map has nothing to place. An entry is published only once a person has verified it.</p>;
  else if (!drawn) note = <p className="fallback" data-atlas-note="loading">The map is drawn in the browser. Without JavaScript, every benchmark is in the <a href="/benchmarks/">browse view</a>.</p>;

  // ---- the hover card and the panel -------------------------------------------------------------------------------
  const domainText = (n: AtlasNode) => `${labelOf('d', n.cluster)} › ${labelOf('d', n.domain_primary)}`;
  const lifecycleText = (n: AtlasNode) => (n.lifecycle == null ? <NotRecorded what="lifecycle" /> : labelOf('lc', n.lifecycle));
  const taglineOf = (id: string) => (Object.hasOwn(taglines, id) ? taglines[id] : null);
  // what the hover card and the panel both say about a benchmark
  const facts = (n: AtlasNode) => (
    <>
      <dt>Domain</dt><dd>{domainText(n)}</dd>
      <dt>Lifecycle</dt><dd data-card-lifecycle>{lifecycleText(n)}</dd>
      <dt>Headroom</dt><dd data-card-headroom>{headroomText(n.headroom_consumed)}</dd>
      <dt>Adoption</dt><dd data-card-adoption>{plural(n.adoption_n, 'system', 'systems')} with claims</dd>
    </>
  );
  const hovered = hover != null ? nodes.get(hover.id) : undefined;
  const picked = selected != null ? nodes.get(selected) : undefined;
  const row = index?.rows.find((r) => r.id === selected);

  const card = hovered != null && hover != null
    ? (
      <div className="card" data-atlas-card={hovered.id} aria-hidden="true"
        style={hover.x > hover.width * 0.6 ? { right: hover.width - hover.x + hover.r + 8, top: hover.y } : { left: hover.x + hover.r + 8, top: hover.y }}>
        <p className="name">{hovered.label}</p>
        {taglineOf(hovered.id) != null ? <p className="tagline">{taglineOf(hovered.id)}</p> : <p className="tagline"><NotRecorded what="tagline" /></p>}
        <dl>
          {facts(hovered)}
        </dl>
      </div>
    )
    : null;

  const panel = picked != null
    ? (
      <div className="summary" data-atlas-panel={picked.id}>
        <h2 id="atlas-panel-h">{picked.label}</h2>
        {taglineOf(picked.id) != null ? <p className="tagline">{taglineOf(picked.id)}</p> : null}
        <dl>
          {facts(picked)}
          {row != null ? <><dt>Claims</dt><dd>{row.claim_count}</dd></> : null}
          {row != null ? <><dt>Released</dt><dd>{row.year != null ? row.year : <NotRecorded what="release year" />}</dd></> : null}
          {matched != null ? <><dt>Filter</dt><dd>{matched.has(picked.id) ? 'matches the filter' : 'outside the filter'}</dd></> : null}
        </dl>
        <p className="actions">
          <a href={`/benchmarks/${picked.id}/`}>Open the full page</a>
          <button type="button" className="close" onClick={() => setSelected(null)}>Close</button>
        </p>
      </div>
    )
    : <p className="hint" data-atlas-panel="">{status === 'drawn' ? 'Point at a benchmark to see what it is; choose one to see its summary here.' : ''}</p>;

  return (
    <div className="atlas-view" ref={root} data-atlas-view data-state={status} data-matching={matched == null ? 'all' : String(matched.size)}>
      {filters}
      <div className="body">
        <div className="frame"
          onKeyDown={(e) => drawn && onKey(e, (it) => setSelected(it.dataset.indexEntry!), () => root.current!.querySelector('select'))}
          onClick={(e) => {
            const f = (e.target as Element).closest<HTMLElement>('[data-highlight]')?.dataset.highlight;
            if (drawn && f) apply({ ...state, d: f === emphasis ? [] : [f] });
          }}>
          {children}
          <div className="stage">
            <div className="canvas" ref={frame} aria-hidden="true" data-atlas-canvas />
            {note}
            {card}
          </div>
        </div>
        <aside className="panel" aria-labelledby={picked != null ? 'atlas-panel-h' : undefined} aria-label={picked != null ? undefined : 'Benchmark summary'}>
          {panel}
        </aside>
      </div>
      <p role="status" className="visually-hidden" data-filter-status>{QUIET.has(status) ? '' : said}</p>
    </div>
  );
}
