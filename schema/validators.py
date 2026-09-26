"""Tier-3 semantic validators (P0-S4-T08; 02-taxonomy.md S11, 04-data-model.md S12, 05 S9 job 4).

Tier 1 (types, enums, required fields) is the models themselves. Tier 3 is the cross-field and
cross-record policy those models cannot see from inside one record: a rule that needs two fields that
live in different blocks, a benchmark and its condition record, a claim and its system, or a record
and the path it sits at.

    python -m schema.validators [--level stub|full]      # validate the repository; exit 1 on a blocking finding

Every rule is registered in RULES with its id, the plan section it implements and its severity, and
returns Findings. "Blocking" means the PR does not merge (02 S11); a warning is reported and does not
block. `auto_fix` names the value the validation bot proposes in a review comment -- it never writes it,
because 02 S11 rule 3 forbids a machine writing a facet value to data/.

The rules, in the order 02 S11 and 04 S12 give them:

  lifecycle-triple            02 S11 legality matrix: lifecycle x activity x maintenance_status, checked
                              as a triple. Blocking: dormant, deprecated or retracted while
                              accepting-submissions; a hand-set saturated. Warning with a required
                              curation.notes: accepting-submissions on an abandoned code base.
  contaminated-lifecycle      lifecycle contaminated -> risk high|confirmed AND evidence
  contamination-evidence      risk high|confirmed -> an evidence entry pointing at a Source
  private-server-blocker      access private-test-server -> private-test-set blocker (auto-fix)
  private-server-submission   access private-test-server -> a server-side submission_process (warning)
  unreleasable-blocker        data_provenance unreleasable-confidential -> unreleasable-data blocker
  wet-lab-execution           compute_tier wet-lab -> wet-lab blocker AND requires-physical-experiment
  no-harness-blocker          harness_availability none -> no-reference-implementation blocker
  fully-automatable           reproducibility_tier fully-automatable -> no blocker but licence-restriction
  reference-grader            model-graded-judge | rubric-graded -> reference_conditions names a grader
                              (blocking at `full`, a warning below it)
  headroom-guard-4            ordinal-grading | pairwise-preference-elo | tournament-play |
                              episodic-return -> derived headroom is null (02 S8 guard 4)
  rating-pool-required        pairwise-preference-elo | tournament-play -> rating_pool_required (auto-fix)
  independence-evidence       an independence flag other than no-known-conflict -> an evidence Source
  contested-pair              maintenance_status_contested -> contested_source AND contested_statement_date
  range-basis                 any range estimate -> basis
  subset-drops-terms          02 S11 rule 4: a subset override with fewer terms than its parent (warning)
  judge-model                 04 S12: a claim on a model-graded-judge benchmark has a judge_model
  value-in-range              04 S12: a claim's value lies within its metric's range
  claim-after-release         04 S12: a claim is not dated before its system's release
  one-primary-baseline        04 S12: exactly one is_primary per (benchmark_version, metric), across
                              data/baselines/ and every benchmark's inline baselines together
  licence-placement           04 S9/S12: a record's licence class decides where it may live
  ingestion-batch             04 S12: an ingested record's ingestion.batch resolves
  non-doi-archive             04 S12: every non-DOI Source has an archive_url
  retired-id-ledger           05 S9 job 9: no retired id is live again, as a term or a record id
  stub-placeholder            05 S3: a `bench new` scaffold's placeholders -- a TODO string, an
                              example.invalid URL, the bench-new-stub tag -- block until replaced
                              (P0-S5-T03). A scaffold passes tier 1 by construction, so tier 3 is
                              where "never estimate" is enforced
  quote-substring             14-roadmap Phase 0, 04 S9: every quote is a substring of its source's
                              committed quote_extract (P0-S5-T06; tools/validate/quotes.py). An
                              ai-drafted-unverified record warns and offers the null as its fix,
                              so the field fails and the record does not; a reviewed record blocks

Two of them read DERIVED values the build computes (maintenance_status, headroom). Where the Corpus
carries no derived value for a benchmark, the part of the rule that needs it is not evaluated, and
says nothing: a missing input is not a pass and not a failure.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from dataclasses import dataclass, field
from typing import Callable

from schema.baseline import Baseline
from schema.benchmark import Benchmark, load_benchmark
from schema.claim import ResultClaim
from schema.conditions import EvalConditions
from schema.entities import IngestBatch
from schema.metric import Metric
from schema.system import System
from schema.taxonomy import RetiredIdFile, load_taxonomy, read_yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HIGH_RISK = ('high', 'confirmed')
SERVER_SIDE_SUBMISSION = ('held-out-server', 'containerized-algorithm-submission', 'assessment-committee')
GRADED = ('model-graded-judge', 'rubric-graded')
NON_CARDINAL = ('ordinal-grading', 'pairwise-preference-elo', 'tournament-play', 'episodic-return')
POOLED = ('pairwise-preference-elo', 'tournament-play')
MULTI_VALUED_FACETS = ('capability',)          # the multi-valued facets a Subset can override today


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str                              # blocking | warning
    entity: str
    message: str
    auto_fix: str | None = None

    def __str__(self):
        fix = ' [auto-fix offered: %s]' % self.auto_fix if self.auto_fix else ''
        return '%s %s %s: %s%s' % (self.severity.upper(), self.rule, self.entity, self.message, fix)


@dataclass
class Corpus:
    """What the rules read. Records are validated models; `paths` maps an entity id to the repo-relative
    path it was loaded from, which licence-placement needs. `derived` holds build-computed values per
    benchmark id: {'maintenance_status': ..., 'headroom': ...}."""
    benchmarks: dict[str, Benchmark] = field(default_factory=dict)
    conditions: dict[str, EvalConditions] = field(default_factory=dict)
    claims: dict[str, ResultClaim] = field(default_factory=dict)
    systems: dict[str, System] = field(default_factory=dict)
    metrics: dict[str, Metric] = field(default_factory=dict)
    baselines: list[Baseline] = field(default_factory=list)          # data/baselines/ only; inline ones are read off benchmarks
    batches: dict[str, IngestBatch] = field(default_factory=dict)
    sources: dict[str, dict] = field(default_factory=dict)           # raw: the draft sources are not all valid yet
    paths: dict[str, str] = field(default_factory=dict)
    derived: dict[str, dict] = field(default_factory=dict)
    retired: set[str] = field(default_factory=set)
    live_terms: set[str] = field(default_factory=set)


RULES: dict[str, 'Rule'] = {}


@dataclass(frozen=True)
class Rule:
    id: str
    cites: str
    check: Callable[[Corpus, str], list[Finding]]


def rule(rule_id: str, cites: str):
    def register(fn):
        RULES[rule_id] = Rule(rule_id, cites, fn)
        return fn
    return register


# ---- reading the entries' shapes ---------------------------------------------------------------

def _blockers(b: Benchmark) -> list[str]:
    return list(b.execution.reproducibility_blockers)


def _submission(b: Benchmark) -> list[str]:
    sp = b.governance.submission_process
    return [] if sp is None else ([sp] if isinstance(sp, str) else list(sp))


def _evidence_sources(items) -> list[str]:
    return [i if isinstance(i, str) else i.source for i in (items or [])]


def _benchmark_rule(rule_id, cites):
    """A rule over one benchmark at a time."""
    def register(fn):
        def check(corpus: Corpus, level: str):
            out: list[Finding] = []
            for bid, b in sorted(corpus.benchmarks.items()):
                for sev, msg, *fix in fn(b, corpus, level) or []:
                    out.append(Finding(rule_id, sev, bid, msg, fix[0] if fix else None))
            return out
        RULES[rule_id] = Rule(rule_id, cites, check)
        return fn
    return register


# ---- 02 S11: the legality matrix ---------------------------------------------------------------

@_benchmark_rule('lifecycle-triple', '02 S11 legality matrix')
def _lifecycle_triple(b, corpus, level):
    lifecycle, activity = b.lifecycle, b.activity
    maintenance = corpus.derived.get(b.id, {}).get('maintenance_status')  # get-default: a derived value not yet built is not evaluated
    if lifecycle == 'saturated':
        yield 'blocking', 'lifecycle saturated is derived only (02 S8) and may not be hand-set'
    if activity == 'accepting-submissions':
        if lifecycle == 'dormant':
            yield 'blocking', 'a dormant instrument cannot be accepting submissions; one of the two is wrong'
        if lifecycle in ('deprecated', 'retracted'):
            yield 'blocking', 'a %s instrument cannot be accepting submissions' % lifecycle
        if maintenance == 'abandoned':
            if b.curation.notes:
                yield 'warning', 'accepting submissions on an abandoned code base (explained in curation.notes)'
            else:
                yield 'blocking', ('accepting submissions on an abandoned code base: a curator must explain it in '
                                   'curation.notes, because the other reading is that one field is wrong')


# ---- 02 S11: single-direction implications ------------------------------------------------------

@_benchmark_rule('contaminated-lifecycle', '02 S11 implications')
def _contaminated_lifecycle(b, corpus, level):
    if b.lifecycle == 'contaminated':
        if b.data.contamination_risk not in HIGH_RISK:
            yield 'blocking', 'lifecycle contaminated needs contamination_risk high or confirmed'
        if not b.data.contamination_evidence:
            yield 'blocking', 'lifecycle contaminated needs contamination_evidence[]'


@_benchmark_rule('contamination-evidence', '02 S11 implications; 04 S12 tier 3')
def _contamination_evidence(b, corpus, level):
    if b.data.contamination_risk in HIGH_RISK and not _evidence_sources(b.data.contamination_evidence):
        yield 'blocking', ('contamination_risk %s needs at least one contamination_evidence entry pointing at a '
                           'Source' % b.data.contamination_risk)


@_benchmark_rule('private-server-blocker', '02 S11 implications')
def _private_server_blocker(b, corpus, level):
    if b.data.access == 'private-test-server' and 'private-test-set' not in _blockers(b):
        yield 'blocking', 'access private-test-server needs private-test-set in reproducibility_blockers', \
            'execution.reproducibility_blockers += private-test-set'


@_benchmark_rule('private-server-submission', '02 S11 implications')
def _private_server_submission(b, corpus, level):
    if b.data.access == 'private-test-server' and not set(_submission(b)) & set(SERVER_SIDE_SUBMISSION):
        yield 'warning', ('access private-test-server with submission_process %s: possible, and worth a note'
                          % (_submission(b) or 'unset'))


@_benchmark_rule('unreleasable-blocker', '02 S11 implications')
def _unreleasable_blocker(b, corpus, level):
    if 'unreleasable-confidential' in (b.data.data_provenance or []) and 'unreleasable-data' not in _blockers(b):
        yield 'blocking', 'unreleasable-confidential data needs unreleasable-data in reproducibility_blockers', \
            'execution.reproducibility_blockers += unreleasable-data'


@_benchmark_rule('wet-lab-execution', '02 S11 implications')
def _wet_lab(b, corpus, level):
    if b.execution.compute_tier == 'wet-lab':
        if 'wet-lab' not in _blockers(b):
            yield 'blocking', 'compute_tier wet-lab needs wet-lab in reproducibility_blockers', \
                'execution.reproducibility_blockers += wet-lab'
        if b.execution.reproducibility_tier != 'requires-physical-experiment':
            yield 'blocking', 'compute_tier wet-lab needs reproducibility_tier requires-physical-experiment', \
                'execution.reproducibility_tier = requires-physical-experiment'


@_benchmark_rule('no-harness-blocker', '02 S11 implications')
def _no_harness(b, corpus, level):
    if b.execution.harness_availability == 'none' and 'no-reference-implementation' not in _blockers(b):
        yield 'blocking', 'harness_availability none needs no-reference-implementation in reproducibility_blockers', \
            'execution.reproducibility_blockers += no-reference-implementation'


@_benchmark_rule('fully-automatable', '02 S11 implications')
def _fully_automatable(b, corpus, level):
    stray = [x for x in _blockers(b) if x != 'licence-restriction']
    if b.execution.reproducibility_tier == 'fully-automatable' and stray:
        yield 'blocking', 'reproducibility_tier fully-automatable with blockers %s' % ', '.join(stray)


@_benchmark_rule('reference-grader', '02 S11 implications')
def _reference_grader(b, corpus, level):
    if not set(b.evaluation_method) & set(GRADED):
        return
    c = corpus.conditions.get(b.reference_conditions) if b.reference_conditions else None
    named = c is not None and c.judge_model is not None and (c.judge_model == 'human' or c.judge_model_version)
    if not named:
        yield ('blocking' if level == 'full' else 'warning'), \
            'a model- or rubric-graded benchmark\'s reference_conditions names its grader (model + version, or human)'


@_benchmark_rule('headroom-guard-4', '02 S8 guard 4; 02 S11 implications')
def _guard_4(b, corpus, level):
    derived = corpus.derived.get(b.id, {})  # get-default: a derived value not yet built is not evaluated
    hit = sorted(set(b.evaluation_method) & set(NON_CARDINAL))
    if hit and derived.get('headroom') is not None:
        yield 'blocking', 'evaluation_method %s is non-cardinal, so headroom is null by construction, not %s' \
            % (', '.join(hit), derived['headroom'])


@_benchmark_rule('rating-pool-required', '02 S11 implications')
def _rating_pool(b, corpus, level):
    if set(b.evaluation_method) & set(POOLED) and not b.comparability.rating_pool_required:
        yield 'blocking', 'a pairwise or tournament benchmark needs comparability.rating_pool_required: true', \
            'comparability.rating_pool_required = true'


@_benchmark_rule('independence-evidence', '02 S11 implications')
def _independence(b, corpus, level):
    for f in b.governance.independence_flags or []:
        flag, src = (f, None) if isinstance(f, str) else (f.flag, f.source)
        if flag != 'no-known-conflict' and not src:
            yield 'blocking', 'independence flag %s needs an evidence Source' % flag


@_benchmark_rule('contested-pair', '02 S11 implications')
def _contested(b, corpus, level):
    if b.maintenance_status_contested and not (b.contested_source and b.contested_statement_date):
        yield 'blocking', 'maintenance_status_contested needs contested_source and contested_statement_date'


@_benchmark_rule('range-basis', '02 S10, S11 implications')
def _range_basis(b, corpus, level):
    for name in ('est_runtime_hours', 'est_cost_usd', 'est_participant_cost_usd'):
        r = getattr(b.execution, name)
        if r is not None and not r.basis:
            yield 'blocking', 'execution.%s is a range estimate with no basis' % name


STUB_TAG = 'bench-new-stub'
PLACEHOLDER_HOST = 'example.invalid'


def _placeholders(value, path=''):
    """Dotted paths of TODO strings and example.invalid URLs anywhere in a dumped record."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _placeholders(v, '%s.%s' % (path, k) if path else str(k))
    elif isinstance(value, list):
        for v in value:
            yield from _placeholders(v, path + '[]')
    elif isinstance(value, str):
        text = value.strip()
        if text == 'TODO' or text.startswith('TODO:') or ('//%s' % PLACEHOLDER_HOST) in text:
            yield path


