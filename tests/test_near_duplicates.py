"""Tests for scripts/near_duplicates.py, the near-duplicate signature (P3-S4-T04; 04 S10, 07 S5.6).

The done-when: "The signature fires on the arc_agi two-spellings pair and does NOT fire on the five
claude-opus-4-6_120K rows, and no merge path exists." The two cases are one cluster. arc_agi_external.csv holds
five claude-opus-4-6_120K rows: High at 0.94 twice (once with Source `https://arcprize.org/leaderboard`, once with
`ARC Prize Leaderboard`: the two-spellings pair), then Max 0.93, Medium 0.92 and Low 0.86. So "does not fire on
the five" is read as: the five are never collapsed, and no pair across two efforts is a match; the one match among
them is the High pair. ARC_ROWS are those five rows as Epoch publishes them (CC-BY-4.0, epoch.ai/data), parsed
with the repository's own stanza for the file.

Bundles are built in memory, and the last test runs over the real snapshot in epochdl/ (gitignored, so skipped
where it is absent). Nothing reaches the network.
"""
import glob
import hashlib
import inspect
import io
import json
import os
import shutil
import socket
import sys
import zipfile
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import near_duplicates as N  # noqa: E402
from ingest import emit  # noqa: E402
from ingest.adapters import epoch  # noqa: E402
from ingest.mappings.schema import load_all  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

ARC_HEADER = ('Model version,Score,Release date,Organization,Country,Training compute (FLOP),Training compute notes,'
              'Name,Cost per task,Source,Source link,Notes,id')
ARC_ROWS = [
    'claude-opus-4-6_120K,0.9400000000000001,2026-02-05,Anthropic,United States of America,,,'
    '"Claude Opus 4.6 (120K, High)",,https://arcprize.org/leaderboard,,,recazrzN9UYUSV1iu',
    'claude-opus-4-6_120K,0.94,2026-02-05,Anthropic,United States of America,,,'
    '"Claude Opus 4.6 (High, 120k thinking)",,ARC Prize Leaderboard,https://arcprize.org/leaderboard,,recZTnD93GgPevLI2',
    'claude-opus-4-6_120K,0.93,2026-02-05,Anthropic,United States of America,,,'
    '"Claude Opus 4.6 (120K, Max)",,https://arcprize.org/leaderboard,,,recM43lOIaRtUf1mn',
    'claude-opus-4-6_120K,0.92,2026-02-05,Anthropic,United States of America,,,'
    '"Claude Opus 4.6 (120K, Medium)",,https://arcprize.org/leaderboard,,,recoN4YV9cS1BcESr',
    'claude-opus-4-6_120K,0.86,2026-02-05,Anthropic,United States of America,,,'
    '"Claude Opus 4.6 (120K, Low)",,https://arcprize.org/leaderboard,,,recAgfLcp2ceTsir9',
]
HIGH_PAIR = {'recazrzN9UYUSV1iu', 'recZTnD93GgPevLI2'}
EFFORTS = {'High', 'Max', 'Medium', 'Low'}
META = {'benchmark_metadata.csv': 'benchmark,source_file,score_column,scale\n',
        'model_metadata.csv': 'model_version,model_group\n'}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('a test reached for the network')
    monkeypatch.setattr(socket, 'socket', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)


