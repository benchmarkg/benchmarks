#!/usr/bin/env python3
"""The golden set's composition: its strata are the plan's, its items match them, and no family exceeds its share
(P6-S3-T08; 11 S7 "The golden set" and "Where the items come from", D3 S3.4 context 4).

    python scripts/check_golden_composition.py                    # the composition; exit 1 on a failure
    python scripts/check_golden_composition.py --require-labels   # and every gold label set, by a person
    python scripts/check_golden_composition.py --root DIR         # another tree (the tests do)

Why. A self-evaluation can be gamed by what goes into it as easily as by how it is scored. 11 S7: "Queries
generated from the taxonomy are drawn from the exact vocabulary the facet translator is best at", so a set of them
is "systematically optimistic"; and a set stacked with one family's queries measures that family. The ledger asks
for a check that the set "matches its declared strata and that no single family exceeds its share".

The set is evals/golden/{nl_search,facet_translation,suite_build,abstention}.yaml. Each file declares its `strata`;
the check asserts, each a failure when it does not hold:

  - the declarations are the plan's (PLAN, derived below), so a file cannot loosen its own bar: v0 is 20 nl_search,
    12 facet_translation, 5 suite_build and 3 abstention items (11 S7, "Ship v0 at 40 items");
  - each split holds its declared number of items, every id is unique and carries its split's prefix, and no query
    appears twice in the set;
  - provenance is generated, harvested or adversarial (11 S7), `stratum` is one of that provenance's techniques
    (STRATA), and at least half of each split is not generated. A harvested item cites its `source` (title, URL,
    retrieval date) and says in `sourcing` how the query was taken from it; a generated item cites none. A query
    marked harvested or adversarial that is nothing but one taxonomy term (give or take "benchmarks") is the
    taxonomy's own vocabulary, so it fails: its provenance is generated;
  - every query fits the input it stands for: 500 characters for F1 (11 S2 F1) and 1,000 for an F2 need statement;
  - facet_translation holds one item per homograph taxonomy/homographs.yaml declares (D3 S3.4 context 4), each
    naming its declared pair and mentioning the word, and no other split holds one;
  - abstention holds three injection items (11 S6 G2), each with a distinct injection string that occurs verbatim
    in its query;
  - in nl_search, facet_translation and suite_build every item names the domain family it was drafted to target,
    or null with a `family_note`. No family holds more than max(1, floor(FAMILY_SHARE * n)) of a split's n items,
    and null holds at most half of them. (A cap on the three splits together would never bind: a sum of floors is
    at most the floor of the sum.);
  - an item carries only the keys ITEM_KEYS names, and its `notes` name no facet value: a label is set in `gold`
    and nowhere else, and a note that named a value would anchor the person labelling;
  - a gold label is a person's. Any gold label set while `labelled_by` names no one fails, and so does a
    `labelled_by` or `confirmed_by` that names an agent (an agent-written label makes the evaluation circular,
    P6-S3-T08). A gold label that is set must have its split's shape (LABEL SHAPES below), with every entry id a
    file under data/benchmarks/ and every facet value one schema/generated/facetquery.schema.json allows.

Without --require-labels, a gold label may be null: the drafts pass, and labelling can proceed item by item.
With it, every gold label must be set, `labelled_by` must name a person, `labelled_on` must be a date and
`labelled_against` the commit the labels were read from. The ledger's done_when needs that mode green, which only
a person can make true.

LABEL SHAPES (each file's `label_shape` says the same in prose):
  nl_search          {entry id: grade 0-3}, at least one grade 3 (Recall@20 on grade 3 needs one)
  facet_translation  {hard: Facets, soft: Facets, unmapped_terms: [str], intent: one of INTENTS}, where Facets maps
                     any of the ten slots to facet-qualified values (year_min to an integer or null); a homograph
                     item's gold names its capability or its subdomain reference
  suite_build        {must_include: [id] (not empty), must_not_include: [id], nice_to_have: [id], rubric: [str]
                     (not empty)}, no id in two lists
  abstention         {behaviour: one of BEHAVIOURS, note: str (optional)}
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.build.facetquery_schema import FIELDS, INTENTS, SCHEMA  # noqa: E402

GOLDEN = 'evals/golden'
SPLITS = ('nl_search', 'facet_translation', 'suite_build', 'abstention')
# 11 S7, "Ship v0 at 40 items, not 150". P6-S6-T01 adds the ~150-item version's sizes when it grows the set.
PLAN = {'v0': {'nl_search': 20, 'facet_translation': 12, 'suite_build': 5, 'abstention': 3}}
FAMILY_SPLITS = ('nl_search', 'facet_translation', 'suite_build')
FAMILY_SHARE = 0.15                 # about three times a uniform share over the 19 families (1/19 is 0.053)
QUERY_MAX = {'nl_search': 500, 'facet_translation': 500, 'suite_build': 1000, 'abstention': 500}   # 11 S2 F1, F2
HOMOGRAPH_SPLIT = 'facet_translation'
INJECTION_SPLIT, INJECTIONS = 'abstention', 3                                                       # 11 S6 G2
STRATA = {                          # provenance -> the techniques (`stratum`) an item of it may name
    'generated': ('taxonomy-vocabulary',),
    'harvested': ('issue-tracker', 'forum-question', 'model-card', 'regulation-text', 'outside-writer',
                  'real-query-log'),
    'adversarial': ('user-jargon', 'near-miss-vocabulary', 'invented-term', 'negation', 'misspelling-abbreviation',
                    'multi-constraint', 'over-constraint-bait', 'homograph', 'injection'),
}
TOP_KEYS = ('split', 'set_version', 'drafted_by', 'drafted_on', 'labelled_by', 'labelled_on', 'labelled_against',
            'confirmed_by', 'label_shape', 'strata', 'items')
ITEM_KEYS = ('id', 'provenance', 'stratum', 'sourcing', 'source', 'family', 'family_note', 'homograph', 'injection',
             'query', 'notes', 'gold')
GRADES = (0, 1, 2, 3)
BEHAVIOURS = ('out-of-scope', 'report-gap', 'clarify', 'deterministic-fallback', 'proceed-without-complying')
SUITE_LISTS = ('must_include', 'must_not_include', 'nice_to_have')
AGENT = re.compile(r'\b(agent|claude|gpt|llm|model|bot|draft|ai)\b', re.I)
COMMIT = re.compile(r'^[0-9a-f]{7,40}$')
VALUE_IN_TEXT = re.compile(r'\b(?:%s):[a-z0-9]' % '|'.join(sorted({v for v, _ in FIELDS.values() if v})))
FILLER = frozenset({'a', 'an', 'the', 'for', 'of', 'and', 'in', 'on', 'benchmark', 'benchmarks', 'eval', 'evals',
                    'evaluation', 'evaluations', 'test', 'tests', 'dataset', 'datasets'})


def family_cap(n: int) -> int:
    return max(1, int(FAMILY_SHARE * n))


def declared(split: str, version: str, homographs: int) -> dict:
    """The strata the plan requires of one split: what its file must declare."""
    n = PLAN[version][split]
    out = {'items': n, 'not_generated_min': (n + 1) // 2}
    if split in FAMILY_SPLITS:
        out.update(family_max=family_cap(n), family_null_max=n // 2)
    out['query_max_chars'] = QUERY_MAX[split]
    if split == HOMOGRAPH_SPLIT:
        out['homograph_items'] = homographs
    if split == INJECTION_SPLIT:
        out['injections'] = INJECTIONS
    return out


# ---- what the set is checked against --------------------------------------------------------------------------

@dataclass
class Context:
    slots: dict[str, set[str]]                      # FacetQuery slot -> its facet-qualified values
    families: set[str]                              # bare family ids
    benchmarks: set[str]                            # entry ids: data/benchmarks/**/<id>.yaml
    homographs: list[tuple[str, str]]               # (capability ref, domain ref), as declared
    vocabulary: set[frozenset] = field(default_factory=set)     # each term id's words


def _tokens(text: str) -> frozenset:
    return frozenset(w for w in re.split(r'[^a-z0-9]+', text.lower()) if w and w not in FILLER)


def load_context(root: str) -> Context:
    with open(os.path.join(root, SCHEMA), encoding='utf-8') as f:
        facets = json.load(f)['$defs']['Facets']['properties']
    slots = {s: set(facets[s]['items']['enum']) for s in FIELDS if s != 'year_min'}
    with open(os.path.join(root, 'taxonomy', 'homographs.yaml'), encoding='utf-8') as f:
        entries = yaml.safe_load(f)['entries']
    found = glob.glob(os.path.join(root, 'data', 'benchmarks', '**', '*.yaml'), recursive=True)
    ctx = Context(slots=slots, families={v.split(':', 1)[1] for v in slots['domain_family']},
                  benchmarks={os.path.basename(p)[:-len('.yaml')] for p in found},
                  homographs=[(e['capability'], e['domain']) for e in entries])
    ctx.vocabulary = {_tokens(v.split(':', 1)[1].rsplit('/', 1)[-1].replace('-', ' ')) for vs in slots.values()
                      for v in vs}
    return ctx


def load_set(root: str) -> tuple[dict, list[str]]:
    docs, errs = {}, []
    for split in SPLITS:
        path = os.path.join(root, *GOLDEN.split('/'), '%s.yaml' % split)
        if not os.path.exists(path):
            errs.append('%s/%s.yaml does not exist' % (GOLDEN, split))
            continue
        with open(path, encoding='utf-8') as f:
            docs[split] = yaml.safe_load(f)
    return docs, errs


# ---- gold labels ----------------------------------------------------------------------------------------------

def _ids(values, ctx: Context, where: str) -> list[str]:
    if not isinstance(values, list):
        return ['%s is not a list of entry ids' % where]
    unknown = [str(v) for v in values if v not in ctx.benchmarks]
    if unknown:
        return ['%s names %s, not an entry under data/benchmarks/' % (where, ', '.join(unknown))]
    return []


def _gold_nl_search(gold, item, ctx) -> list[str]:
    if not isinstance(gold, dict) or not gold:
        return ['gold is not a mapping of entry id to grade']
    out = _ids(list(gold), ctx, 'gold')
    bad = ['%s: %r' % (k, v) for k, v in gold.items() if isinstance(v, bool) or v not in GRADES]
    if bad:
        out.append('gold grades are 0, 1, 2 or 3, not %s' % ', '.join(bad))
    if not any(v == 3 and not isinstance(v, bool) for v in gold.values()):
        out.append('gold grades no entry 3, so Recall@20 on grade 3 is undefined for the item')
    return out


def _facets(side: str, facets, ctx) -> list[str]:
    if not isinstance(facets, dict):
        return ['gold %s is not a mapping of FacetQuery slot to values' % side]
    out = []
    for slot, values in facets.items():
        if slot not in FIELDS:
            out.append('gold %s names %r, not one of the ten FacetQuery slots' % (side, slot))
        elif slot == 'year_min':
            if values is not None and (isinstance(values, bool) or not isinstance(values, int)):
                out.append('gold %s/year_min is %r, not an integer or null' % (side, values))
        elif not isinstance(values, list):
            out.append('gold %s/%s is not a list' % (side, slot))
        else:
            off = [str(v) for v in values if v not in ctx.slots[slot]]
            if off:
                out.append('gold %s/%s: %s not a facet-qualified value the FacetQuery schema allows in the slot'
                           % (side, slot, ', '.join(off)))
    return out


def _gold_facet_translation(gold, item, ctx) -> list[str]:
    keys = ('hard', 'soft', 'unmapped_terms', 'intent')
    if not isinstance(gold, dict) or set(gold) != set(keys):
        return ['gold is not a mapping of exactly %s' % ', '.join(keys)]
    out = _facets('hard', gold['hard'], ctx) + _facets('soft', gold['soft'], ctx)
    terms = gold['unmapped_terms']
    if not isinstance(terms, list) or any(not isinstance(t, str) or not t.strip() for t in terms):
        out.append('gold unmapped_terms is not a list of non-blank strings')
    if gold['intent'] not in INTENTS:
        out.append('gold intent %r is not one of %s' % (gold['intent'], ', '.join(INTENTS)))
    pair = item.get('homograph')
    if isinstance(pair, dict) and not out:
        named = {v for side in ('hard', 'soft') for slot in ('capability', 'domain_subdomain')
                 for v in gold[side].get(slot) or []}           # a slot left out constrains nothing
        if not named & {pair.get('capability'), pair.get('domain')}:
            out.append('gold names neither %s nor %s, so it does not resolve the homograph the item tests'
                       % (pair.get('capability'), pair.get('domain')))
    return out


def _gold_suite_build(gold, item, ctx) -> list[str]:
    keys = SUITE_LISTS + ('rubric',)
    if not isinstance(gold, dict) or set(gold) != set(keys):
        return ['gold is not a mapping of exactly %s' % ', '.join(keys)]
    out = []
    for k in SUITE_LISTS:
        out += _ids(gold[k], ctx, 'gold %s' % k)
    if out:
        return out
    if not gold['must_include']:
        out.append('gold must_include is empty')
    seen = Counter(v for k in SUITE_LISTS for v in set(gold[k]))
    twice = sorted(v for v, c in seen.items() if c > 1)
    if twice:
        out.append('gold puts %s in two lists' % ', '.join(twice))
    rubric = gold['rubric']
    if not isinstance(rubric, list) or not rubric or any(not isinstance(r, str) or not r.strip() for r in rubric):
        out.append('gold rubric is not a non-empty list of non-blank strings')
    return out


def _gold_abstention(gold, item, ctx) -> list[str]:
    if not isinstance(gold, dict) or 'behaviour' not in gold or set(gold) - {'behaviour', 'note'}:
        return ['gold is not a mapping of behaviour and an optional note']
    if gold['behaviour'] not in BEHAVIOURS:
        return ['gold behaviour %r is not one of %s' % (gold['behaviour'], ', '.join(BEHAVIOURS))]
    return []


GOLD = {'nl_search': _gold_nl_search, 'facet_translation': _gold_facet_translation,
        'suite_build': _gold_suite_build, 'abstention': _gold_abstention}


# ---- the check ------------------------------------------------------------------------------------------------

def _is_date(v) -> bool:
    if isinstance(v, date):
        return True
    try:
        date.fromisoformat(str(v))
        return True
    except ValueError:
        return False


def _mentions(query: str, ref: str) -> bool:
    """Whether the query says the term's word: hyphens as spaces or hyphens, -ize as -ise."""
    words = ref.split(':', 1)[1].rsplit('/', 1)[-1].split('-')
    pattern = r'[\s-]+'.join(re.escape(w).replace('z', '[sz]') for w in words)
    return re.search(r'\b%s\b' % pattern, query, re.I) is not None


