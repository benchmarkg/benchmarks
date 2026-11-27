"""S8's claims stage: claims.json, claims-ingested/<benchmark_id>.json and derived/comparability.json (P3-S10-T03;
08 S4.2, S4.1, S3.2 S5, S6; 04 S8).

    bench build --out build/    # emit.emit() calls `stage`, artifacts.write() calls `write`, the manifest hashes them

tools/build/emit.py is the S8 emitter of corpus.json, facets.json and enums.json, and corpus.json holds "No claim
records" (08 S4.2). This is the same stage's other half: the claim records themselves, split the way 08 S4.2 settles
it -- "Putting curated claims in one always-available file and ingested rows behind a per-benchmark fetch that
comparison views never issue makes that separation a property of the network graph rather than of a filter
predicate somebody can forget to apply."

Which claims. Every claim under data/claims/ (never vendor/: 08 S3.2's licence boundary) on a benchmark the build
publishes -- the population of facets.json's claim_count (emit.claim_fields), which has already refused a claim that
fails tier 1 or names a condition record that is missing, doubled or broken. A claim on an unpublished benchmark
goes nowhere, as its benchmark does.

The split. 08 S4.2: claims.json is "every claim with `verification_status != machine-ingested`". A ResultClaim's
flag for that is `ingestion.review_state` (04 S9: "`review_state` is the flag"), so:

  machine-ingested   `ingestion.review_state` is machine-ingested: written by an adapter, seen by nobody. It goes to
                     claims-ingested/<benchmark_id>.json, and nowhere a comparison view reads.
  curated            everything else: a hand-curated claim (`ingestion: null`), and an ingested one a human has since
                     spot-checked, reviewed or promoted (04 S9's other three states). It goes to claims.json.

A claim under data/claims/_ingested/ with no `ingestion` block has no review state to read, so the build refuses it
rather than guess a tier (07 S2 rule 3: an ingested claim "carries `ingestion.review_state: machine-ingested`").

claims.json -- {artifact, format, tier: curated, claims: [row, ...], machine_ingested: {benchmark_id: rows}}, rows in
UTF-8 byte order of the claim id. A row is the shape the site already reads, site/src/lib/claims.ts ClaimRow (P2-S3-T02,
built against site/test/fixtures/provenance-claims.json until this file existed): the claim itself (so its
artifact_url, provenance_snapshot, source and disputed_by refs travel with it), its EvalConditions inlined (null when
it names none), 04 S8's numbers (`comparability`: comparability_key, key_unknown_count, condition_completeness,
unknown_fields, fields_material_total), the benchmark's resolved `material` set and `weights`, `key_shared_with` (the
other rows of the same artifact that share the key), the cited Source reduced to what a citation needs (`source`, the
ClaimSource fields), the reporter's id and published name, and `pool`: the rating pool a rating claim names, as its
data/rating-pools/ record has it (its id and snapshot_date), null for any other claim. 04 S9 makes a pool "a pool at a
date", and 10 V5's rating-pool refusal requires "matching `rating_pool_id` + snapshot date"; RatingPool is not one of
corpus.json's kinds (08 S4.2), so the row carries the date the workbench reads. `machine_ingested` counts the rows each
claims-ingested file holds, so the workbench can say "N machine-ingested claims hidden -- show them" (10 V5) without
fetching one.

claims-ingested/<benchmark_id>.json -- {artifact, format, benchmark, badge: machine-ingested, claims: [row, ...]}, one
file per benchmark with a machine-ingested claim, each row the same shape plus `badge: machine-ingested`, so a row
lifted out of its file still says what it is (08 S4.5: ingested claims "carry `machine-ingested`, which is part of the
contract"). Each row carries condition_completeness, in `comparability` as on a claims.json row (08 S4.2). The
directory is always created and emptied of the last build's files first, so it holds exactly this build's.

derived/comparability.json -- tools/build/comparability.py `pairwise` (the repository's src/derived/comparability.py)
over claims.json's rows only: it loads "With `claims.json`" (08 S4.2), so a machine-ingested claim in it would reach
the comparison view by the back door.

The refusals (`refuse`), run before anything is written and again by `write`, so an artifact that fails one is never
on disk:

  - claims.json holds no machine-ingested row (by `badge` or by the claim's review_state);
  - every claims-ingested file is named for its benchmark, badged, holds only machine-ingested rows on that benchmark,
    and every row carries condition_completeness; and claims.json's `machine_ingested` counts are the files' own;
  - comparability.json's groups are exactly claims.json's (benchmark, metric) groups, no row names a claim
    claims.json does not hold, every group above DEFER_ABOVE claims is `deferred` with no rows and every other one is
    `computed`;
  - no domain-group id is in any of them (emit.refuse's rule, so a build this accepts passes CI 9h);
  - the size budget: claims.json at most BUDGET bytes brotli.

The size budget. 08 S4.1 names the shard trigger "`claims.json` exceeds **0.5 MB brotli**", read here as 500,000
bytes (08 S4.1's sizes are decimal: "2.76 MB", "0.52 MB"), and the task's done_when makes it fail the build. 08 S6
hashes the uncompressed canonical bytes ("compression is a transport concern applied after hashing"), so the brotli
size is a check and is never written into an artifact or the manifest. How it is measured, without a Python brotli
dependency:

  1. A bound first. The reference encoder's BrotliEncoderMaxCompressedSize(n) (google/brotli, c/enc/encode.c) is
     n + 6 + 4 * (n >> 14) bytes, 2 for an empty input, and its header (c/include/brotli/encode.h) says the output "is
     guaranteed to be no longer than that", valid "if quality is at least 2" and no flush was performed. When the
     bound is within the budget the budget holds and nothing needs compressing: every build until claims.json nears
     0.5 MB raw.
  2. Otherwise a measurement: Node's zlib (the reference encoder), brotliCompressSync at quality 11 in one call, so
     no flush. Node is the site's toolchain already (08 S5.1), and tools/build/codegen.py runs it the same way; with
     no `node` on PATH the build fails, because a budget it cannot check is not one it may pass.

Not built here, and why. No claim in the corpus is machine-ingested today (no ingestion block anywhere under
data/claims/, and no data/claims/_ingested/), so claims-ingested/ is empty in a real build; and every benchmark is
still ai-drafted-unverified, which 05 S4 never publishes, so a plain `bench build` writes a claims.json with no rows
and a comparability.json with no groups. tests/build/test_claims_artifacts.py exercises the split, the deferral and
the budget over fixtures for that reason.

Determinism (08 S6): rows and files in UTF-8 byte order, emit.serialise's canonical bytes, NFC throughout, no clock.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from tools.build import comparability
from tools.build.emit import Refused, display_only_ids, group_hits, nfc, serialise, token_re

CLAIMS = 'claims.json'
INGESTED = 'claims-ingested'                  # the directory under --out
DIFF = comparability.DIFF_NAME                # 'derived/comparability.json'
ARTIFACTS = (CLAIMS, DIFF)                    # always written; plus one INGESTED/<benchmark_id>.json per benchmark
FORMATS = {'claims': 1, 'claims-ingested': 1}
MACHINE = 'machine-ingested'                  # the review_state, and the badge
CURATED = 'curated'
INGESTED_ROOT = 'data/claims/_ingested/'
# site/src/lib/claims.ts ClaimSource: the cited Source reduced to what a citation needs (09 S6.6)
SOURCE_FIELDS = ('id', 'type', 'title', 'url', 'publisher', 'accessed', 'fetched_at', 'archive_url', 'archive_captured',
                 'archive_status', 'licence_class')
BUDGET = 500_000                              # bytes of brotli: 08 S4.1's 0.5 MB shard trigger on claims.json
QUALITY = 11                                  # BROTLI_MAX_QUALITY, Node's default
_NODE = r"""
const zlib = require('node:zlib');
const chunks = [];
process.stdin.on('data', (c) => chunks.push(c));
process.stdin.on('end', () => {
  const out = zlib.brotliCompressSync(Buffer.concat(chunks), {params: {[zlib.constants.BROTLI_PARAM_QUALITY]: %d}});
  process.stdout.write(String(out.length));
});
""" % QUALITY


def ingested_name(benchmark: str) -> str:
    return '%s/%s.json' % (INGESTED, benchmark)


def dump(model) -> dict:
    return model.model_dump(mode='json', by_alias=True, exclude_computed_fields=True)


def tier(claim) -> str:
    """08 S4.2's split, read off one ResultClaim (module docstring)."""
    return MACHINE if claim.ingestion is not None and claim.ingestion.review_state == MACHINE else CURATED


