"""Parse rate-limit response headers ourselves (07-ingestion-infrastructure.md S4.3).

07 S4.3: `huggingface_hub` is reported to honour RateLimit headers, but nobody here has observed
it, "so: our own `RateLimit` header parser is implemented in the fetcher regardless, the library's
sleep is treated as an optimisation rather than the mechanism". This module is that parser. It
reads every shape the sources in 06 actually send:

  RateLimit: "api";r=496;t=105                 draft-ietf-httpapi-ratelimit-headers, structured
  RateLimit-Policy: "fixed window";"api";q=500;w=300   (as the HF Hub sends them, 2026-09-24)
  RateLimit: limit=100, remaining=0, reset=12  the earlier combined draft form
  RateLimit-Limit / -Remaining / -Reset        the earliest draft, one field each; reset in seconds
  X-RateLimit-Limit / -Remaining / -Reset      GitHub's form; reset is a Unix EPOCH, not a delta
  Retry-After: 12 | <HTTP-date>                RFC 9110, which wins when present

`wait_seconds()` turns them into the one number the fetcher needs: how long, from the moment the
response arrived, before the next request to that host may be sent.
"""
import re
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

EPOCH_THRESHOLD = 10 ** 9  # a "reset" this large is a Unix timestamp, not a number of seconds


@dataclass(frozen=True)
class RateLimit:
    limit: int = None       # requests allowed per window (q / limit)
    remaining: int = None   # requests left in this window (r / remaining)
    reset: float = None     # seconds from the response until the window resets (t / reset)
    window: int = None      # window length in seconds (w)
    policy: str = None      # the policy's name, when the server gives one ("api")
    retry_after: float = None  # Retry-After, in seconds from the response
    basis: str = None       # which header the reset came from


def _headers(headers):
    """Case-insensitive {name: value}; later duplicates are joined as a list would be."""
    items = headers.items() if hasattr(headers, 'items') else headers
    out = {}
    for k, v in items:
        k = k.lower()
        out[k] = '%s, %s' % (out[k], v) if k in out else str(v)
    return out


def _num(s):
    try:
        f = float(s)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else f


def _params(value):
    """Key=value parameters and quoted names out of one header value, leniently."""
    params, names = {}, []
    for part in re.split(r'[;,]', value):
        part = part.strip()
        if not part:
            continue
        if '=' in part:
            k, v = part.split('=', 1)
            params[k.strip().lower()] = v.strip().strip('"')
        else:
            names.append(part.strip('"'))
    return params, names


def _retry_after(value, now):
    if value is None:
        return None
    n = _num(value.strip())
    if n is not None:
        return max(0.0, float(n))
    try:
        when = parsedate_to_datetime(value.strip())
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - now) if now is not None else None


def parse(headers, now=None):
    """A RateLimit from response headers. `now` (Unix seconds) converts epoch resets and dates."""
    h = _headers(headers)
    limit = remaining = reset = window = policy = basis = None

    if 'ratelimit-policy' in h:
        params, names = _params(h['ratelimit-policy'])
        limit = _num(params.get('q'))
        window = _num(params.get('w'))
        policy = next((n for n in names if n and ' ' not in n), None)
        if limit is None and names:
            limit = _num(names[0])  # the earliest drafts: "100;w=60"

    if 'ratelimit' in h:
        params, names = _params(h['ratelimit'])
        if 'r' in params or 't' in params:          # structured draft
            remaining = _num(params.get('r'))
            reset = _num(params.get('t'))
            policy = policy or next(iter(names), None)
        else:                                        # combined draft
            limit = _num(params.get('limit')) if 'limit' in params else limit
            remaining = _num(params.get('remaining'))
            reset = _num(params.get('reset'))
        basis = 'RateLimit' if reset is not None else None

    for prefix in ('ratelimit-', 'x-ratelimit-'):
        if reset is None and prefix + 'reset' in h:
            r = _num(h[prefix + 'reset'])
            if r is not None and r >= EPOCH_THRESHOLD:
                r = max(0.0, r - now) if now is not None else None
            reset, basis = r, {'ratelimit-': 'RateLimit-Reset', 'x-ratelimit-': 'X-RateLimit-Reset'}[prefix]
        if limit is None and prefix + 'limit' in h:
            limit = _num(h[prefix + 'limit'])
        if remaining is None and prefix + 'remaining' in h:
            remaining = _num(h[prefix + 'remaining'])

    return RateLimit(limit=limit, remaining=remaining, reset=reset, window=window, policy=policy,
                     retry_after=_retry_after(h.get('retry-after'), now), basis=basis)


def wait_seconds(status, headers, now=None):
    """Seconds to wait before the next request, or None when the headers do not say.

    Retry-After wins when present (it is the server's instruction for THIS response). Otherwise a
    429, or a response reporting zero requests remaining, waits for the window reset. A success
    with requests left needs no wait at all.
    """
    rl = parse(headers, now)
    if rl.retry_after is not None:
        return rl.retry_after
    if status == 429 or rl.remaining == 0:
        return float(rl.reset) if rl.reset is not None else None
    return 0.0 if rl.remaining is not None else None
