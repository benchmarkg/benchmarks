"""The `bench` CLI (05-repository-and-workflow.md S3).

    uv run bench --help
    uv run bench new <entity> --id <id> [--domain <d>] [--from-source <url>] [--template <name>]
    uv run bench fmt [paths...] [--check]
    uv run bench validate [paths...] [--tier schema|ref|semantic|quality|all|<comma list>] [--changed-only] [--single] [--json]
    uv run bench schema gen [--check]
    uv run bench build [--derived] [--embed] [--atlas] [--data-only] [--out build/]
    uv run bench migrate <nnnn> [--dry-run|--apply]
    uv run bench check-links [PATH...] [--changed-only] [--archive-missing] [--timeout 20] [--format text|json]
    uv run bench ingest <adapter> --dry-run [--limit N] [--no-network] [--allow-bulk] [--fixture PATH]
    uv run bench report completeness|conflicts|quality [--format md|json|csv] [--out PATH]
    uv run bench eval [--split <name>|all] [--report] [--judge] [--holdout N]

One Typer application. 05 S3's code block is the CLI's only specification -- "other documents add to
this surface, they never invent on it" -- and each subcommand arrives with the task that builds it.
tools/build/ and tools/validate/ hold the implementations, and this file only wires them to the
command line. `schema gen` is P0-S5-T01's, `validate` P0-S5-T02's (its `--tier` takes a comma list since
P2-S6-T04, whose issue-intake bot runs `--single --tier schema,ref,semantic`), `fmt` P0-S5-T04's (tools/fmt.py),
`new` P0-S5-T03's (tools/authoring/), `build` P0-S5-T05's (tools/build/artifacts.py; --derived writes
build/derived/ingest-health.json, P5-S7-T03's, freshness.json, P5-S7-T04's, coverage-states.json,
P1-S12-T08's, and comparability-keys.json, P3-S10-T02's (tools/build/comparability.py); --atlas writes
build/atlas.json, P2-S5-T01's (tools/atlas/); --embed writes build/vectors.i8.bin
and build/vectors.meta.json, P6-S1-T03's (tools/build/embed.py, with the `embed` extra); build/index.sqlite, the
normalised corpus that never ships, is P2-S1-T06's, tools/build/sqlite.py;
--data-only, the preview build that skips S9, S10 and the SQLite emission, is P2-S1-T04's, tools/build/modes.py, beside
scripts/routes_from_diff.py), `migrate`
P0-S5-T07's (tools/migrate.py) and `check-links` P0-S5-T08's (tools/links.py, tools/archive.py).
`ingest` is P3-S1-T06's (tools/bench/cmd_ingest.py; 07 S1.6 declares its surface), and `report`
P3-S1-T07's (tools/report/; three of 05 S3's seven reports, the ones Phase 3 relies on; `staleness`, the
re-verification queue, is P5-S7-T05's). `build` also
regenerates site/src/styles/tokens.css and site/src/lib/tokens.json from design/tokens.yaml
(P2-S2-T01, tools/build/tokens.py), and site/src/lib/taxonomy.json from taxonomy/ (P2-S2-T06,
tools/build/site_taxonomy.py), and writes build/croissant-benchmark/, validated with mlcroissant and the extension
schema before anything is written (P2-S3-T06, tools/build/croissant.py). `promote`, `resolve` and `tag-gap` are
P1-S2-T10's (tools/promote.py, tools/resolve.py, tools/tag_gap.py). `gaps` is P1-S2-T11's (tools/build/gaps.py), and
its gap matrix and `--min-confidence` P1-S14-T08's: `bench gaps --grid coarse --reviewed-only --format json >
build/derived/gaps.json`, checked by scripts/check_gap_claims.py. `eval` is P6-S3-T09's (tools/evals/; 11 S7): the
golden set pooled, graded and written to evals/results/<date>-<commit>.json.
"""
from __future__ import annotations

import datetime as _dt
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
    """Regenerate schema/generated/*.schema.json, site/src/types/*.d.ts and the croissant-benchmark context."""
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


