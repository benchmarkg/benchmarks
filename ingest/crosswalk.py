"""The Epoch model_version crosswalk: data/aliases/systems.yaml (P3-S3-T05; 04 S10, 07 S5.1-5.3).

07 S5.1: "for any source with a stable internal identifier, fuzzy matching runs once, when a crosswalk entry
is first created. Steady-state resolution is an exact dictionary lookup against data/aliases/". This writes
that dictionary for the 927 distinct `Model version` strings in Epoch's per-benchmark CSVs
(reports/epoch-identity-census.md), and the part of it a person has to decide.

    python -m ingest.crosswalk            # write the aliases, the proposal batch and the report
    python -m ingest.crosswalk --check    # exit 1 if either file differs from a fresh run
    python -m ingest.crosswalk --epoch DIR

What is decided here, and what is not. Every string is run through ingest/resolve.py over every System,
curated and stub, with each stub's verbatim Epoch version strings as its external ids (P3-S3-T04 kept
them on `epoch.versions`). The registry's own answer is the check on it: Epoch puts each version in one
model_group, and the group is one System (`external_ids.epoch_model_group`). Then:

  AUTO       the resolver and the registry name the same System, and 04 S10's fixed parse accounts for the
             whole string: a provider prefix or suffix, an effort suffix and a date tail are routed or kept,
             and what is left is the System's own name. Written with decided_by `agent (P3-S3-T05)`,
             confidence high, kind `provider-endpoint` when something was routed and `exact` otherwise.
  PROPOSED   the System is known but the string says more than the parse can route -- a `_16K` that is a
             thinking budget or a context window, a `_thinking`, a `(16K thinking)`, a `-reasoning`, an
             `FP8`, an `owner/` namespace that may or may not be a serving provider, a Bedrock id -- or the
             resolver and the registry disagree. 07 S5.2: such a row is a human task, never a guess. It goes
             to data/_ingest/unresolved/epoch/<date>.yaml with the top three candidates from
             ingest/matching.py, Epoch's Name column for the string, and what to decide.

A person decides a proposal by writing its row in systems.yaml with their own handle in decided_by. A
re-run never touches such a row: only rows whose decided_by is DECIDED_BY are regenerated, and a string
with a person's row is never proposed again.

The date tail. A system alias names no SystemVersion (schema/entities.py: only a benchmark alias may), so
`gpt-4o-2024-08-06` resolves to system:gpt-4o and its date stays in the alias string itself and on the
stub's verbatim `epoch.versions` row. Nothing is discarded; whether aliases should name a SystemVersion is
a schema question, left open.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from ingest import resolve as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPOCH = os.path.join(ROOT, 'epochdl')
META, MODELS = 'benchmark_metadata.csv', 'model_metadata.csv'
SOURCE = 'src-epoch-benchmark-data'
DECIDED_BY = 'agent (P3-S3-T05)'
DECIDED_ON = '2026-10-07'
ALIASES = 'data/aliases/systems.yaml'
BATCH = 'data/_ingest/unresolved/epoch/%s.yaml' % DECIDED_ON
REPORT = 'reports/system-crosswalk.md'
SOURCE_KEY = 'crosswalk:systems'
FIELD = 'model_version'

# Words that state a run condition rather than name a model. 04 S10's parse routes none of them; where one
# is not part of the System's own name ("Kimi K2 Thinking" is a name), the string is a proposal.
CONDITION_WORDS = frozenset('thinking reasoning fp8 fp16 bf16 int8 int4 awq gptq'.split())
# The human-pass estimate is re-derived from the band (the task's step 3), with the minutes stated so the next
# person can disagree with a number rather than with a total. A proposal: read the Name column and the
# provider's documentation for the suffix, write one row. A pattern: the first proposal of a kind (a
# provider's `_NK`, an `owner/` namespace) settles the reading the rest of that kind follows. A spot check:
# one unreviewed auto row whose string and System share few words.
MINUTES = {'proposal': (3, 5), 'pattern': (15, 30), 'spot_check': (1, 2)}
BEDROCK = re.compile(r'^[a-z0-9-]+\.[a-z0-9.-]+-v\d+:\d+$')        # amazon.nova-pro-v1:0 (07 S5.2)


# ---- what Epoch says -------------------------------------------------------------------------------------

@dataclass
class Observed:
    raw: str
    group: str
    organization: str = ''
    released: date | None = None
    names: Counter = field(default_factory=Counter)      # Epoch's free-text Name column, as written
    rows: int = 0


class Missing(Exception):
    pass


def _read(path: str) -> list[dict]:
    with open(path, encoding='utf-8', errors='replace', newline='') as fh:
        return list(csv.DictReader(fh))


def _date(v) -> date | None:
    try:
        return date.fromisoformat(str(v).strip()[:10]) if v and str(v).strip() else None
    except ValueError:
        return None


def observe(epoch: str = EPOCH) -> dict[str, Observed]:
    """Every distinct result-row `Model version`, joined to its registry row (the join is 927/927)."""
    if not os.path.isfile(os.path.join(epoch, MODELS)):
        raise Missing('no %s: restore it with `python scripts/epoch_audit.py --fetch`' % os.path.join(epoch, MODELS))
    registry = {}
    for r in _read(os.path.join(epoch, MODELS)):
        v = (r['model_version'] or '').strip()
        if v:
            registry[v] = r
    out: dict[str, Observed] = {}
    for path in sorted(glob.glob(os.path.join(epoch, '*.csv'))):
        if os.path.basename(path) in (META, MODELS):
            continue
        rows = _read(path)
        if not rows:
            continue
        mv = next((c for c in rows[0] if c and c.strip().lower() == 'model version'), None)
        if mv is None:
            continue
        name = next((c for c in rows[0] if c and c.strip().lower() == 'name'), None)
        for r in rows:
            v = (r[mv] or '').strip()
            if not v:
                continue
            if v not in registry:
                raise SystemExit('%s: %r is not in %s; the census says the join is complete' % (path, v, MODELS))
            if v not in out:
                reg = registry[v]
                out[v] = Observed(v, reg['model_group'].strip(), (reg['organization'] or '').strip(),
                                  _date(reg['date']))
            out[v].rows += 1
            if name and (r[name] or '').strip():
                out[v].names[r[name].strip()] += 1
    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))


# ---- what we hold ----------------------------------------------------------------------------------------

def systems(root: str = ROOT) -> list[dict]:
    """Every System, curated first; a curated record shadows a leftover stub of the same id."""
    from schema.taxonomy import read_yaml
    seen, out = set(), []
    for p in sorted(glob.glob(os.path.join(root, 'data', 'systems', '*.yaml'))) + \
            sorted(glob.glob(os.path.join(root, 'data', 'systems', '_stubs', '*.yaml'))):
        d = read_yaml(p)
        if d['id'] not in seen:
            seen.add(d['id'])
            out.append(d)
    return out


def _groups(d: dict) -> list[str]:
    epoch = d.get('epoch') or {}                                          # get-default: curated records have none
    g = (d.get('external_ids') or {}).get('epoch_model_group')            # get-default: optional
    return [x.strip() for x in ([g] if g else []) + list(epoch.get('model_groups') or [])]  # get-default: as above


def _names(d: dict) -> list[str]:
    """Every label the System answers to: id, name, aliases and its Epoch groups."""
    return [d['id'], d.get('name') or ''] + [str(a) for a in d.get('aliases') or []] + _groups(d)  # get-default: optional


def join(all_systems: list[dict]) -> '_GroupJoin':
    """model_group -> System id: the registry's own identity, through external_ids.epoch_model_group and a
    stub's epoch.model_groups; a curated System that carries neither answers to its name (claude-3-5-sonnet)."""
    out: dict[str, str] = {}
    for d in all_systems:
        for g in _groups(d):
            out.setdefault(g, d['id'])
    by_name = {R.normalise(d.get('name') or d['id']): d['id'] for d in all_systems}   # get-default: as above
    return _GroupJoin(out, by_name)


