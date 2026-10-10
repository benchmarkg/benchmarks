"""Build the LMArena fixture from a real download (P5-S6-T02).

    python tests/ingest/fixtures/lmarena/make_fixture.py SOURCE_DIR

SOURCE_DIR holds what the live endpoints served: api.json (GET /api/datasets/lmarena-ai/leaderboard-dataset?blobs=true)
and <arena>.parquet (each arena's latest-00000-of-00001.parquet at that commit). For five arenas this writes, into
this directory, the responses the adapter asks for, in ingest/http/fixture.py's format:

    api.json                      the metadata: siblings cut to the five arenas (latest and full; full is never
                                  fetched), each latest file's lfs sha256 and size recomputed for the pruned file
    <arena>.resolve               the resolve URL's 302, to a CDN URL named by the pruned file's sha256
    <arena>.parquet               the pruned file at that CDN URL

Pruning keeps rows verbatim and drops rows only: the top 30 of `overall` by rank, and for text and webdev the top 5
of one other category, so the category filter has something to filter. video_edit holds 10 rows upstream and keeps
them all (an arena under the cap of 25); agent is the IPS schema. The parquet is re-encoded by pyarrow, so its bytes
are this script's, not LMArena's; the rows are LMArena's (CC-BY-4.0).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ARENAS = {'text': 'coding', 'text_style_control': 'coding', 'webdev': 'webdev-react', 'video_edit': None, 'agent': None}
HOME = 'https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset'
API = 'https://huggingface.co/api/datasets/lmarena-ai/leaderboard-dataset?blobs=true'
LATEST = 'latest-00000-of-00001.parquet'
KEEP_OVERALL, KEEP_OTHER = 30, 5


def prune(table: pa.Table, other: str | None) -> pa.Table:
    rows = table.to_pylist()
    key = 'rating' if 'rating' in table.column_names else 'score'

    def top(cat, n):
        return sorted((r for r in rows if r['category'] == cat), key=lambda r: (r['rank'], -r[key]))[:n]
    kept = top('overall', KEEP_OVERALL) + (top(other, KEEP_OTHER) if other else [])
    return pa.Table.from_pylist(kept, schema=table.schema)


def encode(table: pa.Table) -> bytes:
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()


def response(name: str, url: str, status: int, headers: list, body: bytes) -> None:
    with open(os.path.join(HERE, name), 'wb') as f:
        f.write(body)
    with open(os.path.join(HERE, name + '.headers.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'url': url, 'status': status, 'headers': headers}, f, indent=1)
        f.write('\n')


def main(src: str) -> int:
    with open(os.path.join(src, 'api.json'), encoding='utf-8') as f:
        meta = json.load(f)
    siblings = []
    for arena, other in ARENAS.items():
        body = encode(prune(pq.read_table(os.path.join(src, arena + '.parquet')), other))
        sha = hashlib.sha256(body).hexdigest()
        cdn = 'https://us.aws.cdn.hf.co/xet-bridge-us/fixture/%s' % sha
        resolve = '%s/resolve/%s/%s/%s' % (HOME, meta['sha'], arena, LATEST)
        response(arena + '.resolve', resolve, 302, [['Location', cdn], ['X-Repo-Commit', meta['sha']],
                                                     ['X-Linked-ETag', '"%s"' % sha]], b'')
        response(arena + '.parquet', cdn, 200, [['Content-Type', 'application/octet-stream']], body)
        for s in meta['siblings']:
            if s['rfilename'] == '%s/%s' % (arena, LATEST):
                siblings.append(dict(s, size=len(body), lfs=dict(s['lfs'], sha256=sha, size=len(body))))
            elif s['rfilename'].startswith(arena + '/full-'):
                siblings.append(s)
    keep = {k: meta[k] for k in ('id', 'author', 'sha', 'lastModified', 'private', 'gated', 'disabled', 'tags')}
    keep['siblings'] = siblings + [s for s in meta['siblings'] if s['rfilename'] in ('README.md', '.gitattributes')]
    response('api.json', API, 200, [['Content-Type', 'application/json; charset=utf-8']],
             (json.dumps(keep, indent=1, sort_keys=True) + '\n').encode('utf-8'))
    print('wrote %d arenas at %s' % (len(ARENAS), meta['sha']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
