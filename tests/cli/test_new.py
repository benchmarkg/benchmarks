"""Tests for `bench new` (P0-S5-T03; tools/authoring/, tools/cli.py; 05 S3).

The verify: "`bench new benchmark --id fixture-x --domain code/repository-scale-se` writes a file
that `bench validate --tier schema` accepts as a stub, and `pytest tests/cli/test_new.py` asserts
every required Benchmark field is stubbed with a comment". The CLI runs against a temporary root
(cli.ROOT patched), so nothing is written into the repository's data/.
"""
import datetime
import inspect
import os
import sys
import typing

import pytest
from pydantic import BaseModel
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.benchmark import Benchmark  # noqa: E402
from schema.paths import type_args  # noqa: E402
from schema.source import Source  # noqa: E402
from tools import cli, fmt  # noqa: E402
from tools.authoring import new  # noqa: E402
from tools.validate import tiers  # noqa: E402

runner = CliRunner()
TODAY = datetime.date(2026, 9, 25)
WARNING = 'NEVER estimate'


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, 'ROOT', str(tmp_path))
    return tmp_path


def scaffold_text(**kw):
    kw.setdefault('today', TODAY)
    kw.setdefault('curator', 'a-curator')
    return new.render('benchmark', 'fixture-x', domain='code/repository-scale-se', **kw)[0].text


# ---- the verify ---------------------------------------------------------------------------------

def test_bench_new_writes_a_stub_that_tier_1_accepts(root):
    result = runner.invoke(cli.app, ['new', 'benchmark', '--id', 'fixture-x', '--domain', 'code/repository-scale-se'])
    assert result.exit_code == 0, result.output
    path = root / 'data' / 'benchmarks' / 'code' / 'fixture-x.yaml'
    assert path.exists() and 'wrote data/benchmarks/code/fixture-x.yaml -- tier 1: ok' in result.output
    check = runner.invoke(cli.app, ['validate', '--tier', 'schema', str(path)])
    assert check.exit_code == 0, check.output
    assert '0 blocking' in check.output


def _required(model, prefix=''):
    """(dotted path, sub-model or None) for every required field, recursively through nested models."""
    for name, f in model.model_fields.items():
        if not f.is_required():
            continue
        key = f.alias or name
        subs = [a for a in type_args(f.annotation) if inspect.isclass(a) and issubclass(a, BaseModel)]
        is_list = typing.get_origin(f.annotation) is list
        yield prefix + key, subs, is_list
        # a list of strings-or-inline-models (curation.sources) is stubbed with strings: nothing nested
        if subs and not (is_list and str in type_args(f.annotation) or
                         any('str' in str(a) for a in typing.get_args(f.annotation))):
            yield from _required(subs[0], prefix + key + ('[0].' if is_list else '.'))


def _node(tree, path):
    """The (parent container, key) for a dotted path with [0] list steps."""
    parent, key = None, None
    node = tree
    for seg in path.split('.'):
        idx = seg.endswith('[0]')
        seg = seg[:-3] if idx else seg
        parent, key, node = node, seg, node[seg]
        if idx:
            parent, key, node = node, 0, node[0]
    return parent, key, node


def _comment(parent, key, node) -> str:
    """The end-of-line comment on the line that opens `key`, wherever ruamel keeps it."""
    tokens = []
    item = parent.ca.items.get(key) if isinstance(parent, (CommentedMap, CommentedSeq)) else None
    tokens += [t for t in (item or []) if t is not None and not isinstance(t, list)]
    if isinstance(node, (CommentedMap, CommentedSeq)) and node.ca.comment:
        tokens += [t for t in node.ca.comment if t is not None and not isinstance(t, list)]
    for t in tokens:
        first = t.value.split('\n', 1)[0].strip()
        if first.startswith('#'):
            return first
    return ''


def test_every_required_benchmark_field_is_stubbed_with_a_comment():
    tree = YAML().load(scaffold_text())
    required = list(_required(Benchmark))
    assert {p for p, _, _ in required} >= {'id', 'name', 'tagline', 'domain.primary', 'learned_entrant_evidence',
                                          'evaluation_target', 'data.access', 'homepage', 'curation.sources'}
    missing, silent = [], []
    for path, _, is_list in required:
        if path == 'id':
            continue                          # the one field the curator typed on the command line
        try:
            parent, key, node = _node(tree, path)
        except (KeyError, IndexError, TypeError):
            missing.append(path)
            continue
        if not _comment(parent, key, node):
            silent.append(path)
    assert missing == [], 'required fields the template does not stub: %s' % missing
    assert silent == [], 'required fields stubbed without an explanatory comment: %s' % silent


