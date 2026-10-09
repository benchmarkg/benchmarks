#!/usr/bin/env python3
"""Check that authorised If-None-Match 304s do not count against GitHub's rate limit (P5-S5-T01; 06 S3.3).

    GH_API_TOKEN=... uv run python scripts/probe_conditional_requests.py [--repo OWNER/NAME] [-n 100] [--json OUT]

06 S3.3: "`If-None-Match` 304s are documented as not counting against the limit, and that single documented claim
is the entire justification for calling a weekly sweep of a few thousand repos affordable. It is therefore the
first thing `make verify-sources` checks, with a scripted probe that issues 100 conditional requests and compares
`X-RateLimit-Remaining` before and after. If the documentation is wrong, the sweep cadence drops from weekly to
monthly and the budget in 07 S10 is wrong by a factor of four."

The probe, through the GitHub adapter's own transport (so through the fetcher's gate, at one request a second):

  1. One unconditional GET of the repository: a 200 with an ETag. This one counts, and its X-RateLimit-Remaining,
     -Resource and -Reset headers are "before".
  2. N GETs of the same URL with that ETag in If-None-Match. Each must answer 304; the last one's headers are
     "after".
  3. GET /rate_limit (free) before and after, recorded as context only.

The measurement is the response headers, not /rate_limit: the headers name the bucket that request was charged
to (X-RateLimit-Resource), and /rate_limit's `core` can disagree with them -- on the first run (2026-10-09) it
read 5000 remaining both before and after while the requests' own headers read 4992 -- and its `reset` moves
with the clock while nothing is used. Confirmed when every conditional request answered 304, in the same bucket
and window as the priming 200, and Remaining did not fall: N requests, zero spent. Exit codes: 0 confirmed; 1
the claim does not hold (a 304 cost a request) -- the 07 S10 budget must be re-sized; 2 no token, or a request
failed; 3 inconclusive -- the window reset mid-probe, or another client spent from the same token, so run it
again.

What it found on 2026-10-09: confirmed on SWE-bench/SWE-bench (100 304s, Remaining 4991 throughout), on
robo-arena/roboarena and on openai/simple-evals; NOT on openai/preparedness, where every 304 was charged (10 of
10). The claim holds as a rule with exceptions, so the GitHub adapter names any repository whose 304s cost a
request (its report's `charged_304s`) rather than the budget assuming every 304 free.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest.adapters import github  # noqa: E402
from ingest.http.fixture import header  # noqa: E402

TARGET = 'SWE-bench/SWE-bench'          # 06 S3.3's own live probe
N = 100


def core(transport) -> dict:
    r = transport.get(github.API + '/rate_limit', {})          # get-default: an HTTP GET with request headers
    if r.status != 200:
        raise RuntimeError('/rate_limit answered HTTP %d' % r.status)
    c = json.loads(r.body)['resources']['core']
    return {'limit': c['limit'], 'remaining': c['remaining'], 'used': c['used'], 'reset': c['reset']}


def probe(transport, repo: str = TARGET, n: int = N) -> dict:
    url = '%s/repos/%s' % (github.API, repo)
    before = core(transport)
    first = transport.get(url, {})                              # get-default: an HTTP GET, as above
    etag = header(first.headers, 'ETag')
    if first.status != 200 or not etag:
        raise RuntimeError('the priming GET of %s answered HTTP %d%s' % (url, first.status, '' if etag else ', no ETag'))
    primed = int(header(first.headers, 'X-RateLimit-Remaining'))
    window = (header(first.headers, 'X-RateLimit-Resource'), header(first.headers, 'X-RateLimit-Reset'))
    statuses, remaining, last = [], [], None
    for _ in range(n):
        r = transport.get(url, {'If-None-Match': etag})          # get-default: an HTTP GET, as above
        statuses.append(r.status)
        left = header(r.headers, 'X-RateLimit-Remaining')
        remaining.append(int(left) if left is not None and str(left).isdigit() else None)
        last = r
    after = core(transport)
    all_304 = all(s == 304 for s in statuses)
    last_window = (header(last.headers, 'X-RateLimit-Resource'), header(last.headers, 'X-RateLimit-Reset'))
    same_window = window == last_window and remaining[-1] is not None
    spent = primed - remaining[-1] if remaining[-1] is not None else None
    if not same_window:
        verdict, code = 'inconclusive: the 304s were charged to another bucket or window (%s -> %s); run it again' % (
            window, last_window), 3
    elif all_304 and spent == 0:
        verdict, code = 'confirmed: %d conditional requests answered 304 and spent nothing' % n, 0
    elif all_304 and spent >= n:
        verdict, code = ('NOT confirmed for %s: %d 304s spent %d requests. If this holds across repositories the '
                         'weekly sweep budget in 07 S10 is wrong and the cadence drops to monthly (06 S3.3); if only '
                         'here, the adapter reports it under charged_304s' % (repo, n, spent)), 1
    elif all_304:
        verdict, code = ('inconclusive: %d spent during the probe, fewer than the %d requests made -- another '
                         'client is probably using this token; run it again' % (spent, n)), 3
    else:
        verdict, code = 'failed: not every conditional request answered 304 (%s)' % sorted(set(statuses)), 2
    return {'probe': 'conditional-requests', 'checked_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'repo': repo, 'conditional_requests': n, 'statuses': {str(s): statuses.count(s) for s in sorted(set(statuses))},
            'resource': window[0], 'reset': window[1], 'remaining_after_priming_200': primed,
            'rate_limit_core_before': before, 'rate_limit_core_after': after,
            'remaining_on_each_304': {'first': remaining[0] if remaining else None,
                                      'last': remaining[-1] if remaining else None,
                                      'distinct': sorted({x for x in remaining if x is not None})},
            'spent_by_conditional_requests': spent, 'same_window': same_window, 'verdict': verdict, 'exit_code': code}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--repo', default=TARGET)
    ap.add_argument('-n', type=int, default=N)
    ap.add_argument('--json', help='also write the result here')
    a = ap.parse_args(argv)
    token = github.token_from_env()
    if not token:
        print('probe: GH_API_TOKEN is not set; an unauthenticated 304 is not the claim being checked', file=sys.stderr)
        return 2
    try:
        result = probe(github.NetworkTransport(token), a.repo, a.n)
    except (RuntimeError, ValueError, TypeError) as e:
        print('probe: %s' % e, file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2) + '\n'
    if a.json:
        with open(a.json, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    print(text, end='')
    print('probe: %s' % result['verdict'], file=sys.stderr)
    return result['exit_code']


if __name__ == '__main__':
    sys.exit(main())
