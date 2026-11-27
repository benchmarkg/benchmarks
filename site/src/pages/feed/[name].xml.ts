// /feed/{domain-family}.xml and /feed/ingest.xml (V8 "Formats"): ingest holds the machine-ingested
// events the default and per-domain feeds exclude. /feed/corrections.xml, the separately subscribable
// trust instrument, is its own route since P3-S10-T09 (feed/corrections.xml.ts: RSS 2.0, with the
// disputes). No family is named corrections or ingest.
import type { APIRoute, GetStaticPaths } from 'astro';
import { onlyRoutes } from '../../lib/bench-routes';
import { atom, atomResponse, domainFamilies, familyEvents, ingestEvents } from '../../lib/feed';

// Fixed narrative routes (lib/bench-routes.ts NARRATIVE): BENCH_ROUTES never leaves a feed out.
export const getStaticPaths: GetStaticPaths = () => {
  const families = domainFamilies();
  if (families.includes('corrections') || families.includes('ingest')) {
    throw new Error('a domain family is named corrections or ingest; the feed routes would collide');
  }
  return onlyRoutes([
    ...families.map((f) => ({ params: { name: f }, props: { kind: 'family' } })),
    { params: { name: 'ingest' }, props: { kind: 'ingest' } },
  ], (p) => `/feed/${p.params.name}.xml`);
};

export const GET: APIRoute = ({ params, props }) => {
  const name = String(params.name);
  const self = `/feed/${name}.xml`;
  if (props.kind === 'ingest') return atomResponse(atom('ingest', 'Benchmark index: machine-ingested', self, ingestEvents()));
  return atomResponse(atom(`family:${name}`, `Benchmark index: ${name}`, self, familyEvents(name)));
};