def zipped(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, text in {**META, **files}.items():
            z.writestr(name, text)
    return buf.getvalue()


def bundle(files: dict):
    """A bundle from {stem: csv text}."""
    return epoch.ZipBundle(zipped({stem + '.csv': text for stem, text in files.items()}))


def arc(rows=ARC_ROWS) -> str:
    return '\n'.join([ARC_HEADER, *rows]) + '\n'


def stanza(benchmark='bench-x', metric='bench-x-score', score='Score', scale=1.0):
    return SimpleNamespace(benchmark_ref=benchmark, metric_ref=metric, score_column=score, scale=scale)


def scored(rows: list[tuple], header='Model version,Score,Source,id') -> str:
    return '\n'.join([header, *(','.join(map(str, r)) for r in rows)]) + '\n'


def effort(name: str) -> str:
    return next(e for e in EFFORTS if e in name)


ARC_STANZAS = {'csv:arc_agi_external': load_all('epoch')['csv:arc_agi_external']}


# ---- the done-when's two cases ------------------------------------------------------------------------------

def test_the_signature_fires_on_the_two_spellings_pair():
    report = N.find(bundle({'arc_agi_external': arc()}), ARC_STANZAS, [])
    assert len(report['matches']) == 1
    m = report['matches'][0]
    assert (m['benchmark'], m['metric'], m['model_version']) == ('arc-agi-1', 'arc-agi-1-score', 'claude-opus-4-6_120K')
    assert {r['id'] for r in m['rows']} == HIGH_PAIR
    assert {r['source'] for r in m['rows']} == {'https://arcprize.org/leaderboard', 'ARC Prize Leaderboard'}
    assert m['delta'] == 0.0 and 'Name' in m['differing_columns']


def test_the_five_rows_are_one_key_and_no_two_efforts_are_paired():
    groups, _, _ = N.epoch_rows(bundle({'arc_agi_external': arc()}), ARC_STANZAS)
    assert [len(rows) for rows in groups.values()] == [5]      # what a model+benchmark dedupe would collapse
    matched = [m for m in N.find(bundle({'arc_agi_external': arc()}), ARC_STANZAS, [])['matches']]
    assert all(len({effort(r['name']) for r in m['rows']}) == 1 for m in matched)


def test_the_four_efforts_never_pair_even_under_four_spellings():
    # one High row only, and each effort's Source spelled differently: the deltas (0.01, 0.06, 0.08) keep them apart
    spellings = ['https://arcprize.org/leaderboard', 'ARC Prize Leaderboard', 'arcprize.org', 'ARC Prize']
    rows = [r.replace('https://arcprize.org/leaderboard,,', s + ',,') for r, s in zip(ARC_ROWS[:1] + ARC_ROWS[2:],
                                                                                    spellings)]
    assert N.find(bundle({'arc_agi_external': arc(rows)}), ARC_STANZAS, [])['matches'] == []


# ---- the signature's four terms -----------------------------------------------------------------------------

def test_the_delta_is_strictly_under_0_005():
    row = lambda v, s: {'value': v, 'spelling': s}  # noqa: E731
    assert len(N.pairs([row(0.5, 'a'), row(0.504, 'b')])) == 1
    assert N.pairs([row(0.5, 'a'), row(0.505, 'b')]) == []
    assert N.pairs([row(0.5, 'a'), row(0.51, 'b')]) == []


def test_one_spelling_or_none_is_never_a_pair():
    same = scored([('m', 0.5, 'Paper A', 'r1'), ('m', 0.5, 'Paper A', 'r2')])
    blank = scored([('m', 0.5, 'Paper A', 'r1'), ('m', 0.5, '', 'r2')])
    unsourced = scored([('m', 0.5, 'r1'), ('m', 0.5, 'r2')], header='Model version,Score,id')
    for text in (same, blank, unsourced):
        assert N.find(bundle({'f': text}), {'csv:f': stanza()}, [])['matches'] == []


def test_another_model_version_metric_or_benchmark_is_never_a_pair():
    text = scored([('m1', 0.5, 'Paper A', 'r1'), ('m2', 0.5, 'Paper B', 'r2')])
    assert N.find(bundle({'f': text}), {'csv:f': stanza()}, [])['matches'] == []
    one = scored([('m', 0.5, 'Paper A', 'r1')])
    two = scored([('m', 0.5, 'Paper B', 'r2')])
    for other in (stanza(metric='bench-x-cost'), stanza(benchmark='bench-y', metric='bench-x-score')):
        assert N.find(bundle({'f': one, 'g': two}), {'csv:f': stanza(), 'csv:g': other}, [])['matches'] == []
    # the same benchmark and metric from two files is one measurement, so it pairs
    got = N.find(bundle({'f': one, 'g': two}), {'csv:f': stanza(), 'csv:g': stanza()}, [])['matches']
    assert [{r['file'] for r in m['rows']} for m in got] == [{'f.csv', 'g.csv'}]


def test_the_delta_is_on_the_value_the_claim_would_carry():
    # a percentage column: 94.0 and 94.3 are 0.94 and 0.943 as claims, 0.003 apart
    text = scored([('m', 94.0, 'Paper A', 'r1'), ('m', 94.3, 'Paper B', 'r2')])
    assert len(N.find(bundle({'f': text}), {'csv:f': stanza(scale=0.01)}, [])['matches']) == 1
    assert N.find(bundle({'f': text}), {'csv:f': stanza(scale=1.0)}, [])['matches'] == []


def test_a_file_without_a_stanza_is_listed_and_its_rows_counted_not_guessed_at():
    text = scored([('m', 0.5, 'Paper A', 'r1'), ('m', 0.5, 'Paper B', 'r2')])
    report = N.find(bundle({'f': text, 'arc_agi_external': arc()}), ARC_STANZAS, [])
    assert report['populations']['epoch']['files_without_stanza'] == ['f.csv']
    assert report['populations']['epoch']['rows'] == 7
    assert all(m['rows'][0]['file'] == 'arc_agi_external.csv' for m in report['matches'])


# ---- the curated claims -------------------------------------------------------------------------------------

def a_claim():
    path = sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True))[0]
    return ResultClaim.model_validate(read_yaml(path))


