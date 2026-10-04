"""Build tests/fixtures/epoch/benchmark_data.zip, a synthetic stand-in for Epoch's bundle (P3-S1-T03).

Epoch's real bundle is bulk data and stays out of git (05 S11; epochdl/ is gitignored). This is
the same layout in miniature, every value made up: a benchmark_metadata.csv with one row whose CSV
exists and one with none (Epoch's `METR` case), one per-benchmark CSV, one orphan CSV no metadata
row names (Epoch has 21), model_metadata.csv, a README, and the epoch_capabilities_index/
subdirectory. Fixed timestamps and order make the bytes, and so the sha256, reproducible.

    python tests/fixtures/epoch/make_fixture.py     # rewrites the zip and its .headers.json
"""
import hashlib
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ZIP = os.path.join(HERE, 'benchmark_data.zip')
ETAG = '"f1x7ure0e7a9000000000000000000a1"'
STAMP = (2026, 9, 16, 0, 0, 0)

FILES = [
    # The citation block is where Epoch's README carries its attribution text (P3-S1-T04 copies it verbatim)
    ('README.md', '## Licensing\nSynthetic test data in the layout of Epoch AI\'s bundle; no real results.\n\n'
                  '### Citation\n```\nExample Lab, ‘Example Benchmarks’. Retrieved from '
                  '‘https://example.org/benchmarks’ [online resource].\n```\n'),
    ('benchmark_metadata.csv',
     'benchmark,in_eci,source_file,score_column,scale,random_baseline,score_ceiling,release_date,superseded_by\n'
     'Example Bench,True,example_bench.csv,Best score (across scorers),1.0,0.25,1.0,2026-01-01,\n'
     'Example Horizon,False,,,,,,,\n'),
    ('example_bench.csv',
     'Model version,mean_score,Best score (across scorers),Release date,Organization,Country,stderr,Started at,id\n'
     'example-model-1_high,0.5,0.5,2026-02-01,Example Lab,Nowhere,0.01,2026-03-01T00:00:00.000Z,AAAAAAAAAAAAAAAAAAAAAA\n'
     'example-model-1_unknown,0.4,0.4,2026-02-01,Example Lab,Nowhere,0.02,2026-03-02T00:00:00.000Z,BBBBBBBBBBBBBBBBBBBBBB\n'),
    ('example_orphan_external.csv',
     'Model version,Score,Source link\n'
     'example-model-1,12.5,https://example.org/results\n'),
    ('model_metadata.csv',
     'model_version,model_group,date,display_name,organization,country,accessibility,training_compute_flop\n'
     'example-model-1_high,Example Model 1,2026-02-01,Example Model 1,Example Lab,Nowhere,API access,\n'),
    ('epoch_capabilities_index/eci_scores.csv', 'Model,eci\nExample Model 1,100.0\n'),
]


def build():
    with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, text in FILES:
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, text.encode('utf-8'))
    body = open(ZIP, 'rb').read()
    meta = {
        'url': 'https://epoch.ai/data/benchmark_data.zip',
        'method': 'GET',
        'status': 200,
        'body_bytes': len(body),
        'body_sha256': hashlib.sha256(body).hexdigest(),
        'note': 'Synthetic. Epoch serves an ETag and no Last-Modified on the bundle (07 S2.2).',
        'headers': [['Content-Type', 'application/zip'], ['Content-Length', str(len(body))], ['ETag', ETAG]],
    }
    with open(ZIP + '.headers.json', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(meta, f, indent=2)
        f.write('\n')
    return meta


if __name__ == '__main__':
    m = build()
    print('%s: %d bytes, sha256 %s' % (ZIP, m['body_bytes'], m['body_sha256']))
