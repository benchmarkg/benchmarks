// site/src/lib/atlas.ts -- P2-S5-T02 (10 V1; 08 S4.2, S5.2; 09 S4.2, S4.3, S4.4, S7.6). The Atlas island's logic, pure
// and DOM-free: atlas.json read and checked, each node's paint from its lifecycle and headroom, the filter's matching set
// over facets.json (lib/browse-view.ts, the browse view's own index and grammar), and the camera state that fits a set.
// islands/Atlas.tsx renders what this computes; test/atlas.test.mjs drives it under Node, which strips the types.
//
// Positions. atlas.json's x and y are the node's place, written by the build (tools/atlas/emit.py, the pack layout) and
// never computed here: "The client never runs a layout algorithm" (10 V1). Nothing below returns a coordinate for a node.
// A filter changes paint and the camera only: "Filtering never moves a node."
//
// Paint (10 V1 "Node colour", 09 S4.3). Nodes are neutral: a --c-ink-muted ring, and headroom consumed as a fill LEVEL in
// the same ink, so a benchmark at 90% headroom consumed looks 90% full. Colour is spent on three of the ten lifecycle
// terms and nothing else: contaminated and retracted take --c-alert, saturated the headroom ramp's top stop
// (--seq-head-6), which is what a full fill already means; both are drawn full. The other seven are neutral and are read
// from the hover card, the side panel and the filter. "If all ten are coloured, none of them is signal" (09 S4.3).
// Domain family has no colour at all (09 S4.2): it is carried by position and by the region labels.
//
//   no filter   every node as above, labelled
//   matching    neutral nodes raised to --c-ink ("matching nodes stay at --c-ink"); coloured ones keep their colour
//   not         --c-ink-faint ring and fill, no label, drawn beneath: "Non-matching nodes drop to --c-ink-faint and
//               lose their labels via sigma's nodeReducer" (10 V1)
//
// A node with no headroom value has no fill: unknown headroom is never drawn as zero headroom consumed's fill, and the
// card and panel say "not recorded" (09 S4.4, S11.2). No build stage computes headroom yet (tools/atlas/emit.py), so
// every node is a ring today. A value over 1 (past a stated human ceiling) fills the node and is named in the card.
//
// The camera. The Atlas may fit the camera to the matching set; the nodes stay where they are. fitState() turns the
// matching set's bounding box in viewport pixels into a camera state: its centre, and the zoom that makes the box fill
// the viewport less FIT_PAD, never closer than MIN_FIT_RATIO. A user-initiated change animates in FIT_MS with an
// ease-out, and under prefers-reduced-motion it is an instant jump; nothing animates on load (09 S7.6).
import { tally, type Index } from './browse-view.ts';
import type { FilterState } from './filter-url.ts';
import type { Theme } from './theme.ts';

// ---- atlas.json ---------------------------------------------------------------------------------------------

/** The atlas.json format this view reads (tools/atlas/emit.py FORMAT). */
export const ATLAS_FORMAT = 1;

/** One node: 10 V1's per-node fields plus 08 S4.2's `cluster`, as tools/atlas/emit.py NODE writes them. */
export interface AtlasNode {
  id: string;
  x: number;
  y: number;
  r: number;
  cluster: string;                     // the domain family it is packed in
  domain_primary: string;              // a subdomain id
  domain_group: string;                // display-only: it orders and bands this one view
  lifecycle: string | null;
  headroom_consumed: number | null;
  adoption_n: number;
  label: string;
  label_priority: number;
}

export interface AtlasEdge {
  from: string;
  to: string;
  kind: 'supersedes' | 'extends' | 'subset_of' | 'decontaminates' | 'correlates_with';
  coefficient: number | null;
  source: string | null;
}

export interface AtlasRegion {
  id: string;
  level: 'group' | 'family';
  parent: string | null;
  label: string;
  x: number;
  y: number;
  r: number;
}

export interface AtlasDoc {
  artifact: 'atlas';
  format: number;
  layout_method: string;
  layout_epoch: number;
  basis_version: string | null;
  nodes: AtlasNode[];
  edges: AtlasEdge[];
  regions: AtlasRegion[];
  drafts?: boolean;
}

/** A fetched atlas.json, or the reason this view cannot draw it. */
export function readAtlas(doc: unknown): { atlas: AtlasDoc } | { error: string } {
  const d = doc as Partial<AtlasDoc> | null;
  if (d == null || typeof d !== 'object' || d.artifact !== 'atlas') return { error: 'the file is not the atlas artifact' };
  if (d.format !== ATLAS_FORMAT) return { error: `atlas.json is format ${String(d.format)}, and this view reads format ${ATLAS_FORMAT}` };
  if (!Array.isArray(d.nodes) || !Array.isArray(d.edges) || !Array.isArray(d.regions)) return { error: 'atlas.json has no node, edge or region list' };
  for (const n of d.nodes) {
    if (!Number.isFinite(n.x) || !Number.isFinite(n.y) || !(n.r > 0)) return { error: `atlas.json places ${String(n.id)} at no finite position` };
  }
  return { atlas: d as AtlasDoc };
}

// ---- paint --------------------------------------------------------------------------------------------------

/** The lifecycle terms that take a colour, and which (09 S4.3). Every other term, and none, is neutral. */
export const ALERT_LIFECYCLES: ReadonlySet<string> = new Set(['contaminated', 'retracted']);
export const SATURATED_LIFECYCLE = 'saturated';

export type Role = 'neutral' | 'alert' | 'saturated';

