// site/astro.config.mjs -- P2-S1-T01. Pins and their as-of dates: docs/pins.md.
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

export default defineConfig({
  // Astro 7 changed the default to 'jsx', which drops the whitespace between adjacent inline
  // elements: <span>a</span> <span>b</span> renders as "ab". Every facet-chip row and inline
  // provenance badge on this site is exactly that shape (08 S5.1, 10 Technology decisions), so
  // this stays literally `true`; test/config.test.mjs fails on anything else.
  compressHTML: true,
  integrations: [react()],
});
