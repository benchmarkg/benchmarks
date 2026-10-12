// site/src/lib/cite.ts -- P2-S3-T07 (10 "The permanent citation URL"; 05 S10; 08 S4.4). One entry's citation in every
// format the site offers, from one set of facts, so the block on the page and the files beside it cannot disagree:
//
//   BibTeX     @misc, for LaTeX                      /benchmarks/{id}/cite.bib
//   CSL-JSON   a one-item array, for Zotero et al.   /benchmarks/{id}/cite.json
//   RIS        TY - DATA, CRLF line ends             /benchmarks/{id}/cite.ris
//   raw YAML   the record itself                     /benchmarks/{id}/cite.yaml
//   APA        a sentence, on the page only
//
// Every format points at the YAML at a commit (a permalink) and at the release's concept DOI, never at an artifact
// URL: "an artifact URL is a cache key, not a citation" (08 S4.4). tools/build/citation.py checks the built files
// against each other and against the page, independently of this module. Croissant JSON-LD, the fifth format 10 names,
// is P2-S3-T06's to generate.
import { blobAt, sha } from './repo';

export interface CiteFacts {
  entity_id: string;
  title: string;
  commit_sha: string;
  release_doi: string | null;
  release_tag: string | null;
  retrieved_at: string;           // YYYY-MM-DD
  yaml_path: string;
  index_title: string;
}

export const AUTHOR = 'Benchmark index contributors';

export const citeKey = (c: CiteFacts) => `uaibi-${c.entity_id}-${sha(c.commit_sha).slice(0, 7)}`.replace(/[^a-zA-Z0-9-]/g, '-');
export const permalink = (c: CiteFacts) => blobAt(sha(c.commit_sha), c.yaml_path);
const year = (c: CiteFacts) => c.retrieved_at.slice(0, 4);
const note = (c: CiteFacts) => `Entry ${c.entity_id} at commit ${sha(c.commit_sha)}`
  + `${c.release_tag != null ? `, release ${c.release_tag}` : ''}, retrieved ${c.retrieved_at}`;

/** BibTeX's specials, escaped, so a title with & or % or _ cannot break the entry. */
const tex = (s: string) => s.replace(/\\/g, '\\textbackslash{}').replace(/([&%$#_{}])/g, '\\$1')
  .replace(/~/g, '\\textasciitilde{}').replace(/\^/g, '\\textasciicircum{}');

export function bibtex(c: CiteFacts): string {
  return [
    `@misc{${citeKey(c)},`,
    `  title = {${tex(c.title)}},`,
    `  author = {{${AUTHOR}}},`,
    `  year = {${year(c)}},`,
    `  howpublished = {\\url{${permalink(c)}}},`,
    `  organization = {${tex(c.index_title)}},`,
    ...(c.release_doi != null ? [`  doi = {${c.release_doi}},`] : []),
    `  note = {${tex(note(c))}}`,
    '}',
  ].join('\n') + '\n';
}

export function apa(c: CiteFacts): string {
  return `${AUTHOR}. (${year(c)}). ${c.title} [Data set entry ${c.entity_id}]. ${c.index_title}. `
    + (c.release_doi != null ? `https://doi.org/${c.release_doi}` : permalink(c));
}

export function cslJson(c: CiteFacts): string {
  const [y, m, d] = c.retrieved_at.split('-').map(Number);
  const item: Record<string, unknown> = {
    id: citeKey(c),
    type: 'dataset',
    title: c.title,
    'container-title': c.index_title,
    author: [{ literal: AUTHOR }],
    issued: { 'date-parts': [[y]] },
    accessed: { 'date-parts': [[y, m, d]] },
    URL: permalink(c),
    version: c.release_tag ?? sha(c.commit_sha),
    note: note(c),
  };
  if (c.release_doi != null) item.DOI = c.release_doi;
  return `${JSON.stringify([item], null, 1)}\n`;
}

export function ris(c: CiteFacts): string {
  const [y, m, d] = c.retrieved_at.split('-');
  return [
    'TY  - DATA',
    `TI  - ${c.title}`,
    `AU  - ${AUTHOR}`,
    `PY  - ${year(c)}`,
    `T2  - ${c.index_title}`,
    `UR  - ${permalink(c)}`,
    ...(c.release_doi != null ? [`DO  - ${c.release_doi}`] : []),
    `Y2  - ${y}/${m}/${d}`,
    `N1  - ${note(c)}`,
    'ER  - ',
  ].join('\r\n') + '\r\n';
}

/** The file formats, by the extension their route is served at. */
export const FORMATS = {
  bib: { label: 'BibTeX', type: 'application/x-bibtex; charset=utf-8' },
  json: { label: 'CSL-JSON', type: 'application/vnd.citationstyles.csl+json; charset=utf-8' },
  ris: { label: 'RIS', type: 'application/x-research-info-systems; charset=utf-8' },
  yaml: { label: 'raw YAML', type: 'text/yaml; charset=utf-8' },
} as const;
export type Format = keyof typeof FORMATS;