class _GroupJoin(dict):
    def __init__(self, exact, by_name):
        super().__init__(exact)
        self.by_name = by_name

    def of(self, group: str) -> str | None:
        return self.get(group) or self.by_name.get(R.normalise(group))   # get-default: no group, no System


def index(all_systems: list[dict]) -> R.Index:
    """ingest/resolve.py's Index over every System, each stub's verbatim Epoch version strings as its
    external ids. Not Index.load(): that excludes stubs, which are exactly what the crosswalk is written
    against (an alias may name a stub; tools/validate/tiers.py)."""
    entries = []
    for d in all_systems:
        epoch = d.get('epoch') or {}                                       # get-default: curated records have none
        ext = [v for v in (d.get('external_ids') or {}).values() if v]     # get-default: optional
        ext += [v['model_version'] for v in epoch.get('versions') or [] if v.get('model_version')]  # get-default: as above
        entries.append(R.Entry(d['id'], d.get('name') or '', tuple(str(a) for a in d.get('aliases') or ()),  # get-default: optional
                               tuple(str(x) for x in ext)))
    return R.Index('system', entries)


# ---- deciding ----------------------------------------------------------------------------------------------

@dataclass
class Decision:
    raw: str
    system: str | None                     # the registry's System
    extracts: dict
    kind: str
    unrouted: list[str]                    # why a person must decide; empty for an auto row
    reason: str = 'unparseable'

    @property
    def auto(self) -> bool:
        return not self.unrouted


