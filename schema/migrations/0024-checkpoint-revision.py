"""Migration 0024: the 20-entry checkpoint's schema revision (ADR-0024; P1-S3-T05).

The corpus half of ADR-0024. Every row below either moves a value the old schema had nowhere to put out of
a note and into the field ADR-0024 adds for it, or rewrites a value into the shape a reshaped field now
takes. Nothing here is a new curation judgement: each value is one the entry, or its Sources, already
stated, and each quote is one the entry already carried (or that its Source's committed extract holds).

  A1  The Well's lifecycle, kept at `active` only because the schema refused null, becomes null.
  A2  SUPERB's aggregation_policy, left at its default for want of an unknown, becomes `unknown`; CALVIN's
      and HarmBench's `submission_process: []`, which their notes say means "not stated", becomes null; and
      every entry records governance.independence_assessed: false where its independence_flags_note says
      "Not assessed", true everywhere else (a flag, or a note saying what was checked).
  A3  history[] for the seven entries whose notes held a dated move, closure or hand-over.
  A4  as_used[] for MedQA, LIBERO, HumanEval and FOLIO.
  A5  paper.doi for OC20 (out of its released_note) and ClimateBench (its paper Source's DOI).
  A6  miniF2F's and HarmBench's ground_truth_source `none` becomes formal-verifier and released-classifier.
  A7  tau-bench's material_extra gains user_simulator.
  A9  rendered_url and extract_preprocessing on the Sources whose notes state them.
  A10 lineage.variants for MMMU (MMMU-Pro) and ClimateBench (v2), the two related benchmarks a read Source
      names; OC22 and miniF2F-Dafny have no Source read yet and stay in header comments.
  D1  `license` and `license_notes` leave the five entries that carry them; the notes move to the data or
      code licence note (a paper's licence is already on its Source).
  D2  The ten `data.size` blocks become lists of rows, headline first, and `languages` moves to data.
  D3  The six forecasting waivers go: the profile rule, not the entries, was wrong.
"""
from __future__ import annotations

import datetime as dt
import re

from schema.migrations import ABSENT, Row, entity_files

KIND = 'field'
SUMMARY = ('ADR-0024, the checkpoint schema revision: null lifecycle, explicit unknowns, history, as_used, '
           'paper.doi, two ground-truth values, user_simulator, Source rendering fields, size rows, a derived '
           'license, and the surrogate-fit profile')

NOT_ASSESSED = re.compile(r'^\s*Not assessed\b')
STRIPPED = re.compile(r'(scripts and styles|<script> and <style> blocks) stripped')
PREPROCESSING = 'script and style blocks removed before normalise()'

RENDERED = {   # Source id -> the page a reader opens, as each Source's notes name it
    'src-cocodataset-detection-eval': 'https://cocodataset.org/#detection-eval',
    'src-cocodataset-guidelines': 'https://cocodataset.org/#guidelines',
    'src-cocodataset-home': 'https://cocodataset.org/#home',
    'src-cocodataset-termsofuse': 'https://cocodataset.org/#termsofuse',
    'src-evalai-oc20-challenge-712': 'https://eval.ai/web/challenges/challenge-page/712',
    'src-evalai-mmmu-challenge-2179': 'https://eval.ai/web/challenges/challenge-page/2179',
    'src-hf-fairchem-leaderboard-content': 'https://huggingface.co/spaces/facebook/fairchem_leaderboard',
    'src-hf-api-flores-plus': 'https://huggingface.co/datasets/openlanguagedata/flores_plus',
    'src-hf-api-folio': 'https://huggingface.co/datasets/yale-nlp/FOLIO',
    'src-crossref-10-1029-2021ms002954': 'https://doi.org/10.1029/2021MS002954',
}

