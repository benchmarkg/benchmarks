"""Open Catalyst claims, batch 1: four OC20 test-set claims from the EvalAI leaderboards, each held-out-server and
set by a curator (P3-S7-T03; 04-data-model.md S7, S9; 06-sourcing-and-scraping.md S8).

The verify: "bench validate --tier all, plus a test asserting every claim's verification is held-out-server and was
set by a curator rather than an adapter". The done-when: "Four claims exist with archived sources and a human-set
verification level." Each rule is a function that returns what is wrong; it runs on the committed claims, which
must pass, and on copies broken the way the rule names, which must fail.

  1. Four claims in data/claims/oc20/, on oc20@oc20's OOD Both test subsplit, one System each, so no (benchmark,
     system, metric) group of two forms. Three are IS2RE energy MAEs from three teams and share one conditions
     record and one comparability key; one is an S2EF force MAE.
  2. Every claim is held-out-server (the verify's first half).
  3. A curator set it, not an adapter (the second half). The repository records who wrote a claim in two places,
     and setter() reads both: 04 S9's `ingestion` block is "present on every machine-written record, null on
     hand-curated ones", and the provenance gate refuses any machine draft without one
     (ingest/gates/record.provenance); and an adapter writes under data/claims/_ingested/<source>/. Inside an
     ingested claim, a curator who later sets a field marks it `curator` in field_provenance (schema/claim.py's
     FieldOrigin) and records the review. A claim with no ingestion block, outside _ingested/, was written by
     hand, verification included. Beside that, no adapter could have produced the rung: taxonomy/verification.yaml
     marks it not machine_assignable, ingest/verification.check_machine_claim refuses it, the verification-ceiling
     gate refuses any ingested draft above rank 3, and the Epoch adapter's own rule gives an external scrape
     self-reported.
  4. The rung is the right one, not just a hand-typed one: the claim's subset sits under the OC20 test set, whose
     evidence quotes the OC20 paper saying the test labels are withheld and a leaderboard-page Source scoring it;
     the claim's Source is that test phase's leaderboard (src-evalai-oc20-challenge-712-splits ties the split id
     to the phase); and the team is not the maintainers', who hold the labels. The failure cases are an OC22 claim
     (no source read says OC22's labels are withheld: the oc20 entry's review check), an OCx24 claim (public
     measurements) and a row entered by the maintainers' own group.
  5. Every number is the board's: each claim's notes quote its row, the row is in the Source's extract, and the
     value is the row's result under the metric's OOD Both column, to six decimals (bench fmt's limit).
  6. The Sources: the IS2RE board is withheld (team handles and free-text metadata), the S2EF board and the split
     list name no person and are pending for the lead's archiver, and no extract holds submission metadata.

Ids are content-derived (05 S2) and are recomputed here, as tests/test_roboarena_claims.py does.

These rules hold every claim on oc20's computational generations (OC20 and OC22). Batch 2's claims on oc20@ocx24
(P3-S7-T04) are scored against laboratory measurements, not by a server; tests/test_open_catalyst_ocx24_claims.py
holds them.
"""
import glob
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest.adapters import epoch  # noqa: E402
from ingest.gates import GateError  # noqa: E402
from ingest.gates.record import provenance, verification_ceiling  # noqa: E402
from ingest.verification import Transcript, check_machine_claim, machine_assignable, verification_rule  # noqa: E402
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.source import Source, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import llm_run  # noqa: E402

BID = 'oc20'
ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'chemistry-materials', BID + '.yaml')
SHARD = os.path.join(ROOT, 'data', 'claims', BID)
RUNG = 'held-out-server'
REPORTER = 'org-open-catalyst-project'
SPLITS = 'src-evalai-oc20-challenge-712-splits'
WITHHELD_QUOTE = 'Ground truth test data is not publicly released'      # the OC20 paper, on the test labels
SERVER = 'leaderboard-page'
# The task's columns on the board, by metric; a claim reads the column for its subsplit.
COLUMN = {'oc-is2re-energy-mae': 'Energy MAE (eV)', 'oc-is2re-ewt': 'EwT', 'oc-s2ef-energy-mae': 'Energy MAE (eV)',
          'oc-s2ef-force-mae': 'Forces MAE (eV / A)', 'oc-s2ef-force-cosine': 'Forces cosine', 'oc-s2ef-efwt': 'EFwT',
          'oc-is2rs-adwt': 'ADwT', 'oc-is2rs-afbt': 'AFbT'}