export function role(lifecycle: string | null): Role {
  if (lifecycle != null && ALERT_LIFECYCLES.has(lifecycle)) return 'alert';
  return lifecycle === SATURATED_LIFECYCLE ? 'saturated' : 'neutral';
}

/** The fill level, 0..1: headroom consumed, a coloured node full, no value no fill. */
export function level(n: Pick<AtlasNode, 'lifecycle' | 'headroom_consumed'>): number {
  if (role(n.lifecycle) !== 'neutral') return 1;
  const h = n.headroom_consumed;
  return h == null || !Number.isFinite(h) ? 0 : Math.min(1, Math.max(0, h));
}

/** The tokens the map paints with, as the hex tokens.json computes for one theme (never a colour typed here). The Atlas
 *  page resolves both themes at build time and hands the island the result; tokens.json is a parameter so that Node can
 *  run this file without a JSON import. */
export interface Palette {
  ink: string;
  muted: string;
  faint: string;
  bg: string;
  border: string;
  borderStrong: string;
  alert: string;
  saturated: string;           // --seq-head-6, the headroom ramp's top stop
  emphasis: string;
}

type ThemeTokens = Record<string, { hex: string }>;

export function palette(theme: Theme, t: { themes: Record<Theme, ThemeTokens> }): Palette {
  const k = t.themes[theme];
  return {
    ink: k['c-ink'].hex, muted: k['c-ink-muted'].hex, faint: k['c-ink-faint'].hex, bg: k['c-bg'].hex,
    border: k['c-border'].hex, borderStrong: k['c-border-strong'].hex, alert: k['c-alert'].hex,
    saturated: k['seq-head-6'].hex, emphasis: k['c-emphasis'].hex,
  };
}

/** Where a node stands against the filter: no filter applied, in the matching set, or out of it. */
export type Standing = 'all' | 'match' | 'out';

/** What sigma draws for one node: ring and fill colour, the colour above the fill, the fill level, the label. */
export interface Paint {
  ring: string;
  fill: string;
  empty: string;
  level: number;
  label: string | null;
  zIndex: number;
}

export function paint(n: AtlasNode, p: Palette, standing: Standing): Paint {
  if (standing === 'out') return { ring: p.faint, fill: p.faint, empty: p.bg, level: level(n), label: null, zIndex: 0 };
  const r = role(n.lifecycle);
  const ink = r === 'alert' ? p.alert : r === 'saturated' ? p.saturated : standing === 'match' ? p.ink : p.muted;
  return { ring: ink, fill: ink, empty: p.bg, level: level(n), label: n.label, zIndex: 1 };
}

// ---- the matching set ---------------------------------------------------------------------------------------

/** Does the selection constrain anything this view applies (the rail's term keys and the year range)? */
export function filtering(index: Pick<Index, 'groups'>, state: FilterState): boolean {
  return state.yr != null || index.groups.some((g) => (state[g.key] ?? []).length > 0);
}

/** The ids the selection matches, or null when it applies no filter: "AND across facets, OR within a facet" (08 S5.7),
 *  by the browse view's own tally, so the map and the list cannot disagree. */
export function matching(index: Index, state: FilterState): Set<string> | null {
  if (!filtering(index, state)) return null;
  return new Set(tally(index, state).matches.map((i) => index.rows[i].id));
}

export const standing = (m: Set<string> | null, id: string): Standing => (m == null ? 'all' : m.has(id) ? 'match' : 'out');

// ---- the camera ---------------------------------------------------------------------------------------------

export const FIT_MS = 200;            // 09 S7.6: a transition on a user-initiated change, at most 200 ms, ease-out
export const FIT_PAD = 1.25;          // the box fills 1/FIT_PAD of the viewport's tighter side
export const MIN_FIT_RATIO = 0.08;    // never closer than this: one node fills a readable patch, not the screen
export const HOME = { x: 0.5, y: 0.5, ratio: 1, angle: 0 } as const;   // sigma's whole-graph camera

export interface CameraState { x: number; y: number; ratio: number; angle: number }
export interface Box { x0: number; y0: number; x1: number; y1: number }

/** The box around circles given as viewport centres and radii, or null for none. */
export function box(circles: readonly { x: number; y: number; r: number }[]): Box | null {
  if (circles.length === 0) return null;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const c of circles) {
    x0 = Math.min(x0, c.x - c.r); y0 = Math.min(y0, c.y - c.r);
    x1 = Math.max(x1, c.x + c.r); y1 = Math.max(y1, c.y + c.r);
  }
  return { x0, y0, x1, y1 };
}

/** The camera state that fits `b`, a box in viewport pixels under camera `cam`, into a `width` x `height` viewport.
 *  `toFramed` turns a viewport point into sigma's framed-graph coordinates under `cam` (sigma.viewportToFramedGraph).
 *  Zoom is linear in the ratio, so the new ratio is the old one scaled by how much of the viewport the box spans. */
export function fitState(b: Box, cam: CameraState, width: number, height: number,
  toFramed: (p: { x: number; y: number }) => { x: number; y: number }): CameraState {
  const centre = toFramed({ x: (b.x0 + b.x1) / 2, y: (b.y0 + b.y1) / 2 });
  const span = Math.max((b.x1 - b.x0) / width, (b.y1 - b.y0) / height);
  const ratio = Math.min(1, Math.max(MIN_FIT_RATIO, cam.ratio * span * FIT_PAD));
  return { x: centre.x, y: centre.y, ratio, angle: 0 };
}