HISTORY = {
    'coco': [
        {'event': 'channel-moved', 'field': 'execution.submission_channel', 'from': 'competitions.codalab.org',
         'to': 'codalab.lisn.upsaclay.fr (competition 7384)', 'source': 'src-codalab-lisn-coco-detection-bbox',
         'quote': 'Current test-dev (bbox) Aug. 11, 2019, midnight UTC End Competition Ends Dec. 31, 2030',
         'note': 'Undated in the sources read: CodaLab suspended competitions.codalab.org, whose COCO pages are '
                 'read-only and point to the migrated server, which the quote shows open until 2030.'},
    ],
    'oc20': [
        {'date': dt.date(2026, 1, 31), 'event': 'channel-closed', 'field': 'execution.submission_channel',
         'from': 'EvalAI challenge 712', 'source': 'src-evalai-oc20-challenge-712',
         'quote': '"end_date":"2026-01-31T23:59:59Z"'},
        {'event': 'channel-opened', 'field': 'execution.submission_channel',
         'to': 'Hugging Face space facebook/fairchem_leaderboard', 'source': 'src-hf-fairchem-leaderboard-content',
         'quote': 'This leaderboard evaluates performance on the **Open Catalyst 2020 (OC20)** dataset',
         'note': 'The sources read do not date the opening.'},
    ],
    'mmmu': [
        {'date': dt.date(2026, 2, 11), 'event': 'channel-closed', 'field': 'execution.submission_channel',
         'from': 'EvalAI challenge 2179', 'source': 'src-evalai-mmmu-challenge-2179',
         'quote': '"end_date":"2026-02-11T16:00:59Z"'},
        {'date': dt.date(2026, 2, 12), 'event': 'access-changed', 'field': 'data.access',
         'from': 'train-open-test-held-out', 'to': 'fully-open', 'source': 'src-github-mmmu-readme',
         'quote': '[2026-02-12] We have released the answers for the MMMU test set!'},
    ],
    'flores': [
        {'event': 'maintainer-changed', 'field': 'governance.maintainer', 'from': 'Meta AI',
         'to': 'Open Language Data Initiative (OLDI)', 'source': 'src-oldi-getting-started',
         'quote': 'The FLORES+ and OLDI-Seed datasets are managed directly by the OLDI team',
         'note': 'FLORES-101 and FLORES-200 came from Meta AI; OLDI took the dataset over from FLORES-200.'},
    ],
    'nle': [
        {'event': 'repository-moved', 'field': 'repository', 'from': 'https://github.com/facebookresearch/nle',
         'to': 'https://github.com/NetHack-LE/nle', 'source': 'src-github-facebookresearch-nle-readme',
         'quote': 'Please find NLE at its new home at',
         'note': 'The maintainer moved with it, from Meta AI and UCL to the NetHack-LE organisation.'},
    ],
    'minif2f': [
        {'event': 'maintainer-changed', 'field': 'governance.maintainer', 'from': 'OpenAI (repository archived)',
         'to': 'Meta FAIR (the facebookresearch fork)', 'source': 'src-github-facebookresearch-minif2f-readme',
         'quote': 'This repository is a fork of the original OpenAI miniF2F repository'},
    ],
    'tau-bench': [
        {'event': 'repository-moved', 'field': 'repository', 'from': 'https://github.com/sierra-research/tau-bench',
         'to': 'https://github.com/sierra-research/tau2-bench', 'source': 'src-github-tau-bench-readme',
         'quote': 'This repository contains outdated versions of the airline and retail tasks.',
         'note': 'tau2-bench holds τ²-bench and now τ³-bench; the versions are the entry\'s, not separate events.'},
    ],
}

AS_USED = {
    'medqa': [{'protocol': 'Closed-book multiple choice: the question and its four options only, with no '
                           'retrieval over the textbooks.',
               'split': 'test (the four-option version)', 'source': 'src-lm-eval-harness-medqa-task',
               'quote': 'task: medqa_4options',
               'note': 'Vals AI\'s board runs it the same way. The paper\'s protocol retrieves from 18 English '
                       'medical textbooks (designed_for_subjects_basis).'}],
    'libero': [{'protocol': 'Multitask training on each suite, scored by average success over the four suites; '
                            'the lifelong protocol\'s FWT, NBT and AUC are not reported.',
                'source': 'src-arxiv-2502-19645',
                'quote': 'OpenVLA\'s average success rate across four task suites from 76.5% to 97.1%'}],
    'humaneval': [{'protocol': 'Instruction-tuned models scored by pass@1, not only the base models whose raw '
                               'continuation the protocol was built for.',
                   'source': 'src-arxiv-2610-09202',
                   'quote': 'on instruction-tuned MobileLLM-Pro-1B at W2A16KV16, CanonQ achieves relative '
                            'improvements of 41.7% in HumanEval pass@1'}],
    'folio': [{'protocol': 'Accuracy on the public validation split.', 'split': 'validation',
               'source': 'src-github-folio-readme',
               'quote': 'A leaderboard will be releeased soon to obtain your results on the unreleased test set.',
               'note': 'The test split was never released and the promised leaderboard did not appear, so '
                       'published results are on validation.'}],
}

