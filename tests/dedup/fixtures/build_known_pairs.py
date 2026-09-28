"""Build tests/dedup/fixtures/known-pairs.yaml, F7's calibration set (P1-S2-T05; 11-ai-features.md S F7).

    uv run python tests/dedup/fixtures/build_known_pairs.py

11 S F7 calibrates the near-duplicate threshold on "the first 200 pairs whose answer we already know
(the SWE-bench family, the CASP editions, the HELM variants, the FrontierMath variants)". This script
is how that set is made, so the set can be audited and rebuilt. It does not look at the scorer: pairs
are chosen by rule, and the rules are below. Every record comes from a file in this repository or from
a page fetched on FETCHED_ON, whose URL it carries. No record's text is written from memory.

Records
  corpus:<id>     taxonomy/_corpus/stress-corpus.yaml (90 entries, verified by P1-S1-T01/T02): name, URL,
                  primary paper title and URL
  data:<id>       data/benchmarks/**/*.yaml (the curated entries): name, aliases, URLs, paper title
  page:<id>       a family member's own page, fetched on FETCHED_ON (FETCHED below): name as the
                  page or its maintainers' documentation writes it, its URLs, the paper title
  family:<id>     the family an overlap row checked (data/_analysis/overlap-*.yaml), by the row's name,
                  when the stress corpus has no entry of that id
  radar:<id>, benchmarklist:<id>
                  the other catalogue's matched entry, by its name and the row's evidence URL

Pairs, and why each label is known
  variant-of / same, 122 pairs:
    - every pair within a family group (GROUPS): the SWE-bench family (data/benchmarks/code/swe-bench.yaml
      lineage: variants and the Scale AI fork), the CASP editions, the HELM leaderboards (the
      maintainers' "Reproducing Leaderboards" list), the FrontierMath components (the stress corpus's
      own flags), and ARC-AGI-2/-3;
    - the stress-corpus entries that data/benchmarks/ curates again (SAME_ACROSS);
    - every overlap row a checker marked present, as (our family, their entry), and, for a family both
      catalogues carry, as (their entry, the other's entry). P0-S10-T01's rule is that "any version or
      child of the family counts", so a row is `same` when the names normalise equal, else `variant-of`
      (GPQA and GPQA Diamond);
  distinct, 78 pairs:
    - LOOK_ALIKES: named pairs whose names or subject invite confusion and whose benchmarks are
      unrelated (MMLU-Pro and MMMU-Pro, FrontierMath and FrontierCode, HarmBench and AgentHarm);
    - the rest, drawn with SEED from the pairs of stress-corpus entries in one domain family, excluding
      any pair in a family group, any pair where one entry's name appears in the other's text, and any
      pair touching an aggregate (AGGREGATES), whose relation to its members is not "distinct".
"""
import os
import random
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from schema.taxonomy import read_yaml  # noqa: E402

OUT = os.path.join(HERE, 'known-pairs.yaml')
FETCHED_ON = '2026-09-28'
SEED = 7
N_PAIRS = 200
HELM_DOCS = 'https://crfm-helm.readthedocs.io/en/latest/reproducing_leaderboards/'

