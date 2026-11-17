// site/src/lib/lineage.ts -- P2-S3-T03. The lineage artifact, build/derived/lineage.json beside the corpus
// (tools/build/lineage_svg.py): for every benchmark with at least one lineage edge, its figure as the build drew it --
// the SVG and the <table> from one figure object, the caption, the one-sentence summary and the ids that wire the
// SVG's aria-labelledby and aria-describedby to them (09 S6.12, S8.4). No file means no figures: the detail page then
// lists the edges as text only, as it did before the figure existed.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { CORPUS_PATH } from './corpus';

export interface LineageEntry {
  id: string;
  caption: string;
  caption_id: string;
  summary: string;
  summary_id: string;
  svg: string;
  table: string;
  relations: number;
  related: number;
}

const read = new Map<string, Map<string, LineageEntry> | null>();

export function lineageFigures(path: string = join(dirname(CORPUS_PATH), 'derived', 'lineage.json')): Map<string, LineageEntry> | null {
  if (read.has(path)) return read.get(path) ?? null;
  let out: Map<string, LineageEntry> | null = null;
  if (existsSync(path)) {
    const doc = JSON.parse(readFileSync(path, 'utf8')) as { artifact: string; drafts?: boolean; benchmarks: Record<string, LineageEntry> };
    if (doc.artifact !== 'lineage') throw new Error(`${path} is not the lineage artifact (artifact: ${doc.artifact})`);
    if (doc.drafts === true && process.env.UAIBI_SITE_DRAFTS !== '1') {
      throw new Error(`${path} was drawn from a draft preview corpus: set UAIBI_SITE_DRAFTS=1 to build a preview that is not deployed.`);
    }
    out = new Map(Object.entries(doc.benchmarks));
  }
  read.set(path, out);
  return out;
}

// What tools/build/svgcharts.py can write, and nothing else: LineageFigure inlines the build's markup, whose every
// string was escaped there (tests/build/test_svgcharts.py), so markup that could run anything is refused rather than
// inlined -- a build failure, not a page.
const ACTIVE = /<\s*(script|foreignobject|iframe|object|embed|style)\b|\son[a-z]+\s*=|(?:href|src)\s*=\s*["']?\s*(?:javascript|data):/i;

/** Throws unless `e` is a lineage figure the build could have drawn: an <svg role="img"> labelled by e.caption_id and
 *  described by e.summary_id, a <table>, and no active content in either. */
export function checkLineage(e: LineageEntry): void {
  for (const k of ['id', 'caption', 'caption_id', 'summary', 'summary_id', 'svg', 'table'] as const) {
    if (typeof e[k] !== 'string' || e[k] === '') throw new Error(`LineageFigure: the figure has no ${k}`);
  }
  if (!e.svg.startsWith('<svg ') || !e.svg.endsWith('</svg>')) throw new Error(`LineageFigure: ${e.id}'s svg is not one <svg>`);
  if (!e.table.startsWith('<table ') || !e.table.endsWith('</table>')) throw new Error(`LineageFigure: ${e.id}'s table is not one <table>`);
  const open = e.svg.slice(0, e.svg.indexOf('>'));
  for (const attr of ['role="img"', `aria-labelledby="${e.caption_id}"`, `aria-describedby="${e.summary_id}"`]) {
    if (!open.includes(attr)) throw new Error(`LineageFigure: ${e.id}'s <svg> lacks ${attr} (09 S8.4)`);
  }
  if (/aria-label=/.test(e.svg)) throw new Error(`LineageFigure: ${e.id}'s svg relies on aria-label (09 S6.12)`);
  for (const part of [e.svg, e.table]) {
    const m = ACTIVE.exec(part);
    if (m) throw new Error(`LineageFigure: ${e.id} carries ${JSON.stringify(m[0])}, which tools/build/svgcharts.py never writes`);
  }
}
