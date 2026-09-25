"""The `bench` CLI (05-repository-and-workflow.md S3).

    uv run bench --help
    uv run bench validate [paths...] [--tier schema|ref|semantic|quality|all] [--changed-only] [--single] [--json]
    uv run bench schema gen [--check]

One Typer application. 05 S3's code block is the CLI's only specification -- "other documents add to
this surface, they never invent on it" -- and each subcommand arrives with the task that builds it.
tools/build/ and tools/validate/ hold the implementations, and this file only wires them to the
command line. `schema gen` is P0-S5-T01's and `validate` is P0-S5-T02's.
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


def main():
    app()


if __name__ == '__main__':
    main()
