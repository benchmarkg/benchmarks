"""Shared test setup.

The fetcher's gate (ingest/http/policy.py, P5-S2-T01): every live transport asks the process-wide gate before a
request, and the gate fetches each host's robots.txt over the network. Every test gets a fresh gate over the real
ingest/policy.yaml -- so an unlisted, forbidden or no-collect URL is refused in a test exactly as in a run -- whose
robots.txt fetch answers 404 (no robots.txt) without a socket and whose bucket never sleeps. A test of the gate
itself builds its own.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope='session')
def _policy():
    from ingest.http import policy
    return policy.Policy.load()                 # frozen: one parse serves every test's fresh gate


@pytest.fixture(autouse=True)
def _offline_gate(monkeypatch, _policy):
    from ingest.http import policy
    monkeypatch.setattr(policy, '_GATE', policy.Gate(_policy, robots=lambda url, ua: (404, ''), sleep=lambda s: None))
