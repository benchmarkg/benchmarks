// site/src/lib/js-yaml.d.ts -- P2-S3-T05. The one js-yaml function the site calls (lib/terms.ts), typed here because
// no @types package is installed for it. js-yaml is pinned in package.json at the major Astro's own file() loader uses.
declare module 'js-yaml' {
  export function load(text: string, options?: { filename?: string }): unknown;
}