LINEAGE = {
    'mmmu': {'role': 'root', 'variants': [
        {'id': 'mmmu-pro', 'relation': 'robust-revision', 'source': 'src-github-mmmu-readme',
         'quote': 'MMMU-Pro: A More Robust Multi-discipline Multimodal Understanding Benchmark'}]},
    'climatebench': {'role': 'root', 'variants': [
        {'id': 'climatebench-v2', 'relation': 'successor', 'source': 'src-arxiv-2610-04558',
         'quote': 'We present ClimateBench v2, a standardized protocol for evaluating climate models'}]},
}

PAPER_DOI = {'oc20': '10.1021/acscatal.0c04525', 'climatebench': '10.1029/2021MS002954'}
GROUND_TRUTH = {'minif2f': 'formal-verifier', 'harmbench': 'released-classifier'}
FORECAST_WAIVED = ('lead_time', 'resolution_window')

LICENCE_NOTES = {   # entry -> {dotted note field: its text}; the paper licences these notes named are on the Sources
    'paperbench': {'execution.code_licence_note': 'Not recorded: the repository has no capture here.'},
    'virtual-cell-challenge': {'data.dataset_licence_note': None},          # the license_notes text, verbatim
    'matbench-discovery': {'data.dataset_licence_note': 'Training datasets carry their own licences, several of '
                           'them non-commercial; the WBM test set\'s was not read from an archived source.'},
    'weatherbench-2': {},                                                   # code_licence and its note say it all
    'forecastbench': {'data.dataset_licence_note': 'Datasets are released "where licensing permits"; no dataset '
                      'licence is stated. The site\'s content and the paper are CC BY-SA 4.0.',
                      'execution.code_licence_note': 'Not read here: no archived copy of the repository.'},
}


def swap(text: str, old: str, new: str) -> str:
    """`text` with the one run of words `old` (any whitespace between them) replaced by `new`; unchanged when
    `new` is already there, so the plan of an applied migration is empty. ABSENT stays ABSENT: migration 0026
    (ADR-0026) moved curation.notes into curation.review_checks, and the text this edited went with it."""
    if text is ABSENT:
        return text
    hits = list(re.finditer(r'\s+'.join(map(re.escape, old.split())), text))
    if not hits and re.search(r'\s+'.join(map(re.escape, new.split())), text):
        return text
    if len(hits) != 1:
        raise ValueError('%d matches for %r' % (len(hits), old[:60]))
    return text[:hits[0].start()] + new + text[hits[0].end():]


def size_rows(size: dict) -> list[dict]:
    head = size['n_items']
    unit = head.get('unit')

    def row(c, default_unit):
        out = {'count': c['value'], 'unit': c.get('unit') or default_unit}
        for k_old, k_new in (('split', 'subset'), ('note', 'note'), ('source', 'source'), ('quote', 'quote')):
            if c.get(k_old) is not None:
                out[k_new] = c[k_old]
        return out
    rows = [row(head, unit)]
    if size.get('n_repositories'):
        rows.append(row(size['n_repositories'], 'repositories'))
    rows += [row(c, unit) for c in size.get('other_splits') or []]
    return rows


