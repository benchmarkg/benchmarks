"""The golden set's metrics, each a published rate with its Wilson interval (P6-S3-T09; 11-ai-features.md S7 "The
golden set", "Statistical power", "Grading and cadence").

Grading is deterministic: set metrics and membership checks, never a model (11 S7: "Only deterministic metrics gate").
Every function here is pure -- gold labels and a system's outputs in, numbers out -- so tests/evals/test_eval_harness.py
holds each on a synthetic labelled fixture while the real gold labels stay empty until a person sets them.

nl_search (gold: entry id -> grade, 3 must, 2 good, 1 ok, 0 wrong), over one configuration's ranked entry ids per item:

  recall@20         grade-3 entries in the top 20, over grade-3 entries, counted over every (item, grade-3 entry) pair
                    in the population: the micro average, so that s and n are counts and the interval is a Wilson
                    interval proper. Pairs within one query are not independent, which the interval ignores. >= 0.90.
  ndcg@10           per item, DCG@10 over the ideal DCG@10 of the item's own grades, gains linear in the grade and the
                    discount log2(rank + 1) (trec_eval's ndcg_cut); averaged over items. An entry the gold does not
                    grade counts 0, TREC's convention for an unjudged document. >= 0.80, secondary.
  must_include_violation   items with a grade-3 entry outside the top 20, over items. <= 0.05.

facet_translation (gold: hard, soft, unmapped_terms, intent; the system's output: a FacetQuery, tools/build/
facetquery_schema.py), per item:

  macro_f1          per facet slot, F1 of the facet-qualified values the output names against the gold's, counted over
                    every item (hard and soft together: where a value sits is what over-constraint measures); year_min
                    is the value `year_min:<year>`. The mean over the slots either side names at all. >= 0.85.
  over_constraint   items whose hard filter rejects something the gold's hard filter admits ("a hard filter excludes
                    a gold entry", 11 S7): per slot, the output's hard values do not cover the gold's (an empty gold
                    slot admits everything); year_min later than the gold's; and the two domain slots read together,
                    a family admitting every subdomain under it (11 S4, "a family filter expands to the union of its
                    subdomains"). Judged on the queries, not on a corpus, so it does not move with curation. <= 0.05.
  enum_hallucination   items whose output names a value outside its slot's enum in schema/generated/facetquery.schema
                    .json, or a slot that is not one of the ten. A hard zero (== 0, the canary).

abstention (gold: behaviour, one of the five check_golden_composition.BEHAVIOURS), per item:

  correct_abstention   items whose response showed the gold behaviour, over items. >= 0.95.

suite_build's four (must-include coverage, forbidden inclusion, citation validity, the "Not covered" section) score the
F2 synthesis, which no task has built: BARS names them so that a results file says which bars exist and are unmeasured,
and nothing here computes them.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable

from tools.evals.stats import ASSERT, AT_LEAST, AT_MOST, Bar, rate

RECALL_K = 20                    # 11 S7: "Recall@20 on grade-3"
NDCG_K = 10                      # 11 S7: "nDCG@10 (secondary)"
MUST = 3                         # the grade that is "must"

# 11 S7's table, split -> metric -> its bar. A metric this module computes has a function below; the others wait
# on a model run that does not exist yet.
BARS = {
    'nl_search': {'recall@20': Bar(AT_LEAST, 0.90), 'ndcg@10': Bar(AT_LEAST, 0.80),
                  'must_include_violation': Bar(AT_MOST, 0.05)},
    'facet_translation': {'macro_f1': Bar(AT_LEAST, 0.85), 'over_constraint': Bar(AT_MOST, 0.05),
                          'enum_hallucination': Bar(ASSERT, 0.0)},
    'suite_build': {'must_include_coverage': Bar(AT_LEAST, 0.85), 'forbidden_inclusion': Bar(ASSERT, 0.0),
                    'citation_validity': Bar(ASSERT, 1.0), 'not_covered_present': Bar(ASSERT, 1.0)},
    'abstention': {'correct_abstention': Bar(AT_LEAST, 0.95)},
}


# ---- nl_search ------------------------------------------------------------------------------------------------

def must(gold: dict) -> set:
    return {e for e, g in gold.items() if g == MUST}


def recall_hits(ranked: list[str], gold: dict, k: int = RECALL_K) -> tuple[int, int]:
    """(grade-3 entries in the top k, grade-3 entries) for one item."""
    wanted = must(gold)
    return len(wanted & set(ranked[:k])), len(wanted)


def ndcg(ranked: list[str], gold: dict, k: int = NDCG_K) -> float:
    """nDCG@k of one ranked list against one item's grades: linear gains, log2(rank + 1) discount, unjudged = 0."""
    dcg = sum(gold[e] / math.log2(i + 2) for i, e in enumerate(ranked[:k]) if e in gold)
    ideal = sorted(gold.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def nl_search(items: list[tuple[list[str], dict]]) -> dict:
    """The three nl_search metrics over (ranked entry ids, gold grades) pairs, one per labelled item."""
    if not items:
        return {}
    hits = pairs = violations = 0
    total = 0.0
    for ranked, gold in items:
        h, n = recall_hits(ranked, gold)
        hits, pairs = hits + h, pairs + n
        violations += int(h < n)
        total += ndcg(ranked, gold)
    bars = BARS['nl_search']
    out = {'ndcg@10': rate(total, len(items), bars['ndcg@10'], per_item=True),
           'must_include_violation': rate(violations, len(items), bars['must_include_violation'])}
    if pairs:                                   # the composition check guarantees a grade 3 on every labelled item
        out = {'recall@20': rate(hits, pairs, bars['recall@20']), **out}
    return out


def judged_at(ranked: list[str], gold: dict, k: int = RECALL_K) -> tuple[int, int]:
    """(entries in the top k the gold grades, entries in the top k): how much of a run its graders saw."""
    top = ranked[:k]
    return sum(1 for e in top if e in gold), len(top)


# ---- facet_translation ----------------------------------------------------------------------------------------

def values(facets: dict | None) -> dict[str, set]:
    """slot -> the values one side (hard or soft) names; year_min as {'year_min:<year>'}; a slot left out, an empty
    list or a null year_min names nothing."""
    out: dict[str, set] = {}
    for slot, v in (facets or {}).items():
        if slot == 'year_min':
            if v is not None:
                out[slot] = {'year_min:%d' % v}
        elif v:
            out[slot] = set(v)
    return out


def named(fq: dict) -> dict[str, set]:
    """slot -> every value a FacetQuery (or a gold label) names, hard and soft together."""
    out: dict[str, set] = {}
    for side in ('hard', 'soft'):
        for slot, v in values(fq.get(side)).items():
            out.setdefault(slot, set()).update(v)
    return out


def macro_f1(pairs: list[tuple[dict, dict]]) -> float | None:
    """Macro-F1 over the slots of (gold, output) pairs (module docstring); None when no slot is named anywhere."""
    counts: dict[str, list[int]] = {}
    for gold, out in pairs:
        g, o = named(gold), named(out)
        for slot in set(g) | set(o):
            gs, os_ = g.get(slot, set()), o.get(slot, set())
            c = counts.setdefault(slot, [0, 0, 0])
            c[0] += len(gs & os_)
            c[1] += len(os_ - gs)
            c[2] += len(gs - os_)
    if not counts:
        return None
    return sum(2 * tp / (2 * tp + fp + fn) for tp, fp, fn in counts.values()) / len(counts)


def _domains(hard: dict, subdomains_of: Callable[[str], set]) -> set | None:
    """The subdomains the two domain slots of one hard filter admit; None for every subdomain."""
    fam, sub = hard.get('domain_family') or [], hard.get('domain_subdomain') or []
    admitted = None
    if fam:
        admitted = set().union(*(subdomains_of(f) for f in fam))
    if sub:
        admitted = set(sub) if admitted is None else admitted & set(sub)
    return admitted


def over_constrained(gold_hard: dict | None, out_hard: dict | None, subdomains_of: Callable[[str], set]) -> bool:
    """Whether the output's hard filter rejects anything the gold's admits (module docstring)."""
    g, o = gold_hard or {}, out_hard or {}
    for slot in set(g) | set(o):
        if slot in ('domain_family', 'domain_subdomain', 'year_min'):
            continue
        gs, os_ = set(g.get(slot) or []), set(o.get(slot) or [])
        if os_ and (not gs or not gs <= os_):
            return True
    gy, oy = g.get('year_min'), o.get('year_min')
    if oy is not None and (gy is None or oy > gy):
        return True
    gd, od = _domains(g, subdomains_of), _domains(o, subdomains_of)
    return od is not None and (gd is None or not gd <= od)


def off_enum(out: dict, allowed: dict[str, set]) -> list[str]:
    """Every value an output names outside its slot's enum (slot:value), and every slot that is not one of ten."""
    bad = []
    for side in ('hard', 'soft'):
        for slot, v in (out.get(side) or {}).items():
            if slot == 'year_min':
                continue
            if slot not in allowed:
                bad.append('%s.%s' % (side, slot))
                continue
            bad += ['%s.%s=%s' % (side, slot, x) for x in v or [] if x not in allowed[slot]]
    return bad


def facet_translation(pairs: list[tuple[dict, dict]], allowed: dict[str, set]) -> dict:
    """The three facet_translation metrics over (gold, output FacetQuery) pairs, one per labelled item."""
    if not pairs:
        return {}

    def subdomains_of(family: str) -> set:              # domain:<family> -> every domain:<family>/<subdomain>
        return {s for s in allowed['domain_subdomain'] if s.startswith(family + '/')}
    bars, n = BARS['facet_translation'], len(pairs)
    out = {}
    f1 = macro_f1(pairs)
    if f1 is not None:
        out['macro_f1'] = rate(f1 * n, n, bars['macro_f1'], per_item=True)
    over = sum(over_constrained(g.get('hard'), o.get('hard'), subdomains_of) for g, o in pairs)
    out['over_constraint'] = rate(over, n, bars['over_constraint'])
    hallucinated = sum(1 for _, o in pairs if off_enum(o, allowed))
    out['enum_hallucination'] = rate(hallucinated, n, bars['enum_hallucination'])
    return out


# ---- abstention -----------------------------------------------------------------------------------------------

def abstention(pairs: Iterable[tuple[dict, str]]) -> dict:
    """correct_abstention over (gold, the behaviour the response showed) pairs."""
    pairs = list(pairs)
    if not pairs:
        return {}
    right = sum(1 for gold, shown in pairs if gold['behaviour'] == shown)
    return {'correct_abstention': rate(right, len(pairs), BARS['abstention']['correct_abstention'])}