FETCHED = [   # id, name, aliases, urls, titles, where the name was read
    ('swe-bench-lite', 'SWE-bench Lite', [], ['https://www.swebench.com/lite.html'], [], 'the page title'),
    ('swe-bench-multimodal', 'SWE-bench Multimodal', [], ['https://www.swebench.com/multimodal.html',
     'https://arxiv.org/abs/2410.03859'], ['SWE-bench Multimodal: Do AI Systems Generalize to Visual Software Domains?'],
     'the page title and the arXiv abstract page'),
    ('swe-bench-multilingual', 'SWE-bench Multilingual', [], ['https://www.swebench.com/multilingual.html'], [],
     'the page title'),
    ('swe-bench-pro', 'SWE-Bench Pro', [], ['https://arxiv.org/abs/2509.16941'],
     ['SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?'], 'the arXiv abstract page'),
    ('casp14', 'CASP14', [], ['https://predictioncenter.org/casp14/'], [], 'the page title "Home - CASP14"'),
    ('casp15', 'CASP15', [], ['https://predictioncenter.org/casp15/'], [], 'the page title "Home - CASP15"'),
    ('casp16', 'CASP16', [], ['https://predictioncenter.org/casp16/'], [], 'the page title "Home - CASP16"'),
    ('helm-classic', 'HELM Classic', ['Holistic Evaluation of Language Models'],
     ['https://crfm.stanford.edu/helm/classic/latest/'], [], HELM_DOCS + ' ("Classic") and the docs index'),
    ('helm-lite', 'HELM Lite', [], ['https://crfm.stanford.edu/helm/lite/latest/'], [], HELM_DOCS + ' ("Lite")'),
    ('helm-safety', 'HELM Safety', [], ['https://crfm.stanford.edu/helm/safety/latest/'], [],
     'the docs index ("HELM Safety")'),
    ('heim', 'HEIM', ['Holistic Evaluation of Text-To-Image Models'],
     ['https://crfm.stanford.edu/helm/heim/latest/', 'https://arxiv.org/abs/2311.04287'], [],
     'the docs index and the arXiv abstract page'),
    ('vhelm', 'VHELM', ['Holistic Evaluation of Vision-Language Models'],
     ['https://crfm.stanford.edu/helm/vhelm/latest/', 'https://arxiv.org/abs/2410.07112'],
     ['VHELM: A Holistic Evaluation of Vision Language Models'], 'the docs index and the arXiv abstract page'),
    ('ahelm', 'AHELM', ['Holistic Evaluation of Audio-Language Models'],
     ['https://crfm.stanford.edu/helm/audio/latest/', 'https://arxiv.org/abs/2508.21376'],
     ['AHELM: A Holistic Evaluation of Audio-Language Models'], 'the docs index and the arXiv abstract page'),
    ('frontiermath-tiers-1-4', 'FrontierMath Tiers 1-4', [], ['https://epoch.ai/frontiermath/tiers-1-4'], [],
     'the stress corpus flag naming the page; the page answered 200'),
    ('frontiermath-erdos', 'FrontierMath Erdős', [], ['https://epoch.ai/benchmarks/frontiermath-erdos'], [],
     'the page title "FrontierMath Erdős"'),
    ('frontiermath-open-problems', 'FrontierMath: Open Problems', [], ['https://epoch.ai/frontiermath/open-problems'],
     [], 'the page title'),
]
GROUPS = {   # a family whose members are all positives with each other: (members, label, basis)
    'swe-bench': (['data:swe-bench', 'corpus:swe-bench-verified', 'page:swe-bench-lite', 'page:swe-bench-multimodal',
                   'page:swe-bench-multilingual', 'page:swe-bench-pro'],
                  'variant-of', 'data/benchmarks/code/swe-bench.yaml lineage (variants, and the Scale AI fork)'),
    'casp': (['data:casp', 'corpus:casp17', 'corpus:casp16-na-rna-puzzles-joint-assessment', 'page:casp14',
              'page:casp15', 'page:casp16'], 'variant-of', 'CASP editions (data/benchmarks/biology-genetics/casp.yaml)'),
    'helm': (['corpus:helm-capabilities', 'corpus:medhelm', 'page:helm-classic', 'page:helm-lite', 'page:helm-safety',
              'page:heim', 'page:vhelm', 'page:ahelm'], 'variant-of', 'HELM leaderboards (' + HELM_DOCS + ')'),
    'frontiermath': (['corpus:frontiermath-tiers-erd-s', 'page:frontiermath-tiers-1-4', 'page:frontiermath-erdos',
                      'page:frontiermath-open-problems'], 'variant-of',
                     'FrontierMath components (the stress corpus flags on frontiermath-tiers-erd-s)'),
    'arc-agi': (['corpus:arc-agi-2', 'corpus:arc-agi-3', 'data:arc-agi-3'], 'variant-of',
                'ARC-AGI versions (the stress corpus flag on arc-agi-2)'),
}
SAME = {('corpus:arc-agi-3', 'data:arc-agi-3')}                 # within a group, the one pair that is one entry
SAME_ACROSS = [   # (corpus, data, label)
    ('corpus:paperbench', 'data:paperbench', 'same'), ('corpus:matbench-discovery', 'data:matbench-discovery', 'same'),
    ('corpus:weatherbench-2', 'data:weatherbench-2', 'same'), ('corpus:roboarena', 'data:roboarena', 'same'),
    ('corpus:forecastbench', 'data:forecastbench', 'same'),
    ('corpus:virtual-cell-challenge-2026', 'data:virtual-cell-challenge', 'variant-of'),   # an edition of the series
]
LOOK_ALIKES = [
    ('corpus:mmlu-pro', 'corpus:mmmu-pro'), ('corpus:wmt25-general-mt-shared-task', 'corpus:iwslt-2026'),
    ('corpus:harmbench', 'corpus:agentharm'), ('corpus:lmarena', 'corpus:kaggle-game-arena'),
    ('corpus:lmarena', 'corpus:roboarena'), ('corpus:kaggle-game-arena', 'corpus:roboarena'),
    ('corpus:posebusters', 'corpus:runs-n-poses'), ('corpus:open-catalyst-oc20-oc22', 'corpus:omol25'),
    ('corpus:terminal-bench-2-0', 'corpus:swe-bench-verified'), ('corpus:mle-bench', 'corpus:paperbench'),
    ('corpus:healthbench', 'corpus:medhelm'), ('corpus:medagentbench-v2', 'corpus:agentharm'),
    ('corpus:osworld-2-0', 'corpus:webarena'), ('corpus:video-mme-v2', 'corpus:mmmu-pro'),
    ('corpus:frontiermath-tiers-erd-s', 'radar:llm-stats-frontiercode'),
    ('corpus:open-problems-in-single-cell-analysis', 'page:frontiermath-open-problems'),
    ('corpus:casp17', 'corpus:camelyon17'), ('corpus:cafa', 'corpus:casp17'),
    ('corpus:luna16', 'corpus:casp16-na-rna-puzzles-joint-assessment'),
    ('benchmarklist:simplebench', 'benchmarklist:simpleqa'), ('corpus:simulacrabench', 'benchmarklist:simplebench'),
    ('corpus:helm-capabilities', 'corpus:holistic-agent-leaderboard-hal'), ('corpus:bend', 'corpus:bench'),
    ('corpus:vbench-2-0', 'corpus:video-mme-v2'), ('corpus:srbench-2-0', 'corpus:terminal-bench-2-0'),
    ('corpus:navsim-v2', 'corpus:video-mme-v2'), ('corpus:dcase-2026', 'corpus:lifeclef-2026'),
    ('corpus:brats-2026-cluster', 'corpus:2026-behavior-challenge'),
]
AGGREGATES = {'corpus:inspect-evals', 'corpus:holistic-agent-leaderboard-hal', 'corpus:epoch-capabilities-index',
              'corpus:helm-capabilities', 'corpus:metriq-qed-c', 'corpus:open-x-embodiment'}


