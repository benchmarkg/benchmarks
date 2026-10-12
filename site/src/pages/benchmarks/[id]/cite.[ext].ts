// site/src/pages/benchmarks/[id]/cite.[ext].ts -- P2-S3-T07 (10 "The permanent citation URL"). The citation as files
// beside the detail page: cite.bib (BibTeX), cite.json (CSL-JSON), cite.ris (RIS) and cite.yaml (the record itself), each
// from lib/cite.ts with the facts the page's citation block uses, so the two cannot disagree. Static files: no script.
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { APIRoute } from 'astro';
import { benchmarks } from '../../../lib/collections';
import { bibtex, cslJson, FORMATS, ris, type CiteFacts, type Format } from '../../../lib/cite';
import { release } from '../../../lib/release';
import type { Benchmark } from '../../../types/benchmark';

const REPO_ROOT = process.env.REPO_ROOT ?? resolve(process.cwd(), '..');

export async function getStaticPaths() {
  return (await benchmarks()).flatMap((benchmark) =>
    (Object.keys(FORMATS) as Format[]).map((ext) => ({ params: { id: benchmark.id, ext }, props: { benchmark } })));
}

export const GET: APIRoute = ({ params, props }) => {
  const b = props.benchmark as Benchmark;
  const ext = params.ext as Format;
  const r = release();
  const yaml_path = `data/benchmarks/${b.domain.primary.split('/')[0]}/${b.id}.yaml`;
  const facts: CiteFacts = { entity_id: b.id, title: b.name, commit_sha: r.commit_sha, release_doi: r.concept_doi,
    release_tag: r.tag, retrieved_at: r.built_on, yaml_path, index_title: r.index_title };
  const body = ext === 'bib' ? bibtex(facts)
    : ext === 'json' ? cslJson(facts)
      : ext === 'ris' ? ris(facts)
        : readFileSync(join(REPO_ROOT, yaml_path), 'utf8');
  return new Response(body, { headers: { 'Content-Type': FORMATS[ext].type } });
};
