#!/usr/bin/env python3
"""Generate the synthetic HELM bucket the adapter's tests read (P5-S6-T05).

    python tests/ingest/fixtures/helm/make_fixture.py        # rewrites every response in this directory

Why synthetic. The bucket's data states no licence (06 S3.5: "a publicly readable bucket is permission to read, not
automatically permission to redistribute"), so none of it may be committed, not even as a fixture -- the
adapter was checked against the live bucket instead (the P5-S6-T05 commit says how). What is real is the shape:
the JSON API's listing and media URLs, the object fields (size and generation as strings, a base64 MD5,
contentEncoding gzip on some), the release layout, and three of the five adapter_spec key sets KEY_SETS declares.
Every scenario, model, deployment, prompt and number is invented. The output is deterministic, and
tests/ingest/test_helm.py regenerates it and compares bytes.

The four suites:
    audio     no releases/ prefix: data, not an error
    lite      releases v1.2.0, v1.13.0 and v1.12.0 (v1.13.0 is newest, which a string sort gets wrong); its
              run_specs.json is stored gzip-encoded; two scenarios, 26-key specs and one 28-key spec
    classic   v0.4.0, the 21-key shape with no model_deployment and no chain-of-thought keys; stored plain
    mmlu      v1.13.0, the 27-key shape (eval_splits), last written over two quarters before the fixture's date
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from ingest.adapters import helm as H  # noqa: E402

PROMPT = 'Answer the invented question about the invented passage.\n'   # never to appear in a draft


def adapter_spec(shape: str, model: str, deployment: str | None, shots=5, cot='', temperature=0.0, outputs=1,
                 method='generation', max_eval=1000) -> dict:
    a = {'method': method, 'global_prefix': '', 'global_suffix': '', 'instructions': PROMPT, 'input_prefix': 'Q: ',
         'input_suffix': '\n', 'reference_prefix': 'A. ', 'reference_suffix': '\n', 'chain_of_thought_prefix': cot,
         'chain_of_thought_suffix': '\n', 'output_prefix': 'A: ', 'output_suffix': '\n', 'instance_prefix': '\n',
         'substitutions': [], 'max_train_instances': shots, 'max_eval_instances': max_eval, 'num_outputs': outputs,
         'num_train_trials': 1, 'num_trials': 1, 'sample_train': True, 'model_deployment': deployment, 'model': model,
         'temperature': temperature, 'max_tokens': 100, 'stop_sequences': ['\n'], 'multi_label': False}
    if shape == '28':
        a.update(output_mapping_pattern=None, reference_prefix_characters=None)
    elif shape == '27':
        a['eval_splits'] = ['test']
    elif shape == '21':
        for k in ('chain_of_thought_prefix', 'chain_of_thought_suffix', 'global_suffix', 'model_deployment', 'num_trials'):
            del a[k]
    return a


def spec(scenario: str, args: dict, a: dict, metrics=('exact_match',)) -> dict:
    name = '%s:%s,model=%s' % (scenario.rsplit('.', 1)[-1].lower(), ','.join('%s=%s' % kv for kv in sorted(args.items())),
                               a['model'].replace('/', '_'))
    return {'name': name, 'scenario_spec': {'class_name': scenario, 'args': args}, 'adapter_spec': a,
            'metric_specs': [{'class_name': 'helm.benchmark.metrics.basic_metrics.BasicMetric',
                              'args': {'names': list(metrics)}}],
            'data_augmenter_spec': {'perturbation_specs': [], 'seeds_per_instance': 1}, 'groups': [scenario.rsplit('.', 1)[-1].lower()]}


QA = 'helm.benchmark.scenarios.example_scenario.ExampleQA'
MATH = 'helm.benchmark.scenarios.example_math_scenario.ExampleMath'
SUITES = {
    'lite': {'releases': ['v1.2.0', 'v1.13.0', 'v1.12.0'], 'gzip': True, 'updated': '2026-06-10T22:01:00.424Z', 'specs': [
        spec(QA, {}, adapter_spec('26', 'example-org/model-a', 'together/model-a')),
        spec(QA, {}, adapter_spec('26', 'example-org/model-b', 'example-org/model-b')),
        spec(QA, {}, adapter_spec('28', 'other-org/model-c', 'huggingface/model-c')),
        spec(MATH, {'subject': 'algebra'}, adapter_spec('26', 'example-org/model-a', 'together/model-a', shots=8,
                                                         cot='Think step by step.', temperature=0.7, outputs=4,
                                                         max_eval=500), metrics=('math_equiv', 'exact_match')),
        spec(MATH, {'subject': 'geometry'}, adapter_spec('26', 'example-org/model-b', 'example-org/model-b', shots=8,
                                                          cot='Think step by step.', temperature=0.7, outputs=4,
                                                          max_eval=500), metrics=('math_equiv',)),
    ]},
    'classic': {'releases': ['v0.4.0'], 'gzip': False, 'updated': '2026-08-01T00:00:00.000Z', 'specs': [
        spec(QA, {'dataset': 'example'}, adapter_spec('21', 'example-org/model-a', None, shots=0)),
    ]},
    'mmlu': {'releases': ['v1.13.0'], 'gzip': True, 'updated': '2025-12-01T00:00:00.000Z', 'specs': [
        spec(QA, {'subject': 'anatomy'}, adapter_spec('27', 'example-org/model-a', 'together/model-a', method='multiple_choice_joint')),
    ]},
}


def response(name: str, url: str, body: bytes, headers=(('Content-Type', 'application/json; charset=UTF-8'),)) -> None:
    with open(os.path.join(HERE, name), 'wb') as f:
        f.write(body)
    with open(os.path.join(HERE, name + '.headers.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'url': url, 'status': 200, 'headers': [list(h) for h in headers]}, f, indent=1)
        f.write('\n')


def listing(name: str, prefix: str, prefixes=(), items=()) -> None:
    doc = {'kind': 'storage#objects'}
    if prefixes:
        doc['prefixes'] = list(prefixes)
    if items:
        doc['items'] = list(items)
    response(name, H.list_url(prefix), (json.dumps(doc, indent=1, sort_keys=True) + '\n').encode('utf-8'))


def main() -> int:
    for f in os.listdir(HERE):
        if f.endswith('.json') and f != 'manifest.json':
            os.remove(os.path.join(HERE, f))
    listing('root.json', '', prefixes=['audio/'] + ['%s/' % s for s in SUITES])
    listing('audio-releases.json', 'audio/' + H.RELEASES)
    for suite, s in SUITES.items():
        base = '%s/%s' % (suite, H.RELEASES)
        listing('%s-releases.json' % suite, base, prefixes=['%s%s/' % (base, r) for r in s['releases']])
        latest = H.newest(['%s%s/' % (base, r) for r in s['releases']])
        body = json.dumps(s['specs'], indent=1).encode('utf-8')
        stored = gzip.compress(body, mtime=0) if s['gzip'] else body
        gen = str(1781128860000000 + len(stored))
        item = {'name': latest + H.RUN_SPECS, 'size': str(len(stored)), 'generation': gen, 'updated': s['updated'],
                'md5Hash': base64.b64encode(hashlib.md5(stored).digest()).decode(), 'contentType': 'application/json'}
        if s['gzip']:
            item['contentEncoding'] = 'gzip'
        runs = {'name': latest + 'runs.json', 'size': '4', 'generation': '1', 'updated': s['updated'], 'md5Hash': 'x'}
        listing('%s-objects.json' % suite, latest, items=[runs, item])
        response('%s-run_specs.bin' % suite, H.media_url(item['name'], gen), stored)
    print('wrote the synthetic bucket: %d suites' % (len(SUITES) + 1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
