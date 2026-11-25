// tools/evals/lexical_runs.mjs -- P6-S3-T09 (11 S7 "Where the items come from": TREC-style pooling; 11 S4 "The
// pipeline", step 2). The pooling harness's two lexical configurations, run by the site's own BM25 leg,
// site/src/islands/search/lexical.ts, loaded by Node as it is (types stripped, as site/test/ loads it). There is one
// BM25 implementation in the repository and this is not a second: tools/evals/retrieval.py pipes the rows and queries
// in and reads the ranked lists out.
//
//   node tools/evals/lexical_runs.mjs < request.json > runs.json      # needs `npm ci` in site/ (minisearch)
//
// request: {rows: [{id, name, aliases, editions, tagline, description, maintainer}], queries: [{id, text}],
//           configurations: ["lexical", "lexical-wide"]}
// answer:  {configuration: {query id: [[row, score], ...]}}, every matching row, best first, equal scores by row.
//
//   lexical       buildLexicalIndex and bm25 exactly as the site runs them: name, aliases, editions and id, the
//                 site's boosts, fuzzy and prefix rules and BM25+ parameters.
//   lexical-wide  the same leg over the five fields 11 S4 names ("name, aliases, edition names, description and
//                 maintainer") and the tagline 08 S5.7 names. lexical.ts leaves those three out only for facets.json's
//                 36 KB budget, and says adding them "is then a change to LEXICAL_FIELDS and BOOST alone": this index
//                 is that change, made here and not in the site. Each added field boosts 1, the rule lexical.ts
//                 states (how directly the field names the row's benchmark), which ranks a description match with an
//                 id match. Everything else -- tokenizer, normaliser, fuzziness, weights, BM25+, the exact-name boost
//                 -- is lexical.ts's own export, so a change there moves both configurations.
//
// MiniSearch is the class of the index lexical.ts builds, so this file resolves no package of its own and cannot load
// a second copy of MiniSearch at another version.
import { readFileSync } from 'node:fs';
import {
  BM25_PARAMS, BOOST, FUZZY_WEIGHT, LEXICAL_FIELDS, MAX_FUZZY, PREFIX_WEIGHT, bm25, buildLexicalIndex, fuzziness,
  normalise, phrase,
} from '../../site/src/islands/search/lexical.ts';

const WIDE_EXTRA = ['tagline', 'description', 'maintainer'];
const WIDE_FIELDS = [...LEXICAL_FIELDS, ...WIDE_EXTRA];
const WIDE_BOOST = { ...BOOST, ...Object.fromEntries(WIDE_EXTRA.map((f) => [f, 1])) };

function buildWideIndex(rows) {
  const MiniSearch = buildLexicalIndex([]).constructor;
  const index = new MiniSearch({
    idField: 'row',
    fields: WIDE_FIELDS,
    storeFields: ['exact'],
    processTerm: (term) => normalise(term) || null,
    searchOptions: {
      boost: { ...WIDE_BOOST },
      prefix: true,
      fuzzy: fuzziness,
      maxFuzzy: MAX_FUZZY,
      weights: { prefix: PREFIX_WEIGHT, fuzzy: FUZZY_WEIGHT },
      combineWith: 'OR',
      bm25: { ...BM25_PARAMS },
    },
  });
  index.addAll(rows.map((r, row) => ({
    row, id: r.id, name: r.name, aliases: r.aliases.join(' '), editions: r.editions.join(' '),
    tagline: r.tagline ?? '', description: r.description ?? '', maintainer: r.maintainer ?? '',
    exact: [...new Set([r.name, ...r.aliases, ...r.editions, r.id].map(phrase))],
  })));
  return index;
}

const BUILD = { lexical: buildLexicalIndex, 'lexical-wide': buildWideIndex };

function runs(request) {
  const out = {};
  for (const name of request.configurations) {
    if (!(name in BUILD)) throw new Error(`unknown configuration ${name}: ${Object.keys(BUILD).join(', ')}`);
    const index = BUILD[name](request.rows);
    out[name] = Object.fromEntries(request.queries.map((q) => [q.id, bm25(index, q.text).map((r) => [r.row, r.score])]));
  }
  return out;
}

process.stdout.write(JSON.stringify(runs(JSON.parse(readFileSync(0, 'utf8')))));
