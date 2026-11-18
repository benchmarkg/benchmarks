"""The croissant-benchmark extension's published JSON-LD context (P4-S6-T01; tools/build/croissant.py, codegen.py;
08 S5.8, 10 "Croissant", 15 A8).

The verify is a jq expression over site/public/ns/croissant-benchmark/v1/context.jsonld (JQ below): the five
extension term groups are declared, and the upstream Croissant context is declared alongside them. jq is not installed
on every machine that runs this suite, so `test_verify_the_jq_assertion` is the same assertion in Python, and
`test_verify_with_jq` runs the expression itself wherever jq is on PATH and skips elsewhere.

Done when: "The context resolves at its own URI, declares the five extension term groups, and redefines nothing
upstream." Nothing is deployed and the host is a placeholder, so that the live URI resolves is P4-S7's launch-checklist
row. What this holds is everything short of it: the file is what `bench schema gen` renders from the module's terms,
it sits at the path its URI names and is served there with a long TTL, its keys are exactly the keys the build's
documents carry beside the upstream context and none is an upstream term, the host is one constant, and the
documentation page says the extension is unofficial and names the CC BY-ND constraint.
"""
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import codegen, croissant  # noqa: E402
from tools.build import manifest as M  # noqa: E402

PATH = os.path.join(ROOT, croissant.CONTEXT)
PUBLIC = os.path.join(ROOT, 'site', 'public')
PAGE = os.path.join(ROOT, 'site', 'src', 'pages', 'ns', 'croissant-benchmark', 'v1', 'index.astro')
DIST = os.path.join(ROOT, 'site', 'dist')
GROUPS = ('tasks', 'metrics', 'protocol', 'conditions', 'lineage')       # 08 S5.8's five
JQ = ('([."@context"] | flatten) as $c | (($c | map(select(type == "object")) | add | keys) as $k | '
      '["tasks","metrics","protocol","conditions","lineage"] | all(. as $t | $k | index($t))) and '
      '($c | map(select(type == "string")) | any(test("croissant")))')


def load(path: str = PATH) -> dict:
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def ours(doc: dict) -> dict:
    [obj] = [x for x in doc['@context'] if isinstance(x, dict)]
    return obj


def flatten(x) -> list:
    """jq's `flatten`: nested arrays, to any depth, into one."""
    return [y for v in x for y in (flatten(v) if isinstance(v, list) else [v])]


def jq_verify(doc: dict) -> bool:
    """The verify's jq expression, step for step. `add` merges the objects (null for none, whose `keys` is an error,
    which `jq -e` reports as a failure); `index` finds a key; `test` is an unanchored regular expression."""
    c = flatten([doc.get('@context')])
    objects = [x for x in c if isinstance(x, dict)]
    if not objects:
        return False
    keys = set().union(*objects)
    return all(t in keys for t in GROUPS) and any(re.search('croissant', s) for s in c if isinstance(s, str))


# ---- the verify ---------------------------------------------------------------------------------------------------

def test_verify_the_jq_assertion():
    assert jq_verify(load())


@pytest.mark.parametrize('broken', [
    {'@context': [croissant.CROISSANT_VERSION, {k: v for k, v in croissant.extension_context().items() if k != 'lineage'}]},
    {'@context': croissant.extension_context()},                                  # no upstream declared beside it
    {'@context': ['https://example.org/ctx.jsonld', croissant.extension_context()]},
    {'@context': [croissant.CROISSANT_VERSION]},
])
def test_the_assertion_fails_a_context_missing_a_group_or_the_upstream(broken):
    assert not jq_verify(broken)


