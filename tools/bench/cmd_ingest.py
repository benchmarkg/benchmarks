"""`bench ingest <adapter>` (P3-S1-T06; 07 S1.6, S6.2, S8.1).

    bench ingest epoch --dry-run --no-network --limit 50     # the local epochdl/ snapshot, 50 candidates
    bench ingest epoch --dry-run --fixture tests/fixtures/epoch

07 S1.6 is the sole declaration of the surface. This module wires the flags phase 0 needs -- --dry-run,
--limit, --no-network, --allow-bulk and --fixture -- for the one adapter there is, and prints 07 S6.2's
change-class summary. The replay, recompute, state and unresolved subcommands, --since, --max-runtime
and --max-drafts arrive with the tasks that build what they drive.

Where the bytes come from. --fixture replays a recorded response (ingest/http/fixture.py). Without it,
--no-network reads the unpacked snapshot at epochdl/ (07 S2: the bundle "is also already on disk at
epochdl/, so it can be developed entirely offline"). A live fetch is not built in phase 0 (07 S11.3,
"--fixture only"), so a run that is allowed the network says so and stops.

Exit codes: 0 a clean run (including no-change); 1 a hard fail -- schema drift, or a draft that does not
validate as its entity; 2 a run this phase cannot do (no --dry-run, no offline source); 3 capped, over 07
S8.1's per-type caps without --allow-bulk.
"""
from __future__ import annotations

import os
from typing import Annotated, Optional

import typer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADAPTERS = ('epoch',)
EXIT = {'ok': 0, 'no-change': 0, 'hard-fail': 1, 'capped': 3}


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
    return lines


def ingest(
    adapter: Annotated[str, typer.Argument(help='The adapter to run: %s.' % ', '.join(ADAPTERS))],
    dry_run: Annotated[bool, typer.Option('--dry-run', help='Fetch, normalise and report; write nothing.')] = False,
    limit: Annotated[Optional[int], typer.Option('--limit', min=1, help='Process at most N candidates.')] = None,
    no_network: Annotated[bool, typer.Option(
        '--no-network', help='Forbid the network; read epochdl/ unless --fixture is given.')] = False,
    allow_bulk: Annotated[bool, typer.Option(
        '--allow-bulk', help="Let one run exceed 07 S8.1's per-type caps (the first Epoch run).")] = False,
    fixture: Annotated[Optional[str], typer.Option('--fixture', help='Recorded responses in place of the network.')] = None,
):
    """Run an ingestion adapter (07 S1.6). Phase 0: --dry-run only, offline only."""
    if adapter not in ADAPTERS:
        typer.echo('ingest: no adapter %r (have: %s)' % (adapter, ', '.join(ADAPTERS)), err=True)
        raise typer.Exit(2)
    if not dry_run:
        typer.echo('ingest: writing drafts needs the differ and the resolver (P3-S3), which are not built; '
                   'run with --dry-run', err=True)
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
