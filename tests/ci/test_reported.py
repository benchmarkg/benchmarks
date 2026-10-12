"""scripts/reported.py: a reported check says what it found and never fails the job, unless the check is broken."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORTED = os.path.join(ROOT, 'scripts', 'reported.py')


def check(tmp_path, body):
    path = tmp_path / 'check.py'
    path.write_text(body, encoding='utf-8')
    return str(path)


def run(tmp_path, body):
    summary = tmp_path / 'summary.md'
    env = dict(os.environ, GITHUB_STEP_SUMMARY=str(summary))
    r = subprocess.run([sys.executable, REPORTED, '--title', 'demo check', check(tmp_path, body)], capture_output=True,
                       text=True, encoding='utf-8', env=env)
    return r.returncode, r.stdout, summary.read_text(encoding='utf-8') if summary.exists() else ''


def test_findings_are_a_warning_on_a_green_job(tmp_path):
    code, out, summary = run(tmp_path, 'import sys\nprint("3 problem(s)")\nsys.exit(1)\n')
    assert code == 0
    assert '::warning title=demo check (reported, not blocking)::3 problem(s)' in out
    assert '### demo check: reported, not blocking' in summary and '3 problem(s)' in summary


def test_a_clean_check_passes_without_a_warning(tmp_path):
    code, out, summary = run(tmp_path, 'print("0 problem(s)")\n')
    assert code == 0 and '::warning' not in out and '### demo check: holds' in summary


def test_a_broken_check_still_fails_the_job(tmp_path):
    code, out, summary = run(tmp_path, 'raise RuntimeError("boom")\n')       # exit 1, but a traceback
    assert code != 0 and '::error title=demo check::' in out and 'BROKEN' in summary
    code, out, _ = run(tmp_path, 'import sys\nsys.exit(2)\n')                # a usage error
    assert code == 2
