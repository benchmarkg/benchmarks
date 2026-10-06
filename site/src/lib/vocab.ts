// site/src/lib/vocab.ts -- P2-S2-T06. The closed vocabularies the components of 09-design-system.md S6 render,
// each read from where it is governed or stated once here with its section, never retyped in a component.
import taxonomy from './taxonomy.json';

// ---- taxonomy terms (09 S6.2) -------------------------------------------------------------------------------

export interface Term { label: string; status?: string }
const FACETS = taxonomy.facets as Record<string, Record<string, Term>>;

/** The term `id` of `facet`, or a thrown error: "a chip with an unresolvable term is a build failure" (09 S6.2). */
export function term(facet: string, id: string): Term {
  const terms = FACETS[facet];
  if (!terms) throw new Error(`facet ${facet} is not in taxonomy/ (have: ${Object.keys(FACETS).sort().join(', ')})`);
  const t = terms[id];
  if (!t) throw new Error(`term ${facet}:${id} does not resolve in taxonomy/ (09 S6.2: a stale chip is a build failure)`);
  return t;
}

// ---- the verification ladder (09 S4.3, S6.3) ----------------------------------------------------------------

/** Rung ids by rank, rank 1 first, as taxonomy/verification.yaml orders them. */
export const RUNGS: readonly string[] = taxonomy.verification;

/** The 2-letter code a badge shows at --fs-2xs (09 S6.3). Unique; every rung has one (components.test.mjs). */
export const RUNG_CODES: Record<string, string> = {
  'self-reported': 'SR',
  'maintainer-verified': 'MV',
  'independent-reproduction': 'IR',
  'held-out-server': 'HO',
  'prospective-experiment': 'PE',
  'third-party-audited': 'TA',
  'sandboxed-rerun': 'SB',
};

export function rank(verification: string): number {
  const r = RUNGS.indexOf(verification);
  if (r < 0) throw new Error(`verification ${JSON.stringify(verification)} is not a rung of taxonomy/verification.yaml `
    + '(09 S6.3: there is no "unknown verification"; an unrecorded one is a schema violation)');
  return r + 1;
}

/** "independent-reproduction" -> "Independent reproduction". */
export const rungName = (id: string) => id.charAt(0).toUpperCase() + id.slice(1).replace(/-/g, ' ');

// ---- the four absence phrases (09 S11.2, S6.9) --------------------------------------------------------------

export const ABSENCE = {
  'not-reported': 'not reported',
  'not-recorded': 'not recorded',
  'not-applicable': 'not applicable',
  unknown: 'unknown',
} as const;
export type AbsenceState = keyof typeof ABSENCE;

export function absencePhrase(state: string): string {
  if (!(state in ABSENCE)) {
    throw new Error(`absence state ${JSON.stringify(state)} is not one of ${Object.keys(ABSENCE).join(', ')} (09 S11.2)`);
  }
  return ABSENCE[state as AbsenceState];
}

// ---- staleness (09 S6.7) ------------------------------------------------------------------------------------

export type Band = 'fresh' | 'ageing' | 'stale' | 'unverified-since-creation';
export const BAND_LABEL: Record<Band, string> = {
  fresh: 'fresh', ageing: 'ageing', stale: 'stale', 'unverified-since-creation': 'unverified since creation',
};
const DAY = 86_400_000;

/** The band for a last_verified_at date (ISO), on `today`: < 90 days fresh, 90-365 ageing, > 365 stale. */
export function band(lastVerifiedAt: string | null, today: Date = new Date()): Band {
  if (lastVerifiedAt == null) return 'unverified-since-creation';
  const t = Date.parse(lastVerifiedAt.length === 10 ? `${lastVerifiedAt}T00:00:00Z` : lastVerifiedAt);
  if (Number.isNaN(t)) throw new Error(`last_verified_at ${JSON.stringify(lastVerifiedAt)} is not an ISO 8601 date`);
  const days = Math.floor((today.getTime() - t) / DAY);
  return days < 90 ? 'fresh' : days <= 365 ? 'ageing' : 'stale';
}

export function daysSince(iso: string, today: Date = new Date()): number {
  return Math.floor((today.getTime() - Date.parse(iso.length === 10 ? `${iso}T00:00:00Z` : iso)) / DAY);
}

// ---- numbers (09 S3.4, S11.4) -------------------------------------------------------------------------------

/** A number as the source gave it: its own string when it has one (precision is the source's), U+2212 for minus,
 *  and a comma thousands separator from 10,000. Locale is fixed to `en`, never the reader's (09 S11.4). */
export function formatValue(value: number | string): string {
  const s = typeof value === 'string' ? value : String(value);
  const [int, frac] = s.replace(/^-/, '').split('.');
  const grouped = int.length >= 5 ? int.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : int;
  return (s.startsWith('-') ? '−' : '') + grouped + (frac !== undefined ? `.${frac}` : '');
}