def _tokens(s: str) -> set[str]:
    return set(R.normalise(s).split())


def unrouted(raw: str, residue: str, names: list[str]) -> list[str]:
    """What the string says that 04 S10's fixed parse does not route, given the System's own labels."""
    out = []
    labels = {R.normalise(n) for n in names if n}
    name_tokens = set().union(*(_tokens(n) for n in names if n))
    m = R.TRAILING_TOKEN.search(residue)
    if m and R.normalise(residue) not in labels and not (_tokens(m.group(1)) <= name_tokens):
        out.append('the suffix %r, which is not a reasoning effort: a thinking budget, a context window or a '
                   'mode' % ('_' + m.group(1)))
    if '/' in residue:
        out.append('the namespace %r, which is not in 04 S10\'s provider-prefix list: the model owner\'s '
                   'namespace or a serving provider' % (residue.split('/', 1)[0] + '/'))
    if BEDROCK.match(residue):
        out.append('a Bedrock model id: 07 S5.2 routes `amazon.nova-pro-v1:0` to serving_provider '
                   'org-aws-bedrock, which 04 S10\'s parse does not do')
    words = sorted((_tokens(residue) & CONDITION_WORDS) - name_tokens)
    if words and not (m and set(words) <= _tokens(m.group(1))):
        out.append('the word%s %s, a run condition the System\'s name does not contain'
                   % ('s' if len(words) > 1 else '', ', '.join(repr(w) for w in words)))
    return out


def organizations(root: str = ROOT) -> set[str]:
    """Every Organization id, curated and stub: what a routed serving_provider may name."""
    return {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(root, 'data', 'organizations', '*.yaml'))
            + glob.glob(os.path.join(root, 'data', 'organizations', '_stubs', '*.yaml'))}


def decide(o: Observed, ix: R.Index, groups: _GroupJoin, by_id: dict[str, dict],
           orgs: set[str] | None = None) -> Decision:
    sid = groups.of(o.group)
    residue, routed, _ = R.parse(o.raw)
    if sid is None:
        return Decision(o.raw, None, routed, 'exact', ['no System carries the model_group %r' % o.group], 'no-match')
    # The registry join is step 1 on the identifier the row itself carries (its model_group against
    # external_ids.epoch_model_group). The resolver over the bare string is the cross-check: naming nothing is
    # not a disagreement (a promoted System keeps its group but not the stub's version list), naming a
    # different System is.
    r = ix.resolve(o.raw)
    got = r.entity.split(':', 1)[1] if r.entity else None
    if got is not None and got != sid:
        return Decision(o.raw, sid, routed, 'exact',
                        ['the resolver names system:%s but the registry puts it in %r, which is system:%s'
                         % (got, o.group, sid)], 'ambiguous-match')
    why = unrouted(o.raw, residue, _names(by_id[sid]) + [o.group])
    sp = routed.get('serving_provider')                                   # get-default: most strings route none
    if sp and orgs is not None and sp not in orgs:
        # 04 S10 routes the prefix to this id, but no Organization holds it, and an alias may not dangle. A
        # serving provider is not one of Epoch's organisations, so there is no stub to point at: adding the
        # Organization is a person's decision, and until then the string is a proposal.
        why.append('the serving provider %s, which 04 S10 routes the prefix to but no Organization record holds'
                   % sp)
    return Decision(o.raw, sid, routed, 'provider-endpoint' if routed else 'exact', why)