@_benchmark_rule('stub-placeholder', '05 S3 (bench new); P0-S5-T03')
def _stub_placeholder(b, corpus, level):
    found = sorted(set(_placeholders(b.model_dump(mode='json', exclude={'tags'}))))
    if found:
        yield 'blocking', 'scaffold placeholders remain: %s' % ', '.join(found)
    if STUB_TAG in b.tags:
        yield 'blocking', ('tagged %s: replace every STUB VALUE the scaffold chose (enums with no null) from a '
                           'cited source, then remove the tag' % STUB_TAG)


@_benchmark_rule('quote-substring', '14-roadmap Phase 0; 04 S9; P0-S5-T06')
def _quote_substring(b, corpus, level):
    from tools.validate import quotes
    record = b.model_dump(mode='json', by_alias=True, exclude_computed_fields=True)
    if not quotes.check(record, corpus.sources):
        return
    draft = b.curation.verification_status == 'ai-drafted-unverified'
    for r in quotes.apply(record, corpus.sources)[1]:
        where = quotes.dotted(r.quote.at + (r.quote.key,))
        if r.nulled is None:
            yield 'blocking', '%s: %s' % (where, r.reason)
            continue
        fix = '%s %s, the reason recorded in curation.notes' % (
            'remove' if isinstance(r.nulled[-1], int) else 'set to null', quotes.dotted(r.nulled))
        if draft:
            yield 'warning', '%s: %s; the field is nulled, the record still validates' % (where, r.reason), fix
        else:
            yield 'blocking', ('%s: %s; the record is %s, so correct the quote from the source rather than '
                               'accept the null' % (where, r.reason, b.curation.verification_status)), fix