def _tiers(value: str):
    """`--tier`: one tier, `all`, or a comma list such as `schema,ref,semantic` (the issue-intake bot's, P2-S6-T04)."""
    names = [v.strip() for v in str(value).split(',') if v.strip()]
    if not names or any(n not in Tier.__members__ for n in names) or ('all' in names and len(names) > 1):
        raise typer.BadParameter('%r: give one of %s, or a comma list of the first four'
                                 % (value, ', '.join(t.value for t in Tier)), param_hint="'--tier'")
    return 'all' if names == ['all'] else names


@app.command('validate')
def validate(
    paths: Annotated[Optional[list[Path]], typer.Argument(
        help='Report only on these files or directories (the whole corpus is still read).')] = None,
    tier: Annotated[str, typer.Option(
        '--tier', help='One tier (schema, ref, semantic, quality), all four (all), or a comma list: '
                       'schema,ref,semantic.')] = 'all',
    changed_only: Annotated[bool, typer.Option(
        '--changed-only', help='Report only on files changed against the merge base with origin/main.')] = False,
    single: Annotated[bool, typer.Option(
        '--single', help='Validate one file with no corpus load (what the issue-intake bot calls).')] = False,
    as_json: Annotated[bool, typer.Option('--json', help='Print the report as JSON.')] = False,
):
    """The four validation tiers (04 S12). Tiers 1-3 block; tier 4, quality, is report-only."""
    from tools.validate import tiers
    selected = _tiers(tier)
    if single:
        if changed_only or not paths or len(paths) != 1:
            typer.echo('--single takes exactly one path and no --changed-only', err=True)
            raise typer.Exit(2)
        report = tiers.single(str(paths[0]), selected, ROOT)
    else:
        try:
            report = tiers.run(ROOT, selected, [str(p) for p in paths] if paths else None, changed_only)
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
    derived: Annotated[bool, typer.Option('--derived', help='Also write build/derived/ (05 S3): ingest-health.json, freshness.json, coverage-states.json, lineage.json and comparability-keys.json.')] = False,
    embed: Annotated[bool, typer.Option('--embed', help='Also write build/vectors.i8.bin and build/vectors.meta.json, the int8 document embeddings in facets.json order (08 S3.2 S6, 11 S4). Needs the embed extra and the cached model: tools/build/embed.py.')] = False,
    atlas: Annotated[bool, typer.Option('--atlas', help='Also write build/atlas.json, the deterministic pack layout (08 S5.3, 10 V1).')] = False,
    data_only: Annotated[bool, typer.Option('--data-only', help='The preview build (08 S3.4): skip the S9 release artifacts (croissant-benchmark/, index.sqlite) and S10 codegen (the design tokens, the site taxonomy).')] = False,
):
    """Emit the shipped JSON artifacts (08 S4.2), their content-hashed copies and build-manifest.json (08 S4.4, S6.1),
    the croissant-benchmark JSON-LD (08 S5.8) and index.sqlite (08 S4.2), drafts excluded, and regenerate the design
    tokens (09 S13). --data-only skips the last three (08 S3.4; tools/build/modes.py)."""
    from tools.build import artifacts, modes, site_taxonomy, tokens
    result = artifacts.build(ROOT)
    for e in result.errors:
        typer.echo('error  %s' % e, err=True)
    if result.errors:
        typer.echo('build: %d error(s); nothing written' % len(result.errors), err=True)
        raise typer.Exit(1)
    if embed:
        # S6 (P6-S1-T03) is computed before anything is written, so a model that is not cached fails a build that has
        # written nothing; its two files are written with --atlas's, below
        from tools.build import embed as embedder
        try:
            vectors = embedder.build(result.corpus, result.facets, embedder.encoder())
        except embedder.EmbedError as e:
            typer.echo('error  %s' % e, err=True)
            typer.echo('build: --embed failed; nothing written', err=True)
            raise typer.Exit(1)
    # 08 S5.8 (P2-S3-T06): the croissant-benchmark JSON-LD, validated before anything is written -- mlcroissant base
    # conformance and the committed extension schema, over the withheld drafts' documents too -- so a mapping or
    # schema change that breaks either fails this build, which is CI's build step
    from tools.build import croissant
    if not data_only:                                   # S9, which --data-only skips (P2-S1-T04)
        documents, problems, summary = croissant.build(result.corpus, result.withheld, conditions=result.conditions)
        for e in problems:
            typer.echo('error  %s' % e, err=True)
        if problems:
            typer.echo('build: %d croissant-benchmark problem(s); nothing written' % len(problems), err=True)
            raise typer.Exit(1)
    shipped = artifacts.write(result, str(out))
    for path in shipped:
        typer.echo('wrote %s' % path)
    if data_only:
        # ---- --data-only (P2-S1-T04) ------------------------------------------------------------------------------
        # 08 S3.4: S9 and the SQLite emission are a release's, not a preview's. What a full build left in --out goes, so
        # the directory and its manifest never pair this corpus with another build's documents or database
        for path in modes.clear(str(out)):
            typer.echo("removed %s (a full build's S9 output; --data-only writes none)" % path)
        # ---- end --data-only --------------------------------------------------------------------------------------
    else:
        croissant.write(documents, str(out / croissant.DIR))
        typer.echo('wrote %s (%d benchmark document(s) and the collection; %d withheld draft(s) validated, not written; '
                   'mlcroissant %s, %d recommended-property notice(s))'
                   % (out / croissant.DIR, summary['written'], summary['withheld'], summary['mlcroissant'],
                      summary['notices']))
        # ---- index.sqlite (P2-S1-T06) -------------------------------------------------------------------------------
        # 08 S4.2: the whole corpus, normalised, for build-time analytics and the release archive. It sits beside the
        # artifacts it is built from and is never shipped: not under data/, not in the manifest's paths, and nothing
        # copies --out into the site (tools/build/sqlite.py)
        from tools.build import sqlite
        try:
            typer.echo('wrote %s' % sqlite.write({'corpus.json': result.corpus, 'facets.json': result.facets,
                                                  'enums.json': result.enums}, str(out / sqlite.NAME)))
        except sqlite.SqliteError as e:
            typer.echo('error  %s' % e, err=True)
            raise typer.Exit(1)
        # ---- end index.sqlite ---------------------------------------------------------------------------------------
    # SUCCESSION.md item 5: the date of the last human commit to data/, which the site's banner reads (P0-S7-T04)
    from tools import dormancy
    typer.echo('wrote %s' % dormancy.write(dormancy.state(dormancy.last_human_commit(ROOT), _dt.date.today()),
                                          str(out / 'dormancy.json')))
    # ---- --atlas (P2-S5-T01) ----------------------------------------------------------------------------------------
    # build/atlas.json over the published corpus: the pack layout, the shipping Atlas for public v1 (08 S5.3, 10 V1)
    if atlas:
        from tools.atlas import emit as atlas_emit
        try:
            written = atlas_emit.write(atlas_emit.build(result.corpus, ROOT), str(out))
            typer.echo('wrote %s' % written)
            shipped.append(written)                              # hashed and named in the manifest with the rest
        except atlas_emit.AtlasError as e:
            typer.echo('error  %s' % e, err=True)
            raise typer.Exit(1)
    # ---- end --atlas ------------------------------------------------------------------------------------------------
    # ---- --embed (P6-S1-T03) ----------------------------------------------------------------------------------------
    # S6 (08 S3.2): one int8 vector per published benchmark family, in facets.json order, from the pinned model in the
    # local cache; never the network. Not in the manifest's `shipped`: it hashes canonical JSON only (tools/build/embed.py)
    if embed:
        for path in embedder.write(vectors, str(out)):
            typer.echo('wrote %s' % path)
        typer.echo('embedded %d benchmark famil%s with %s@%s (%d dims, int8, one scale per row)'
                   % (len(vectors.ids), 'y' if len(vectors.ids) == 1 else 'ies', vectors.meta['model']['id'],
                      vectors.meta['model']['revision'][:12], vectors.meta['dims']))
    # ---- end --embed ------------------------------------------------------------------------------------------------
    if derived:
        # 07 S9.1: every source's health, read from ingest/state/ and the run logs (P5-S7-T03)
        from tools.build import ingest_health
        typer.echo('wrote %s' % ingest_health.write(ROOT, str(out / 'derived' / 'ingest-health.json')))
        # 05 S7 and 06 S3.0: every entry's freshness badge and its live sources' freshness (P5-S7-T04)
        from tools.build import freshness
        typer.echo('wrote %s' % freshness.write(ROOT, str(out / 'derived' / 'freshness.json')))
        # 02 S3 and 02 S11 rule 6: every subdomain page's and coarse cell's state, surveyed-and-empty only
        # behind a dated survey note in data/surveys/ (P1-S12-T08)
        from tools.build import coverage_states
        typer.echo('wrote %s' % coverage_states.write(ROOT, str(out / 'derived' / 'coverage-states.json')))
        # 10 V6 section 11: each published benchmark's lineage as a build-time SVG and its table (P2-S3-T03)
        from tools.build import lineage_svg
        typer.echo('wrote %s' % lineage_svg.write(result.corpus, str(out / 'derived' / 'lineage.json')))
        # 04 S8: every claim's comparability_key, key_unknown_count and condition_completeness, beside each curated
        # benchmark's resolved profile and weights (P3-S10-T02)
        from tools.build import comparability
        typer.echo('wrote %s' % comparability.write(ROOT, str(out / 'derived' / 'comparability-keys.json')))
    # 08 S4.4 and S6.1 (P2-S1-T05): each shipped artifact at /data/<name>.<sha8>.json, and the manifest naming them;
    # `python tools/build/manifest.py --site <dist>` completes it after the site build (S13)
    from tools.build import manifest
    try:
        hashed = manifest.write(str(out), shipped, None if data_only else str(out / croissant.DIR))
    except manifest.ManifestError as e:
        typer.echo('error  %s' % e, err=True)
        raise typer.Exit(1)
    typer.echo('wrote %s (%d content-hashed artifact(s) under %s)' % (hashed[-1], len(hashed) - 1, out / 'data'))
    try:
        # S10, which --data-only skips (P2-S1-T04): a preview reads the committed copies.
        # committed files: `git diff` after a build is the drift check. A data-only tree (a test
        # corpus, a fork of data/) has no design/ and gets no tokens.
        for path in tokens.write(ROOT) if os.path.exists(os.path.join(ROOT, tokens.TOKENS)) and not data_only else []:
            typer.echo('wrote %s' % path)
        # the taxonomy terms the site's components resolve (P2-S2-T06), committed on the same terms
        for path in site_taxonomy.write(ROOT) if os.path.isdir(os.path.join(ROOT, 'site')) and not data_only else []:
            typer.echo('wrote %s' % path)
    except tokens.TokenError as e:
        typer.echo('error  %s' % e, err=True)
        raise typer.Exit(1)
    # ---- BENCH_ROUTES (P2-S1-T04) -----------------------------------------------------------------------------------
    # the site build's half of --routes-from-diff reads it (site/src/lib/bench-routes.ts); say what it will render
    line = modes.note(os.environ, result.corpus)
    if line:
        typer.echo(line)
    # ---- end BENCH_ROUTES -------------------------------------------------------------------------------------------
    counts = result.counts()
    reasons: dict[str, int] = {}
    for _, _, reason in result.excluded:
        reasons[reason] = reasons.get(reason, 0) + 1  # get-default: a first reason starts its count
    typer.echo('build: published %s; %d subset(s) materialised; excluded %s%s'
               % (', '.join('%d %s' % (n, k) for k, n in counts.items()), len(result.corpus['subsets']),
                  ', '.join('%d (%s)' % (n, r) for r, n in sorted(reasons.items())) or 'nothing',
                  '; --data-only: S9 (%s) and S10 (%s) skipped' % (', '.join(modes.SKIPPED['S9']),
                                                                   ', '.join(modes.SKIPPED['S10'])) if data_only else ''))


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
    staleness = 'staleness'


