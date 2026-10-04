"""Tests for ingest/emit.py: the adapters' YAML writer and the round-trip gate (P3-S1-T05; 07 S1.5, S8).

The verify: "Re-emission is byte-identical, so the round-trip determinism gate in 07 S8 can be
enforced." Two round trips are held here. The committed one: every YAML file under data/ re-emits to
the same bytes, comments and all (the gate itself). The adapter's: every file's DATA, loaded as plain
Python the way an adapter holds it and emitted, gives text that keeps every value and re-emits to the
same bytes again. tests/cli/test_fmt.py covers the emitter's rules one by one; these are the
properties ingestion depends on.
"""
import os
import random
import subprocess
import sys
from datetime import date

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest import emit  # noqa: E402
from tools import fmt  # noqa: E402

SAFE = YAML(typ='safe', pure=True)
CLAIM_PATH = 'data/claims/_ingested/epoch/gpqa-diamond/claim-0123456789ab.yaml'
CLAIM = {   # shaped like 07 S2.2's Epoch claim draft, keys deliberately out of model order
    'value': 0.7870000000000001,
    'system': 'example-model',
    'id': 'claim-0123456789ab',
    'benchmark': 'gpqa-diamond',
    'metric': 'accuracy',
    'date_reported': date(2026, 3, 1),
    'reported_by': 'org-epoch',
    'verification': 'third-party-run',
    'source': 'src-epoch-benchmark-data',
    'notes': 'A model named “Example”, with a colon: and a # that is not a comment.',
}


def load(text):
    return SAFE.load(text)


# ---- the committed round trip: 07 S8's gate --------------------------------------------------------

def test_every_file_under_data_re_emits_byte_identically():
    assert emit.roundtrip() == []


def test_the_gate_names_a_file_that_would_change(tmp_path, capsys):
    p = tmp_path / 'data' / 'metrics' / 'x.yaml'
    p.parent.mkdir(parents=True)
    p.write_text("sources: [src-x]\nname: 'X'\nid: x\n", encoding='utf-8')     # unordered, over-quoted, flow
    bad = emit.roundtrip(root=str(tmp_path))
    assert [rel for rel, _ in bad] == ['data/metrics/x.yaml'] and 'changes it' in bad[0][1]


def test_the_cli_check_exits_non_zero_only_on_a_failure(tmp_path, capsys):
    good = emit.write({'id': 'good', 'name': 'Good', 'definition': 'd', 'value_type': 'ratio', 'optimum': 'max',
                       'sources': ['src-x']}, 'data/metrics/good.yaml', str(tmp_path))
    root = ['--root', str(tmp_path)]
    assert emit.main(['--check', *root, good]) == 0
    assert 'every file re-emits byte-identically' in capsys.readouterr().out
    (tmp_path / 'data' / 'metrics' / 'bad.yaml').write_text("id: bad\nname: 'Bad'\n", encoding='utf-8')
    assert emit.main(['--check', *root, 'data/metrics/bad.yaml']) == 1      # a quote YAML does not need
    assert emit.main([*root, 'data/metrics/bad.yaml']) == 0                 # without --check, a report
    assert 'data/metrics/bad.yaml' in capsys.readouterr().out


def test_a_long_string_with_backslashes_keeps_its_value():
    # ruamel's double-quoted folding put a space into this text from an Epoch page (src-epoch-text-
    # arena-coding); emit() writes such a string as a literal block, which never folds
    s = ('Return only the React code. DO NOT START WITH \\`\\`\\`typescript or \\`\\`\\`javascript or '
         '\\`\\`\\`tsx or \\`\\`\\`. - ONLY IF the user asks for multiple files, return them in order.')
    text = emit.emit({'id': 'src-x', 'quote_extract': s}, 'data/sources/2026/src-x.yaml')
    assert load(text)['quote_extract'] == s and 'quote_extract: |-' in text
    assert emit.reemit(text, 'data/sources/2026/src-x.yaml') == text


def test_the_emitted_text_must_read_back_as_the_data_given(monkeypatch):
    monkeypatch.setattr(fmt, 'format_text', lambda text, model=None, name='': text.replace('0.5', '0.6'))
    with pytest.raises(fmt.FmtError, match='does not read back'):
        emit.emit(dict(CLAIM, value=0.5), CLAIM_PATH)


# ---- the adapter's round trip: plain data in, canonical text out ------------------------------------

def test_every_files_data_emitted_from_plain_python_keeps_its_values_and_re_emits_identically():
    failures = []
    for rel in fmt.files(fmt.DEFAULT_PATHS, ROOT):
        with open(os.path.join(ROOT, *rel.split('/')), encoding='utf-8') as f:
            data = load(f.read())
        text = emit.emit(data, rel)
        if load(text) != data:
            failures.append('%s: a value changed' % rel)
        elif emit.reemit(text, rel) != text or emit.emit(load(text), rel) != text:
            failures.append('%s: not a fixed point' % rel)
    assert failures == []


def test_the_bytes_do_not_depend_on_key_insertion_order():
    want = emit.emit(CLAIM, CLAIM_PATH)
    rng = random.Random(7)
    for _ in range(20):
        keys = list(CLAIM)
        rng.shuffle(keys)
        assert emit.emit({k: CLAIM[k] for k in keys}, CLAIM_PATH) == want
    assert want.startswith('id: claim-0123456789ab\nsystem: example-model\nbenchmark: gpqa-diamond\n')


def test_float_noise_is_stripped_and_real_digits_are_refused():
    assert 'value: 0.787\n' in emit.emit(CLAIM, CLAIM_PATH)
    with pytest.raises(fmt.FmtError):
        emit.emit(dict(CLAIM, value=0.12345678), CLAIM_PATH)        # rounding would change the data


@pytest.mark.parametrize('seed', ['0', '1', '4242'])
def test_the_bytes_are_the_same_in_a_fresh_interpreter(seed):
    want = emit.emit(CLAIM, CLAIM_PATH)
    code = ('import sys; sys.path.insert(0, %r)\n'
            'import datetime\n'
            'from ingest import emit\n'
            'sys.stdout.buffer.write(emit.emit(%r, %r).encode("utf-8"))' % (ROOT, CLAIM, CLAIM_PATH))
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, check=True,
                         env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONUTF8='1')).stdout.decode('utf-8')
    assert out == want


def test_the_text_is_lf_trailing_space_free_and_ends_with_one_newline():
    text = emit.emit(CLAIM, CLAIM_PATH)
    assert '\r' not in text and text.endswith('\n') and not text.endswith('\n\n')
    assert all(line == line.rstrip() for line in text.split('\n'))
    assert all(len(line) <= 100 for line in text.split('\n'))


# ---- writing -------------------------------------------------------------------------------------------

def test_write_puts_the_emitted_text_on_disk_and_never_overwrites_by_accident(tmp_path):
    rel = emit.write(CLAIM, CLAIM_PATH, str(tmp_path), header='written by a test')
    text = (tmp_path / rel).read_text(encoding='utf-8')
    assert text == '# written by a test\n' + emit.emit(CLAIM, CLAIM_PATH)
    assert emit.roundtrip([str(tmp_path / rel)], root=str(tmp_path)) == []
    with pytest.raises(FileExistsError, match='replace=True'):
        emit.write(CLAIM, CLAIM_PATH, str(tmp_path))
    emit.write(dict(CLAIM, value=0.5), CLAIM_PATH, str(tmp_path), replace=True)
    assert 'value: 0.5\n' in (tmp_path / rel).read_text(encoding='utf-8')