def row_tier(row: dict) -> str:
    """The same rule, read off a written row: its badge, or its claim's review_state."""
    review = ((row.get('claim') or {}).get('ingestion') or {}).get('review_state')
    return MACHINE if row.get('badge') == MACHINE or review == MACHINE else CURATED


# ---- the stage -----------------------------------------------------------------------------------------------------

def stage(benchmarks: dict, claims: list, conditions: dict, sources: dict, organizations: list[dict],
          drafts: bool = False, pools: dict | None = None) -> dict[str, dict]:
    """published name -> artifact, NFC, after every refusal has passed; raises emit.Refused otherwise.

    `benchmarks` maps a published benchmark id to its model; `claims` are tools.validate.tiers Records from
    data/claims/; `conditions`, `sources` and `pools` map an id to the Records that hold it (`pools` the
    data/rating-pools/ ones); `organizations` are corpus.json's published ones."""
    profiles = comparability.load_profiles()
    names = {o['id']: o.get('name') for o in organizations}      # get-default: a name is optional on the record
    resolutions: dict[str, Any] = {}
    rows: dict[str, list[tuple[dict, Any]]] = {CURATED: [], MACHINE: []}
    facts: list[comparability.ClaimFacts] = []
    errors = []
    for r in claims:
        bench = r.raw.get('benchmark') if isinstance(r.raw, dict) else None
        bench = bench.split('@')[0] if isinstance(bench, str) else None
        if bench not in benchmarks:
            continue                                    # unpublished: no artifact carries it
        c = r.model
        if c is None or any(f.blocks for f in r.schema_findings):
            errors.append('%s: %s is a claim on published benchmark %s, but fails tier 1' % (r.path, r.id, bench))
            continue
        if c.ingestion is None and r.anchored.startswith(INGESTED_ROOT):
            errors.append('%s: %s lives under %s but has no ingestion block, so it has no review_state to say whether '
                          'claims.json or claims-ingested/ may hold it (08 S4.2; 07 S2 rule 3)'
                          % (r.path, c.id, INGESTED_ROOT))
            continue
        cond = conditions[c.eval_conditions][0].model if c.eval_conditions else None   # emit.claim_fields checked it
        held = sources.get(c.source, [])                # get-default: a dangling source is reported below
        if len(held) != 1 or held[0].model is None or any(f.blocks for f in held[0].schema_findings):
            errors.append('%s: %s cites source %s, but %s' % (
                r.path, c.id, c.source, 'no data/sources/ file holds it' if not held else
                'it is held by %d files' % len(held) if len(held) > 1 else 'it fails tier 1'))
            continue
        pool = None
        if c.rating_pool is not None:
            kept = (pools or {}).get(c.rating_pool, [])  # get-default: a dangling pool is reported here
            if len(kept) != 1 or kept[0].model is None or any(f.blocks for f in kept[0].schema_findings):
                errors.append('%s: %s names rating pool %s, but %s' % (
                    r.path, c.id, c.rating_pool, 'no data/rating-pools/ file holds it' if not kept else
                    'it is held by %d files' % len(kept) if len(kept) > 1 else 'it fails tier 1'))
                continue
            pool = {'id': kept[0].model.id, 'snapshot_date': kept[0].model.snapshot_date.isoformat()}
        if bench not in resolutions:
            resolutions[bench] = comparability.resolve_profile(benchmarks[bench], profiles)
        res = resolutions[bench]
        comp = comparability.compute_for_claim(c, res, cond)
        source = dump(held[0].model)
        row = {'claim': dump(c), 'conditions': dump(cond) if cond is not None else None,
               'comparability': comp.as_dict(), 'material': list(res.material),
               'weights': {f: res.weights[f] for f in res.material}, 'source': {k: source.get(k) for k in SOURCE_FIELDS},
               'reporter': {'id': c.reported_by, 'name': names.get(c.reported_by)}, 'pool': pool}
        t = tier(c)
        if t == MACHINE:
            row['badge'] = MACHINE
        else:
            facts.append(comparability.claim_facts(c, res, cond))
        rows[t].append((row, bench))
    if errors:
        raise Refused(errors)

    def ordered(pairs):
        out = [row for row, _ in sorted(pairs, key=lambda p: p[0]['claim']['id'].encode('utf-8'))]
        keys: dict[str, int] = {}
        for row in out:
            k = row['comparability']['comparability_key']
            keys[k] = keys.get(k, 0) + 1            # get-default: a key's first row starts its count
        for row in out:
            row['key_shared_with'] = keys[row['comparability']['comparability_key']] - 1
        return out

    flag = {'drafts': True} if drafts else {}
    by_bench: dict[str, list] = {}
    for row, bench in rows[MACHINE]:
        by_bench.setdefault(bench, []).append((row, bench))
    out = {CLAIMS: {'artifact': 'claims', 'format': FORMATS['claims'], 'tier': CURATED,
                    'claims': ordered(rows[CURATED]),
                    'machine_ingested': {b: len(v) for b, v in sorted(by_bench.items())}, **flag}}
    for bench, pairs in sorted(by_bench.items()):
        out[ingested_name(bench)] = {'artifact': 'claims-ingested', 'format': FORMATS['claims-ingested'],
                                     'benchmark': bench, 'badge': MACHINE, 'claims': ordered(pairs), **flag}
    out[DIFF] = dict(comparability.pairwise(facts), **flag)
    out = nfc(out)
    refuse(out)
    return out