def _labelling(doc: dict, items: list, require: bool) -> list[str]:
    out = []
    by, confirmed = doc['labelled_by'], doc['confirmed_by']
    for key, who in (('labelled_by', by), ('confirmed_by', confirmed)):
        if who is not None and (not isinstance(who, str) or not who.strip()):
            out.append('%s is blank: name a person or leave it null' % key)
        elif who is not None and AGENT.search(who):
            out.append('%s is %r, which names an agent: a gold label must be a person\'s, or the evaluation is '
                       'circular' % (key, who))
    if confirmed is not None and confirmed == by:
        out.append('confirmed_by is labelled_by: the confirmation is a second person\'s')
    labelled = [str(it.get('id')) for it in items if it.get('gold') is not None]
    if labelled and by is None:
        out.append('%d gold label(s) set (%s) but labelled_by names no one' % (len(labelled), ', '.join(labelled[:3])))
    if require:
        if by is None:
            out.append('labelled_by names no one: a person labels every item')
        if not _is_date(doc['labelled_on']):
            out.append('labelled_on is %r, not a date' % doc['labelled_on'])
        if not COMMIT.match(str(doc['labelled_against'])):
            out.append('labelled_against is %r, not the commit the labels were read from' % doc['labelled_against'])
        empty = [str(it.get('id')) for it in items if it.get('gold') is None]
        if empty:
            out.append('%d of %d gold labels are empty: %s%s' % (len(empty), len(items), ', '.join(empty[:5]),
                                                               ', ...' if len(empty) > 5 else ''))
    return out