def alias_row(d: Decision) -> dict:
    return {'alias': d.raw, 'resolves_to': 'system:' + d.system, 'extracts': dict(d.extracts), 'kind': d.kind,
            'confidence': 'high', 'decided_by': DECIDED_BY, 'decided_on': date.fromisoformat(DECIDED_ON),
            'source': SOURCE}


def proposal(d: Decision, o: Observed, targets) -> dict:
    from ingest import matching
    residue = R.parse(o.raw)[0]
    suggestions = [[i, float(s)] for i, s in matching.propose(residue, o.organization or None, o.released, targets)]
    names = ', '.join('%r (%d row%s)' % (n, c, '' if c == 1 else 's') for n, c in sorted(o.names.items()))
    task = ('Epoch\'s registry puts %r in model_group %r%s. It says more than 04 S10\'s parse can route: %s. '
            'Epoch\'s Name column for it: %s. Decide what each part routes to (eval_conditions.'
            'thinking_token_budget, context_window_used, reasoning_effort, serving_provider, or nothing), then '
            'write its row in %s with your handle in decided_by.'
            % (o.raw, o.group, ', System %s' % d.system if d.system else '', '; '.join(d.unrouted),
               names or 'empty', ALIASES))
    key = '%s|%s|%s' % (SOURCE_KEY, FIELD, o.raw)
    return {'source_key': SOURCE_KEY, 'field': FIELD, 'observed': o.raw, 'reason': d.reason,
            'suggestions': suggestions, 'human_task': task,
            'fingerprint': hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}


# ---- the files ----------------------------------------------------------------------------------------------

ALIAS_HEADER = (
    '# data/aliases/systems.yaml -- the System alias table (04 S10; P3-S3-T05): every distinct Epoch\n'
    '# `Model version` string and the System it names, read by ingest/resolve.py at step 2. Rows decided by\n'
    '# `%s` are GENERATED by `python -m ingest.crosswalk` from Epoch\'s registry join and\n'
    '# 04 S10\'s parse, and are unreviewed. A person who checks one, or decides a proposal from\n'
    '# %s, writes the row with their own handle, and the\n'
    '# generator never touches that row again.\n'
    % (DECIDED_BY, BATCH))
BATCH_HEADER = (
    '# %s -- GENERATED by `python -m ingest.crosswalk`\n'
    '# (P3-S3-T05). The Epoch model_version strings whose System is known but which say more than\n'
    '# 04 S10\'s parse can route: 07 S5.2\'s human tasks. Each is decided by a row in\n'
    '# %s, never by a guess.\n' % (BATCH, ALIASES))


def human_rows(root: str = ROOT) -> list[dict]:
    """The rows a person wrote: everything in systems.yaml not decided by this generator."""
    from schema.taxonomy import read_yaml
    path = os.path.join(root, *ALIASES.split('/'))
    if not os.path.exists(path):
        return []
    return [r for r in read_yaml(path) or [] if r['decided_by'] != DECIDED_BY]