TASK = {'oc-is2re': 'IS2RE', 'oc-s2ef': 'S2EF', 'oc-is2rs': 'IS2RS'}
SUBSPLIT = {'oc20#oc20-test-id': 'ID', 'oc20#oc20-test-ood-ads': 'OOD Ads', 'oc20#oc20-test-ood-cat': 'OOD Cat',
            'oc20#oc20-test-ood-both': 'OOD Both'}
# The maintainers' own group, as team names on the board spell it: a row they entered was scored on labels they hold.
MAINTAINERS = re.compile(r'\bFAIR\b|\bMeta\b|\bCMU\b|Carnegie Mellon|Open Catalyst\s+Project', re.IGNORECASE)
ROW = re.compile(r'("submission__participant_team__team_name":.*?"submission__id":\d+)')


def load(kind, ident):
    return read_yaml(os.path.join(ROOT, 'data', kind, ident + '.yaml'))


def source(sid):
    return Source.model_validate(load(os.path.join('sources', '2026'), sid))


def raw_claims():
    """(repo-relative path, raw mapping) for every claim under data/claims/ on oc20, wherever it lives, but for those
    on the wet-lab generation, oc20@ocx24, which tests/test_open_catalyst_ocx24_claims.py holds."""
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True)):
        raw = read_yaml(p)
        bench, _, version = str(raw.get('benchmark', '')).partition('@') if isinstance(raw, dict) else ('', '', '')
        if bench == BID and version != 'ocx24':
            out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), raw))
    return out


RAW = raw_claims()
CLAIMS = [ResultClaim.model_validate(raw) for _, raw in RAW]
PATHS = {c.id: rel for c, (rel, _) in zip(CLAIMS, RAW)}


@pytest.fixture(scope='module')
def entry():
    return load_benchmark(ENTRY)


# ---- the rules ------------------------------------------------------------------------------------------------

def setter(claim, rel):
    """Who set the claim's verification: 'adapter' or 'curator', read from how the repository records provenance.
    A machine-written claim carries an ingestion block (04 S9) or lives under data/claims/_ingested/; within one, a
    curator's later change is a field_provenance entry `curator` with a recorded review."""
    ing = claim.ingestion
    if ing is None:
        return 'adapter' if '/_ingested/' in '/' + rel else 'curator'
    reviewed = ing.review_state in ('human-reviewed', 'promoted') and ing.reviewed_by and ing.reviewed_on
    return 'curator' if ing.field_provenance.get('verification') == 'curator' and reviewed else 'adapter'


def row_of(claim):
    """The board row the claim's notes quote, as a mapping, or None."""
    m = ROW.search(claim.notes or '')
    return json.loads('{' + m.group(1) + '}') if m else None


def held_out_problems(claim, rel, b):
    """Why the claim may not hold held-out-server as P3-S7-T03 sets it; empty when it may."""
    out = []
    if claim.verification != RUNG:
        out.append('verification %s, not %s' % (claim.verification, RUNG))
    if setter(claim, rel) != 'curator':
        out.append('the verification was set by an adapter; rung 4 is never machine-assigned (04 S7)')
    bench, _, version = claim.benchmark.partition('@')
    by_id = {s.id: s for s in b.subsets}
    s, chain, ancestors = by_id.get(claim.subset), [], []
    while s is not None:
        chain += list(s.evidence)
        ancestors.append(s.id)
        s = by_id.get(s.parent) if s.parent else None
    if bench != BID or version != 'oc20' or 'oc20#oc20-test' not in ancestors:
        out.append('%s on %s is not on the OC20 test set, the split whose labels a source says are withheld'
                   % (claim.subset, claim.benchmark))
    found = [ev for ev in chain if ev.quote and quote_found(ev.quote, source(ev.source).quote_extract or '')]
    if not any(WITHHELD_QUOTE in ev.quote for ev in found):
        out.append('no source quoted for %s says its test labels are withheld' % claim.subset)
    if not any(source(ev.source).type == SERVER for ev in found):
        out.append('no leaderboard-page Source quoted for %s scores it' % claim.subset)
    src = source(claim.source)
    row = row_of(claim)
    if src.type != SERVER or row is None:
        out.append('%s is not a leaderboard row' % claim.source)
    else:
        task = next((t for prefix, t in TASK.items() if claim.metric.startswith(prefix + '-')), '?')
        split = r'\{"id":%d,"dataset_split":\d+,"challenge_phase":\d+,"challenge_phase_name":"[^"]*\(%s\) -- Test"' \
            % (row['challenge_phase_split'], task)
        if not re.search(split, source(SPLITS).quote_extract or ''):
            out.append('split %s is not the %s -- Test phase in %s' % (row['challenge_phase_split'], task, SPLITS))
        if MAINTAINERS.search(row['submission__participant_team__team_name']):
            out.append('the row was entered by the maintainers\' group (%s), who hold the test labels'
                       % row['submission__participant_team__team_name'])
    return out


