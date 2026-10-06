"""The fuzzy step: match_confidence and its proposals (P3-S3-T03; 07 S5.3, 04 S10 step 5).

07 S5.1: fuzzy matching is "a crosswalk-authoring tool, not a per-row operation". It runs for sources that
publish free-text names -- arXiv tables, leaderboard HTML, vendor posts -- once, when a crosswalk entry is
first written; steady-state resolution is ingest/resolve.py's exact steps 1-4. What it produces is never an
accepted match. 07 S5.3's table: the best candidate at or above THRESHOLD is PROPOSED (an Unresolved with
reason ambiguous-match and the top three candidates); below it, the record is a human task. Nothing here
creates an entity or writes an alias.

The score is 07 S5.3's formula, four weighted terms:

    name    rapidfuzz similarity of the candidate and the entity's best label, / 100
    org     the source's organisation string names one of the entity's organisations
    date    |source release date - entity first release| <= 120 days
    alias   the raw string equals one of the entity's aliases exactly, before normalisation

Calibrated (scripts/calibrate_identity.py, against the 100 labelled pairs at
evals/golden/identity_resolution.yaml), and the calibration changed more than the weights:

  - 07 writes the name term as token_SET_ratio. A token set drops repeats and scores a subset as 100, so
    "GPT-5.1 (Medium)" against gpt-5 and "openai/gpt-5.6-sol" against gpt-5-5 ("gpt 5 5" is the set
    {gpt, 5}) score exactly what a true match does. On the labelled set no weighting of 07's four terms
    reaches precision 0.95 at 0.92 (the best is 0.72). The name term is therefore token_SORT_ratio, so a
    version digit or a "mini" costs the score. Before comparing, the CANDIDATE drops its eight-digit snapshot
    dates and budgets ("8k"), and any QUALIFIER (an effort word, "thinking", "preview", "zero shot") that
    the target's label does not itself contain. The label is never stripped: in a catalogue name such a word
    is identity ("Kimi K2 Thinking", "GPT-5.1-Codex-Max", "o1-preview"). Of two equal scores, propose()
    ranks first the target that needed fewer words dropped. NAME_SCORER = 'set' restores 07's term.
  - With that term, the weights nearest 07's starting values that reach precision >= 0.95 at 0.92 move
    0.05 from alias to name. WEIGHTS holds them; STARTING_WEIGHTS keeps 07's.

The consequence, stated so nobody reads 0.92 as "probably right": with no alias recorded, a proposal needs
the organisation and the date to agree AND a near-exact name (above 0.945). Everything else is a human task.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from datetime import date

from rapidfuzz import fuzz

from ingest.resolve import normalise, parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THRESHOLD = 0.92                    # 07 S5.3: at or above, propose (never accept)
BAND = (0.80, 0.95)                 # 07 S5.3: the band half the calibration sample is drawn from
DATE_WINDOW_DAYS = 120              # 07 S5.3: date_plausible
STARTING_WEIGHTS = {'name': 0.50, 'org': 0.20, 'date': 0.20, 'alias': 0.10}     # 07 S5.3, verbatim
WEIGHTS = {'name': 0.55, 'org': 0.20, 'date': 0.20, 'alias': 0.05}              # calibrated 2026-10-05 (P3-S3-T03)
NAME_SCORER = 'sort'                # 'set' is 07's token_set_ratio, kept for the calibration's comparison
# Words that qualify a run rather than name a model: reasoning effort and mode, prompt setting, release stage.
QUALIFIERS = frozenset(
    'high medium low minimal max xhigh x none default thinking reasoning adaptive effort preview exp '
    'experimental zero shot scratchpad instruct it chat latest'.split())
NOT_IDENTITY = re.compile(r'\d{8}|\d+k')   # a snapshot date (20250514), a thinking budget or context (8k)


@dataclass(frozen=True)
class Target:
    """What one System offers the fuzzy step: its labels, organisations and first release."""
    id: str
    labels: tuple                   # id, name, aliases -- each compared after normalisation
    aliases: tuple                  # compared exactly, for the alias term
    orgs: tuple                     # normalised organisation names
    first_released: date | None


@dataclass(frozen=True)
class MatchContext:
    org_agrees: bool
    date_plausible: bool
    alias_exact: bool


def norm(raw: str) -> str:
    """The candidate's comparable form: 04 S10's step-4 strips (provider, effort suffix, date tail), then
    step 3's normalisation. A stripped part is the resolver's to route; here it only stops being noise."""
    return normalise(parse(raw)[0])


def name_match(raw: str, target: Target, scorer: str | None = None) -> tuple[float, int]:
    """(the name term against the target's best label, 0-1; how many candidate words were dropped for it).
    'sort' is the calibrated term (the module docstring); 'set' is 07 S5.3 as written."""
    if (scorer or NAME_SCORER) == 'set':
        pairs = [(norm(raw), normalise(label)) for label in target.labels if label]
        return max((fuzz.token_set_ratio(a, b) for a, b in pairs), default=0.0) / 100.0, 0
    words = [t for t in norm(raw).split() if not NOT_IDENTITY.fullmatch(t)]
    best = (0.0, -len(words))
    for label in target.labels:
        if not label:
            continue
        named = normalise(label).split()
        kept = [t for t in words if t in named or t not in QUALIFIERS]
        best = max(best, (fuzz.token_sort_ratio(' '.join(kept), ' '.join(named)) / 100.0, len(kept) - len(words)))
    return best[0], -best[1]


def name_similarity(raw: str, target: Target, scorer: str | None = None) -> float:
    return name_match(raw, target, scorer)[0]


def org_parts(org: str | None) -> set:
    """Epoch-style organisation strings are comma-joined ("Z.ai (Zhipu AI),Tsinghua University")."""
    return {normalise(p) for p in (org or '').split(',') if normalise(p)}


def context(raw: str, org: str | None, released: date | None, target: Target) -> MatchContext:
    return MatchContext(
        org_agrees=bool(org_parts(org) & set(target.orgs)),
        date_plausible=bool(released and target.first_released
                            and abs((released - target.first_released).days) <= DATE_WINDOW_DAYS),
        alias_exact=raw in target.aliases)


def match_confidence(raw: str, target: Target, ctx: MatchContext, weights: dict | None = None,
                     scorer: str | None = None) -> float:
    """07 S5.3's formula. `weights` defaults to the calibrated WEIGHTS, `scorer` to NAME_SCORER."""
    w = weights or WEIGHTS
    return (w['name'] * name_similarity(raw, target, scorer) + w['org'] * float(ctx.org_agrees)
            + w['date'] * float(ctx.date_plausible) + w['alias'] * float(ctx.alias_exact))


def propose(raw: str, org: str | None, released: date | None, targets, k: int = 3, weights: dict | None = None):
    """The top k (target id, score), best first: step 5's suggestions. Whether the first is at or above
    THRESHOLD decides only how the Unresolved is phrased (ambiguous-match or no-match); it is never accepted."""
    scored = [(round(match_confidence(raw, t, context(raw, org, released, t), weights), 4), name_match(raw, t)[1], t.id)
              for t in targets]
    return [(i, s) for s, _, i in sorted(scored, key=lambda p: (-p[0], p[1], p[2]))[:k]]


# ---- the targets ----------------------------------------------------------------------------------------

def _date(v) -> date | None:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def load_targets(root: str = ROOT) -> list[Target]:
    """Every System, curated and stub. Stubs are not resolution targets for a curated claim (resolve.py),
    but they are the catalogue a crosswalk entry is being written against, so the fuzzy step sees them."""
    from schema.taxonomy import read_yaml
    org_names = {}
    for p in glob.glob(os.path.join(root, 'data', 'organizations', '**', '*.yaml'), recursive=True):
        d = read_yaml(p)
        org_names[d['id']] = {normalise(x) for x in [d.get('name') or ''] + list(d.get('aliases') or []) if x}  # get-default: optional
    seen, targets = set(), []
    for p in sorted(glob.glob(os.path.join(root, 'data', 'systems', '*.yaml'))) + \
            sorted(glob.glob(os.path.join(root, 'data', 'systems', '_stubs', '*.yaml'))):
        d = read_yaml(p)
        if d['id'] in seen:                         # a curated record shadows a leftover stub of the same id
            continue
        seen.add(d['id'])
        epoch = d.get('epoch') or {}                                            # get-default: curated records have none
        ids = [d.get('organization')] + list(d.get('organizations') or [])      # get-default: either spelling
        orgs = set().union(*(org_names.get(i, set()) for i in ids if i)) | org_parts(epoch.get('organization'))  # get-default: our own org index; an unknown id names no organisation
        released = [_date(d.get('first_released'))] + [_date(v.get('released')) for v in epoch.get('versions') or []]  # get-default: optional
        released = [r for r in released if r]
        aliases = tuple(str(a) for a in d.get('aliases') or [])                 # get-default: optional
        targets.append(Target(d['id'], (d['id'], d.get('name') or '') + aliases, aliases, tuple(sorted(orgs)),
                              min(released) if released else None))
    return targets
