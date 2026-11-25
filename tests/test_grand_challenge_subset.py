"""Grand Challenge subset: per-challenge metrics and access gating (P3-S6-T06; 04 S6, S7; 01 S10).

The verify: "bench validate --tier all, plus a test asserting every selected challenge declares a metric with a range
and a data.submission_limit". The done-when: "Eight challenges are selected and none shares a metric definition it
does not actually share." Each rule is a function below that returns what is wrong; it runs on the committed records,
which must pass, and on copies broken the way the rule names, which must fail, so the test also fails if a check stops
catching its case.

Where the entries live. The ledger names data/benchmarks/grand-challenge/, but every data/benchmarks/ directory is a
domain family: tools/validate/tiers.py reads any YAML file under data/benchmarks/ as a Benchmark and blocks it
(`file-name`) unless it sits at data/benchmarks/<family of domain.primary>/<id>.yaml. All eight are medicine-health
entries, so they live there, and "the Grand Challenge subset" is this module's SELECTED list, not a directory.

The selection. 01 S10 counts 264 challenges in Grand Challenge's public API; the list is not in the repository (the
API is disallowed by robots.txt, and the 2026-11-16 sweep's copy of it was not kept), so the candidates came from the
four catalogue entries Grand Challenge already hosts and from docs/sweeps/log/2026-11-16-medicine-health.yaml. A
challenge was selected when (a) it runs on Grand Challenge, (b) a public source states its submission limit, so
`data.submission_limit` can carry a quote rather than a guess, (c) a public source defines its ranking metric, and (d)
it widens the set of metric definitions and data-access regimes rather than repeating one. Existing entries came
first. Left out: luna16, because its rules let a team submit as often as it liked and its board closed in 2018, so it
has no limit to record (data.submission_limit needs max_submissions >= 1); and the sweep's candidates (ATM, Learn2Reg,
SynthRAD, FLARE, TopBrain, DALPHIN, BEETLE, COBRA, PANTHER), which have no entry yet and, for ATM22 and SynthRAD2023,
whose challenge papers state no submission limit in the passages searched.

Each challenge has Metric records of its own. Two records with the same name (CAMELYON17's and AIROGS's kappa; KiTS's
Surface Dice and the Decathlon's NSD; STOIC2021's two AUCs) are kept apart because their classes, weighting,
tolerance or population differ, which each record's pitfalls say; no challenge here shares a definition with another,
so SELECTED's metric sets are disjoint and no metric is a shared record such as f1-score or vqa-accuracy.
"""
import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import Benchmark, load_benchmark  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import quote_found  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

# id -> (new or extended, why it was selected, its own metrics)
SELECTED = {
    'camelyon17': ('extended', 'pathology slides staged per patient; a weighted kappa over an ordinal scale; three '
                   'submissions per team in the rules', {'camelyon17-pn-stage-kappa'}),
    'pi-cai': ('extended', 'prostate MRI with hidden cohorts and containers; a mean of AUROC and AP; a weekly limit '
               'per verified user', {'pi-cai-ranking-score'}),
    'kits': ('extended', 'kidney CT segmentation; the editions rank differently (KiTS19 composite Dice, then '
             'rank-then-aggregate over HEC Dice and Surface Dice); one final submission per team in 2019',
             {'kits-hec-dice', 'kits-hec-surface-dice', 'kits19-kidney-tumour-dice'}),
    'medical-segmentation-decathlon': ('new', 'ten tasks for one method, train-open and test-labels-held; DSC and '
                                       'NSD into a significance ranking; 15 submissions per team in the live '
                                       'challenge', {'msd-dsc', 'msd-nsd'}),
    'airogs': ('new', 'glaucoma screening with ungradable test images and a never-released test set; four '
               'classification metrics ranked by mean rank; one final submission per team', {
                   'airogs-screening-pauc', 'airogs-screening-sensitivity', 'airogs-ungradability-kappa',
                   'airogs-ungradability-auroc'}),
    'conic': ('new', 'nuclei in colon histology, two tasks with a metric each (pooled mPQ+, multi-class R2); data '
              'behind an accepted registration; one final submission per team and task',
              {'conic-mpq-plus', 'conic-multiclass-r2'}),
    'stoic2021': ('new', 'COVID-19 prognosis from CT where the finalists\' code was trained on sequestered data; an '
                  'AUC over RT-PCR-positive cases; one qualifying submission per team', {
                      'stoic2021-severity-auc', 'stoic2021-covid-auc'}),
    'midog': ('new', 'mitosis detection across scanners and tumour types; F1 pooled over slides with a distance '
              'match; one final submission per team in 2021', {'midog-2021-f1'}),
}
# Shared records a challenge must not borrow: their definitions are another benchmark's or no one's.
GENERIC = {'f1-score', 'vqa-accuracy', 'mmlu-score', 'r-squared', 'kendall-tau', 'brier-score'}
GC_HOST = 'grand-challenge.org'