def build(epoch: str = EPOCH, root: str = ROOT):
    """(decisions, {relpath: text}) for the alias table and the proposal batch."""
    from ingest import matching
    from schema.entities import AliasFile, UnresolvedFile
    from tools import fmt
    obs = observe(epoch)
    all_systems = systems(root)
    by_id = {d['id']: d for d in all_systems}
    ix, groups = index(all_systems), join(all_systems)
    decided = {r['alias'] for r in human_rows(root)}
    orgs = organizations(root)
    decisions = [decide(o, ix, groups, by_id, orgs) for o in obs.values()]
    rows = [alias_row(d) for d in decisions if d.auto and d.raw not in decided] + human_rows(root)
    rows.sort(key=lambda r: (r['alias'].lower(), r['alias']))
    AliasFile.model_validate(rows)
    targets = matching.load_targets(root)
    band = [proposal(d, obs[d.raw], targets) for d in decisions if not d.auto and d.raw not in decided]
    UnresolvedFile.model_validate(band)
    files = {ALIASES: fmt.format_text(ALIAS_HEADER + fmt.dumps(rows), AliasFile),
             BATCH: fmt.format_text(BATCH_HEADER + fmt.dumps(band), UnresolvedFile),
             REPORT: render_report([d for d in decisions if d.raw not in decided], by_id)}
    return decisions, files


def unresolved(epoch: str = EPOCH, root: str = ROOT) -> list[str]:
    """The Epoch model_version strings with no row in systems.yaml. 07 S5.1's steady state is an exact
    lookup, so a string is resolved when, and only when, the alias table holds it verbatim."""
    from schema.taxonomy import read_yaml
    path = os.path.join(root, *ALIASES.split('/'))
    held = {r['alias'] for r in (read_yaml(path) or [])} if os.path.exists(path) else set()
    return [v for v in observe(epoch) if v not in held]


REASONS = (('the suffix', 'suffix'), ('the namespace', 'namespace'), ('a Bedrock', 'bedrock'),
           ('the word', 'condition word'), ('the serving provider', 'no Organization record'),
           ('the resolver', 'resolver disagrees'), ('no System', 'no System'))


def reason_key(text: str) -> str:
    return next(k for prefix, k in REASONS if text.startswith(prefix))


def pattern(d: Decision) -> str:
    """The reading a proposal waits on: its first reason, and for a suffix or a namespace, which one."""
    key = reason_key(d.unrouted[0])
    residue = R.parse(d.raw)[0]
    if key == 'suffix':
        tok = R.TRAILING_TOKEN.search(residue).group(1)
        return 'suffix `_%s`' % ('NK' if re.fullmatch(r'\d+[Kk]', tok) else tok)
    if key == 'namespace':
        return 'namespace `%s/`' % residue.split('/', 1)[0].lower()
    return key


def look_again(decisions: list[Decision], by_id: dict[str, dict], cut: float = 0.34) -> list[tuple[str, str]]:
    """Auto rows whose string and System share under a third of their words: the registry's identity claims
    a reviewer should read first (API aliases whose target moves, renamed lines)."""
    out = []
    for d in decisions:
        if d.auto:
            rt = _tokens(R.parse(d.raw)[0])
            nt = set().union(*(_tokens(x) for x in _names(by_id[d.system]) if x))
            if len(rt & nt) / max(1, len(rt | nt)) < cut:
                out.append((d.raw, d.system))
    return out


def summary(decisions: list[Decision]) -> dict:
    auto = [d for d in decisions if d.auto]
    band = [d for d in decisions if not d.auto]
    return {'strings': len(decisions), 'auto': len(auto),
            'auto_exact': sum(1 for d in auto if d.kind == 'exact'),
            'auto_routed': sum(1 for d in auto if d.extracts),
            'proposed': len(band),
            'by_reason': Counter(reason_key(d.unrouted[0]) for d in band),
            'by_pattern': Counter(pattern(d) for d in band),
            'band_systems': len({d.system for d in band})}


def estimate(s: dict, spot_checks: int) -> tuple[float, float]:
    """(low, high) hours for the human pass, from the band's size and MINUTES."""
    def total(i):
        return (s['proposed'] * MINUTES['proposal'][i] + len(s['by_pattern']) * MINUTES['pattern'][i]
                + spot_checks * MINUTES['spot_check'][i]) / 60
    return total(0), total(1)


def _rows(counter: Counter) -> list[str]:
    return ['| %s | %d |' % (k, n) for k, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]