def _item(split: str, it, ctx: Context) -> list[str]:
    if not isinstance(it, dict):
        return ['an item is not a mapping: %r' % (it,)]
    name = str(it.get('id'))
    out = []

    def bad(msg):
        out.append('%s: %s' % (name, msg))
    extra = sorted(set(it) - set(ITEM_KEYS))
    if extra:
        bad('carries %s: an item holds ITEM_KEYS only, and its answer goes in gold and nowhere else' % ', '.join(extra))
    missing = [k for k in ('id', 'provenance', 'stratum', 'query', 'gold') if k not in it]
    if missing:
        bad('has no %s' % ', '.join(missing))
        return out
    if not str(it['id']).startswith(split + '-'):
        bad('the id does not start with %s-' % split)
    prov, stratum, query = it['provenance'], it['stratum'], it['query']
    if prov not in STRATA:
        bad('provenance %r is not one of %s' % (prov, ', '.join(STRATA)))
    elif stratum not in STRATA[prov]:
        bad('stratum %r is not a %s technique (%s)' % (stratum, prov, ', '.join(STRATA[prov])))
    if not isinstance(query, str) or not query.strip():
        bad('the query is blank')
        return out
    if len(query) > QUERY_MAX[split]:
        bad('the query is %d characters, over the %d its input allows' % (len(query), QUERY_MAX[split]))
    source = it.get('source')
    if prov in ('harvested', 'adversarial') and not str(it.get('sourcing') or '').strip():
        bad('a %s item says in `sourcing` how it was sourced' % prov)
    if prov == 'harvested':
        if not isinstance(source, dict) or not str(source.get('title') or '').strip() or \
                not _is_date(source.get('retrieved_on')) or \
                (stratum != 'outside-writer' and not str(source.get('url') or '').startswith('https://')):
            bad('a harvested item cites its source: title, https url (but for an outside writer) and retrieved_on')
    elif prov == 'generated' and source is not None:
        bad('a generated item has no external source; one that does is harvested')
    if prov in ('harvested', 'adversarial') and _tokens(query) in ctx.vocabulary:
        bad('the query is one taxonomy term, the taxonomy\'s own vocabulary: its provenance is generated')
    notes = it.get('notes')
    if notes is not None and (not isinstance(notes, str) or VALUE_IN_TEXT.search(notes)):
        bad('the notes name a facet value: a label goes in gold, and a note naming one anchors the labeller')

    if split in FAMILY_SPLITS:
        if 'family' not in it:
            bad('names no family (null, with a family_note, where the item targets none)')
        elif it['family'] is None:
            if not str(it.get('family_note') or '').strip():
                bad('family is null without a family_note saying why')
        elif not isinstance(it['family'], str) or it['family'] not in ctx.families:
            bad('family %r is not a domain family' % it['family'])

    pair = it.get('homograph')
    if (pair is not None) != (stratum == 'homograph'):
        bad('a homograph block goes with stratum homograph, and only with it')
    elif pair is not None:
        if split != HOMOGRAPH_SPLIT:
            bad('a homograph item belongs in %s (D3 S3.4 context 4)' % HOMOGRAPH_SPLIT)
        if not isinstance(pair, dict) or (pair.get('capability'), pair.get('domain')) not in ctx.homographs:
            bad('the homograph %r is not a pair taxonomy/homographs.yaml declares' % (pair,))
        elif not _mentions(query, pair['capability']):
            bad('the query does not say %r, the homograph it tests' % pair['capability'].split(':', 1)[1])
    inj = it.get('injection')
    if (inj is not None) != (stratum == 'injection'):
        bad('an injection block goes with stratum injection, and only with it')
    elif inj is not None:
        if split != INJECTION_SPLIT:
            bad('an injection item belongs in %s (11 S6 G2)' % INJECTION_SPLIT)
        if not isinstance(inj, dict) or any(not str(inj.get(k) or '').strip() for k in ('string', 'technique',
                                                                                          'aims_at')):
            bad('the injection block needs string, technique and aims_at')
        elif inj['string'] not in query:
            bad('the injection string does not occur verbatim in the query')

    if it['gold'] is not None:
        out += ['%s: %s' % (name, e) for e in GOLD[split](it['gold'], it, ctx)]
    return out


