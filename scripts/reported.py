#!/usr/bin/env python3
"""Run a check as a reported signal: say what it found, never fail the job for it (pr-validate.yml's reported jobs).

    python scripts/reported.py --title "schema freeze" scripts/check_schema_churn.py --window 40

Some checks are signals until a condition clears -- the schema freeze until the schema has held for 40 entries
(P1-S3-T09), the drafts gate until the drafts are promoted (P0-S6-T03, P1-S2-T04). A job with `continue-on-error`
still shows a red X on every pull request, which reads as a failure when it is the expected state. This runs the
check instead and:

  - prints its output, and appends it to the job summary ($GITHUB_STEP_SUMMARY) under the title;
  - when the check reports findings (exit 1), emits a `::warning::` annotation with the check's last line, so the
    pull request shows a warning on a green job, and exits 0;
  - when the check itself is broken -- any other exit code, or a Python traceback -- exits non-zero, so a reported
    job can never hide a check that does not run.

Once the condition clears, the job runs the check directly and it blocks; the tests that pin each job say when.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--title', required=True, help='what the summary and the annotation call the check')
    p.add_argument('script', help='the check to run, with this interpreter')
    p.add_argument('args', nargs=argparse.REMAINDER)
    a = p.parse_args(argv)
    r = subprocess.run([sys.executable, a.script, *a.args], capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    output = (r.stdout or '') + (r.stderr or '')
    sys.stdout.write(output)
    broken = r.returncode not in (0, 1) or 'Traceback (most recent call last)' in output
    verdict = 'BROKEN' if broken else 'holds' if r.returncode == 0 else 'reported, not blocking'
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        lines = output.rstrip().splitlines()
        with open(summary, 'a', encoding='utf-8') as fh:
            fh.write('### %s: %s\n\n```\n%s\n```\n\n' % (a.title, verdict, '\n'.join(lines[-30:])))
    if broken:
        print('::error title=%s::the check did not run cleanly (exit %d)' % (a.title, r.returncode))
        return r.returncode or 1
    if r.returncode == 1:
        last = (output.strip().splitlines() or ['findings'])[-1]
        print('::warning title=%s (reported, not blocking)::%s' % (a.title, last))
    return 0


if __name__ == '__main__':
    sys.exit(main())