def test_claims_pair_on_the_signature_and_superseded_ones_do_not():
    c = a_claim()
    one = c.model_copy(update={'id': 'claim-000000000001', 'value': 0.5, 'source': 'src-paper-a', 'subset': None})
    two = c.model_copy(update={'id': 'claim-000000000002', 'value': 0.501, 'source': 'src-paper-b', 'subset': None})
    got = N.find(None, {}, [one, two])
    assert [{r['claim'] for r in m['rows']} for m in got['matches']] == [{one.id, two.id}]
    assert got['populations'] == {'claims': {'claims': 2}}       # no snapshot read, and none claimed
    old = two.model_copy(update={'superseded_by': 'claim-000000000003'})
    assert N.find(None, {}, [one, old])['matches'] == []
    other = two.model_copy(update={'subset': 'another-subset'})
    assert N.find(None, {}, [one, other])['matches'] == []
    same = two.model_copy(update={'source': one.source})
    assert N.find(None, {}, [one, same])['matches'] == []


# ---- no merge path ------------------------------------------------------------------------------------------

def digest(folder) -> dict:
    return {os.path.relpath(p, folder): hashlib.sha256(open(p, 'rb').read()).hexdigest()
            for p in glob.glob(os.path.join(folder, '**', '*'), recursive=True) if os.path.isfile(p)}


def test_the_signature_does_no_io():
    for fn in (N.pairs, N.epoch_rows, N.claim_rows, N.find, N._match):
        src = inspect.getsource(fn)
        assert 'open(' not in src and '.write' not in src and 'remove' not in src, fn.__name__


def test_a_run_reads_every_row_and_writes_only_its_artifact(tmp_path):
    tree = tmp_path / 'tree'
    shutil.copytree(os.path.join(ROOT, 'data', 'claims'), tree / 'data' / 'claims')
    before = digest(tree)
    (tmp_path / 'b.zip').write_bytes(zipped({'arc_agi_external.csv': arc()}))
    out = tmp_path / 'derived' / 'near_duplicates.json'
    assert N.main(['--zip', str(tmp_path / 'b.zip'), '--root', str(tree), '--out', str(out)]) == 0
    assert digest(tree) == before
    report = json.loads(out.read_text(encoding='utf-8'))
    assert report['populations']['epoch']['rows'] == len(ARC_ROWS)
    assert report['populations']['claims']['claims'] == len(glob.glob(str(tree / 'data' / 'claims' / '**' / '*.yaml'),
                                                                      recursive=True))
    assert report['summary']['epoch'] == 1


def test_a_missing_snapshot_is_said_not_silently_skipped(tmp_path, capsys):
    out = tmp_path / 'near_duplicates.json'
    assert N.main(['--snapshot', str(tmp_path), '--out', str(out)]) == 2
    assert 'no Epoch snapshot' in capsys.readouterr().err and not out.exists()
    assert N.main(['--no-snapshot', '--out', str(out)]) == 0
    assert 'epoch' not in json.loads(out.read_text(encoding='utf-8'))['populations']


def test_a_second_claim_at_one_path_is_refused_not_merged(tmp_path):
    # 07 S1.4 derives a claim id from (benchmark, system, metric, subset, value, source, date_reported), where
    # source is the stanza's source_ref: the two High rows would mint one id. The writer refuses the second
    # file, so the run fails where a person sees it instead of one row replacing the other.
    rel = 'data/claims/_ingested/epoch/arc-agi-1/claim-000000000001.yaml'
    first = {'id': 'claim-000000000001', 'notes': 'Source https://arcprize.org/leaderboard'}
    emit.write(first, rel, root=str(tmp_path))
    kept = (tmp_path / rel).read_bytes()
    with pytest.raises(FileExistsError):
        emit.write({'id': 'claim-000000000001', 'notes': 'Source ARC Prize Leaderboard'}, rel, root=str(tmp_path))
    assert (tmp_path / rel).read_bytes() == kept


# ---- the real snapshot --------------------------------------------------------------------------------------

EPOCHDL = os.path.join(ROOT, 'epochdl')


@pytest.mark.skipif(not os.path.isfile(os.path.join(EPOCHDL, 'arc_agi_external.csv')),
                    reason='epochdl/ is gitignored; restore it with `python scripts/epoch_audit.py --fetch`')
def test_the_real_snapshot_pairs_the_high_rows_and_no_two_efforts():
    report = N.find(epoch.bundle_from_directory(EPOCHDL), load_all('epoch'), [])
    cluster = [m for m in report['matches'] if m['model_version'] == 'claude-opus-4-6_120K']
    assert [{r['id'] for r in m['rows']} for m in cluster] == [HIGH_PAIR]
    assert report['populations']['epoch']['files_without_stanza'] == []
    assert report['populations']['epoch']['rows'] == 6598      # 00 S8.1's row count: every row read
