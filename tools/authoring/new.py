"""`bench new <entity> --id <id> [--domain <d>] [--from-source <url>] [--template <name>]` (P0-S5-T03; 05 S3).

05 S3: "A template that stubs every required field with an inline comment explaining it is how
curation quality stays consistent across contributors." The templates are tools/authoring/templates/
<entity>.yaml, with `$name` placeholders filled by string.Template. They are written in the model's
field order with the emitter's style, so the scaffold is already what `bench fmt` writes.

A scaffold must pass tier 1 (the task's verify), and some required fields are enums with no null --
`evaluation_target`, `data.access`. A legal term has to go there, and a legal term is a guess, which
05 S3's comments exist to prevent. So a scaffold marks every placeholder three ways: strings are
`TODO`, the homepage of a benchmark with no `--from-source` is an `example.invalid` URL (RFC 2606,
never resolves), and the record carries the tag `bench-new-stub`. Tier 3's `stub-placeholder` rule
blocks the file while any of the three remains, and `curation.verification_status:
ai-drafted-unverified` keeps it out of the published build regardless (05 S4, S9 job 6).

Entities: `benchmark` and `source`, the two templates this task creates. A Source for a non-DOI page
fails tier 1 until the archiver writes its `archive_url` (04 S12), and that is reported, not hidden.
`--from-source <url>` makes the URL the benchmark's homepage and scaffolds its Source beside it.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import subprocess
from dataclasses import dataclass
from string import Template

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
STUB_TAG = 'bench-new-stub'
PLACEHOLDER_HOST = 'example.invalid'
SLUG = re.compile(r'^[a-z0-9][a-z0-9-]{1,62}$')
SOURCE_ID = re.compile(r'^src-[a-z0-9]+(-[a-z0-9]+)*$')
URL = re.compile(r'^https?://\S+$')
ENTITIES = ('benchmark', 'source')


class NewError(ValueError):
    pass


@dataclass(frozen=True)
class Scaffold:
    path: str                           # root-relative, forward slashes
    text: str


def added_by(root: str = ROOT) -> str:
    """The curator's handle: git's user.name, or a TODO placeholder the stub rule will catch."""
    try:
        name = subprocess.run(['git', 'config', 'user.name'], cwd=root, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        name = ''
    return name if name and re.fullmatch(r'[\w .@-]+', name) else 'TODO'


def _template(name: str) -> Template:
    path = os.path.join(TEMPLATES, name + '.yaml')
    if not os.path.exists(path):
        have = sorted(f[:-5] for f in os.listdir(TEMPLATES) if f.endswith('.yaml'))
        raise NewError('no template %r (have: %s)' % (name, ', '.join(have)))
    with open(path, encoding='utf-8') as fh:
        return Template(fh.read())


def _leaf(domain: str | None) -> tuple[str, str]:
    from schema.benchmark import DomainLeaf
    if not domain:
        raise NewError('a benchmark needs --domain <family>/<subdomain> (02 S3: domain.primary is a leaf)')
    leaves = set(DomainLeaf.__args__)
    if domain not in leaves:
        family = [x for x in leaves if x.startswith(domain + '/')]
        hint = ('%s is a family, which is navigational and not assignable; pick a subdomain, e.g. %s'
                % (domain, sorted(family)[0])) if family else '%s is not a taxonomy/domains.yaml subdomain' % domain
        raise NewError(hint)
    return domain, domain.split('/')[0]


def render(entity: str, ident: str, domain: str | None = None, from_source: str | None = None,
           template: str | None = None, today: _dt.date | None = None, curator: str | None = None) -> list[Scaffold]:
    """The files a `bench new` would write, without writing them."""
    if entity not in ENTITIES:
        raise NewError('bench new knows %s, not %r' % (' and '.join(ENTITIES), entity))
    if from_source is not None and not URL.match(from_source):
        raise NewError('--from-source %r is not an http(s) URL' % from_source)
    today = today or _dt.date.today()
    curator = curator or added_by()
    if entity == 'source':
        if not SOURCE_ID.match(ident):
            raise NewError('a Source id is src-<slug> (05 S2), not %r' % ident)
        text = _template(template or 'source').substitute(
            id=ident, year=today.year, today=today.isoformat(),
            url=from_source or 'https://%s/%s' % (PLACEHOLDER_HOST, ident))
        return [Scaffold('data/sources/%d/%s.yaml' % (today.year, ident), text)]
    if not SLUG.match(ident):
        raise NewError('a benchmark id is a lowercase kebab slug of 2-63 characters (05 S2), not %r' % ident)
    domain, family = _leaf(domain)
    source_id = 'src-%s-homepage' % ident
    out = [Scaffold('data/benchmarks/%s/%s.yaml' % (family, ident), _template(template or 'benchmark').substitute(
        id=ident, domain=domain, family=family, today=today.isoformat(), added_by=curator, source_id=source_id,
        homepage=from_source or 'https://%s/%s' % (PLACEHOLDER_HOST, ident)))]
    if from_source:
        out += render('source', source_id, from_source=from_source, today=today)
    return out


def scaffold(entity: str, ident: str, root: str = ROOT, **kw) -> list[Scaffold]:
    """Write the scaffold; refuse to overwrite anything."""
    files = render(entity, ident, **kw)
    existing = [f.path for f in files if os.path.exists(os.path.join(root, f.path))]
    if existing:
        raise NewError('refusing to overwrite %s' % ', '.join(existing))
    for f in files:
        full = os.path.join(root, f.path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(f.text)
    return files
