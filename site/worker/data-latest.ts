// site/worker/data-latest.ts -- P2-S1-T05 (08 S4.4, S7.2). /data/latest/<name>.json: a 302 to this deploy's
// content-hashed file, for casual consumers, notebooks and curl, at a five-minute TTL. "Telling a researcher to parse
// a manifest before they can `curl` a file is hostile, and a five-minute TTL on a redirect costs nothing."
//
// The target comes from the deploy's own /build-manifest.json (tools/build/manifest.py), whose `paths` names every
// hashed artifact of the build, so the redirect and the file it points at are always one version. Nothing is ever
// built under /data/latest/ (S13 refuses a file there), so a request for it is an asset miss, and the Worker that
// imports this (site/worker/index.ts, the deploy task's, as for redirects.ts) runs on a miss and never first: 08
// S7.2 keeps run_worker_first off every path but /api/*. Nothing deploys it yet.
//
// latest() is the whole decision, a pure function of the URL and the manifest; readManifest() is the one fetch.

export const LATEST = '/data/latest/';
export const TTL = 300;                                    // seconds (08 S4.4)
export const MANIFEST = '/build-manifest.json';

export interface BuildManifest {
  artifact: 'build-manifest';
  paths: Record<string, string>;                           // 'corpus.json' -> '/data/corpus.<sha8>.json'
}

/** Cloudflare's static-assets binding (env.ASSETS), the only part of it this uses. */
export interface Assets {
  fetch(request: Request): Promise<Response>;
}

const NAME = /^(?:[a-z0-9-]+\/)*[a-z0-9-]+\.json$/;

/** The hashed path `name` must redirect to, as a pattern: its own stem, eight hex digits, never under latest/. */
function hashedFor(name: string): RegExp {
  return new RegExp(`^/data/${name.slice(0, -'.json'.length)}\\.[0-9a-f]{8}\\.json$`);
}

/** The answer for a request URL, or null when its path is not under /data/latest/. A name the manifest gives a
 *  hashed path is a 302 to it; any other name is a 404; no readable manifest is a 503 that is never cached, so the
 *  next request tries again. The 302 and the 404 carry max-age=300. The query string is not carried: a hashed file
 *  takes none. */
export function latest(url: URL, manifest: BuildManifest | null): Response | null {
  if (!url.pathname.startsWith(LATEST)) return null;
  const text = { 'Content-Type': 'text/plain; charset=utf-8' };
  if (manifest == null) {
    return new Response('The build manifest cannot be read.\n',
      { status: 503, headers: { ...text, 'Cache-Control': 'no-store' } });
  }
  const cache = { 'Cache-Control': `public, max-age=${TTL}` };
  const name = url.pathname.slice(LATEST.length);
  const to = NAME.test(name) && Object.hasOwn(manifest.paths, name) ? manifest.paths[name] : null;
  if (to == null || !hashedFor(name).test(to)) {
    return new Response(`No artifact ${name} in this build; ${MANIFEST} lists them.\n`,
      { status: 404, headers: { ...text, ...cache } });
  }
  return new Response(null, { status: 302, headers: { ...cache, Location: new URL(to, url).toString() } });
}

/** This deploy's manifest, read from its own static assets; null when it is missing or is not the manifest. */
export async function readManifest(assets: Assets, url: URL): Promise<BuildManifest | null> {
  const r = await assets.fetch(new Request(new URL(MANIFEST, url)));
  if (!r.ok) return null;
  try {
    const doc = (await r.json()) as Partial<BuildManifest> | null;
    return doc != null && doc.artifact === 'build-manifest' && typeof doc.paths === 'object' && doc.paths != null
      ? (doc as BuildManifest) : null;
  } catch {
    return null;
  }
}
