// site/src/lib/dormancy.ts -- P0-S7-T04. The staleness banner's input (SUCCESSION.md item 5, 05 S10).
//
// tools/dormancy.py computes, from the date of the last human commit to data/, whether the 180-day banner is on,
// and `bench build` writes that to build/dormancy.json before the site build. The banner text is the build's,
// word for word, so the wording lives in one place. No file means no banner: a build that skipped `bench build`
// has no evidence of dormancy, and the banner is an admission, never a guess.
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

export interface Dormancy {
  last_human_commit: string | null;
  days: number | null;
  succession: boolean;
  banner: boolean;
  banner_text: string | null;
}

const REPO_ROOT = process.env.REPO_ROOT ?? resolve(process.cwd(), '..');

export function dormancy(path: string = join(REPO_ROOT, 'build', 'dormancy.json')): Dormancy | null {
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, 'utf8')) as Dormancy;
}

export function bannerText(d: Dormancy | null): string | null {
  return d && d.banner ? d.banner_text : null;
}
