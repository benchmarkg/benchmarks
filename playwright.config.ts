// playwright.config.ts -- the repository-root e2e suite (tests/e2e/), first used by P4-S4-T06.
//
// The web server is the SITE built against a committed fixture, not against the live data: the
// live repository's only entries are unpublishable Phase-0 drafts, so its feeds are empty and
// would test nothing. FEED_EVENTS points site/src/lib/feed.ts at the fixture, which
// tests/e2e/fixtures/make_feed_events.py regenerates from tools/build/feed.py itself.
// reuseExistingServer lets a verify that curls :4321 first share the same server.
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e',
  fullyParallel: true,
  reporter: 'list',
  use: { baseURL: 'http://localhost:4321' },
  webServer: {
    command: 'npm --prefix site run build && npm --prefix site run preview -- --port 4321',
    url: 'http://localhost:4321/feed.xml',
    reuseExistingServer: true,
    timeout: 180_000,
    env: {
      FEED_EVENTS: 'tests/e2e/fixtures/feed-events.json',
      ASTRO_TELEMETRY_DISABLED: '1',
      // Astro 7's `preview` detaches into a background daemon when it detects a coding agent
      // (cli/preview: `!process.env.ASTRO_PREVIEW_BACKGROUND && isRunByAgent()`). Playwright then
      // sees its server "exit early" and the daemon outlives the run. Setting the variable turns
      // that detection off, so the server stays in the foreground where Playwright can stop it.
      ASTRO_PREVIEW_BACKGROUND: '0',
    },
  },
});
