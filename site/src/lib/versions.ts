// site/src/lib/versions.ts -- P2-S3-T08 (10 "Information architecture": /benchmarks/{id}/v/{version}/). Which versions
// get a page of their own: every superseded one -- a version whose `superseded_by` names its successor -- so a
// citation to "FrontierMath as it was before the 2026-06-12 correction" has a page to land on. Current versions and
// current editions are not pages of their own; they render on the benchmark's page (section 4), which is where a
// citation to the benchmark as it stands lands.
import type { Benchmark, BenchmarkVersion } from '../types/benchmark';

export function supersededVersions(b: Benchmark): BenchmarkVersion[] {
  return (b.versions ?? []).filter((v) => v.superseded_by != null);
}

export const versionHref = (benchmark: string, version: string) => `/benchmarks/${benchmark}/v/${encodeURIComponent(version)}/`;
