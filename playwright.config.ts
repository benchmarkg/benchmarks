// playwright.config.ts -- the repository-root e2e suite (tests/e2e/), first used by P4-S4-T06.
//
// The web server is the SITE built against committed or generated fixtures, not against the live data: the
// live repository's only entries are unpublishable Phase-0 drafts, so its feeds are empty and its published
// claims none, and both would test nothing. FEED_EVENTS points site/src/lib/feed.ts at the feed fixture, which
// tests/e2e/fixtures/make_feed_events.py regenerates from tools/build/feed.py itself.
//
// P3-S10-T07's tests/e2e/provenance-drilldown.spec.ts reads the claim and condition pages, which exist only over
// the draft preview (scripts/preview_corpus.py; UAIBI_SITE_DRAFTS=1, as site/playwright.config.ts builds it), and
// its ingested claims, of which the corpus has none yet: tests/e2e/fixtures/make_claims_fixture.py writes the
// preview's claims artifacts again into build/e2e-claims/ with two constructed ingested rows, and UAIBI_CLAIMS
// points the site at them (site/src/lib/claims.ts). The feed does not read the corpus, so the feed spec reads the
// same server.
//
// P3-S10-T09's tests/e2e/corrections.spec.ts reads /corrections/ and /feed/corrections.xml: the corrections come from
// the same feed fixture, and the disputes from tests/e2e/fixtures/disputes/, constructed records (data/disputes/ holds
// none yet) that UAIBI_DISPUTES points the site at (site/src/lib/corrections.ts).
// reuseExistingServer lets a verify that curls :4321 first share the same server.
import { defineConfig } from '@playwright/test';
import { join } from 'node:path';

const BUILD = join(__dirname, 'build');

export default defineConfig({
  testDir: 'tests/e2e',
  fullyParallel: true,
  reporter: 'list',
  use: { baseURL: 'http://localhost:4321' },
  webServer: {
    command: 'uv run python scripts/preview_corpus.py --out build/preview'
      + ' && uv run python tests/e2e/fixtures/make_claims_fixture.py --preview build/preview --out build/e2e-claims'
      + ' && npm --prefix site run build && npm --prefix site run preview -- --port 4321',
    url: 'http://localhost:4321/feed.xml',
    reuseExistingServer: true,
    // a cold build of the whole preview took about 14 minutes on a slow machine (site/playwright.config.ts)
    timeout: 1_800_000,
    env: {
      FEED_EVENTS: 'tests/e2e/fixtures/feed-events.json',
      UAIBI_DISPUTES: join(__dirname, 'tests', 'e2e', 'fixtures', 'disputes'),
      UAIBI_CORPUS: join(BUILD, 'preview', 'corpus.json'),
      UAIBI_CLAIMS: join(BUILD, 'e2e-claims', 'claims.json'),
      UAIBI_SITE_DRAFTS: '1',
      ASTRO_TELEMETRY_DISABLED: '1',
      // Astro 7's `preview` detaches into a background daemon when it detects a coding agent
      // (cli/preview: `!process.env.ASTRO_PREVIEW_BACKGROUND && isRunByAgent()`). Playwright then
      // sees its server "exit early" and the daemon outlives the run. Setting the variable turns
      // that detection off, so the server stays in the foreground where Playwright can stop it.
      ASTRO_PREVIEW_BACKGROUND: '0',
    },
  },
});