def entry_path(bid):
    return os.path.join(ROOT, 'data', 'benchmarks', 'medicine-health', bid + '.yaml')


def entry_doc(bid):
    return read_yaml(entry_path(bid))


def metric_doc(mid):
    return read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml'))


def source_doc(sid):
    path = os.path.join(ROOT, 'data', 'sources', '2026', sid + '.yaml')
    return read_yaml(path) if os.path.exists(path) else None


def quoted(source_id, quote):
    src = source_doc(source_id) if source_id else None
    return bool(src and quote and quote_found(quote, src.get('quote_extract') or ''))


# ---- the rules ----------------------------------------------------------------------------------------------

def metric_problems(doc: dict, metrics: dict) -> list[str]:
    """The entry declares metrics, every one a Metric record with a range; at least one bounded on both sides."""
    refs = doc.get('metrics') or []
    if not refs:
        return ['declares no metrics']
    out, bounded = [], False
    for mid in refs:
        m = metrics.get(mid)
        if m is None:
            out.append('%s has no Metric record' % mid)
            continue
        Metric.model_validate(m)
        rng = m.get('range') or {}
        if rng.get('min') is None and rng.get('max') is None:
            out.append('%s declares no range' % mid)
        bounded |= rng.get('min') is not None and rng.get('max') is not None
    if refs and not bounded:
        out.append('no metric has a range bounded on both sides')
    if doc.get('headline_metric') and doc['headline_metric'] not in refs:
        out.append('headline_metric %s is not among its metrics' % doc['headline_metric'])
    return out


def limit_problems(doc: dict) -> list[str]:
    """data.submission_limit is set, and a quote in its source's extract says so."""
    data = doc.get('data') or {}
    lim = data.get('submission_limit')
    if not lim:
        return ['no data.submission_limit']
    out = []
    if not quoted(data.get('submission_limit_source'), data.get('submission_limit_quote')):
        out.append('data.submission_limit_quote is not in data.submission_limit_source\'s extract')
    if lim.get('source') != data.get('submission_limit_source'):
        out.append('the limit and its quote cite different sources')
    return out


def gating_problems(doc: dict) -> list[str]:
    """data.access is set, with a quoted basis and a note that says how the data are gated."""
    data = doc.get('data') or {}
    out = []
    if not data.get('access'):
        out.append('no data.access')
    basis = data.get('access_basis') or {}
    if not quoted(basis.get('source'), basis.get('quote')):
        out.append('data.access_basis carries no quote from its source')
    if not data.get('access_note'):
        out.append('no data.access_note saying what is open and what is gated')
    return out


def own_metric_problems(selected: dict[str, set[str]], docs: dict[str, dict], metrics: dict) -> list[str]:
    """No metric is borrowed: none is generic, none serves two selected challenges, and each one's definition cites a
    source its own challenge's entry cites."""
    out, owner = [], {}
    for bid, mids in selected.items():
        declared = set(docs[bid].get('metrics') or [])
        if declared != mids:
            out.append('%s declares %s, not its own %s' % (bid, sorted(declared), sorted(mids)))
        cited = set((docs[bid].get('curation') or {}).get('sources') or [])
        for mid in declared:
            if mid in GENERIC:
                out.append('%s borrows the shared record %s' % (bid, mid))
            if mid in owner:
                out.append('%s is declared by both %s and %s' % (mid, owner[mid], bid))
            owner.setdefault(mid, bid)
            m = metrics.get(mid) or {}
            if not set(m.get('sources') or []) & cited:
                out.append('%s defines %s from no source the entry cites' % (bid, mid))
    return out


def host_problems(bid: str, doc: dict) -> list[str]:
    """The challenge runs on Grand Challenge: its home page, or a page it cites, is on grand-challenge.org, or a cited
    extract says it is hosted there (KiTS cites KiTS19's report rather than its Grand Challenge pages)."""
    cited = [source_doc(s) or {} for s in (doc.get('curation') or {}).get('sources') or []]
    texts = [doc.get('homepage') or ''] + [(s.get('url') or '') + ' ' + (s.get('quote_extract') or '') for s in cited]
    return [] if any(GC_HOST in t for t in texts) else ['%s cites no grand-challenge.org page' % bid]


# ---- the committed records pass ------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def docs():
    return {bid: entry_doc(bid) for bid in SELECTED}


@pytest.fixture(scope='module')
def metrics():
    return {mid: metric_doc(mid) for _, _, mids in SELECTED.values() for mid in mids}


def test_eight_challenges_are_selected_three_extended_five_new():
    assert len(SELECTED) == 8
    kinds = [k for k, _, _ in SELECTED.values()]
    assert kinds.count('extended') == 3 and kinds.count('new') == 5


def test_no_grand_challenge_directory_exists():
    """The ledger's path would be read as a family and blocked; the entries sit under medicine-health."""
    assert not os.path.exists(os.path.join(ROOT, 'data', 'benchmarks', 'grand-challenge'))