@pytest.mark.skipif(shutil.which('jq') is None, reason='jq is not installed; test_verify_the_jq_assertion is the same')
def test_verify_with_jq(tmp_path):
    r = subprocess.run(['jq', '-e', JQ, PATH], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0 and r.stdout.strip() == 'true', r.stdout + r.stderr
    bad = tmp_path / 'context.jsonld'
    bad.write_text(json.dumps({'@context': croissant.extension_context()}), encoding='utf-8')
    assert subprocess.run(['jq', '-e', JQ, str(bad)], capture_output=True).returncode != 0


# ---- generated, so it cannot drift --------------------------------------------------------------------------------

def test_the_committed_context_is_what_bench_schema_gen_renders(monkeypatch):
    monkeypatch.setattr(codegen, 'typescript', lambda schemas, json2ts: {})       # the TS half needs node; not this
    rendered = codegen.render(ROOT)[croissant.CONTEXT]
    with open(PATH, encoding='utf-8', newline='') as fh:
        assert fh.read() == rendered
    assert rendered.endswith('}\n') and '\r' not in rendered
    assert json.loads(rendered) == croissant.context_document()


def test_a_term_added_without_regenerating_is_drift(monkeypatch):
    """`bench schema gen --check` (CI job 5) reports the committed context as differing; drift() writes nothing."""
    monkeypatch.setattr(codegen, 'typescript', lambda schemas, json2ts: {})
    assert 'differs  %s' % croissant.CONTEXT not in codegen.drift(ROOT)
    monkeypatch.setitem(croissant.TERMS, 'heldOutPolicy', ('Protocol', None))
    assert 'differs  %s' % croissant.CONTEXT in codegen.drift(ROOT)
    assert '"heldOutPolicy": "cb:heldOutPolicy"' in codegen.render(ROOT)[croissant.CONTEXT]


# ---- the keys: the documents' own, and none upstream ------------------------------------------------------------------

def test_the_upstream_context_comes_first_and_is_named_not_copied():
    doc = load()
    assert list(doc) == ['@context'] and len(doc['@context']) == 2
    upstream, mine = doc['@context']
    assert upstream == croissant.CROISSANT_VERSION                    # the version the documents conform to
    assert mine == croissant.extension_context()


def test_its_keys_are_exactly_the_keys_the_documents_carry_beside_the_upstream_context():
    documents = croissant.context()                                   # benchmark_document's ctx
    upstream = dict(croissant.upstream_context())
    beside = {k: v for k, v in documents.items() if k not in upstream}
    assert beside == ours(load())
    assert list(beside) == list(ours(load()))


def test_no_key_redefines_an_upstream_term():
    mine = ours(load())
    upstream = dict(croissant.upstream_context())
    assert not set(mine) & (set(upstream) | croissant.schema_org_terms())
    assert not [k for k in mine if k.startswith('@')]                # no @vocab or @language of its own
    assert mine.pop(croissant.PREFIX) == croissant.NAMESPACE
    assert mine == {t: 'cb:%s' % t for t in croissant.TERMS}
    assert set(GROUPS) <= set(mine)


# ---- the URI, the host and the TTL --------------------------------------------------------------------------------

def test_the_host_is_one_constant_and_the_file_sits_where_its_uri_says():
    host = croissant.NS_HOST
    assert croissant.NAMESPACE == 'https://%s/ns/croissant-benchmark/v1#' % host
    assert croissant.CONTEXT_URL == croissant.NAMESPACE[:-1] + '/context.jsonld'
    served = urlsplit(croissant.CONTEXT_URL).path
    assert os.path.normpath(os.path.join(PUBLIC, served.lstrip('/'))) == os.path.normpath(PATH)
    with open(PATH, encoding='utf-8') as fh:
        text = fh.read()
    assert set(re.findall(r'https?://([^/"]+)', text)) == {host, urlsplit(croissant.CROISSANT_VERSION).hostname}
    assert read_yaml(os.path.join(ROOT, 'taxonomy', 'crosswalks', 'croissant.yaml'))['extension']['namespace'] == \
        ours(load())['cb']


def test_ns_is_served_with_a_long_ttl_and_the_context_falls_under_no_other_rule():
    with open(os.path.join(PUBLIC, '_headers'), encoding='utf-8') as fh:
        rules = M.parse_headers(fh.read())
    assert rules['/ns/*'] == {'cache-control': croissant.CONTEXT_CACHE}
    age = int(re.fullmatch(r'public, max-age=(\d+)', croissant.CONTEXT_CACHE).group(1))
    assert age >= 86400                                               # long: a day at the least (a week today)
    served = urlsplit(croissant.CONTEXT_URL).path
    assert [p for p in rules if fnmatch.fnmatchcase(served, p)] == ['/ns/*']   # Cloudflare's * spans `/` too


# ---- the documentation page ---------------------------------------------------------------------------------------

def test_the_page_says_unofficial_names_the_licence_and_links_the_context():
    with open(PAGE, encoding='utf-8') as fh:
        src = fh.read()
    assert "const CONTEXT = '%s';" % croissant.CONTEXT in src
    assert "const HREF = '%s';" % urlsplit(croissant.CONTEXT_URL).path in src
    assert 'An unofficial extension.' in src and 'not part of Croissant' in src
    assert 'CC BY-ND 4.0' in src and 'reproduces any of its text' in src
    for group in GROUPS:
        assert "['%s', '" % group in src, group


def test_the_built_page_and_context():
    """Over a built site (cd site && npx astro build), when there is one: the context is copied byte for byte, and the
    page beside it links the context, lists every term and ships no JavaScript but the prepaint script."""
    page = os.path.join(DIST, 'ns', 'croissant-benchmark', 'v1', 'index.html')
    if not os.path.exists(page):
        pytest.skip('build the site first (cd site && npx astro build)')
    with open(os.path.join(DIST, *croissant.CONTEXT.split('/')[2:]), 'rb') as a, open(PATH, 'rb') as b:
        assert a.read() == b.read()
    with open(page, encoding='utf-8') as fh:
        html = fh.read()
    assert 'href="%s"' % urlsplit(croissant.CONTEXT_URL).path in html and croissant.NAMESPACE in html
    codes = set(re.findall(r'<code\b[^>]*>([^<]*)</code>', html))           # Astro scopes the element's class
    assert [t for t in croissant.TERMS if t not in codes] == []
    assert 'An unofficial extension.' in html and 'CC BY-ND 4.0' in html
    assert re.findall(r'<script\b[^>]*>', html) == ['<script data-prepaint>']