def render_report(decisions: list[Decision], by_id: dict[str, dict]) -> str:
    s = summary(decisions)
    again = look_again(decisions, by_id)
    lo, hi = estimate(s, len(again))
    m = MINUTES
    lines = [
        '# The Epoch System crosswalk', '',
        '<!-- Generated by `python -m ingest.crosswalk`; do not edit by hand. -->', '',
        'P3-S3-T05. Every distinct Epoch `Model version` string (%d; reports/epoch-identity-census.md), '
        'resolved against the Systems in `data/systems/`, curated and stub. The aliases are in `%s`. The '
        'proposals are in `%s`: the band a person decides. 04 S10 and 07 S5.1-5.3 set the rules.'
        % (s['strings'], ALIASES, BATCH),
        '', '## The counts', '', '| | Strings |', '| --- | ---: |',
        '| Written as aliases, unreviewed | %d |' % s['auto'],
        '| of which `exact`: nothing stripped | %d |' % s['auto_exact'],
        '| of which `provider-endpoint`: a provider or an effort routed | %d |' % s['auto_routed'],
        '| **Proposed for a person (the band)** | **%d** |' % s['proposed'],
        '| Total | %d |' % s['strings'], '',
        'The band covers %d Systems. Why each string is in it (its first reason):' % s['band_systems'], '',
        '| Reason | Strings |', '| --- | ---: |'] + _rows(s['by_reason']) + [
        '', '## The estimate, re-derived from the band', '',
        'The task carried 8-24 h, "proportional to a number nobody has measured". The number is **%d '
        'proposals** in %d patterns, plus %d auto rows worth a second look (below). The human pass costs:'
        % (s['proposed'], len(s['by_pattern']), len(again)), '',
        '- %d-%d minutes for each proposal;' % m['proposal'],
        '- %d-%d minutes to settle each pattern\'s reading the first time;' % m['pattern'],
        '- %d-%d minutes for each spot check.' % m['spot_check'], '',
        'In total, **%.1f-%.1f hours**.' % (lo, hi), '',
        'The patterns, each a reading to settle once:', '',
        '| Pattern | Strings |', '| --- | ---: |'] + _rows(s['by_pattern']) + [
        '', '## Auto rows to read first', '',
        'These rows come from Epoch\'s registry join, so they are Epoch\'s identity claims, unreviewed. Each '
        'shares under a third of its words with the System it names. Renamed lines, and API aliases whose '
        'target moves over time (`deepseek-chat`), are where a registry is likeliest to be wrong.', '',
        '| String | System |', '| --- | --- |'] + ['| `%s` | `%s` |' % (a, b) for a, b in again] + [
        '', '## What a person does', '',
        '1. For each proposal in `%s`, read its `human_task`, which quotes Epoch\'s Name column.' % BATCH,
        '2. Write the string\'s row in `%s` with your own handle in `decided_by`. Route what the string '
        'says to `extracts`: a thinking budget goes to `eval_conditions.thinking_token_budget`, a context '
        'window to `eval_conditions.context_window_used`. Where the effort varies by row and not by string, '
        'route nothing for it; the claim carries it.' % ALIASES,
        '3. Re-run `python -m ingest.crosswalk`, and the decided string leaves the batch. '
        '`bench resolve --candidates --systems` exits 0 once none is left.', '']
    return '\n'.join(lines)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    epoch = argv[argv.index('--epoch') + 1] if '--epoch' in argv else EPOCH
    try:
        decisions, files = build(epoch)
    except Missing as e:
        print(e, file=sys.stderr)
        return 2
    stale = [rel for rel, text in files.items() if not os.path.exists(os.path.join(ROOT, rel))
             or open(os.path.join(ROOT, rel), encoding='utf-8').read() != text]
    if '--check' in argv:
        for rel in stale:
            print('stale   %s' % rel, file=sys.stderr)
        return 1 if stale else 0
    for rel in stale:
        path = os.path.join(ROOT, *rel.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(files[rel])
    s = summary(decisions)
    print('crosswalk: %d strings; %d written as aliases (%d routing a provider or effort), %d proposed for a '
          'person in %d patterns; %d file(s) written' % (s['strings'], s['auto'], s['auto_routed'], s['proposed'],
                                                        len(s['by_pattern']), len(stale)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
