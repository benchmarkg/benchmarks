"""Retry with backoff, the way 07-ingestion-infrastructure.md S4.2 allows and no other way.

  - Only a 429 or a 5xx is retried. Every other status is returned to the caller as it came.
  - A 403 is never retried, not even once (07 S4.2): on OpenReview it is an anti-bot challenge,
    and retrying a challenge is a different legal posture from honouring a robots.txt line.
  - Three attempts in all, then SoftFail: the job stops cleanly and resumes next run.
  - The wait is the server's when it states one (Retry-After, RateLimit reset -- see
    ratelimit.py), and otherwise exponential with full jitter: uniform(0, min(cap, base * 2**n)).
  - A stated wait longer than `max_wait` is not slept out inside a job: that is a 429 storm, which
    06 S3.2 treats as a soft failure to resume next run.

"Irrespective of which layer sleeps" (07 S4.3). The wait is measured from the moment the response
arrived, against a clock, and only the part not yet elapsed is slept. If a library underneath has
already slept the RateLimit reset before handing back its 429, this layer sleeps nothing more; if
it has not, this layer sleeps all of it. Either way the next request goes out once, at the time
the server named, and never early.

`call()` performs one request and returns a Response; the clock, sleep and random source are
injectable so the policy is tested without waiting.
"""
import random
import time
from dataclasses import dataclass, field

from . import ratelimit

MAX_ATTEMPTS = 3
BASE = 1.0      # seconds
CAP = 60.0      # seconds; the jitter ceiling
MAX_WAIT = 900  # seconds; a stated wait above this soft-fails instead of sleeping


@dataclass
class Response:
    status: int
    headers: object = field(default_factory=dict)
    body: bytes = b''
    received_at: float = None  # clock() when the response arrived; set by retry() if None


class SoftFail(Exception):
    """Retries exhausted, or the server asked for a longer wait than a job may sleep."""

    def __init__(self, reason, response, attempts):
        super().__init__(reason)
        self.reason, self.response, self.attempts = reason, response, attempts


def retryable(status):
    return status == 429 or 500 <= status <= 599


def jitter(attempt, rng, base=BASE, cap=CAP):
    """Full jitter (the AWS formulation): uniform over [0, min(cap, base * 2**attempt)]."""
    return rng.uniform(0, min(cap, base * (2 ** attempt)))


def retry(call, *, clock=time.monotonic, wall=time.time, sleep=time.sleep, rng=None,
          max_attempts=MAX_ATTEMPTS, max_wait=MAX_WAIT, log=None):
    """Run call() under 07 S4.2's policy; return the first non-retryable Response."""
    rng = rng or random.Random()
    for attempt in range(max_attempts):
        resp = call()
        if resp.received_at is None:
            resp.received_at = clock()
        if resp.status == 403 or not retryable(resp.status):
            return resp
        if attempt == max_attempts - 1:
            raise SoftFail('%d after %d attempts' % (resp.status, max_attempts), resp, max_attempts)
        stated = ratelimit.wait_seconds(resp.status, resp.headers, now=wall())
        if stated is not None and stated > max_wait:
            raise SoftFail('server asked for %.0fs, over the %ds a job may wait' % (stated, max_wait),
                           resp, attempt + 1)
        wait = stated if stated is not None else jitter(attempt, rng)
        remaining = resp.received_at + wait - clock()
        if log:
            log('status %d, attempt %d: wait %.3fs (%s), %.3fs still to sleep'
                % (resp.status, attempt + 1, wait, 'stated' if stated is not None else 'jitter',
                   max(0.0, remaining)))
        if remaining > 0:
            sleep(remaining)
    raise AssertionError('unreachable')