@pytest.mark.parametrize('bid', sorted(SELECTED))
def test_each_entry_loads_in_medicine_health_and_runs_on_grand_challenge(bid, docs):
    b = load_benchmark(entry_path(bid))
    assert isinstance(b, Benchmark) and b.domain.primary.startswith('medicine-health/')
    assert host_problems(bid, docs[bid]) == []


@pytest.mark.parametrize('bid', sorted(SELECTED))
def test_each_declares_a_metric_with_a_range(bid, docs, metrics):
    assert metric_problems(docs[bid], metrics) == []


@pytest.mark.parametrize('bid', sorted(SELECTED))
def test_each_declares_a_quoted_submission_limit(bid, docs):
    assert limit_problems(docs[bid]) == []


@pytest.mark.parametrize('bid', sorted(SELECTED))
def test_each_records_its_data_access_gating(bid, docs):
    assert gating_problems(docs[bid]) == []


def test_no_challenge_shares_a_metric_it_does_not_share(docs, metrics):
    assert own_metric_problems({b: m for b, (_, _, m) in SELECTED.items()}, docs, metrics) == []


def test_same_named_metrics_are_told_apart(metrics):
    """The look-alikes the done-when is about: each pair differs in a stated way."""
    cam, airogs = metrics['camelyon17-pn-stage-kappa'], metrics['airogs-ungradability-kappa']
    assert 'quadratic' in cam['definition'] and 'quadratic' not in airogs['definition']
    severity, covid = metrics['stoic2021-severity-auc'], metrics['stoic2021-covid-auc']
    assert 'RT-PCR-positive' in severity['full_name'] and 'all cases' in covid['full_name']
    assert metrics['conic-multiclass-r2']['range'].get('min') is None       # R2 has no floor
    assert metrics['kits-hec-dice']['must_report_with'] == ['kits-hec-surface-dice']


# ---- broken copies fail ---------------------------------------------------------------------------------------

def test_a_challenge_without_metrics_or_ranges_fails(docs, metrics):
    doc = copy.deepcopy(docs['midog'])
    doc['metrics'] = []
    assert metric_problems(doc, metrics) == ['declares no metrics']
    unbounded = copy.deepcopy(metrics)
    unbounded['midog-2021-f1'] = dict(unbounded['midog-2021-f1'], range=None)
    assert 'midog-2021-f1 declares no range' in metric_problems(docs['midog'], unbounded)
    doc = copy.deepcopy(docs['midog'])
    doc['metrics'] = ['no-such-metric']
    assert 'no-such-metric has no Metric record' in metric_problems(doc, metrics)


def test_a_missing_or_unquoted_submission_limit_fails(docs):
    doc = copy.deepcopy(docs['conic'])
    del doc['data']['submission_limit']
    assert limit_problems(doc) == ['no data.submission_limit']
    doc = copy.deepcopy(docs['conic'])
    doc['data']['submission_limit_quote'] = 'each team may submit as often as it likes'
    assert limit_problems(doc) == ["data.submission_limit_quote is not in data.submission_limit_source's extract"]


def test_an_unrecorded_gate_fails(docs):
    doc = copy.deepcopy(docs['stoic2021'])
    doc['data']['access_basis'] = {'reason': 'assumed', 'source': 'src-gc-stoic2021-home', 'quote': 'open to all'}
    del doc['data']['access_note']
    assert gating_problems(doc) == ['data.access_basis carries no quote from its source',
                                    'no data.access_note saying what is open and what is gated']


def test_a_borrowed_or_shared_metric_fails(docs, metrics):
    selected = {b: set(m) for b, (_, _, m) in SELECTED.items()}
    broken = copy.deepcopy(docs)
    broken['midog']['metrics'] = ['midog-2021-f1', 'f1-score']
    selected['midog'] = {'midog-2021-f1', 'f1-score'}
    found = own_metric_problems(selected, broken, dict(metrics, **{'f1-score': metric_doc('f1-score')}))
    assert 'midog borrows the shared record f1-score' in found
    assert 'midog defines f1-score from no source the entry cites' in found
    selected = {b: set(m) for b, (_, _, m) in SELECTED.items()}
    broken = copy.deepcopy(docs)
    broken['airogs']['metrics'] = sorted(selected['airogs'] | {'camelyon17-pn-stage-kappa'})
    selected['airogs'] |= {'camelyon17-pn-stage-kappa'}
    found = own_metric_problems(selected, broken, metrics)
    assert 'camelyon17-pn-stage-kappa is declared by both camelyon17 and airogs' in found
    assert 'airogs defines camelyon17-pn-stage-kappa from no source the entry cites' in found


def test_a_challenge_off_grand_challenge_fails(docs):
    doc = copy.deepcopy(docs['kits'])
    doc['homepage'] = 'https://example.org/'
    doc['curation']['sources'] = ['src-kits-challenge-kits23']
    assert host_problems('kits', doc) == ['kits cites no grand-challenge.org page']
