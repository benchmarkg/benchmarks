"""Tests for ingest/http/ratelimit.py and ingest/http/backoff.py (P5-S1-T05; 07 S4.2, S4.3).

Time is simulated: a FakeClock stands in for both time.monotonic and time.sleep, so "a 12-second
wait" is asserted exactly and the suite runs in milliseconds.
"""
import json
import os
import random
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from ingest.http import backoff, ratelimit  # noqa: E402
from ingest.http.backoff import Response, SoftFail  # noqa: E402

FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'hf-hub')


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t
        self.slept = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        assert s >= 0
        self.slept.append(s)
        self.t += s


def run(responses, clock, **kw):
    """retry() over a scripted list of (status, headers, library_sleep) and the send times."""
    sent = []
    script = list(responses)

    def call():
        sent.append(clock())
        status, headers, library_sleep = script.pop(0)
        received = clock()
        if library_sleep:  # a layer underneath sleeping before it hands back the response
            clock.t += library_sleep
        return Response(status, headers, received_at=received)

    kw.setdefault('rng', random.Random(7))
    result = backoff.retry(call, clock=clock, wall=lambda: 1_790_000_000.0, sleep=clock.sleep, **kw)
    return result, sent


# ---- the parser --------------------------------------------------------------------------------

def test_parses_the_hf_hub_headers_as_captured():
    with open(os.path.join(FIX, 'dataset-detail.json.headers.json'), encoding='utf-8') as f:
        headers = json.load(f)['headers']
    rl = ratelimit.parse(headers)
    assert (rl.limit, rl.window, rl.policy) == (500, 300, 'api')
    raw = dict(headers)['RateLimit']
    assert rl.remaining == int(raw.split('r=')[1].split(';')[0])
    assert rl.reset == int(raw.split('t=')[1])
    assert ratelimit.wait_seconds(200, headers) == 0.0  # requests left: no wait


@pytest.mark.parametrize('headers, want', [
    ({'RateLimit-Reset': '12'}, 12.0),                                        # the S4.3 case
    ({'RateLimit': 'limit=100, remaining=0, reset=12'}, 12.0),               # combined draft
    ({'RateLimit': '"api";r=0;t=12', 'RateLimit-Policy': '"api";q=500;w=300'}, 12.0),
    ({'X-RateLimit-Reset': str(1_790_000_000 + 12), 'X-RateLimit-Remaining': '0'}, 12.0),  # epoch
    ({'Retry-After': '30', 'RateLimit-Reset': '12'}, 30.0),                   # Retry-After wins
    ({'Retry-After': 'Wed, 16 Sep 2026 00:00:42 GMT'}, 42.0),                 # HTTP-date form
    ({}, None),                                                               # nothing stated
])
def test_wait_for_a_429(headers, want):
    now = 1_790_000_000.0 if 'X-RateLimit-Reset' in headers else 1_789_516_800.0  # 2026-09-16T00:00Z
    assert ratelimit.wait_seconds(429, headers, now=now) == want


def test_header_names_are_case_insensitive():
    assert ratelimit.wait_seconds(429, [('ratelimit-reset', '12')]) == 12.0


# ---- the S4.3 test: 12 seconds, whichever layer sleeps -----------------------------------------

@pytest.mark.parametrize('library_sleep', [0, 5, 12])
def test_a_synthetic_429_with_ratelimit_reset_12_waits_12_seconds(library_sleep):
    clock = FakeClock()
    result, sent = run([(429, {'RateLimit-Reset': '12'}, library_sleep), (200, {}, 0)], clock)
    assert result.status == 200
    assert sent[1] - sent[0] == 12.0  # the retry goes out exactly 12 s after the 429 arrived
    assert sum(clock.slept) == 12 - library_sleep  # and this layer sleeps only what is left


def test_a_403_is_never_retried():
    clock = FakeClock()
    result, sent = run([(403, {'Retry-After': '1'}, 0), (200, {}, 0)], clock)
    assert result.status == 403 and len(sent) == 1 and clock.slept == []


@pytest.mark.parametrize('status', [400, 401, 404, 410, 451])
def test_other_4xx_are_returned_not_retried(status):
    result, sent = run([(status, {}, 0), (200, {}, 0)], FakeClock())
    assert result.status == status and len(sent) == 1


@pytest.mark.parametrize('status', [429, 500, 502, 503, 504])
def test_three_attempts_then_soft_fail(status):
    clock = FakeClock()
    with pytest.raises(SoftFail) as e:
        run([(status, {}, 0)] * 5, clock)
    assert e.value.attempts == 3 and e.value.response.status == status
    assert len(clock.slept) == 2  # two waits between three attempts, none after the last


def test_jitter_is_full_jitter_under_the_exponential_ceiling():
    rng = random.Random(1)
    for attempt in range(6):
        ceiling = min(backoff.CAP, backoff.BASE * 2 ** attempt)
        draws = [backoff.jitter(attempt, rng) for _ in range(200)]
        assert all(0 <= d <= ceiling for d in draws)
        assert min(draws) < 0.2 * ceiling and max(draws) > 0.8 * ceiling  # spread over the range


def test_a_5xx_without_headers_backs_off_with_jitter():
    clock = FakeClock()
    result, sent = run([(503, {}, 0), (500, {}, 0), (200, {}, 0)], clock)
    assert result.status == 200
    assert 0 <= clock.slept[0] <= 1.0 and 0 <= clock.slept[1] <= 2.0


def test_a_wait_longer_than_a_job_may_sleep_soft_fails_at_once():
    clock = FakeClock()
    with pytest.raises(SoftFail, match='over the 900s'):
        run([(429, {'Retry-After': '3600'}, 0), (200, {}, 0)], clock)
    assert clock.slept == []


# ---- the package name must not break scripts run from ingest/ ----------------------------------

@pytest.mark.parametrize('argv', [['ingest/archive_sources.py', '--help'], ['-m', 'ingest.archive_sources', '--help']])
def test_ingest_http_does_not_shadow_the_standard_library(argv):
    # Run as a file, ingest/ is sys.path[0], where ingest/http/ would hide the stdlib's http.
    r = subprocess.run([sys.executable, *argv], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
