// site/src/pages/embed/[file].ts -- P6-S1-T06 (08 S4.2, S4.3; 11 S4). /embed/vectors.meta.json and
// /embed/vectors.i8.bin: the document vectors `bench build --embed` wrote beside the corpus, published byte for byte
// beside the query encoder's files (public/embed/) for the semantic tier's loader (islands/search/loader.ts). A build
// that wrote none renders neither (lib/vectors.ts shippedVectors, which also checks them), and a BENCH_ROUTES preview
// renders them only when it lists them (lib/bench-routes.ts), which pages/search.astro asks before it names them.
import type { APIRoute } from 'astro';
import { readFileSync } from 'node:fs';
import { onlyRoutes } from '../../lib/bench-routes';
import { VECTORS_BASE, VECTOR_FILES, shippedVectors } from '../../lib/vectors';

export function getStaticPaths() {
  const shipped = shippedVectors();
  const paths = shipped == null ? [] : VECTOR_FILES.map((file) => ({ params: { file }, props: { path: shipped[file] } }));
  return onlyRoutes(paths, (p) => `${VECTORS_BASE}${p.params.file}`);
}

export const GET: APIRoute = ({ props }) => new Response(readFileSync((props as { path: string }).path));