# ---- the size budget -----------------------------------------------------------------------------------------------

class BudgetError(Exception):
    """The brotli size cannot be measured here."""


def max_brotli_size(n: int) -> int:
    """The reference encoder's BrotliEncoderMaxCompressedSize: no brotli output of n bytes at quality >= 2, with no
    flush, is longer (module docstring)."""
    return 2 if n == 0 else n + 2 + 4 * (n >> 14) + 3 + 1


def brotli_size(data: bytes) -> int:
    """The length of `data` brotli-compressed by Node's zlib at QUALITY, in one call."""
    node = shutil.which('node')
    if node is None:
        raise BudgetError('node is not on PATH, and the brotli size is measured with its zlib '
                          '(08 S5.1 pins node >= 22.12)')
    r = subprocess.run([node, '-e', _NODE], input=data, capture_output=True, check=False)
    out = r.stdout.decode('ascii', 'replace').strip()
    if r.returncode != 0 or not out.isdigit():
        raise BudgetError('node could not brotli-compress it: %s' % r.stderr.decode('utf-8', 'replace').strip()[-500:])
    return int(out)


@dataclass(frozen=True)
class Budget:
    raw: int
    bound: int                  # max_brotli_size(raw)
    brotli: int | None          # measured, or None when the bound already proved it
    within: bool

    def describe(self) -> str:
        how = ('brotli at most %s, by the encoder\'s bound' % format(self.bound, ',') if self.brotli is None else
               '%s brotli (Node zlib, quality %d)' % (format(self.brotli, ','), QUALITY))
        return '%s bytes, %s, budget %s' % (format(self.raw, ','), how, format(BUDGET, ','))