def norm(s):
    s = unicodedata.normalize('NFKD', s)
    return ' '.join(re.sub(r'[^0-9a-z]+', ' ', ''.join(c for c in s if not unicodedata.combining(c)).casefold()).split())


def rec(rid, name, aliases=(), urls=(), titles=(), source=None):
    out = {'id': rid, 'name': name}
    if aliases:
        out['aliases'] = list(aliases)
    if urls:
        out['urls'] = list(dict.fromkeys(u for u in urls if u))
    if titles:
        out['titles'] = list(titles)
    out['source'] = source
    return out


def build():
    records, texts = {}, {}
    corpus = read_yaml(os.path.join(ROOT, 'taxonomy', '_corpus', 'stress-corpus.yaml'))['entries']
    domain = {}
    for e in corpus:
        paper = e.get('primary_paper') or {}
        rid = 'corpus:' + e['id']
        records[rid] = rec(rid, e['name'], (), [e.get('url'), paper.get('url')],
                           [paper['title']] if paper.get('title') else [], 'taxonomy/_corpus/stress-corpus.yaml')
        domain[rid] = e['domain_family']
        texts[rid] = ' '.join([e.get('description') or ''] + list(e.get('flags') or []))
    for path in sorted(os.path.join(d, f) for d, _, fs in os.walk(os.path.join(ROOT, 'data', 'benchmarks'))
                       for f in fs if f.endswith('.yaml')):
        b = read_yaml(path)
        rid = 'data:' + b['id']
        paper = b.get('paper') or {}
        records[rid] = rec(rid, b['name'], b.get('aliases') or [],
                           [b.get(k) for k in ('homepage', 'repository', 'leaderboard_url', 'dataset_url')],
                           [paper['title']] if paper.get('title') else [],
                           os.path.relpath(path, ROOT).replace(os.sep, '/'))
    for pid, name, aliases, urls, titles, where in FETCHED:
        records['page:' + pid] = rec('page:' + pid, name, aliases, urls, titles, 'fetched %s; name from %s' % (FETCHED_ON, where))

    pairs, seen = [], set()

    def add(a, b, label, basis):
        key = tuple(sorted((a, b)))
        assert a in records and b in records, (a, b)
        assert key not in seen, key
        seen.add(key)
        pairs.append({'a': key[0], 'b': key[1], 'label': label, 'basis': basis})

    grouped = {}
    for g, (members, label, basis) in GROUPS.items():
        for m in members:
            grouped[m] = g
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                add(a, b, 'same' if tuple(sorted((a, b))) in SAME else label, basis)
    for a, b, label in SAME_ACROSS:
        add(a, b, label, 'the stress corpus entry is curated again in data/benchmarks/')

    for service, prefix in (('benchmark-radar', 'radar'), ('benchmarklist', 'benchmarklist')):
        d = read_yaml(os.path.join(ROOT, 'data', '_analysis', 'overlap-%s-2026-09.yaml' % service))
        for row in d['rows']:
            if not row['present']:
                continue
            ours = 'corpus:' + row['family']
            if ours not in records:
                ours = 'family:' + row['family']
                records.setdefault(ours, rec(ours, row['name'], source='data/_analysis/overlap-%s-2026-09.yaml' % service))
            theirs = '%s:%s' % (prefix, row['matched']['id'])
            records[theirs] = rec(theirs, row['matched']['name'], (), [row['evidence_url']],
                                  source='data/_analysis/overlap-%s-2026-09.yaml' % service)
            label = 'same' if norm(row['name']) == norm(row['matched']['name']) else 'variant-of'
            add(ours, theirs, label, 'overlap check %s (%s, %s)' % (service, row['checked_by'], row['checked_on']))
            row_of = records.setdefault('_rows', {})
            row_of.setdefault(row['family'], {})[prefix] = theirs
    rows = records.pop('_rows')
    for family, both in sorted(rows.items()):
        if len(both) == 2:
            a, b = both['radar'], both['benchmarklist']
            label = 'same' if norm(records[a]['name']) == norm(records[b]['name']) else 'variant-of'
            add(a, b, label, 'both overlap checks matched the family %s' % family)

    for a, b in LOOK_ALIKES:
        add(a, b, 'distinct', 'look-alike: names or subject invite confusion; unrelated benchmarks')

    def related(a, b):
        if a in AGGREGATES or b in AGGREGATES or (grouped.get(a) and grouped.get(a) == grouped.get(b)):
            return True
        na, nb = norm(records[a]['name']), norm(records[b]['name'])
        return (len(na) > 3 and na in norm(texts.get(b, ''))) or (len(nb) > 3 and nb in norm(texts.get(a, '')))
    ids = sorted(domain)
    pool = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]
            if domain[a] == domain[b] and tuple(sorted((a, b))) not in seen and not related(a, b)]
    need = N_PAIRS - len(pairs)
    for a, b in sorted(random.Random(SEED).sample(pool, need)):
        add(a, b, 'distinct', 'same domain family (%s), unrelated benchmarks; drawn with seed %d' % (domain[a], SEED))

    used = {p['a'] for p in pairs} | {p['b'] for p in pairs}
    return [records[r] for r in sorted(used)], pairs, len(pool)


HEADER = """\
# tests/dedup/fixtures/known-pairs.yaml -- F7's calibration set (P1-S2-T05; 11-ai-features.md S F7).
#
# GENERATED by tests/dedup/fixtures/build_known_pairs.py, whose docstring states every rule: which
# records, which pairs, and why each label is known. Do not edit by hand; change the rules and rebuild.
# A pair is positive (`same` or `variant-of`: the candidate generator should propose it for
# adjudication) or `distinct` (it should not). Records carry only identity text -- names, aliases,
# URLs, titles -- each from a file in this repository or a page fetched on the date its `source` gives.
"""


def main():
    from tools import fmt
    records, pairs, pool = build()
    assert len(pairs) == N_PAIRS, len(pairs)
    body = {'built_by': 'tests/dedup/fixtures/build_known_pairs.py', 'fetched_on': FETCHED_ON, 'seed': SEED,
            'distinct_pool': pool, 'n_pairs': len(pairs), 'records': records, 'pairs': pairs}
    text = fmt.format_text(HEADER + fmt.dumps(body), None, 'known-pairs.yaml')
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    from collections import Counter
    print(OUT, len(records), 'records', dict(Counter(p['label'] for p in pairs)))


if __name__ == '__main__':
    main()
