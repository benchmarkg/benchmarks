#!/usr/bin/env python3
"""Rebuild site/public/fonts/*.woff2: IBM Plex subset to Latin plus 09 S12.1's named glyphs.

    uvx --from "fonttools[woff]==4.60.1" python scripts/subset_fonts.py

The sources are IBM's own npm tarballs, fetched straight from the registry and checked against
their pinned sha512 integrity. They are NOT npm dependencies: every @ibm/plex-* package runs
`ibmtelemetry` as a postinstall hook, which reports to www-api.ibm.com on every install
(telemetry.yml, observed 2026-09-24), and 09 S12.1 wants a site that "should collect nothing".
Downloading the tarball and reading the WOFF2 out of it runs no package code.

The four faces and why (09 S3.1, S12.1; budget <= 120 KB for all faces together):

    plex-sans.woff2         Plex Sans variable roman, wght 400-700, wdth pinned at 100   preloaded
    plex-sans-italic.woff2  Plex Sans variable italic, wght 400-700, wdth pinned at 100
    plex-mono.woff2         Plex Mono Regular (static)                                     preloaded
    plex-condensed.woff2    Plex Sans Condensed Regular (static; axis and tick labels only)

The weight range is narrowed to 400-700 and the width axis pinned because nothing in 09 sets a
weight under 400 or uses the variable width; together they save about a third of the roman file.
Mono and Condensed are single static weights: 09 uses Mono for identifiers and code and Condensed
for labels, neither in bold. The Plex Sans Condensed family is the separate design 09 names, not
the variable file at wdth 85, so that the roman file preloaded on every page carries no width axis.

Coverage. Basic Latin, Latin-1 Supplement and the typographic punctuation a Latin text face needs
(dashes, curly quotes, ellipsis, bullet, euro, trademark, arrows), plus the named glyphs
`∅ → ± ≥ ≤ × ▲ ▼ − · §`. Plex has no ∅ (U+2205), ▲ (U+25B2) or ▼ (U+25BC) in any of these faces,
so those three render from the system fallback wherever they appear; the script prints them.
Latin Extended-A (Czech, Polish, Turkish, ... names) is NOT included: 09 asks for Latin plus the
named set, and adding it costs ~14 KB with hinting, which would take the total past the budget.

Every OpenType layout feature is kept (`tnum` and `zero` are load-bearing, 09 S3.4), and TrueType
hinting is kept because the smallest text is 11px (09 S3.2).
"""
import base64
import hashlib
import io
import os
import sys
import tarfile
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'public', 'fonts')

TARBALLS = {
    'sans-variable': ('https://registry.npmjs.org/@ibm/plex-sans-variable/-/plex-sans-variable-0.2.0.tgz',
                      'sha512-S8xew9E8CPPKFvitbu2gDtwNFVWwwhClheaIBeykDYg7DrVK3cV5Xq5MjMrWPP5Os0xyiRFjMOmtGBLzz3urTQ=='),
    'mono': ('https://registry.npmjs.org/@ibm/plex-mono/-/plex-mono-2.5.0.tgz',
             'sha512-STBJIPxPomOYPmBMO7z5TKPJUotAF9u3gAUumTqVgwgrAO+K4FRNh0MlhsoJjKhJKsMbBJR10/bk4inkj/wc1w=='),
    'sans-condensed': ('https://registry.npmjs.org/@ibm/plex-sans-condensed/-/plex-sans-condensed-2.0.0.tgz',
                       'sha512-dzgR4Npf/JJMiTYf6iOBQJpTDQfllZFLN0A0FkW5gtWhNr9JeQNvRrIRwJvbZHfL0I8wae8kIhO/ukYdeXW54g=='),
}

FACES = [  # (output, tarball, member inside the tarball, variable-axis limits or None)
    ('plex-sans.woff2', 'sans-variable', 'package/fonts/complete/woff2/IBM Plex Sans Var-Roman.woff2',
     {'wght': (400, 700), 'wdth': 100}),
    ('plex-sans-italic.woff2', 'sans-variable', 'package/fonts/complete/woff2/IBM Plex Sans Var-Italic.woff2',
     {'wght': (400, 700), 'wdth': 100}),
    ('plex-mono.woff2', 'mono', 'package/fonts/complete/woff2/IBMPlexMono-Regular.woff2', None),
    ('plex-condensed.woff2', 'sans-condensed', 'package/fonts/complete/woff2/IBMPlexSansCondensed-Regular.woff2',
     None),
]
LICENCE_MEMBER = ('sans-variable', 'package/LICENSE.txt')

LATIN = ('U+0020-007E,U+00A0-00FF,U+0131,U+0152-0153,U+02C6,U+02DA,U+02DC,U+2013-2014,U+2018-201A,'
         'U+201C-201E,U+2020-2022,U+2026,U+2030,U+2039-203A,U+2044,U+20AC,U+2122,U+2190-2193,'
         'U+2212,U+2215')
NAMED = '∅→±≥≤×▲▼−·§'  # 09 S12.1


def fetch(name):
    url, integrity = TARBALLS[name]
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read()
    got = 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode()
    if got != integrity:
        sys.exit('%s: integrity mismatch\n  want %s\n  got  %s' % (url, integrity, got))
    return tarfile.open(fileobj=io.BytesIO(data))


def build(src_bytes, limits):
    # Deterministic output: keep the source's head.modified instead of stamping "now".
    font = TTFont(io.BytesIO(src_bytes), recalcTimestamp=False)
    opts = subset.Options()
    opts.layout_features = ['*']
    opts.name_IDs = ['*']
    opts.name_languages = ['*']
    opts.notdef_outline = True
    opts.hinting = True
    unicodes = subset.parse_unicodes(LATIN) + [ord(c) for c in NAMED]
    s = subset.Subsetter(opts)
    s.populate(unicodes=unicodes)
    s.subset(font)
    if limits:
        # Instance after subsetting: fontTools 4.60.1 fails on gvar when the order is reversed.
        buf = io.BytesIO()
        font.flavor = None
        font.save(buf)
        font = instancer.instantiateVariableFont(TTFont(io.BytesIO(buf.getvalue()), recalcTimestamp=False), limits)
    missing = [c for c in NAMED if ord(c) not in font.getBestCmap()]
    out = io.BytesIO()
    font.flavor = 'woff2'
    font.save(out)
    return out.getvalue(), missing


def main():
    os.makedirs(OUT, exist_ok=True)
    tars = {name: fetch(name) for name in TARBALLS}
    total = 0
    for out, tar, member, limits in FACES:
        data, missing = build(tars[tar].extractfile(member).read(), limits)
        with open(os.path.join(OUT, out), 'wb') as f:
            f.write(data)
        total += len(data)
        print('%-24s %7d bytes  not in the face: %s' % (
            out, len(data), ' '.join('U+%04X' % ord(c) for c in missing) or '-'))
    lic = tars[LICENCE_MEMBER[0]].extractfile(LICENCE_MEMBER[1]).read()
    with open(os.path.join(OUT, 'OFL.txt'), 'wb') as f:
        f.write(lic.replace(b'\r\n', b'\n'))
    print('total %d bytes (%.1f KB)' % (total, total / 1024))


if __name__ == '__main__':
    main()
