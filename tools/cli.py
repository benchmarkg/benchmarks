"""The `bench` CLI (05-repository-and-workflow.md S3).

    uv run bench --help
    uv run bench new <entity> --id <id> [--domain <d>] [--from-source <url>] [--template <name>]
    uv run bench fmt [paths...] [--check]
    uv run bench validate [paths...] [--tier schema|ref|semantic|quality|all] [--changed-only] [--single] [--json]
    uv run bench schema gen [--check]
    uv run bench build [--out build/]
    uv run bench migrate <nnnn> [--dry-run|--apply]
    uv run bench check-links [PATH...] [--changed-only] [--archive-missing] [--timeout 20] [--format text|json]
    uv run bench ingest <adapter> --dry-run [--limit N] [--no-network] [--allow-bulk] [--fixture PATH]
    uv run bench report completeness|conflicts|quality [--format md|json|csv] [--out PATH]

One Typer application. 05 S3's code block is the CLI's only specification -- "other documents add to
this surface, they never invent on it" -- and each subcommand arrives with the task that builds it.
tools/build/ and tools/validate/ hold the implementations, and this file only wires them to the
command line. `schema gen` is P0-S5-T01's, `validate` P0-S5-T02's, `fmt` P0-S5-T04's (tools/fmt.py),
`new` P0-S5-T03's (tools/authoring/), `build` P0-S5-T05's (tools/build/artifacts.py; --derived writes
build/derived/ingest-health.json, P5-S7-T03's, and freshness.json, P5-S7-T04's; --embed and --atlas arrive
with their stages), `migrate`
P0-S5-T07's (tools/migrate.py) and `check-links` P0-S5-T08's (tools/links.py, tools/archive.py).
`ingest` is P3-S1-T06's (tools/bench/cmd_ingest.py; 07 S1.6 declares its surface), and `report`
P3-S1-T07's (tools/report/; three of 05 S3's seven reports, the ones Phase 3 relies on). `build` also
regenerates site/src/styles/tokens.css and site/src/lib/tokens.json from design/tokens.yaml
(P2-S2-T01, tools/build/tokens.py), and site/src/lib/taxonomy.json from taxonomy/ (P2-S2-T06,
tools/build/site_taxonomy.py). `promote`, `resolve` and `tag-gap` are P1-S2-T10's (tools/promote.py,
tools/resolve.py, tools/tag_gap.py).
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

from tools.bench.cmd_ingest import ingest as _ingest  # noqa: E402

app.command('ingest')(_ingest)


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
        if f.path.startswith('data/sources/'):
            from schema.taxonomy import read_yaml
            rec = read_yaml(os.path.join(ROOT, f.path))
            if not rec.get('doi') and not rec.get('archive_url'):
                # 06 S7.1: pending passes tier 1, and tier 3 blocks it seven days after the request
                typer.echo('  (a non-DOI Source needs an archive_url within seven days (06 S7.1): `bench archive %s`)'
                           % f.path.rsplit('/', 1)[1][:-5])
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
    derived: Annotated[bool, typer.Option('--derived', help='Also write build/derived/ (05 S3): ingest-health.json and freshness.json.')] = False,
):
    """Emit the shipped JSON artifacts (08 S4.2), drafts excluded, and regenerate the design tokens (09 S13)."""
    from tools.build import artifacts, site_taxonomy, tokens
    result = artifacts.build(ROOT)
    for e in result.errors:
        typer.echo('error  %s' % e, err=True)
    if result.errors:
        typer.echo('build: %d error(s); nothing written' % len(result.errors), err=True)
        raise typer.Exit(1)
    for path in artifacts.write(result, str(out)):
        typer.echo('wrote %s' % path)
    if derived:
        # 07 S9.1: every source's health, read from ingest/state/ and the run logs (P5-S7-T03)
        from tools.build import ingest_health
        typer.echo('wrote %s' % ingest_health.write(ROOT, str(out / 'derived' / 'ingest-health.json')))
        # 05 S7 and 06 S3.0: every entry's freshness badge and its live sources' freshness (P5-S7-T04)
        from tools.build import freshness
        typer.echo('wrote %s' % freshness.write(ROOT, str(out / 'derived' / 'freshness.json')))
    try:
        # committed files: `git diff` after a build is the drift check. A data-only tree (a test
        # corpus, a fork of data/) has no design/ and gets no tokens.
        for path in tokens.write(ROOT) if os.path.exists(os.path.join(ROOT, tokens.TOKENS)) else []:
            typer.echo('wrote %s' % path)
        # the taxonomy terms the site's components resolve (P2-S2-T06), committed on the same terms
        for path in site_taxonomy.write(ROOT) if os.path.isdir(os.path.join(ROOT, 'site')) else []:
            typer.echo('wrote %s' % path)
    except tokens.TokenError as e:
        typer.echo('error  %s' % e, err=True)
        raise typer.Exit(1)
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


class Format(str, Enum):
    text = 'text'
    json = 'json'


@app.command('check-links')
def check_links(
    paths: Annotated[Optional[list[Path]], typer.Argument(
        help='YAML files or directories to check, inside data/ or not (default: every file under data/).')] = None,
    changed_only: Annotated[bool, typer.Option(
        '--changed-only', help='Check only files changed against the merge base with origin/main.')] = False,
    archive_missing: Annotated[bool, typer.Option(
        '--archive-missing', help='Look up or request a Wayback capture for every unarchived non-DOI Source, '
        'and fail while any is unarchived.')] = False,
    timeout: Annotated[float, typer.Option('--timeout', help='Seconds per request.')] = 20,
    fmt_: Annotated[Format, typer.Option('--format', help='text or json.')] = Format.text,
):
    """HTTP-check every url in data/ (or in PATH), classify rot, and optionally queue archiving (05 S3, 06 S7)."""
    from tools import links
    try:
        named = [str(p) for p in paths] if paths else None
        report = links.run(ROOT, changed_only, archive_missing, resolver=links.default_resolver(timeout),
                           wayback=links.default_wayback(), paths=named)
    except FileNotFoundError as e:
        typer.echo('check-links: no such file or directory: %s' % e, err=True)
        raise typer.Exit(2)
    typer.echo(links.as_json(report) if fmt_ is Format.json else links.text(report))
    raise typer.Exit(report['exit_code'])


class ReportName(str, Enum):
    completeness = 'completeness'
    conflicts = 'conflicts'
    quality = 'quality'


class ReportFormat(str, Enum):
    md = 'md'
    json = 'json'
    csv = 'csv'


@app.command('report')
def report_cmd(
    name: Annotated[ReportName, typer.Argument(help='The report: completeness, conflicts or quality.')],
    fmt_: Annotated[ReportFormat, typer.Option('--format', help='md, json or csv.')] = ReportFormat.md,
    out: Annotated[Optional[Path], typer.Option('--out', help='Write here instead of stdout.')] = None,
):
    """A report over the repository (05 S3). Deterministic: a re-run gives the same bytes."""
    import importlib

    from tools import report
    text = report.render(importlib.import_module('tools.report.%s' % name.value).build(ROOT), fmt_.value)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding='utf-8', newline='\n')
        typer.echo('report: wrote %s' % out)
    else:
        typer.echo(text, nl=False)


@app.command('promote')
def promote_cmd(
    paths: Annotated[list[Path], typer.Argument(help='The records to promote, under data/.')],
    to: Annotated[str, typer.Option('--to', help="The rung to raise them to, on 05 S4's ladder.")],
    evidence: Annotated[list[str], typer.Option('--evidence', help='A cited Source id; repeat for several.')],
    by: Annotated[str, typer.Option('--by', help='Who is promoting: not the record\'s author.')],
    reviewer: Annotated[Optional[str], typer.Option(
        '--reviewer', help='The expert or maintainer who signed off (expert-reviewed, maintainer-confirmed).')] = None,
    note: Annotated[Optional[str], typer.Option('--note', help='A line for the promotion record.')] = None,
):
    """Raise curation.verification_status, recording who, when and against which evidence (05 S3)."""
    from tools import promote
    try:
        written = promote.promote([str(p) for p in paths], to, evidence, by, reviewer, note, ROOT)
    except promote.PromotionError as e:
        typer.echo('promote: refused: %s' % e, err=True)
        raise typer.Exit(1)
    for w in written:
        typer.echo('wrote %s' % w)


@app.command('resolve')
def resolve_cmd(
    paths: Annotated[Optional[list[Path]], typer.Argument(help='Drafts or other entries to compare as well.')] = None,
    candidates: Annotated[bool, typer.Option('--candidates', help='List the candidate pairs (the default).')] = True,
    threshold: Annotated[Optional[float], typer.Option(
        '--threshold', help='The cosine threshold; default the calibrated one in config/dedup.yaml.')] = None,
    pairs: Annotated[Optional[Path], typer.Option('--pairs', help='A pair file to give verdicts on instead.')] = None,
    as_json: Annotated[bool, typer.Option('--json', help='JSON, one object per pair.')] = False,
    systems: Annotated[bool, typer.Option(
        '--systems', help="Report Epoch's model_version strings that data/aliases/systems.yaml does not resolve.")] = False,
):
    """Identity resolution: same, variant-of or distinct for each pair, with its score. It never merges (05 S3).

    With --systems, the System crosswalk instead (P3-S3-T05; 07 S5.1): every distinct Epoch `Model version`
    string is resolved when the alias table holds it verbatim. Exit 1 while any is unresolved, 2 without the
    export."""
    if systems:
        from ingest import crosswalk
        try:
            left = crosswalk.unresolved(crosswalk.EPOCH, crosswalk.ROOT)
        except crosswalk.Missing as e:
            typer.echo('resolve: %s' % e, err=True)
            raise typer.Exit(2)
        for v in left:
            typer.echo('unresolved  %s' % v)
        typer.echo('resolve: %d unresolved model_version string(s); proposals in %s' % (len(left), crosswalk.BATCH),
                   err=True)
        raise typer.Exit(1 if left else 0)
    from tools import resolve
    try:
        cfg = resolve.config(threshold)
    except ValueError as e:
        typer.echo('resolve: %s' % e, err=True)
        raise typer.Exit(2)
    verdicts = resolve.resolve_pairs(str(pairs), cfg) if pairs else \
        resolve.resolve_corpus([str(p) for p in paths or []], cfg)
    if as_json:
        typer.echo(json.dumps([dict(v.__dict__, signals=list(v.signals)) for v in verdicts], indent=1))
    else:
        for v in verdicts:
            typer.echo('%-10s %s  <->  %s   cosine %.2f  name %.2f  [%s]%s' % (
                v.verdict, v.a, v.b, v.cosine, v.name, ', '.join(v.signals) or 'no signal',
                '' if v.label is None else '   label %s%s' % (v.label, '' if v.agrees else '  (DISAGREES)')))
    if pairs:
        a = resolve.agreement(verdicts)
        typer.echo('resolve: %d of %d labelled pairs agree at cosine %.2f' % (a['agree'], a['pairs'], cfg['cosine_threshold']),
                   err=as_json)
    else:
        typer.echo('resolve: %d candidate pair(s) at cosine %.2f; nothing written' % (len(verdicts), cfg['cosine_threshold']),
                   err=as_json)


@app.command('gaps')
def gaps_cmd(
    grid: Annotated[str, typer.Option('--grid', help='coarse (19 x 13, the default) or fine (refused in Phase 1).')] = 'coarse',
    reviewed_only: Annotated[bool, typer.Option(
        '--reviewed-only', help='Only families a reviewer has signed (reviewer_signoff other than none).')] = False,
    fmt_: Annotated[str, typer.Option('--format', help='md or json.')] = 'md',
):
    """The coverage grid gap claims are read from: non-empty coarse cells, each with its entry count, its terms
    and both axes' vocabulary (12 S5.1; P1-S2-T11). The gap score and what may be published are Phase 4's."""
    from tools.build import gaps
    if fmt_ not in ('md', 'json'):
        typer.echo('gaps: --format is md or json, not %r' % fmt_, err=True)
        raise typer.Exit(2)
    try:
        doc = gaps.emit(grid, ROOT, reviewed_only)
    except gaps.GridRefused as e:
        typer.echo('gaps: refused: %s' % e, err=True)
        raise typer.Exit(2)
    except ValueError as e:
        typer.echo('gaps: %s' % e, err=True)
        raise typer.Exit(2)
    if fmt_ == 'json':
        typer.echo(json.dumps(doc, indent=1, ensure_ascii=False))
    else:
        typer.echo(gaps.markdown(doc), nl=False)


@app.command('tag-gap')
def tag_gap_cmd(
    benchmark: Annotated[str, typer.Option('--benchmark', help='The benchmark id.')],
    facet: Annotated[str, typer.Option('--facet', help='The facet the source does not answer, e.g. data.access.')],
    note: Annotated[str, typer.Option('--note', help='What could not be expressed, and why.')],
    by: Annotated[str, typer.Option('--by', help='Who is logging it.')],
    kind: Annotated[str, typer.Option('--kind', help='source-silent (default), missing-term, ...')] = 'source-silent',
    blocking: Annotated[bool, typer.Option('--blocking', help='The gap blocks classifying the entry.')] = False,
    proposed_term: Annotated[Optional[str], typer.Option('--proposed-term')] = None,
):
    """Log a facet the vocabulary or the source could not answer, as a taxonomy/_failures/ entry (05 S3)."""
    from tools import tag_gap
    try:
        rel = tag_gap.tag_gap(benchmark, facet, note, by, kind, blocking, proposed_term, root=ROOT)
    except tag_gap.TagGapError as e:
        typer.echo('tag-gap: refused: %s' % e, err=True)
        raise typer.Exit(1)
    typer.echo('wrote %s' % rel)


def main():
    app()


if __name__ == '__main__':
    main()
