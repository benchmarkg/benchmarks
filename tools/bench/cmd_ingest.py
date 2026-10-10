"""`bench ingest <adapter>` (P3-S1-T06; 07 S1.6, S6.2, S8.1).

    bench ingest epoch --dry-run --no-network --limit 50     # the local epochdl/ snapshot, 50 candidates
    bench ingest epoch --dry-run --fixture tests/fixtures/epoch
    bench ingest openalex --dry-run --limit 20                # live; OPENALEX_API_KEY from the environment
    bench ingest semantic-scholar --dry-run --limit 20        # live; SEMANTIC_SCHOLAR_API_KEY and OPENALEX_API_KEY
    bench ingest github --dry-run                             # live; GH_API_TOKEN from the environment
    bench ingest arxiv-oai --dry-run --since 2026-10-06       # live: set=cs from that date to today
    bench ingest swe-bench --dry-run                          # live: the leaderboard page, one conditional GET
    bench ingest lm-eval-harness --dry-run                    # live: a depth-1 fetch of the pinned commit
    bench ingest mteb-results --dry-run --fixture tests/ingest/fixtures/harness

07 S1.6 is the sole declaration of the surface. This module wires the flags phase 0 needs -- --dry-run,
--limit, --no-network, --allow-bulk and --fixture -- for the adapters there are (epoch, P3-S1-T06;
openalex, P4-S2-T06; semantic-scholar, the citation cross-check, P4-S2-T10; github, P5-S5-T01; arxiv-oai, P5-S5-T04, with --since; swe-bench, P5-S6-T03; lm-eval-harness and mteb-results, the shallow clones, P5-S5-T02), and prints 07 S6.2's change-class summary. The replay, recompute, state and
unresolved subcommands, --since, --max-runtime and --max-drafts arrive with the tasks that build what
they drive.

Where the bytes come from. --fixture replays recorded responses (ingest/http/fixture.py). Without it,
epoch's --no-network reads the unpacked snapshot at epochdl/ (07 S2: the bundle "is also already on disk
at epochdl/, so it can be developed entirely offline"); epoch's live fetch is not built in phase 0 (07
S11.3, "--fixture only"). openalex and semantic-scholar call the live APIs unless --fixture is given, and
have no local copy, so --no-network without a fixture stops. semantic-scholar's fixture directory holds one
subdirectory per API, semantic-scholar/ and openalex/.

Exit codes: 0 a clean run (including no-change); 1 a hard fail -- schema drift, or a draft that does not
validate as its entity; 2 a run this phase cannot do (no --dry-run, no offline source); 3 capped, over 07
S8.1's per-type caps without --allow-bulk; 4 a soft fail -- a 429, the daily budget spent -- which the next
run resumes.
"""
from __future__ import annotations

import os
from typing import Annotated, Optional

import typer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADAPTERS = ('epoch', 'openalex', 'semantic-scholar', 'github', 'arxiv-oai', 'swe-bench', 'lm-eval-harness', 'mteb-results')
EXIT = {'ok': 0, 'no-change': 0, 'hard-fail': 1, 'capped': 3, 'soft-fail': 4}


def _source(fixture: Optional[str], no_network: bool, root: str):
    """(bundle or None for a 304, a description), or raise typer.Exit(2) when there is nothing offline."""
    from ingest.adapters import epoch
    if fixture:
        from ingest.http.fixture import FixtureTransport
        return epoch.fetch_bundle(FixtureTransport(fixture), {}), 'fixture %s' % fixture
    if not no_network:
        typer.echo('ingest: a live fetch is not built in phase 0 (07 S11.3); pass --no-network to read '
                   'epochdl/, or --fixture PATH', err=True)
        raise typer.Exit(2)
    local = os.path.join(root, 'epochdl')
    if not os.path.isdir(local):
        typer.echo('ingest: --no-network reads epochdl/, which is not in this working tree (00 S8.1); '
                   'pass --fixture PATH', err=True)
        raise typer.Exit(2)
    return epoch.bundle_from_directory(local), 'epochdl/ (local snapshot)'


def summary(report: dict) -> list[str]:
    """07 S6.2's change classes, every one printed even at zero, then what else the run saw."""
    snap = report['snapshot']
    lines = ['ingest %s %s: %s' % (report['adapter'], report['adapter_version'], report['status'])]
    if snap:
        lines.append('  snapshot      sha256 %s, %d bytes' % (snap['artefact_sha256'], snap['artefact_bytes']))
    lines.append('  candidates    %d' % report['candidates_seen'])
    for c in ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change'):
        lines.append('  %-13s %d' % (c, report['drafts'][c]))
    lines.append('  unresolved    %d' % report['unresolved'])
    lines += ['  error: %s' % e for e in report['errors']]
    lines += ['  proposal: %s' % p for p in report.get('proposals', [])]           # get-default: epoch has none
    allowance = report.get('allowance')                                               # get-default: epoch has none
    if allowance:
        lines.append('  allowance     %s' % ', '.join('%s=%s' % kv for kv in sorted(allowance.items())))
    return lines