def _carries_a_number(tp) -> bool:
    for a in type_args(tp):
        if a in (int, float):
            return True
        if inspect.isclass(a) and issubclass(a, BaseModel) and any(
                _carries_a_number(f.annotation) for f in a.model_fields.values()):
            return True
    return False


def test_every_numeric_field_carries_the_null_versus_guess_warning():
    """The task's step 3: the warning is a comment on every numeric field the template writes."""
    tree = YAML().load(scaffold_text())
    numeric = []

    def walk(node, model, prefix):
        for key in list(node):
            f = model.model_fields.get(key)
            if f is None:
                continue
            path = prefix + key
            # a field whose value is written in place (a number, or the null that stands for one), not a
            # block that contains numbers further down -- those are checked when the walk reaches them
            scalar = not isinstance(node[key], (CommentedMap, CommentedSeq))
            if scalar and _carries_a_number(f.annotation):
                numeric.append(path)
                assert WARNING in _comment(node, key, node[key]), '%s has no "%s" comment' % (path, WARNING)
            subs = [a for a in type_args(f.annotation) if inspect.isclass(a) and issubclass(a, BaseModel)]
            if subs and isinstance(node[key], CommentedMap):
                walk(node[key], subs[0], path + '.')
    walk(tree, Benchmark, '')
    assert 'data.size' in numeric


# ---- what a scaffold is -------------------------------------------------------------------------

def test_the_scaffold_is_already_formatted():
    text = scaffold_text()
    assert fmt.format_text(text, Benchmark) == text
    src = new.render('source', 'src-example-page', from_source='https://example.org/p', today=TODAY)[0].text
    assert fmt.format_text(src, Source) == src


def test_the_scaffold_blocks_at_tier_3_until_every_placeholder_is_replaced(tmp_path):
    path = tmp_path / 'data' / 'benchmarks' / 'code' / 'fixture-x.yaml'
    path.parent.mkdir(parents=True)
    path.write_text(scaffold_text(), encoding='utf-8')
    r = tiers.single(str(path), root=ROOT)
    stub = [f for f in r.findings if f.rule == 'stub-placeholder']
    assert len(stub) == 2 and all(f.blocks for f in stub)
    assert 'homepage, learned_entrant_evidence[].system, name, tagline' in stub[0].message
    # a curator replaces the placeholders and removes the tag
    text = path.read_text(encoding='utf-8').replace('name: TODO', 'name: Fixture X').replace(
        'tagline: TODO', 'tagline: A fixture.').replace('system: TODO', 'system: Some Model').replace(
        'https://example.invalid/fixture-x', 'https://example.org/x').replace('  - bench-new-stub', '  - fixture')
    path.write_text(text, encoding='utf-8')
    assert [f for f in tiers.single(str(path), root=ROOT).findings if f.rule == 'stub-placeholder'] == []


def test_a_scaffold_is_never_published():
    doc = YAML(typ='safe').load(scaffold_text())
    assert doc['curation']['verification_status'] == 'ai-drafted-unverified'     # 05 S4: excluded from the build
    assert 'bench-new-stub' in doc['tags']


def test_every_placeholder_is_filled():
    text = scaffold_text()
    assert '$' not in text
    doc = YAML(typ='safe').load(text)
    assert doc['id'] == 'fixture-x' and doc['domain']['primary'] == 'code/repository-scale-se'
    assert doc['curation']['added_by'] == 'a-curator' and doc['curation']['added_on'] == TODAY
    assert doc['curation']['sources'] == ['src-fixture-x-homepage']


