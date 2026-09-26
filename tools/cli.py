"""The `bench` CLI (05-repository-and-workflow.md S3).

    uv run bench --help
    uv run bench new <entity> --id <id> [--domain <d>] [--from-source <url>] [--template <name>]
    uv run bench fmt [paths...] [--check]
    uv run bench validate [paths...] [--tier schema|ref|semantic|quality|all] [--changed-only] [--single] [--json]
    uv run bench schema gen [--check]
    uv run bench build [--out build/]
    uv run bench migrate <nnnn> [--dry-run|--apply]

One Typer application. 05 S3's code block is the CLI's only specification -- "other documents add to
this surface, they never invent on it" -- and each subcommand arrives with the task that builds it.
tools/build/ and tools/validate/ hold the implementations, and this file only wires them to the
command line. `schema gen` is P0-S5-T01's, `validate` P0-S5-T02's, `fmt` P0-S5-T04's (tools/fmt.py),
`new` P0-S5-T03's (tools/authoring/), `build` P0-S5-T05's (tools/build/artifacts.py; the minimal
build, without 05 S3's --derived, --embed and --atlas, which arrive with their stages) and `migrate`
P0-S5-T07's (tools/migrate.py).
"""
from __future__ import annotations

import json
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.build import codegen  # noqa: E402

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help='The benchmark catalogue toolchain (05 S3).')
schema_app = typer.Typer(no_args_is_help=True, help='The canonical schema and its generated artifacts.')
app.add_typer(schema_app, name='schema')


@schema_app.callback()
def _schema():
    """The canonical schema and its generated artifacts."""


@schema_app.command('gen')
def schema_gen(
    check: Annotated[bool, typer.Option('--check', help='Regenerate in memory and fail on any difference.')] = False,
    json2ts: Annotated[Optional[Path], typer.Option(
        help='The json-schema-to-typescript package directory (default: site/node_modules/...).')] = None,
):
    """Regenerate schema/generated/*.schema.json and site/src/types/*.d.ts from the Pydantic models."""
    j2t = str(json2ts) if json2ts else None
    if check:
        problems = codegen.drift(ROOT, j2t)
        for p in problems:
            typer.echo(p, err=True)
        if problems:
            typer.echo('schema gen --check: %d generated file(s) out of date; run `bench schema gen` and commit '
                       'the result' % len(problems), err=True)
            raise typer.Exit(1)
        typer.echo('schema gen --check: generated artifacts match the models and taxonomy/')
        return
    changed = codegen.write(ROOT, j2t)
    typer.echo('schema gen: %d file(s) written' % len(changed) if changed else 'schema gen: up to date')


@app.command('new')
def new_cmd(
    entity: Annotated[str, typer.Argument(help='What to scaffold: benchmark or source.')],
    ident: Annotated[str, typer.Option('--id', help='The new id (05 S2).')],
    domain: Annotated[Optional[str], typer.Option(
        '--domain', help='A benchmark\'s domain.primary: a subdomain from taxonomy/domains.yaml.')] = None,
    from_source: Annotated[Optional[str], typer.Option(
        '--from-source', help='The source URL; for a benchmark, its homepage, with a Source scaffolded beside it.')] = None,
    template: Annotated[Optional[str], typer.Option(
        '--template', help='A template in tools/authoring/templates/ other than <entity>.yaml.')] = None,
):
    """Scaffold an entity file from a template, every required field stubbed and commented (05 S3)."""
    from tools.authoring import new
    from tools.validate import tiers
    try:
        files = new.scaffold(entity, ident, ROOT, domain=domain, from_source=from_source, template=template)
    except new.NewError as e:
        typer.echo('new: %s' % e, err=True)
        raise typer.Exit(2)
    for f in files:
        report = tiers.single(os.path.join(ROOT, f.path), 'schema', ROOT)
        typer.echo('wrote %s -- tier 1: %s' % (f.path, 'ok' if not report.blocking else '%d finding(s)'
                                                % len(report.blocking)))
        for finding in report.blocking:
            typer.echo('  ' + str(finding))
        if f.path.startswith('data/sources/') and report.blocking:
            typer.echo('  (a non-DOI Source passes tier 1 once it is archived: `bench archive %s`)' % f.path.rsplit('/', 1)[1][:-5])
    typer.echo('next: replace every TODO and STUB VALUE from a cited source, then remove the %s tag; '
               '`bench validate %s` lists what remains' % (new.STUB_TAG, files[0].path))


@app.command('fmt')
def fmt_cmd(
    paths: Annotated[Optional[list[Path]], typer.Argument(help='Files or directories (default: data/).')] = None,
    check: Annotated[bool, typer.Option('--check', help='Write nothing; exit 1 if any file would change.')] = False,
):
    """Normalise YAML key order, quoting, line width and list style (05 S1; 07 S1.5)."""
    from tools import fmt
    changed, errors = fmt.run([str(p) for p in paths] if paths else None, check, ROOT)
    for rel in changed:
        typer.echo(('would reformat  %s' if check else 'reformatted  %s') % rel, err=check)
    for e in errors:
        typer.echo('error  %s' % e, err=True)
    if check and changed:
        typer.echo('fmt --check: %d file(s) would change; run `bench fmt` and commit the result' % len(changed), err=True)
    elif not changed and not errors:
        typer.echo('fmt: %s' % ('every file is formatted' if check else 'nothing to change'))
    raise typer.Exit(1 if errors or (check and changed) else 0)