@_benchmark_rule('subset-drops-terms', '02 S11 rule 4')
def _subset_drops(b, corpus, level):
    for s in b.subsets:
        for facet in MULTI_VALUED_FACETS:
            override = getattr(s, facet + '_override')
            parent = getattr(b, facet)
            if override is not None and len(override) < len(parent):
                dropped = sorted(set(parent) - set(override))
                yield 'warning', '%s replaces %s with fewer terms, dropping %s: confirm the drop' \
                    % (s.id, facet, ', '.join(dropped) or '(none by name)')


# ---- 04 S12: claims -----------------------------------------------------------------------------

def _claim_findings(rule_id, fn):
    def check(corpus: Corpus, level: str):
        out = []
        for cid, c in sorted(corpus.claims.items()):
            for sev, msg in fn(c, corpus) or []:
                out.append(Finding(rule_id, sev, cid, msg))
        return out
    return check


def _judge_model(c: ResultClaim, corpus: Corpus):
    b = corpus.benchmarks.get(c.benchmark.split('@')[0])
    if b is None or 'model-graded-judge' not in b.evaluation_method:
        return
    cond = corpus.conditions.get(c.eval_conditions) if c.eval_conditions else None
    if cond is None or cond.judge_model is None:
        yield 'blocking', 'a claim on a model-graded-judge benchmark names its judge_model in its conditions'


