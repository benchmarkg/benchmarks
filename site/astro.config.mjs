// site/astro.config.mjs -- P2-S1-T01. Pins and their as-of dates: docs/pins.md.
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import { fileURLToPath } from 'node:url';

// Test-only pages, never in a normal build: UAIBI_SITE_FIXTURES names which (P4-S5-T06). The page lives in
// test/fixtures/, outside src/pages/, so only this hook can route it.
const FIXTURES = {
  citations: './test/fixtures/citations.astro',
  'citations-openalex-headline': './test/fixtures/citations.astro',
};

function fixturePages(name) {
  return {
    name: 'uaibi-fixture-pages',
    hooks: {
      'astro:config:setup': ({ injectRoute }) => {
        injectRoute({ pattern: '/_fixtures/' + name, entrypoint: fileURLToPath(new URL(FIXTURES[name], import.meta.url)) });
      },
    },
  };
}

const fixture = process.env.UAIBI_SITE_FIXTURES;
if (fixture && !(fixture in FIXTURES)) {
  throw new Error(`UAIBI_SITE_FIXTURES=${fixture}: no such fixture (have: ${Object.keys(FIXTURES).join(', ')})`);
}

export default defineConfig({
  // Astro 7 changed the default to 'jsx', which drops the whitespace between adjacent inline
  // elements: <span>a</span> <span>b</span> renders as "ab". Every facet-chip row and inline
  // provenance badge on this site is exactly that shape (08 S5.1, 10 Technology decisions), so
  // this stays literally `true`; test/config.test.mjs fails on anything else.
  compressHTML: true,
  integrations: [react(), ...(fixture ? [fixturePages(fixture)] : [])],
});
