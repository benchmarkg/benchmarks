// site/src/lib/claims.ts -- P2-S3-T02. One claim as the provenance drill-down reads it: the claims.json row 08 S4.2
// describes ("every claim ... with its EvalConditions inlined, plus comparability_key, artifact_url,
// provenance_snapshot and source refs"), which P3-S10-T03 emits. Until it does, the drill-down is built against
// test/fixtures/provenance-claims.json, which test/fixtures/make_provenance_fixture.py writes in this shape from the
// committed claims and tools/build/comparability.py.
import type { EvalConditions } from '../types/eval-conditions';
import type { ResultClaim } from '../types/result-claim';

/** tools/build/comparability.py Comparability.as_dict(): 04 S8's three numbers, and the unknown set. */
export interface ClaimComparability {
  comparability_key: string;
  key_unknown_count: number;
  condition_completeness: number | null;     // null only when every material field was waived
  unknown_fields: string[];
  fields_material_total: number;
}

/** The source a claim cites, reduced to what a citation needs (09 S6.6). */
export interface ClaimSource {
  id: string;
  type: string;
  title: string | null;
  url: string;
  publisher: string | null;
  accessed: string | null;
  fetched_at: string | null;
  archive_url: string | null;
  archive_captured: string | null;
  archive_status: string;
  licence_class: string;
}

export interface ClaimRow {
  claim: ResultClaim;
  conditions: EvalConditions | null;          // inlined; null when the claim names no condition record
  comparability: ClaimComparability;
  material: string[];                         // the benchmark's resolved material fields (04 S8), sorted
  weights: Record<string, number>;            // per material field; 2.0 where 04 S8 doubles one
  key_shared_with: number;                    // other claims with the same comparability_key
  source: ClaimSource | null;
  reporter: { id: string; name: string | null };
}
