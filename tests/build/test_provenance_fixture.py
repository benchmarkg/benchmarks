"""The provenance drill-down's fixture is the build's arithmetic over the committed claims (P2-S3-T02).

site/test/fixtures/provenance-claims.json is written by site/test/fixtures/make_provenance_fixture.py from
data/claims/ and tools/build/comparability.py. If a claim, a condition record or a comparability profile changes,
the committed fixture no longer says what the build would, and the page tests would pass against a stale picture.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, 'site', 'test', 'fixtures', 'make_provenance_fixture.py')


def test_the_committed_fixture_is_what_the_generator_writes_today():
    r = subprocess.run([sys.executable, SCRIPT, '--check'], capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