def test_from_source_makes_the_homepage_and_scaffolds_the_source(root):
    result = runner.invoke(cli.app, ['new', 'benchmark', '--id', 'fixture-y', '--domain', 'code/bug-repair',
                                     '--from-source', 'https://example.org/fixture-y'])
    assert result.exit_code == 0, result.output
    bench = YAML(typ='safe').load((root / 'data' / 'benchmarks' / 'code' / 'fixture-y.yaml').read_text(encoding='utf-8'))
    assert bench['homepage'] == 'https://example.org/fixture-y'
    year = datetime.date.today().year
    src_path = root / 'data' / 'sources' / str(year) / 'src-fixture-y-homepage.yaml'
    src = YAML(typ='safe').load(src_path.read_text(encoding='utf-8'))
    assert src['url'] == 'https://example.org/fixture-y' and src['archive_status'] == 'pending'
    # a non-DOI Source fails tier 1 until it is archived, and bench new says so rather than hiding it
    assert 'archive_url' in result.output and 'bench archive src-fixture-y-homepage' in result.output


def test_bench_new_source(root):
    result = runner.invoke(cli.app, ['new', 'source', '--id', 'src-example-org-page-2026',
                                     '--from-source', 'https://example.org/page'])
    assert result.exit_code == 0, result.output
    assert list((root / 'data' / 'sources').rglob('src-example-org-page-2026.yaml'))


def test_a_curator_without_a_git_name_gets_a_placeholder_the_rule_catches(monkeypatch):
    monkeypatch.setattr(new.subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(OSError('no git')))
    assert new.added_by() == 'TODO'


# ---- refusals -----------------------------------------------------------------------------------

@pytest.mark.parametrize('args, message', [
    (['new', 'benchmark', '--id', 'x-bench', '--domain', 'code'], 'navigational and not assignable'),
    (['new', 'benchmark', '--id', 'x-bench', '--domain', 'code/no-such'], 'not a taxonomy/domains.yaml subdomain'),
    (['new', 'benchmark', '--id', 'x-bench'], 'needs --domain'),
    (['new', 'benchmark', '--id', 'X Bench', '--domain', 'code/bug-repair'], 'kebab slug'),
    (['new', 'source', '--id', 'example-page'], 'src-<slug>'),
    (['new', 'system', '--id', 'example-model'], 'knows benchmark and source'),
    (['new', 'benchmark', '--id', 'x-bench', '--domain', 'code/bug-repair', '--template', 'no-such'],
     'no template'),
    (['new', 'benchmark', '--id', 'x-bench', '--domain', 'code/bug-repair', '--from-source', 'example.org'],
     'not an http(s) URL'),
])
def test_bench_new_refuses(root, args, message):
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 2 and message in result.output, result.output
    assert not (root / 'data').exists()                                        # nothing written


def test_bench_new_never_overwrites(root):
    args = ['new', 'benchmark', '--id', 'fixture-x', '--domain', 'code/repository-scale-se']
    assert runner.invoke(cli.app, args).exit_code == 0
    path = root / 'data' / 'benchmarks' / 'code' / 'fixture-x.yaml'
    path.write_text(path.read_text(encoding='utf-8').replace('name: TODO', 'name: Curated'), encoding='utf-8')
    again = runner.invoke(cli.app, args)
    assert again.exit_code == 2 and 'refusing to overwrite' in again.output
    assert 'name: Curated' in path.read_text(encoding='utf-8')


def test_template_selects_another_template(root, tmp_path, monkeypatch):
    alt = tmp_path / 'templates'
    alt.mkdir()
    for f in ('benchmark', 'source'):
        (alt / (f + '.yaml')).write_text(open(os.path.join(new.TEMPLATES, f + '.yaml'), encoding='utf-8').read(),
                                         encoding='utf-8')
    (alt / 'benchmark-minimal.yaml').write_text(
        (alt / 'benchmark.yaml').read_text(encoding='utf-8').replace('aliases: []', 'aliases: [minimal]'),
        encoding='utf-8')
    monkeypatch.setattr(new, 'TEMPLATES', str(alt))
    result = runner.invoke(cli.app, ['new', 'benchmark', '--id', 'fixture-z', '--domain', 'code/bug-repair',
                                     '--template', 'benchmark-minimal'])
    assert result.exit_code == 0, result.output
    doc = YAML(typ='safe').load((root / 'data' / 'benchmarks' / 'code' / 'fixture-z.yaml').read_text(encoding='utf-8'))
    assert doc['aliases'] == ['minimal']