def _value_in_range(c: ResultClaim, corpus: Corpus):
    m = corpus.metrics.get(c.metric)
    if m is None or m.range is None or c.value is None:
        return
    lo, hi = m.range.min, m.range.max
    if (lo is not None and c.value < lo) or (hi is not None and c.value > hi):
        yield 'blocking', 'value %s is outside %s\'s range [%s, %s]' % (c.value, m.id, lo, hi)


def _after_release(c: ResultClaim, corpus: Corpus):
    sid, _, version = c.system.partition('@')
    s = corpus.systems.get(sid)
    if s is None:
        return
    released = next((v.released for v in s.versions if v.version == version), None) if version else None
    released = released or s.first_released
    if released is not None and c.date_reported < released:
        yield 'blocking', 'date_reported %s is before %s was released (%s)' % (c.date_reported, c.system, released)


RULES['judge-model'] = Rule('judge-model', '04 S12 tier 3', _claim_findings('judge-model', _judge_model))
RULES['value-in-range'] = Rule('value-in-range', '04 S12 tier 3', _claim_findings('value-in-range', _value_in_range))
RULES['claim-after-release'] = Rule('claim-after-release', '04 S12 tier 3',
                                    _claim_findings('claim-after-release', _after_release))


# ---- 04 S12: baselines, licence placement, ingestion, sources, the ledger -----------------------