# A report whose module is not named after it: 05 S7's re-verification queue is `bench report staleness`
# (P5-S7-T05), and 07 S9's adapter table joins the same report with P5-S4-T03.
REPORT_MODULES = {'staleness': 'reverification'}


class ReportFormat(str, Enum):
    md = 'md'
    json = 'json'
    csv = 'csv'


@app.command('report')
def report_cmd(
    name: Annotated[ReportName, typer.Argument(help='The report: completeness, conflicts, quality or staleness.')],
    fmt_: Annotated[ReportFormat, typer.Option('--format', help='md, json or csv.')] = ReportFormat.md,
    out: Annotated[Optional[Path], typer.Option('--out', help='Write here instead of stdout.')] = None,
    root: Annotated[Optional[Path], typer.Option('--root', help='Report over this tree (a fixture corpus) instead.')] = None,
    critical: Annotated[bool, typer.Option('--critical', help='staleness: only entries past 730 days on an active benchmark (05 S7).')] = False,
    as_of: Annotated[Optional[str], typer.Option('--as-of', help="staleness: count days to YYYY-MM-DD; default the data commit's date.")] = None,
    issue: Annotated[bool, typer.Option('--issue', help='staleness: write the weekly re-verification issue body instead.')] = False,
):
    """A report over the repository (05 S3). Deterministic: a re-run gives the same bytes."""
    import importlib
    from datetime import date

    from tools import report
    tree = str(root.resolve()) if root else ROOT
    mod = importlib.import_module('tools.report.%s' % REPORT_MODULES.get(name.value, name.value))  # get-default: most modules are named after their report
    if name is ReportName.staleness:
        built = mod.build(tree, date.fromisoformat(as_of) if as_of else None, critical=critical)
        text = mod.issue_body(built) if issue else report.render(built, fmt_.value)
    else:
        if critical or as_of or issue:
            typer.echo('report: --critical, --as-of and --issue belong to staleness', err=True)
            raise typer.Exit(2)
        text = report.render(mod.build(tree), fmt_.value)
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
    min_confidence: Annotated[Optional[float], typer.Option(
        '--min-confidence', help='The curation_confidence a gap claim needs (default 0.6, 00 S7.1 criterion S3).')] = None,
):
    """The coverage grid and the gap matrix: non-empty coarse cells with their counts and terms (12 S5.1;
    P1-S2-T11), and every coarse cell's four gap-score factors beside its score, with the claims asserted from them
    (12 S5.3-5.4; P1-S14-T08). The JSON is build/derived/gaps.json; scripts/check_gap_claims.py checks it."""
    from tools.build import gaps
    if fmt_ not in ('md', 'json'):
        typer.echo('gaps: --format is md or json, not %r' % fmt_, err=True)
        raise typer.Exit(2)
    try:
        doc = gaps.emit(grid, ROOT, reviewed_only, gaps.MIN_CONFIDENCE if min_confidence is None else min_confidence)
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