class Tier(str, Enum):
    schema = 'schema'
    ref = 'ref'
    semantic = 'semantic'
    quality = 'quality'
    all = 'all'


@app.command('validate')
def validate(
    paths: Annotated[Optional[list[Path]], typer.Argument(
        help='Report only on these files or directories (the whole corpus is still read).')] = None,
    tier: Annotated[Tier, typer.Option('--tier', help='One tier, or all four.')] = Tier.all,
    changed_only: Annotated[bool, typer.Option(
        '--changed-only', help='Report only on files changed against the merge base with origin/main.')] = False,
    single: Annotated[bool, typer.Option(
        '--single', help='Validate one file with no corpus load (what the issue-intake bot calls).')] = False,
    as_json: Annotated[bool, typer.Option('--json', help='Print the report as JSON.')] = False,
):
    """The four validation tiers (04 S12). Tiers 1-3 block; tier 4, quality, is report-only."""
    from tools.validate import tiers
    if single:
        if changed_only or not paths or len(paths) != 1:
            typer.echo('--single takes exactly one path and no --changed-only', err=True)
            raise typer.Exit(2)
        report = tiers.single(str(paths[0]), tier.value, ROOT)
    else:
        try:
            report = tiers.run(ROOT, tier.value, [str(p) for p in paths] if paths else None, changed_only)
        except (OSError, tiers.subprocess.CalledProcessError) as e:
            typer.echo('validate: could not list changed files: %s' % e, err=True)
            raise typer.Exit(2)
    if as_json:
        typer.echo(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    else:
        for f in report.findings:
            typer.echo(str(f))
        for note in report.not_checked:
            typer.echo('not checked: ' + note)
        typer.echo(report.summary())
    raise typer.Exit(report.exit_code)


@app.command('build')
def build_cmd(
    out: Annotated[Path, typer.Option('--out', help='The output directory (gitignored).')] = Path('build'),
):
    """Emit the shipped JSON artifacts (08 S4.2): today corpus.json and facets.json, drafts excluded."""
    from tools.build import artifacts
    result = artifacts.build(ROOT)
    for e in result.errors:
        typer.echo('error  %s' % e, err=True)
    if result.errors:
        typer.echo('build: %d error(s); nothing written' % len(result.errors), err=True)
        raise typer.Exit(1)
    for path in artifacts.write(result, str(out)):
        typer.echo('wrote %s' % path)
    counts = result.counts()
    reasons: dict[str, int] = {}
    for _, _, reason in result.excluded:
        reasons[reason] = reasons.get(reason, 0) + 1  # get-default: a first reason starts its count
    typer.echo('build: published %s; %d subset(s) materialised; excluded %s'
               % (', '.join('%d %s' % (n, k) for k, n in counts.items()), len(result.corpus['subsets']),
                  ', '.join('%d (%s)' % (n, r) for r, n in sorted(reasons.items())) or 'nothing'))


@app.command('migrate')
def migrate_cmd(
    number: Annotated[str, typer.Argument(help='The migration and its ADR number, e.g. 0027.')],
    dry_run: Annotated[bool, typer.Option('--dry-run', help='Report the rows it would touch (the default).')] = False,
    apply: Annotated[bool, typer.Option('--apply', help='Write them; needs adr/<nnnn>-*.md.')] = False,
):
    """Run a taxonomy migration from schema/migrations/<nnnn>-<slug>.py across the corpus (03 S9)."""
    from tools import migrate
    if dry_run and apply:
        typer.echo('migrate: --dry-run and --apply are exclusive', err=True)
        raise typer.Exit(2)
    try:
        m = migrate.find(number)
        rows = m.plan(ROOT)
        adr = migrate.adr_for(number, ROOT)
    except migrate.MigrateError as e:
        typer.echo('migrate: %s' % e, err=True)
        raise typer.Exit(1)
    files = sorted({r.path for r in rows})
    typer.echo('migration %s (%s): %s' % (number, m.kind, m.summary))
    typer.echo('  script: %s' % os.path.relpath(m.path, ROOT).replace(os.sep, '/'))
    typer.echo('  adr:    %s' % ('%s (Status: %s)' % (adr, migrate.adr_status(ROOT, adr)) if adr
                                 else 'none -- --apply refuses until adr/%s-*.md exists' % number))
    typer.echo('plan: %d row(s) in %d file(s)' % (len(rows), len(files)))
    for r in rows:
        typer.echo('  %s  %s: %r -> %r' % (r.path, r.where(), r.old, r.new))
    if m.kind == 'split':
        typer.echo('a split: every row writes a publication-blocking sentinel, and --apply needs a human at a '
                   'terminal (03 S9.1)')
    if not apply:
        typer.echo('dry run: nothing written')
        return

    def confirm(mig, planned):
        answer = typer.prompt('This split writes %d sentinel(s) that block publication until each entry is '
                              're-adjudicated against its primary source. Type %s to proceed' % (len(planned), mig.number),
                              default='', show_default=False)
        return answer.strip() == mig.number
    try:
        written = migrate.apply(m, ROOT, confirm)
    except (migrate.MigrateError, ValueError) as e:
        typer.echo('migrate: %s' % e, err=True)
        raise typer.Exit(1)
    for rel in written:
        typer.echo('wrote %s' % rel)
    typer.echo('applied %d row(s) to %d file(s); next: `bench validate --tier all`%s' % (
        len(rows), len(written), ', and open the tracking issue listing every affected file (03 S9.1)'
        if m.kind == 'split' else ''))


def main():
    app()


if __name__ == '__main__':
    main()