def _families(items: list, cap: int, null_cap: int) -> list[str]:
    named = Counter(it['family'] for it in items if isinstance(it.get('family'), str))
    out = ['family %s holds %d items, over its share of %d (FAMILY_SHARE %.2f)' % (f, c, cap, FAMILY_SHARE)
           for f, c in sorted(named.items()) if c > cap]
    nulls = sum(1 for it in items if 'family' in it and it['family'] is None)
    if nulls > null_cap:
        out.append('%d items target no family, over the %d (half the split) allowed' % (nulls, null_cap))
    return out


def check(docs: dict, ctx: Context, require_labels: bool = False) -> list[str]:
    """Every way the set breaks its composition (and, with require_labels, its labelling); empty when it holds."""
    errs = []
    versions = {d.get('set_version') for d in docs.values() if isinstance(d, dict)}
    if len(versions) != 1 or not versions <= set(PLAN):
        return ['the files declare set_version %s; one of %s, the same in all four' % (sorted(map(str, versions)),
                                                                                       ', '.join(PLAN))]
    version = versions.pop()
    ids, queries = Counter(), {}
    for split, doc in docs.items():
        def e(msg, split=split):
            errs.append('%s: %s' % (split, msg))
        if not isinstance(doc, dict):
            e('the file is not a mapping')
            continue
        missing = [k for k in TOP_KEYS if k not in doc]
        extra = sorted(set(doc) - set(TOP_KEYS))
        if missing or extra:
            e('the file %s' % '; '.join(filter(None, ['lacks %s' % ', '.join(missing) if missing else '',
                                                      'carries %s' % ', '.join(extra) if extra else ''])))
            continue
        if doc['split'] != split:
            e('the file says split %r' % doc['split'])
        want, got = declared(split, version, len(ctx.homographs)), doc['strata']
        if got != want:
            e('the declared strata %s are not the plan\'s %s' % (got, want))
        items = doc['items'] if isinstance(doc['items'], list) else []
        if len(items) != want['items']:
            e('%d items, not the %d the plan declares' % (len(items), want['items']))
        for it in items:
            errs += ['%s: %s' % (split, m) for m in _item(split, it, ctx)]
            if isinstance(it, dict):
                ids[it.get('id')] += 1
                q = ' '.join(str(it.get('query')).lower().split())
                if q in queries:
                    e('%s repeats the query of %s' % (it.get('id'), queries[q]))
                queries.setdefault(q, it.get('id'))
        items = [it for it in items if isinstance(it, dict)]
        not_generated = sum(1 for it in items if it.get('provenance') in ('harvested', 'adversarial'))
        if not_generated < want['not_generated_min']:
            e('%d of %d items are harvested or adversarial; at least half (%d) must be (11 S7)'
              % (not_generated, len(items), want['not_generated_min']))
        if split in FAMILY_SPLITS:
            errs += ['%s: %s' % (split, m) for m in _families(items, want['family_max'], want['family_null_max'])]
        if split == HOMOGRAPH_SPLIT:
            hom = [it for it in items if it.get('stratum') == 'homograph']
            if len(hom) != want['homograph_items']:
                e('%d homograph items, not the %d declared' % (len(hom), want['homograph_items']))
            covered = {(it['homograph'].get('capability'), it['homograph'].get('domain')) for it in hom
                       if isinstance(it.get('homograph'), dict)}
            for cap, dom in ctx.homographs:
                if (cap, dom) not in covered:
                    e('no item tests the declared homograph %s / %s (D3 S3.4 context 4)' % (cap, dom))
        if split == INJECTION_SPLIT:
            strings = [it['injection']['string'] for it in items if isinstance(it.get('injection'), dict)
                       and 'string' in it['injection']]
            if len(strings) != want['injections'] or len(set(strings)) != len(strings):
                e('%d injection string(s), %d distinct; the split declares %d distinct (11 S6 G2)'
                  % (len(strings), len(set(strings)), want['injections']))
        errs += ['%s: %s' % (split, m) for m in _labelling(doc, items, require_labels)]
    errs += ['the set: id %s is used %d times' % (i, c) for i, c in sorted(ids.items(), key=str) if c > 1]
    return errs