def number_problems(claim):
    """Why the claim's value is not the board's number for its metric and subsplit."""
    row = row_of(claim)
    if row is None:
        return ['the notes quote no board row']
    out = []
    span = ROW.search(claim.notes).group(1)
    if not quote_found(span, source(claim.source).quote_extract or ''):
        out.append('the quoted row is not in %s' % claim.source)
    label = '%s -- %s' % (COLUMN[claim.metric], SUBSPLIT[claim.subset])
    labels = row['leaderboard__schema']['labels']
    if label not in labels or len(labels) != len(row['result']):
        return out + ['the row has no column %r' % label]
    if claim.value != round(row['result'][labels.index(label)], 6):
        out.append('value %s is not the row\'s %r under %r' % (claim.value, row['result'][labels.index(label)], label))
    if claim.date_reported.isoformat() != row['submission__submitted_at'][:10]:
        out.append('date_reported %s is not the row\'s submission date' % claim.date_reported)
    system = System.model_validate(load('systems', claim.system))
    if system.name != row['submission__method_name']:
        out.append('system %s is named %r, the row %r' % (system.id, system.name, row['submission__method_name']))
    return out


# ---- 1. four claims ----------------------------------------------------------------------------------------------

def test_four_claims_in_the_shard_one_system_each():
    assert len(CLAIMS) == 4
    assert all(rel.startswith('data/claims/oc20/') for rel in PATHS.values()), PATHS
    assert {c.benchmark for c in CLAIMS} == {'oc20@oc20'} and {c.subset for c in CLAIMS} == {'oc20#oc20-test-ood-both'}
    assert len({(c.benchmark, c.system, c.metric) for c in CLAIMS}) == 4              # no group of two forms
    assert len({c.system for c in CLAIMS}) == 4
    assert sorted(c.metric for c in CLAIMS) == ['oc-is2re-energy-mae'] * 3 + ['oc-s2ef-force-mae']
    assert {c.reported_by for c in CLAIMS} == {REPORTER} and {c.claim_type for c in CLAIMS} == {'absolute'}


# ---- 2 and 3. held-out-server, set by a curator (the verify) -----------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_verify_every_claim_is_held_out_server_set_by_a_curator(claim, entry):
    assert claim.verification == RUNG
    assert claim.ingestion is None                                    # hand-curated (04 S9)
    assert setter(claim, PATHS[claim.id]) == 'curator'
    assert held_out_problems(claim, PATHS[claim.id], entry) == []


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_no_adapter_could_have_written_the_rung(claim):
    """Each lock an ingested claim passes through refuses held-out-server, so the rung can only be a curator's."""
    rungs = read_yaml(os.path.join(ROOT, 'taxonomy', 'verification.yaml'))['rungs']
    assert [(r['rank'], r['machine_assignable']) for r in rungs if r['id'] == RUNG] == [(4, False)]
    assert RUNG not in machine_assignable(ROOT)
    with pytest.raises(ValueError, match='not machine-assignable'):
        check_machine_claim(RUNG, None, ROOT)
    draft = read_yaml(os.path.join(ROOT, *PATHS[claim.id].split('/')))
    with pytest.raises(GateError, match='rank 4'):
        verification_ceiling(draft, None, ROOT)
    with pytest.raises(GateError, match='no ingestion block'):
        provenance(draft)                                                # a machine draft without one never merges
    # and the Epoch adapter's own rule, for a row it scraped from someone else's board, is rung 1
    assert verification_rule('external-scrape', Transcript(None, 'absent')) == 'self-reported'