@rule('one-primary-baseline', '04 S7, S12 tier 3')
def _one_primary(corpus: Corpus, level: str):
    groups: dict[tuple[str, str], list[str]] = {}
    everything = list(corpus.baselines) + [x for b in corpus.benchmarks.values() for x in b.baselines]
    for x in everything:
        groups.setdefault((x.benchmark_version, x.metric), [])
        if x.is_primary:
            groups[(x.benchmark_version, x.metric)].append(x.id)
    return [Finding('one-primary-baseline', 'blocking', '%s/%s' % key,
                    'exactly one is_primary baseline, found %d%s' % (len(ids), (' (%s)' % ', '.join(ids)) if ids else ''))
            for key, ids in sorted(groups.items()) if len(ids) != 1]


# Where a record derived from a licence class may live (04 S9's firewall table). `None`: nowhere.
PLACEMENT = {
    'permissive-attribution': ('data/claims/_ingested/', 'data/_ingest/'),
    'share-alike': ('vendor/pwc-archive/',),
    'non-commercial': None,
    'no-redistribution': None,
    'unlicensed': None,
}


def _placement_finding(entity, path, cls, promoted=False):
    allowed = PLACEMENT[cls]
    if allowed is None:
        return Finding('licence-placement', 'blocking', entity,
                       '%s content may not be stored anywhere; cross-reference by id only (at %s)' % (cls, path))
    if cls == 'permissive-attribution' and promoted and path.startswith('data/'):
        return None                                                    # promotion admits it to the core
    if not path.startswith(allowed):
        return Finding('licence-placement', 'blocking', entity,
                       '%s content may live only under %s, not %s' % (cls, ' or '.join(allowed), path))
    return None


@rule('licence-placement', '04 S9 licence firewall; 04 S12 tier 3')
def _licence_placement(corpus: Corpus, level: str):
    out = []
    for cid, c in sorted(corpus.claims.items()):
        if c.ingestion is not None:
            f = _placement_finding(cid, corpus.paths[cid], c.ingestion.licence_class,
                                   promoted=c.ingestion.review_state == 'promoted')
            out += [f] if f else []
    for bid, b in sorted(corpus.batches.items()):
        path = corpus.paths[bid]
        cls = b.licence.class_
        if PLACEMENT[cls] is None:
            f = _placement_finding(bid, path, cls)
            out += [f] if f else []
    return out