def budget(data: bytes) -> Budget:
    """claims.json's bytes against BUDGET: the bound when it suffices, else Node's measurement (module docstring)."""
    bound = max_brotli_size(len(data))
    if bound <= BUDGET:
        return Budget(len(data), bound, None, True)
    size = brotli_size(data)
    return Budget(len(data), bound, size, size <= BUDGET)


# ---- the refusals --------------------------------------------------------------------------------------------------

def refuse(artifacts: dict[str, dict]) -> None:
    """Raise Refused unless the claims artifacts (published name -> artifact) are fit to write (module docstring)."""
    errors = ['%s was not built' % name for name in ARTIFACTS if not artifacts.get(name)]
    if errors:
        raise Refused(errors)
    curated = artifacts[CLAIMS]['claims']
    for i, row in enumerate(curated):
        if row_tier(row) == MACHINE:
            errors.append('claims.json: claims[%d] (%s) is machine-ingested; 08 S4.2 keeps it to claims-ingested/, '
                          'which no comparison view loads' % (i, (row.get('claim') or {}).get('id')))
    files = {name: doc for name, doc in artifacts.items() if name.startswith(INGESTED + '/')}
    for name, doc in sorted(files.items()):
        bench = name[len(INGESTED) + 1:-len('.json')] if name.endswith('.json') else None
        if doc.get('artifact') != 'claims-ingested' or doc.get('benchmark') != bench or doc.get('badge') != MACHINE:
            errors.append('%s: not a badged claims-ingested file for benchmark %s (artifact %r, benchmark %r, badge %r)'
                          % (name, bench, doc.get('artifact'), doc.get('benchmark'), doc.get('badge')))
        for i, row in enumerate(doc.get('claims') or []):
            cid = (row.get('claim') or {}).get('id')
            if row.get('badge') != MACHINE or row_tier(row) != MACHINE:
                errors.append('%s: claims[%d] (%s) is not a badged machine-ingested row' % (name, i, cid))
            if 'condition_completeness' not in (row.get('comparability') or {}):
                errors.append('%s: claims[%d] (%s) carries no condition_completeness (08 S4.2)' % (name, i, cid))
            if str((row.get('claim') or {}).get('benchmark', '')).split('@')[0] != bench:
                errors.append('%s: claims[%d] (%s) is a claim on another benchmark' % (name, i, cid))
    counts = {name[len(INGESTED) + 1:-len('.json')]: len(doc.get('claims') or []) for name, doc in files.items()}
    if artifacts[CLAIMS].get('machine_ingested') != counts:
        errors.append('claims.json: machine_ingested says %s, but the claims-ingested files hold %s'
                      % (artifacts[CLAIMS].get('machine_ingested'), counts))
    errors += diff_problems(artifacts[DIFF], curated)
    pattern = token_re(display_only_ids())
    errors += ['%s: %s carries the display-only domain-group id %s (taxonomy/domain_groups.yaml; 08 S3.2, D4)'
               % (name, path, gid) for name in sorted(artifacts) for path, gid in group_hits(artifacts[name], pattern)]
    try:
        b = budget(serialise(artifacts[CLAIMS]))
        if not b.within:
            errors.append('claims.json is %s: over the 0.5 MB brotli budget, 08 S4.1\'s trigger to shard it'
                          % b.describe())
    except BudgetError as e:
        raw = len(serialise(artifacts[CLAIMS]))
        errors.append('claims.json is %s bytes, which the encoder\'s bound cannot keep within the %s-byte brotli '
                      'budget (08 S4.1), and it cannot be measured: %s' % (format(raw, ','), format(BUDGET, ','), e))
    if errors:
        raise Refused(errors)


