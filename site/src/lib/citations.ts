// site/src/lib/citations.ts -- P4-S5-T06. A citation figure as ingest/adapters/semantic_scholar.py emits it
// (CitationFigure.to_json), and the rules for rendering one (12 S6, 06 S3.10).
//
// Every citation count on the site renders through components/CitationCount.astro, which applies these rules;
// scripts/check_single_source.py checks the built HTML for the attributes it writes.

export type Aggregator = 'semantic_scholar' | 'openalex';

export interface CitationFigure {
  arxiv: string;
  sources: string[];
  observed_on: string;
  counts: Record<Aggregator, number | null>;
  records: Record<Aggregator, string | null>;
  corroborating: Aggregator[];
  value: number;
  single_source: boolean;
  ratio: number | null;
  disagreement: boolean;
  identity_conflicts: string[];
}

export const AGGREGATOR_NAMES: Record<Aggregator, string> = {
  semantic_scholar: 'Semantic Scholar',
  openalex: 'OpenAlex',
};

export type MarkerReason = 'single-source' | 'disagreement';

/** Why a figure is unverified, or null when two aggregators agree within 2x. Single-source wins: a figure
 *  only one aggregator supports has no second count to disagree with. */
export function markerReason(fig: CitationFigure): MarkerReason | null {
  if (fig.single_source || fig.corroborating.length < 2) return 'single-source';
  if (fig.disagreement) return 'disagreement';
  return null;
}

/** The aggregator whose count is the figure's value: the first corroborating one, as the adapter orders them. */
export function valueSource(fig: CitationFigure): Aggregator {
  return fig.corroborating[0];
}

/** 06 S3.10: an OpenAlex citation count is never a headline influence number. */
export function mayHeadline(fig: CitationFigure): boolean {
  return valueSource(fig) !== 'openalex';
}

export function formatCount(n: number): string {
  return n.toLocaleString('en-US');
}
