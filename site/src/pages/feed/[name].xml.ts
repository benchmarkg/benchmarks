// /feed/{domain-family}.xml, /feed/corrections.xml and /feed/ingest.xml (V8 "Formats").
// corrections is a separately subscribable trust instrument; ingest holds the machine-ingested
// events the default and per-domain feeds exclude. No family is named corrections or ingest.
import type { APIRoute, GetStaticPaths } from 'astro';
import { atom, atomResponse, correctionEvents, domainFamilies, familyEvents, ingestEvents } from '../../lib/feed';

export const getStaticPaths: GetStaticPaths = () => {
  const families = domainFamilies();
  if (families.includes('corrections') || families.includes('ingest')) {
    throw new Error('a domain family is named corrections or ingest; the feed routes would collide');
  }
  return [
    ...families.map((f) => ({ params: { name: f }, props: { kind: 'family' } })),
    { params: { name: 'corrections' }, props: { kind: 'corrections' } },
    { params: { name: 'ingest' }, props: { kind: 'ingest' } },
  ];
};

export const GET: APIRoute = ({ params, props }) => {
  const name = String(params.name);
  const self = `/feed/${name}.xml`;
  if (props.kind === 'corrections') return atomResponse(atom('corrections', 'Benchmark index: corrections', self, correctionEvents()));
  if (props.kind === 'ingest') return atomResponse(atom('ingest', 'Benchmark index: machine-ingested', self, ingestEvents()));
  return atomResponse(atom(`family:${name}`, `Benchmark index: ${name}`, self, familyEvents(name)));
};