@app.command('eval')
def eval_cmd(
    split: Annotated[str, typer.Option(
        '--split', help='nl_search, facet_translation, suite_build, abstention, or all (the default).')] = 'all',
    report: Annotated[bool, typer.Option(
        '--report', help='Print the whole run as Markdown, the pool to grade included.')] = False,
    judge: Annotated[bool, typer.Option(
        '--judge', help='Also ask for the LLM-as-judge pass (refuses without a key; advisory, it never blocks).')] = False,
    holdout: Annotated[int, typer.Option(
        '--holdout', help='Hold out N items as the test split, scored apart and never tuned on.')] = 0,
):
    """Pool, grade and publish the AI layer's golden set, every rate with its Wilson interval (11 S7). Writes
    evals/results/<date>-<commit>.json when anything was graded; says so plainly when nothing can be."""
    from tools.evals import harness
    try:
        doc = harness.evaluate(ROOT, harness.select(split), holdout=holdout, judge=judge)
    except harness.UsageError as e:
        typer.echo('eval: %s' % e, err=True)
        raise typer.Exit(2)
    except harness.EvalError as e:
        for line in e.errors:
            typer.echo('error  %s' % line, err=True)
        typer.echo('eval: nothing graded; fix the golden set or the corpus first', err=True)
        raise typer.Exit(1)
    if report:
        typer.echo(harness.report(doc), nl=False)
    else:
        for line in harness.summary(doc):
            typer.echo(line)
    written = harness.write(doc, ROOT)
    if written:
        typer.echo('eval: wrote %s' % os.path.relpath(written, ROOT).replace(os.sep, '/'))


def main():
    app()


if __name__ == '__main__':
    main()