def _openalex(limit: Optional[int], no_network: bool, fixture: Optional[str]):
    from ingest.adapters import openalex
    if fixture:
        from ingest.http.fixture import FixtureTransport
        transport, where = FixtureTransport(fixture), 'fixture %s' % fixture
    elif no_network:
        typer.echo('ingest: openalex has no local copy to read; --no-network needs --fixture PATH', err=True)
        raise typer.Exit(2)
    else:
        key = openalex.key_from_env()
        transport = openalex.NetworkTransport(key)
        where = 'api.openalex.org (%s)' % ('OPENALEX_API_KEY set' if key else 'no key: the smaller, unauthenticated budget')
    report = openalex.run(transport, limit=limit)
    typer.echo('reading %s' % where)
    for line in summary(report):
        typer.echo(line)
    raise typer.Exit(EXIT[report['status']])


def _semantic_scholar(limit: Optional[int], no_network: bool, fixture: Optional[str]):
    from ingest.adapters import openalex, semantic_scholar
    if fixture:
        from ingest.http.fixture import FixtureTransport
        s2t = FixtureTransport(os.path.join(fixture, 'semantic-scholar'))
        oat = FixtureTransport(os.path.join(fixture, 'openalex'))
        where = 'fixture %s' % fixture
    elif no_network:
        typer.echo('ingest: semantic-scholar has no local copy to read; --no-network needs --fixture PATH', err=True)
        raise typer.Exit(2)
    else:
        s2key, oakey = semantic_scholar.key_from_env(), openalex.key_from_env()
        s2t, oat = semantic_scholar.NetworkTransport(s2key), openalex.NetworkTransport(oakey)
        where = 'api.semanticscholar.org (%s) and api.openalex.org (%s)' % (
            'SEMANTIC_SCHOLAR_API_KEY set' if s2key else 'no key: the shared, contended pool',
            'OPENALEX_API_KEY set' if oakey else 'no key')
    report = semantic_scholar.run(s2t, oat, limit=limit)
    typer.echo('reading %s' % where)
    for line in summary(report):
        typer.echo(line)
    raise typer.Exit(EXIT[report['status']])


def _github(limit: Optional[int], no_network: bool, fixture: Optional[str]):
    from ingest.adapters import github
    if fixture:
        from ingest.http.fixture import FixtureTransport
        transport, where = FixtureTransport(fixture), 'fixture %s' % fixture
    elif no_network:
        typer.echo('ingest: github has no local copy to read; --no-network needs --fixture PATH', err=True)
        raise typer.Exit(2)
    else:
        token = github.token_from_env()
        transport = github.NetworkTransport(token)
        where = 'api.github.com (%s)' % ('GH_API_TOKEN set' if token else 'no token: 60 requests an hour')
    report = github.run(github.GitHub(transport), limit=limit)
    typer.echo('reading %s' % where)
    for line in summary(report):
        typer.echo(line)
    raise typer.Exit(EXIT[report['status']])


def _arxiv(limit: Optional[int], no_network: bool, fixture: Optional[str], since: Optional[str]):
    from datetime import date, datetime, timezone

    from ingest.adapters import arxiv_oai
    start = date.fromisoformat(since) if since else None
    if fixture:
        from ingest.http.fixture import FixtureTransport
        if start is None:
            typer.echo('ingest: an arxiv-oai fixture holds one recorded window; name its day with --since', err=True)
            raise typer.Exit(2)
        transport, until, where = FixtureTransport(fixture), start, 'fixture %s' % fixture
    elif no_network:
        typer.echo('ingest: arxiv-oai has no local copy to read; --no-network needs --fixture PATH', err=True)
        raise typer.Exit(2)
    else:
        transport, until = arxiv_oai.NetworkTransport(), datetime.now(timezone.utc).date()
        where = 'oaipmh.arxiv.org set=cs, %s to %s' % (start or until, until)
    state = arxiv_oai.new_state()
    if start is not None and (start == until or fixture):
        state['last_until'] = start.isoformat()          # one window, not a month-by-month backfill
    report = arxiv_oai.run(arxiv_oai.ArxivOai(transport, until, backfill_from=start), state, limit=limit)
    typer.echo('reading %s' % where)
    for line in summary(report):
        typer.echo(line)
    typer.echo('  records       %s' % ', '.join('%s=%d' % kv for kv in report['records'].items()))
    raise typer.Exit(EXIT[report['status']])