def benchmark_rows(rel: str, doc: dict) -> list[Row]:
    bid, rows = doc['id'], []

    def at(*path):
        node = doc
        for p in path:
            if not isinstance(node, dict) or p not in node:
                return ABSENT
            node = node[p]
        return node

    def put(path, new):
        if at(*path) != new:                                     # an applied row plans nothing
            rows.append(Row(rel, path, at(*path), new))

    # A1
    if bid == 'the-well':
        put(('lifecycle',), None)
        basis = dict(at('lifecycle_basis'))
        basis['reason'] = swap(basis['reason'], 'dormant\'s exclusion test says to leave the field null and log it, '
                               'but the schema requires a value (default active), so active stands for a benchmark '
                               'under two years old whose maintainers still work on it.',
                               'So lifecycle is null, as dormant\'s exclusion test asks (ADR-0024).')
        put(('lifecycle_basis',), basis)
        put(('curation', 'notes'), swap(at('curation', 'notes'), 'lifecycle active is a placeholder the schema '
                                        'forces:', 'lifecycle is null (ADR-0024):'))
    # A2
    if bid == 'superb':
        put(('aggregation_policy',), 'unknown')
        put(('curation', 'notes'), swap(at('curation', 'notes'), 'aggregation_policy is left at its default only '
                                        'because the schema has no unknown, and the paper',
                                        'aggregation_policy is unknown (ADR-0024), and the paper'))
    if bid in ('calvin', 'harmbench'):
        put(('governance', 'submission_process'), None)
    flags_note = at('governance', 'independence_flags_note')
    assessed = not (isinstance(flags_note, str) and NOT_ASSESSED.match(flags_note) and not at('governance', 'independence_flags'))
    put(('governance', 'independence_assessed'), assessed)
    # A3, A4, A10
    if bid in HISTORY:
        put(('history',), HISTORY[bid])
    if bid in AS_USED:
        put(('as_used',), AS_USED[bid])
    if bid in LINEAGE:
        put(('lineage',), LINEAGE[bid])
    # A5
    if bid in PAPER_DOI:
        put(('paper', 'doi'), PAPER_DOI[bid])
    if bid == 'oc20':
        put(('released_note',), swap(at('released_note'), '(published in ACS Catalysis, doi:10.1021/acscatal.0c04525, '
                                     'which no field of the entry holds);', '(published in ACS Catalysis; its DOI is paper.doi);'))
    # A6
    if bid in GROUND_TRUTH:
        put(('ground_truth_source',), GROUND_TRUTH[bid])
    # A7
    if bid == 'tau-bench' and 'user_simulator' not in at('comparability', 'material_extra'):
        put(('comparability', 'material_extra'), list(at('comparability', 'material_extra')) + ['user_simulator'])
    # D1
    if bid in LICENCE_NOTES and at('license_notes') is not ABSENT:
        notes = at('license_notes')
        put(('license',), ABSENT)
        put(('license_notes',), ABSENT)
        for dotted, text in LICENCE_NOTES[bid].items():
            put(tuple(dotted.split('.')), text if text is not None else ' '.join(notes.split()))
    # D2
    size = at('data', 'size')
    if isinstance(size, dict):
        put(('data', 'size'), size_rows(size))
        if size.get('languages'):
            put(('data', 'languages'), list(size['languages']))
    # D3
    waived = at('comparability', 'material_waived')
    if isinstance(waived, list) and any(w.get('field') in FORECAST_WAIVED for w in waived):
        kept = [w for w in waived if w.get('field') not in FORECAST_WAIVED]
        if kept or set(at('comparability')) - {'material_waived'}:       # the rest of the block, and its comments, stay
            put(('comparability', 'material_waived'), kept or ABSENT)
        else:
            put(('comparability',), ABSENT)
    if bid == 'virtual-cell-challenge':
        put(('curation', 'notes'), swap(at('curation', 'notes'), 'so lead_time and resolution_window arrive as '
                                        'material and are waived.', 'so lead_time and resolution_window arrived '
                                        'as material and were\n   waived, until ADR-0024 gave the pair its own '
                                        'profile.'))
    if bid == 'matbench-discovery':
        put(('curation', 'notes'), swap(at('curation', 'notes'), 'the pair\'s mapping is the thing to fix in '
                                        'taxonomy/comparability-profiles.yaml.', 'ADR-0024 fixed the pair\'s '
                                        'mapping (surrogate-fit), and the waivers are gone.'))
    return rows


def source_rows(rel: str, doc: dict) -> list[Row]:
    rows = []
    sid = doc.get('id')
    if sid in RENDERED and 'rendered_url' not in doc:
        rows.append(Row(rel, ('rendered_url',), ABSENT, RENDERED[sid]))
    if isinstance(doc.get('notes'), str) and STRIPPED.search(doc['notes']) and 'extract_preprocessing' not in doc:
        rows.append(Row(rel, ('extract_preprocessing',), ABSENT, PREPROCESSING))
    return rows


def plan(root: str) -> list:
    rows = []
    for rel, doc in entity_files(root, 'benchmarks'):
        if '/_stubs/' in rel or not isinstance(doc, dict):
            continue
        rows += benchmark_rows(rel, doc)
    for rel, doc in entity_files(root, 'sources'):
        if isinstance(doc, dict):
            rows += source_rows(rel, doc)
    return rows
