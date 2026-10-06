#!/usr/bin/env python3
"""Calibrate ingest/matching.py's match_confidence against the labelled pairs (P3-S3-T03; 07 S5.3).

    python scripts/calibrate_identity.py                     # score the committed set; search the weights
    python scripts/calibrate_identity.py --draw out.yaml     # draw a fresh unlabelled sample from epochdl/

07 S5.3: "Before the thresholds are used in anger, 100 pairs are hand-labelled -- 50 drawn from the score
band 0.80--0.95 and 50 uniformly -- and the weights are adjusted until precision at the auto-propose
threshold is above 0.95 on the labelled set." The set is evals/golden/identity_resolution.yaml. Each pair
keeps the view of its target it was labelled against (labels, aliases, organisations, first release), so
the score is recomputed from the file alone and a later change to the catalogue does not move it.

The report prints precision and recall at THRESHOLD for the committed WEIGHTS and NAME_SCORER, for 07's
formula as written, and the weights the search prefers: among the weightings (step 0.05, summing to 1) that
reach precision >= 0.95, those with the highest recall, and of those the nearest to 07's starting weights
(L1), ties broken toward a heavier name term. Exit 1 when the committed weights miss 0.95.

The draw (`--draw`): the candidates are the free-text `Name` strings in Epoch's per-benchmark files -- what
other leaderboards call a model, the strings 07 S5.1 says fuzzy matching exists for -- each with the row's
Organization and Release date as its context. Every candidate's top three targets (curated Systems and
stubs) are scored; 50 pairs are drawn from those scoring in BAND and 50 uniformly from the rest, with a fixed
seed. Epoch's own identification of the row (Model version -> model_group -> System) is written beside each
pair as evidence for the labeller, never as the label. `--scorer set --starting` reproduces the draw the
committed set came from. A caveat the labeller should know: in Epoch's files Organization and Release date
are Epoch's join on its identified model, so for these pairs the org and date terms are as informative as
they will ever be; a source that supplies its own will be noisier.
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest import matching as M  # noqa: E402

GOLDEN = os.path.join(ROOT, 'evals', 'golden', 'identity_resolution.yaml')
SEED = 20261005
PRECISION = 0.95


def load(path: str = GOLDEN) -> dict:
    from schema.taxonomy import read_yaml
    return read_yaml(path)


def target_of(pair: dict) -> M.Target:
    """The target as it stood when the pair was labelled."""
    t = pair['target_view']
    return M.Target(pair['target'], tuple(t['labels']), tuple(t['aliases']), tuple(t['orgs']),
                    M._date(t['first_released']))


def score(pair: dict, weights: dict, scorer: str) -> float:
    t = target_of(pair)
    ctx = M.context(pair['candidate'], pair['source_org'], M._date(pair['source_released']), t)
    return M.match_confidence(pair['candidate'], t, ctx, weights, scorer)


def metrics(pairs, weights: dict, scorer: str, threshold: float = M.THRESHOLD) -> dict:
    """precision and recall at threshold; precision is None when nothing reaches it."""
    hits = [p['label'] == 'match' for p in pairs if score(p, weights, scorer) >= threshold - 1e-9]
    positives = sum(p['label'] == 'match' for p in pairs)
    return {'above': len(hits), 'precision': (sum(hits) / len(hits)) if hits else None,
            'recall': (sum(hits) / positives) if positives else None}


def search(pairs, scorer: str, step: float = 0.05, threshold: float = M.THRESHOLD):
    """(the preferred weights or None, the best precision any weighting reached)."""
    feats = []
    for p in pairs:
        t = target_of(p)
        ctx = M.context(p['candidate'], p['source_org'], M._date(p['source_released']), t)
        feats.append((M.name_similarity(p['candidate'], t, scorer), ctx, p['label'] == 'match'))
    positives = sum(y for *_, y in feats)
    n, best_precision, ok = round(1 / step), 0.0, []
    for a in range(n + 1):
        for b in range(n + 1 - a):
            for c in range(n + 1 - a - b):
                w = {'name': a * step, 'org': b * step, 'date': c * step, 'alias': (n - a - b - c) * step}
                hits = [y for s, x, y in feats if w['name'] * s + w['org'] * x.org_agrees + w['date'] * x.date_plausible
                        + w['alias'] * x.alias_exact >= threshold - 1e-9]
                if not hits:
                    continue
                precision = sum(hits) / len(hits)
                best_precision = max(best_precision, precision)
                if precision >= PRECISION:
                    distance = sum(abs(w[k] - M.STARTING_WEIGHTS[k]) for k in w)
                    ok.append((-sum(hits) / positives, round(distance, 6), -w['name'], {k: round(v, 2) for k, v in w.items()}))
    return (min(ok, key=lambda o: o[:3])[3] if ok else None), best_precision


def report(path: str = GOLDEN) -> int:
    doc = load(path)
    pairs = doc['pairs']
    fmt = lambda m: 'precision %s, recall %s, %d pair(s) at or above %.2f' % (  # noqa: E731
        '%.3f' % m['precision'] if m['precision'] is not None else '-',
        '%.3f' % m['recall'] if m['recall'] is not None else '-', m['above'], M.THRESHOLD)
    print('%d labelled pairs (%d match), labelled by %s, confirmed by %s'
          % (len(pairs), sum(p['label'] == 'match' for p in pairs), doc['labelled_by'], doc['confirmed_by']))
    committed = metrics(pairs, M.WEIGHTS, M.NAME_SCORER)
    print('committed  %s %s: %s' % (M.NAME_SCORER, M.WEIGHTS, fmt(committed)))
    print("07 as written  set %s: %s" % (M.STARTING_WEIGHTS, fmt(metrics(pairs, M.STARTING_WEIGHTS, 'set'))))
    for scorer in ('set', 'sort'):
        w, best = search(pairs, scorer)
        print('search  %-4s best precision %.3f; preferred weights %s' % (scorer, best, w))
    return 0 if committed['precision'] is not None and committed['precision'] >= PRECISION else 1


# ---- the draw -------------------------------------------------------------------------------------------

def candidates(export: str) -> dict:
    """{(Name, Organization, Release date): {Model version, ...}} over every per-benchmark file."""
    out = {}
    for f in sorted(os.listdir(export)):
        if not f.endswith('.csv') or f in ('benchmark_metadata.csv', 'model_metadata.csv'):
            continue
        with open(os.path.join(export, f), encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh):
                name = (r.get('Name') or '').strip()                    # get-default: not every file has Name
                if name:
                    key = (name, (r.get('Organization') or '').strip(), (r.get('Release date') or '').strip())  # get-default: as above
                    out.setdefault(key, set()).add((r.get('Model version') or '').strip())                     # get-default: as above
    return out


def epoch_reference(export: str, root: str = ROOT) -> dict:
    """{Model version: System id} by Epoch's model_metadata.csv and the Systems' epoch model groups."""
    import glob
    from schema.taxonomy import read_yaml
    with open(os.path.join(export, 'model_metadata.csv'), encoding='utf-8', newline='') as fh:
        group = {r['model_version'].strip(): r['model_group'].strip() for r in csv.DictReader(fh) if r['model_version'].strip()}
    system = {}
    for p in sorted(glob.glob(os.path.join(root, 'data', 'systems', '*.yaml'))) + \
            sorted(glob.glob(os.path.join(root, 'data', 'systems', '_stubs', '*.yaml'))):
        d = read_yaml(p)
        groups = list((d.get('epoch') or {}).get('model_groups') or [])                 # get-default: optional
        groups.append((d.get('external_ids') or {}).get('epoch_model_group'))           # get-default: optional
        for g in groups:
            if g:
                system.setdefault(g, d['id'])
    return {v: system[g] for v, g in group.items() if g in system}


def draw(export: str, weights: dict, scorer: str, seed: int = SEED, root: str = ROOT) -> list[dict]:
    targets = M.load_targets(root)
    by_id = {t.id: t for t in targets}
    ref = epoch_reference(export, root)
    pairs = []
    for (name, org, released), versions in sorted(candidates(export).items()):
        scored = sorted(((t.id, round(M.match_confidence(name, t, M.context(name, org, M._date(released), t), weights, scorer), 4))
                         for t in targets), key=lambda p: (-p[1], p[0]))[:3]
        for rank, (tid, s) in enumerate(scored, 1):
            t = by_id[tid]
            pairs.append({'candidate': name, 'source_org': org, 'source_released': released,
                          'epoch_model_versions': sorted(versions), 'epoch_reference': sorted({ref[v] for v in versions if v in ref}),
                          'target': tid, 'target_view': {'labels': list(t.labels), 'aliases': list(t.aliases),
                                                         'orgs': list(t.orgs), 'first_released': t.first_released},
                          'rank_at_draw': rank, 'score_at_draw': s})
    rng = random.Random(seed)
    band = rng.sample([p for p in pairs if M.BAND[0] <= p['score_at_draw'] <= M.BAND[1]], 50)
    taken = {id(p) for p in band}
    uniform = rng.sample([p for p in pairs if id(p) not in taken], 50)
    return [dict(p, draw='band') for p in band] + [dict(p, draw='uniform') for p in uniform]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--golden', default=GOLDEN)
    ap.add_argument('--draw', metavar='OUT', help='write a fresh unlabelled sample here instead of reporting')
    ap.add_argument('--dir', default=os.path.join(ROOT, 'epochdl'), help='the Epoch export (for --draw)')
    ap.add_argument('--scorer', choices=('set', 'sort'), default=M.NAME_SCORER, help='the name term (for --draw)')
    ap.add_argument('--starting', action='store_true', help="draw with 07's starting weights, not WEIGHTS")
    ap.add_argument('--seed', type=int, default=SEED)
    a = ap.parse_args(argv)
    if not a.draw:
        return report(a.golden)
    from ingest import emit
    pairs = draw(a.dir, M.STARTING_WEIGHTS if a.starting else M.WEIGHTS, a.scorer, a.seed)
    for p in pairs:
        p.update(label=None, reason=None)
    doc = {'drawn_on': None, 'seed': a.seed, 'drawn_with': {'scorer': a.scorer, 'weights': dict(
        M.STARTING_WEIGHTS if a.starting else M.WEIGHTS)}, 'labelled_by': None, 'confirmed_by': None, 'pairs': pairs}
    emit.write(doc, os.path.relpath(os.path.abspath(a.draw), ROOT).replace(os.sep, '/'), ROOT, replace=True,
               header='an unlabelled identity-calibration sample drawn by scripts/calibrate_identity.py --draw')
    print('drew %d pairs into %s; label each `match` or `no-match` with a reason' % (len(pairs), a.draw))
    return 0


if __name__ == '__main__':
    sys.exit(main())