@rule('ingestion-batch', '04 S9, S12 tier 3')
def _ingestion_batch(corpus: Corpus, level: str):
    return [Finding('ingestion-batch', 'blocking', cid, 'ingestion.batch %s has no IngestBatch record' % c.ingestion.batch)
            for cid, c in sorted(corpus.claims.items())
            if c.ingestion is not None and c.ingestion.batch not in corpus.batches]


@rule('non-doi-archive', '04 S9, S12 tier 3')
def _non_doi_archive(corpus: Corpus, level: str):
    return [Finding('non-doi-archive', 'blocking', sid, 'a non-DOI Source needs an archive_url')
            for sid, s in sorted(corpus.sources.items()) if not s.get('doi') and not s.get('archive_url')]


@rule('retired-id-ledger', '05 S9 job 9; 03 S9.2')
def _retired(corpus: Corpus, level: str):
    record_ids = set(corpus.benchmarks) | set(corpus.conditions) | set(corpus.claims) | set(corpus.systems) \
        | set(corpus.metrics) | set(corpus.batches) | set(corpus.sources) | {b.id for b in corpus.baselines}
    out = []
    for rid in sorted(corpus.retired):
        bare = rid.split(':', 1)[-1]
        if bare in corpus.live_terms or rid in corpus.live_terms:
            out.append(Finding('retired-id-ledger', 'blocking', rid, 'a retired id is a live taxonomy term again'))
        if bare in record_ids:
            out.append(Finding('retired-id-ledger', 'blocking', rid, 'a retired id is reused as a record id'))
    return out


# ---- running them -------------------------------------------------------------------------------

def validate(corpus: Corpus, level: str = 'stub', only: str | None = None) -> list[Finding]:
    assert level in ('stub', 'full'), level
    rules = [RULES[only]] if only else list(RULES.values())
    return [f for r in rules for f in r.check(corpus, level)]


def blocking(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == 'blocking']


def _rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, '/')


def load_corpus(root: str = ROOT) -> Corpus:
    c = Corpus()

    def each(pattern):
        return sorted(glob.glob(os.path.join(root, pattern), recursive=True))

    for p in each('data/benchmarks/**/*.yaml'):
        b = load_benchmark(p)
        c.benchmarks[b.id], c.paths[b.id] = b, _rel(root, p)
    for p in each('data/conditions/**/*.yaml'):
        x = EvalConditions.model_validate(read_yaml(p))
        c.conditions[x.id], c.paths[x.id] = x, _rel(root, p)
    for p in each('data/claims/**/*.yaml') + each('vendor/**/claims/**/*.yaml'):
        x = ResultClaim.model_validate(read_yaml(p))
        c.claims[x.id], c.paths[x.id] = x, _rel(root, p)
    for p in each('data/systems/**/*.yaml'):
        x = System.model_validate(read_yaml(p))
        c.systems[x.id], c.paths[x.id] = x, _rel(root, p)
    for p in each('data/metrics/**/*.yaml'):
        x = Metric.model_validate(read_yaml(p))
        c.metrics[x.id], c.paths[x.id] = x, _rel(root, p)
    for p in each('data/baselines/**/*.yaml'):
        c.baselines += [Baseline.model_validate(d) for d in read_yaml(p)]
    for p in each('data/_ingest/batches/**/*.yaml'):
        x = IngestBatch.model_validate(read_yaml(p))
        c.batches[x.id], c.paths[x.id] = x, _rel(root, p)
    for p in each('data/sources/**/*.yaml'):
        d = read_yaml(p)
        c.sources[d['id']], c.paths[d['id']] = d, _rel(root, p)
    ledger = os.path.join(root, 'taxonomy', 'retired-ids.yaml')
    if os.path.exists(ledger):
        c.retired = {r.id for r in RetiredIdFile.model_validate(read_yaml(ledger)).retired}
    models, _ = load_taxonomy(os.path.join(root, 'taxonomy'))
    c.live_terms = {t.id for m in models.values() for t in (getattr(m, 'terms', None) or []) if t.status != 'retired'}
    return c


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--level', choices=('stub', 'full'), default='stub')
    a = p.parse_args(argv)
    findings = validate(load_corpus(a.root), a.level)
    for f in findings:
        print(f)
    print('validators: %d rule(s), %d blocking, %d warning(s)'
          % (len(RULES), len(blocking(findings)), len(findings) - len(blocking(findings))))
    return 1 if blocking(findings) else 0


if __name__ == '__main__':
    sys.exit(main())