def diff_problems(diff: dict, curated: list[dict]) -> list[str]:
    """derived/comparability.json against the claims.json rows it was computed from."""
    want: dict[tuple[str, str], int] = {}
    for row in curated:
        c = row.get('claim') or {}
        key = (str(c.get('benchmark', '')).split('@')[0], c.get('metric'))
        want[key] = want.get(key, 0) + 1                # get-default: a group's first claim starts its count
    ids = {(row.get('claim') or {}).get('id') for row in curated}
    groups = diff.get('groups') or []
    got = {(g.get('benchmark'), g.get('metric')): g.get('claims') for g in groups}
    out = []
    if got != want:
        out.append('derived/comparability.json: its groups %s are not claims.json\'s (benchmark, metric) groups %s'
                   % (sorted(got.items()), sorted(want.items())))
    for g in groups:
        where = 'derived/comparability.json: group (%s, %s)' % (g.get('benchmark'), g.get('metric'))
        n = g.get('claims') or 0
        if n > comparability.DEFER_ABOVE and (g.get('diff_status') != 'deferred' or g.get('rows') is not None):
            out.append('%s holds %d claims, above %d, but is %s rather than deferred with no rows (08 S3.2)'
                       % (where, n, comparability.DEFER_ABOVE, g.get('diff_status')))
        if n <= comparability.DEFER_ABOVE and (g.get('diff_status') != 'computed'
                                               or not isinstance(g.get('rows'), list)):
            out.append('%s holds %d claims, so its diff is computed, not %s' % (where, n, g.get('diff_status')))
        stray = sorted({x for r in g.get('rows') or [] for x in (r.get('a'), r.get('b'))} - ids)
        if stray:
            out.append('%s names %s, which claims.json does not hold' % (where, ', '.join(map(str, stray))))
    return out


# ---- writing -------------------------------------------------------------------------------------------------------

def write(artifacts: dict[str, dict], out_dir: str) -> list[str]:
    """Write every claims artifact under `out_dir`, refusing again first; claims-ingested/ holds this build's files
    only. Returns the paths, claims.json first."""
    refuse(artifacts)
    ingested = os.path.join(out_dir, INGESTED)
    if os.path.isdir(ingested):
        for name in os.listdir(ingested):
            if name.endswith('.json'):
                os.remove(os.path.join(ingested, name))
    os.makedirs(ingested, exist_ok=True)
    written = []
    for name in [CLAIMS] + sorted(n for n in artifacts if n.startswith(INGESTED + '/')) + [DIFF]:
        path = os.path.join(out_dir, *name.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(serialise(artifacts[name]))
        written.append(path)
    return written


def describe(artifacts: dict[str, dict]) -> str:
    """One line for `bench build`: what the stage wrote, and the budget (BudgetError when it cannot be checked)."""
    files = [n for n in artifacts if n.startswith(INGESTED + '/')]
    diff = artifacts[DIFF]['summary']
    return ('claims: %d curated in claims.json (%s); %d machine-ingested in %d claims-ingested/ file(s); '
            'derived/comparability.json: %d group(s), %d deferred above %d claims, %d row(s)'
            % (len(artifacts[CLAIMS]['claims']), budget(serialise(artifacts[CLAIMS])).describe(),
               sum(len(artifacts[n]['claims']) for n in files), len(files), diff['groups'], diff['deferred'],
               comparability.DEFER_ABOVE, diff['rows']))
