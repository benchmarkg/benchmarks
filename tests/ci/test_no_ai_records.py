"""Check 9i, no AI-written record under data/ (P0-S6-T03; 05 S9).

The verify: "`python scripts/check_no_ai_records.py` exits 0 on main and exits 1 on a fixture branch carrying an
ai-drafted-unverified record under data/ or a provenance: ai-worker field anywhere". The fixture-branch half runs
here over throwaway trees. The main half waits on the maintainer: every entry in data/ is still an agent draft (the
decision of 2026-10-12 keeps the job reported until P1-S13-T02 promotes them), so the last tests pin the job's
state to the repository's -- reported while drafts remain, and blocking the moment the check passes on main.
"""
import os
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECK = os.path.join(ROOT, 'scripts', 'check_no_ai_records.py')
CLEAN = 'id: alpha-bench\ncuration:\n  verification_status: primary-source-verified\n'


def write(root, rel, text):
    path = os.path.join(root, *rel.split('/'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def run(root):
    r = subprocess.run([sys.executable, CHECK, '--root', str(root)], capture_output=True, text=True, encoding='utf-8')
    return r.returncode, r.stdout


@pytest.fixture
def tree(tmp_path):
    write(tmp_path, 'data/benchmarks/code/alpha-bench.yaml', CLEAN)
    write(tmp_path, 'data/claims/alpha-bench/claim-000000000001.yaml', 'id: claim-000000000001\nverification: self-reported\n')
    return tmp_path


def test_a_clean_data_tree_passes(tree):
    code, out = run(tree)
    assert code == 0 and '0 AI-written record marker(s)' in out


def test_verify_an_ai_drafted_unverified_record_under_data_fails(tree):
    write(tree, 'data/benchmarks/code/beta-bench.yaml', 'id: beta-bench\ncuration:\n  verification_status: ai-drafted-unverified\n')
    code, out = run(tree)
    assert code == 1 and 'data/benchmarks/code/beta-bench.yaml:3: ai-drafted-unverified' in out


def test_verify_provenance_ai_worker_anywhere_under_data_fails(tree):
    write(tree, 'data/sources/2026/src-x.yaml', 'id: src-x\nfields:\n  - name: title\n    provenance: ai-worker\n')
    code, out = run(tree)
    assert code == 1 and 'data/sources/2026/src-x.yaml:4: provenance: ai-worker' in out


def test_drafts_and_comments_are_not_hits(tree):
    write(tree, 'drafts/benchmarks/gamma-bench.yaml', 'curation:\n  verification_status: ai-drafted-unverified\n')
    write(tree, 'data/benchmarks/code/alpha-bench.yaml', CLEAN + '# was ai-drafted-unverified until reviewed\n')
    assert run(tree)[0] == 0


def test_the_drafts_readme_says_drafts_are_never_built_published_or_citable():
    text = open(os.path.join(ROOT, 'drafts', 'README.md'), encoding='utf-8').read()
    assert 'Nothing here' in text and 'built, published or citable' in text


def job():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh)['jobs']['check-9i-no-ai-records']


BLOCKING = 'uv run --locked --python "$PYTHON" python scripts/check_no_ai_records.py'
REPORTED = ('uv run --locked --python "$PYTHON" python scripts/reported.py --title "9i no AI-written record in data/" '
            'scripts/check_no_ai_records.py')


def test_the_job_is_reported_while_drafts_remain_and_blocking_once_none_do():
    runs = [s['run'] for s in job()['steps'] if 'run' in s]
    assert 'continue-on-error' not in job()             # reported.py keeps it green; no red X on every pull request
    if run(ROOT)[0] == 0:
        assert runs == [BLOCKING], 'data/ holds no AI-written record any more: run the check directly, so it blocks'
    else:
        assert runs == [REPORTED], 'drafts remain under data/, and the decision of 2026-10-12 reports them'