def ingested(claim, field_origin, **review):
    """The claim as the Epoch adapter would have written it: an ingestion block, with `verification`'s origin."""
    block = {'batch': 'ingest-epoch-2026-11-24', 'source_adapter': epoch.NAME, 'adapter_version': epoch.VERSION,
             'source_record_id': 'oc20-is2re-test:%s' % claim.system, 'last_seen_upstream': date(2026, 11, 24),
             'source_url': epoch.ZIP_URL, 'source_licence': epoch.LICENCE, 'licence_class': epoch.LICENCE_CLASS,
             'source_attribution': 'Epoch AI', 'ingested_at': datetime(2026, 11, 24, tzinfo=timezone.utc),
             'extraction_confidence': 1.0, 'field_provenance': {'value': 'source', 'verification': field_origin},
             **review}
    return ResultClaim.model_validate({**claim.model_dump(), 'ingestion': block})


def test_an_adapter_set_rung_is_caught(entry):
    c = CLAIMS[0]
    lower = c.model_copy(update={'verification': 'maintainer-verified'})
    assert held_out_problems(lower, PATHS[c.id], entry)[0] == 'verification maintainer-verified, not held-out-server'
    machine = ingested(c, 'derived')
    assert setter(machine, PATHS[c.id]) == 'adapter'
    assert any('set by an adapter' in p for p in held_out_problems(machine, PATHS[c.id], entry))
    # a hand-shaped file in the adapter's tree is the adapter's
    moved = 'data/claims/_ingested/epoch/oc20/%s.yaml' % c.id
    assert setter(c, moved) == 'adapter'
    # a curator marked as such in field_provenance, without a recorded review, is not enough
    assert setter(ingested(c, 'curator'), PATHS[c.id]) == 'adapter'


def test_a_curator_may_set_the_rung_on_an_ingested_claim():
    """The rule is about who set the field, not about whether a machine ever touched the record."""
    c = CLAIMS[0]
    reviewed = ingested(c, 'curator', review_state='human-reviewed', reviewed_by='curator', reviewed_on=date(2026, 11, 24))
    assert setter(reviewed, 'data/claims/_ingested/epoch/oc20/%s.yaml' % c.id) == 'curator'


# ---- 4. the rung is the right one ----------------------------------------------------------------------------------

def test_the_oc20_test_set_quotes_withheld_labels_and_a_server(entry):
    test = next(s for s in entry.subsets if s.id == 'oc20#oc20-test')
    paper = next(ev for ev in test.evidence if WITHHELD_QUOTE in (ev.quote or ''))
    assert quote_found(paper.quote, source(paper.source).quote_extract) and source(paper.source).doi
    assert any(source(ev.source).type == SERVER for ev in test.evidence)
    assert RUNG in entry.governance.submission_process


def test_an_oc22_or_ocx24_claim_is_refused(entry):
    """OC22's withheld labels rest on its server alone (the oc20 entry's review check), and OCx24's measurements are
    public, so neither generation's claims may take the rung on this evidence."""
    c = CLAIMS[0]
    oc22 = c.model_copy(update={'benchmark': 'oc20@oc22', 'subset': 'oc20#oc22-test-ood'})
    found = held_out_problems(oc22, PATHS[c.id], entry)
    assert any('not on the OC20 test set' in p for p in found)
    assert 'no source quoted for oc20#oc22-test-ood says its test labels are withheld' in found
    ocx24 = c.model_copy(update={'benchmark': 'oc20@ocx24', 'subset': 'oc20#ocx24-her-loco'})
    found = held_out_problems(ocx24, PATHS[c.id], entry)
    assert 'no leaderboard-page Source quoted for oc20#ocx24-her-loco scores it' in found


def test_a_row_the_maintainers_entered_is_refused(entry):
    c = CLAIMS[0]
    team = row_of(c)['submission__participant_team__team_name']
    theirs = c.model_copy(update={'notes': c.notes.replace('team_name":"%s"' % team, 'team_name":"FAIR + CMU"')})
    assert any('maintainers\' group (FAIR + CMU)' in p for p in held_out_problems(theirs, PATHS[c.id], entry))
    assert any('not in %s' % c.source in p for p in number_problems(theirs))
    assert not any(MAINTAINERS.search(row_of(x)['submission__participant_team__team_name']) for x in CLAIMS)