def summary(docs: dict) -> list[str]:
    out = []
    for split, doc in docs.items():
        items = doc['items']
        prov = Counter(it['provenance'] for it in items)
        line = '%-18s %2d items: %s' % (split, len(items), ', '.join('%d %s' % (prov[p], p) for p in STRATA))
        if split in FAMILY_SPLITS:
            fam = Counter(it['family'] for it in items if it['family'] is not None)
            top = max(fam.values()) if fam else 0
            biggest = sorted(f for f, c in fam.items() if c == top)
            line += '; %d families, largest %d (%s), %d none' % (
                len(fam), top, ', '.join(biggest) if len(biggest) <= 2 else '%d tied' % len(biggest),
                sum(1 for it in items if it['family'] is None))
        line += '; %d labelled' % sum(1 for it in items if it['gold'] is not None)
        out.append(line)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT, help='the tree to check (default: this repository)')
    p.add_argument('--require-labels', action='store_true',
                   help='also fail while any gold label is empty or not a person\'s (the done_when)')
    a = p.parse_args(argv)
    docs, errs = load_set(a.root)
    if not errs:
        errs = check(docs, load_context(a.root), a.require_labels)
    if errs:
        for e in errs:
            print('%s: %s' % (GOLDEN, e))
        print('check_golden_composition: %d failure(s)%s'
              % (len(errs), ' (--require-labels)' if a.require_labels else ''))
        return 1
    total = sum(len(d['items']) for d in docs.values())
    labelled = sum(1 for d in docs.values() for it in d['items'] if it['gold'] is not None)
    for line in summary(docs):
        print(line)
    print('check_golden_composition: set %s, %d items, composition as declared; %d of %d gold labels set%s'
          % (next(iter(docs.values()))['set_version'], total, labelled, total,
             ', all by a person' if a.require_labels else
             ' (--require-labels fails until a person has set every one)' if labelled < total else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
