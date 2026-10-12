// site/src/lib/release.ts -- P2-S3-T01. The build's own release metadata, which every detail page's citation block
// renders (10 V6 section 18, "The permanent citation URL"): the live site is always HEAD, so the citable object is
// the YAML at a commit plus the release's DOI, and a page that cannot say which commit produced it is not citable.
//
//   commit_sha    UAIBI_COMMIT_SHA, else GITHUB_SHA (CI), else `git rev-parse HEAD`; none of them throws
//   tag           UAIBI_RELEASE_TAG, else the newest vX.Y.Z tag at or before the commit; null before the first
//                 tagged release, which the page says rather than inventing one
//   concept_doi   CITATION.cff's `doi:`, the Zenodo concept DOI, which resolves to the latest version (docs/releasing.md)
//   built_on      the build date (SOURCE_DATE_EPOCH when set, for a reproducible build), YYYY-MM-DD
//
// P2-S1-T05's build-manifest.json will carry the same four facts; until it exists they are read here.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

export interface Release {
  tag: string | null;
  commit_sha: string;
  concept_doi: string | null;
  built_on: string;
}

const REPO_ROOT = process.env.REPO_ROOT ?? resolve(process.cwd(), '..');

function git(...args: string[]): string | null {
  try {
    return execFileSync('git', args, { cwd: REPO_ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim() || null;
  } catch {
    return null;
  }
}

let memo: Release | undefined;

export function release(): Release {
  if (memo) return memo;
  const commit = process.env.UAIBI_COMMIT_SHA || process.env.GITHUB_SHA || git('rev-parse', 'HEAD');
  if (!commit || !/^[0-9a-f]{40}$/.test(commit)) {
    throw new Error(`release: no commit SHA (got ${JSON.stringify(commit)}); set UAIBI_COMMIT_SHA outside a git checkout. `
      + 'A page that cannot tell you which version of the data produced it is not a citable page (10 V6).');
  }
  const tag = process.env.UAIBI_RELEASE_TAG || git('describe', '--tags', '--abbrev=0', '--match', 'v[0-9]*', commit);
  const cff = join(REPO_ROOT, 'CITATION.cff');
  const doi = existsSync(cff) ? (/^doi:\s*(\S+)\s*$/m.exec(readFileSync(cff, 'utf8'))?.[1] ?? null) : null;
  const epoch = process.env.SOURCE_DATE_EPOCH;
  const built = epoch ? new Date(Number(epoch) * 1000) : new Date();
  memo = { tag, commit_sha: commit, concept_doi: doi, built_on: built.toISOString().slice(0, 10) };
  return memo;
}