def test_a_claim_on_another_phase_s_board_is_refused(entry):
    is2re = next(c for c in CLAIMS if c.metric == 'oc-is2re-energy-mae')
    as_s2ef = is2re.model_copy(update={'metric': 'oc-s2ef-energy-mae'})
    assert any('is not the S2EF -- Test phase' in p for p in held_out_problems(as_s2ef, PATHS[is2re.id], entry))


# ---- 5. every number is the board's ----------------------------------------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_the_value_is_the_quoted_row_s_column(claim):
    assert number_problems(claim) == []
    row = row_of(claim)
    assert row['submission__is_public'] is True and row['submission__is_baseline'] is False


def test_a_wrong_number_is_caught():
    c = CLAIMS[0]
    assert any('is not the row' in p for p in number_problems(c.model_copy(update={'value': c.value + 0.01})))
    assert number_problems(c.model_copy(update={'notes': 'no row'})) == ['the notes quote no board row']
    late = c.model_copy(update={'date_reported': date(2026, 11, 24)})
    assert any('submission date' in p for p in number_problems(late))


def test_each_board_is_read_whole():
    """One page holds every row ("next":null), so no row was missed by paging."""
    for sid, n in (('src-evalai-oc20-leaderboard-1950', 36), ('src-evalai-oc20-leaderboard-1946', 13)):
        assert quote_found('{"count":%d,"next":null,"previous":null,"results":[' % n, source(sid).quote_extract)


# ---- 6. the Sources --------------------------------------------------------------------------------------------------

def test_the_sources_archive_status_and_personal_data():
    is2re = source('src-evalai-oc20-leaderboard-1950')
    assert (is2re.archive_status, is2re.contains_personal_data, is2re.archive_url) == ('withheld', True, None)
    assert is2re.failure_reason and is2re.archive_requested_at is None
    for sid in ('src-evalai-oc20-leaderboard-1946', SPLITS):
        s = source(sid)
        assert s.contains_personal_data is False and s.archive_status in ('pending', 'ok'), sid
    for sid in ('src-evalai-oc20-leaderboard-1950', 'src-evalai-oc20-leaderboard-1946', SPLITS):
        x = source(sid).quote_extract
        assert '@' not in x and 'submission_metadata' not in x, sid           # no free-text answers, no code links
        for field in ('Code URL', 'Background', 'Institution name', 'team_url":"http://', 'github.com'):
            assert field not in x, (sid, field)
        assert BID in source(sid).cited_by


# ---- the comparability and the non-LLM count --------------------------------------------------------------------------

def test_the_three_is2re_claims_share_a_key_and_the_s2ef_one_does_not(entry):
    r = comp.resolve_profile(entry)
    assert set(r.material) == {'subset_used', 'training_data_policy'}
    keys = {}
    for c in CLAIMS:
        cond = EvalConditions.model_validate(load('conditions', c.eval_conditions))
        got = comp.compute_for_claim(c, r, cond)
        assert got.condition_completeness == 1.0 and got.key_unknown_count == 0, c.id
        keys.setdefault(c.metric, set()).add(got.comparability_key)
    assert len(keys['oc-is2re-energy-mae']) == 1 and len(keys['oc-s2ef-force-mae']) == 1


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_no_claim_is_llm_run(claim):
    assert llm_run.llm_run(claim.system) is False
    assert System.model_validate(load('systems', claim.system)).system_type == 'scientific-surrogate-model'


# ---- the records' identity ---------------------------------------------------------------------------------------------

def _content_id(prefix, d):
    return '%s-%s' % (prefix, hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',', ':')).encode('utf-8'))
                      .hexdigest()[:12])


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_ids_are_content_derived(claim):
    key = {'benchmark': claim.benchmark, 'system': claim.system, 'metric': claim.metric, 'subset': claim.subset,
           'value': claim.value, 'source': claim.source, 'date_reported': claim.date_reported.isoformat()}
    assert claim.id == _content_id('claim', key)
    raw = {k: v for k, v in load('conditions', claim.eval_conditions).items() if k != 'id'}
    assert claim.eval_conditions == _content_id('cond', {k: comp.canonicalise(v) for k, v in raw.items()})
