"""The round-trip emitter assertion (P5-S2-T06; 07 S1.5).

Done when: "Re-emission produces a zero-byte diff and a seeded float-format variant fails the check". The
repository's data/ is the first case; a throwaway tree with one float written `0.50` is the second.
"""
import os
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECK = os.path.join(ROOT, 'scripts', 'roundtrip_check.py')
CLEAN = 'id: example-bench\nname: Example Bench\nscore: 0.5\ntags:\n  - demo\n'


def run(*args):
    return subprocess.run([sys.executable, CHECK, *args], capture_output=True, text=True, encoding='utf-8')


def tree(tmp_path, text):
    p = tmp_path / 'data' / 'benchmarks' / 'code' / 'example-bench.yaml'
    p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8', newline='\n')
    return str(tmp_path)


def test_the_repository_data_round_trips_with_a_zero_byte_diff():
    r = run()
    assert r.returncode == 0, r.stdout


def test_a_clean_file_passes(tmp_path):
    assert run('--root', tree(tmp_path, CLEAN)).returncode == 0


@pytest.mark.parametrize('variant, why', [
    (CLEAN.replace('score: 0.5', 'score: 0.50'), 'a float with a trailing zero'),
    (CLEAN.replace('score: 0.5', 'score: 5.0e-1'), 'a float in exponent form'),
    (CLEAN.replace('name: Example Bench', "name: 'Example Bench'"), 'a needlessly quoted string'),
    (CLEAN.replace('tags:\n  - demo\n', 'tags: [demo]\n'), 'a flow list'),
    (CLEAN.replace('\n', '\r\n'), 'CRLF line endings'),
])
def test_a_seeded_format_variant_fails(tmp_path, variant, why):
    r = run('--root', tree(tmp_path, variant))
    assert r.returncode == 1 and 'example-bench.yaml: re-emission differs' in r.stdout, why


def test_it_runs_beside_fmt_check_in_job_1():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        body = YAML(typ='safe').load(fh)['jobs']['check-1-fmt']
    runs = [s['run'] for s in body['steps'] if 'run' in s]
    assert runs == ['uv run --locked --python "$PYTHON" bench fmt --check',
                    'uv run --locked --python "$PYTHON" python scripts/roundtrip_check.py']
