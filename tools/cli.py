"""The `bench` CLI (05-repository-and-workflow.md S3).

    uv run bench --help
    uv run bench schema gen [--check]

One Typer application. 05 S3's code block is the CLI's only specification -- "other documents add to
this surface, they never invent on it" -- and each subcommand arrives with the task that builds it.
This one is P0-S5-T01's `schema gen`; tools/build/ holds the implementations, and this file only
wires them to the command line.
"""
from __future__ import annotations

import os
import sys
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


def main():
    app()


if __name__ == '__main__':
    main()