def _swebench(no_network: bool, fixture: Optional[str]):
    from ingest.adapters import swebench
    if fixture:
        from ingest.http.fixture import FixtureTransport
        transport, where = FixtureTransport(fixture), 'fixture %s' % fixture
    elif no_network:
        typer.echo('ingest: swe-bench has no local copy to read (its page may not be kept, 07 S4.4); '
                   '--no-network needs --fixture PATH', err=True)
        raise typer.Exit(2)
    else:
        transport, where = swebench.NetworkTransport(), swebench.PAGE_URL
    report = swebench.run(swebench.SweBench(transport), swebench.new_state())
    typer.echo('reading %s' % where)
    for line in summary(report):
        typer.echo(line)
    if report['counts']:
        typer.echo('  results       %s (%d)' % (', '.join('%s=%d' % kv for kv in report['counts'].items()),
                                                sum(report['counts'].values())))
    if report['unresolved_by_field']:
        typer.echo('  unresolved by %s' % ', '.join('%s=%d' % kv for kv in sorted(report['unresolved_by_field'].items())))
    for a in report['anomalies']:
        typer.echo('  ANOMALY: %s (needs-scrutiny; nothing is gone)' % a)
    raise typer.Exit(EXIT[report['status']])


def _clone(name: str, limit: Optional[int], no_network: bool, fixture: Optional[str]):
    import tempfile

    from ingest.adapters import github_clones as G
    if not fixture and no_network:
        typer.echo('ingest: %s has no local copy to read; --no-network needs --fixture PATH' % name, err=True)
        raise typer.Exit(2)
    with tempfile.TemporaryDirectory() as work:
        if fixture:
            source = G.fixture_source(os.path.join(fixture, G.FIXTURE_DIRS[name]), work)
            where = 'fixture %s' % os.path.join(fixture, G.FIXTURE_DIRS[name])
        else:
            source, where = None, '%s at %s (depth 1)' % (G.PINS[name].url, G.PINS[name].pin[:12])
        report = G.run(G.ADAPTERS[name](source), G.new_state(), limit=limit)
    typer.echo('reading %s' % where)
    for line in summary(report):
        typer.echo(line)
    if report['counts']:
        typer.echo('  tree          %s' % ', '.join('%s=%d' % kv for kv in report['counts'].items()))
    if report['snapshot']:
        typer.echo('  commit        %s' % report['snapshot']['commit'])
    raise typer.Exit(EXIT[report['status']])


def ingest(
    adapter: Annotated[str, typer.Argument(help='The adapter to run: %s.' % ', '.join(ADAPTERS))],
    dry_run: Annotated[bool, typer.Option('--dry-run', help='Fetch, normalise and report; write nothing.')] = False,
    limit: Annotated[Optional[int], typer.Option('--limit', min=1, help='Process at most N candidates.')] = None,
    no_network: Annotated[bool, typer.Option(
        '--no-network', help='Forbid the network; read epochdl/ unless --fixture is given.')] = False,
    allow_bulk: Annotated[bool, typer.Option(
        '--allow-bulk', help="Let one run exceed 07 S8.1's per-type caps (the first Epoch run).")] = False,
    fixture: Annotated[Optional[str], typer.Option('--fixture', help='Recorded responses in place of the network.')] = None,
    since: Annotated[Optional[str], typer.Option('--since', help='arxiv-oai: harvest from this date (YYYY-MM-DD).')] = None,
):
    """Run an ingestion adapter (07 S1.6). Phase 0: --dry-run only, offline only."""
    if adapter not in ADAPTERS:
        typer.echo('ingest: no adapter %r (have: %s)' % (adapter, ', '.join(ADAPTERS)), err=True)
        raise typer.Exit(2)
    if not dry_run:
        typer.echo('ingest: writing drafts needs the differ and the resolver (P3-S3), which are not built; '
                   'run with --dry-run', err=True)
        raise typer.Exit(2)
    if adapter == 'openalex':
        _openalex(limit, no_network, fixture)
    if adapter == 'semantic-scholar':
        _semantic_scholar(limit, no_network, fixture)
    if adapter == 'github':
        _github(limit, no_network, fixture)
    if adapter == 'arxiv-oai':
        _arxiv(limit, no_network, fixture, since)
    if adapter == 'swe-bench' and not since:
        _swebench(no_network, fixture)
    if adapter in ('lm-eval-harness', 'mteb-results') and not since:
        _clone(adapter, limit, no_network, fixture)
    if since:
        typer.echo('ingest: --since belongs to arxiv-oai', err=True)
        raise typer.Exit(2)
    from ingest.adapters import epoch
    try:
        bundle, where = _source(fixture, no_network, ROOT)
    except (epoch.FetchError, epoch.BundleError) as e:
        typer.echo('ingest: %s: %s' % (type(e).__name__, e), err=True)
        raise typer.Exit(1)
    report = epoch.run(bundle, limit=limit, allow_bulk=allow_bulk)
    typer.echo('reading %s' % where)
    for line in summary(report):
        typer.echo(line)
    raise typer.Exit(EXIT[report['status']])
