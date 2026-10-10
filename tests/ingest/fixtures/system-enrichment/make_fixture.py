#!/usr/bin/env python3
"""Generate the synthetic OpenRouter and LiteLLM responses the enrichment tests read (P5-S6-T07).

    python tests/ingest/fixtures/system-enrichment/make_fixture.py

Why synthetic. Neither feed states a licence for its data (OpenRouter's list states none; LiteLLM's repository reads
NOASSERTION), so neither is committed. What is real is the shape: OpenRouter's `{"data": [...]}` with every key a
model carries on the live endpoint (2026-10-10), and LiteLLM's mapping of model keys to entries, `sample_spec`
included. Every model, organisation, price and date is invented. tests/ingest/test_system_enrichment.py regenerates
the files and compares bytes.

The cases, named so the tests can point at them:
    example-lab/model-alpha     matches a System's external id exactly
    example-lab/model-beta      its canonical_slug matches an alias exactly; its :batch route shares that slug,
                                as 86 routes did on the live list
    example-lab/model-alpha:free, Example-Lab/Model-Alpha
                                near misses: a fuzzy matcher would take them; an exact lookup does not
    other-lab/model-gamma, stealth/union-alpha
                                unmatched: human tasks, never Systems
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def model(mid, slug, name, hf=None, created=1788220800, context=131072, prompt='0.000001', completion='0.000004',
          params=('max_tokens', 'temperature', 'top_p')):
    return {'id': mid, 'canonical_slug': slug, 'hugging_face_id': hf, 'name': name, 'created': created,
            'description': 'An invented model for the fixture.', 'context_length': context,
            'architecture': {'modality': 'text->text', 'input_modalities': ['text'], 'output_modalities': ['text'],
                             'tokenizer': 'Other', 'instruct_type': None},
            'pricing': {'prompt': prompt, 'completion': completion, 'request': '0', 'image': '0'},
            'top_provider': {'context_length': context, 'max_completion_tokens': 16384, 'is_moderated': False},
            'per_request_limits': None, 'supported_parameters': list(params), 'default_parameters': {},
            'expiration_date': None, 'knowledge_cutoff': None, 'links': {}, 'reasoning': None,
            'supported_voices': None}


MODELS = [
    model('example-lab/model-alpha', 'example-lab/model-alpha-20260901', 'Example Lab: Model Alpha',
          hf='example-lab/Model-Alpha'),
    model('example-lab/model-beta', 'example-lab/model-beta-20260815', 'Example Lab: Model Beta', created=1786752000,
          params=('max_tokens', 'reasoning', 'tools')),
    model('example-lab/model-beta:batch', 'example-lab/model-beta-20260815', 'Example Lab: Model Beta (batch)',
          created=1786752000, prompt='0.0000015', completion='0.0000075', params=('max_tokens', 'reasoning', 'tools')),
    model('example-lab/model-alpha:free', 'example-lab/model-alpha-20260901:free', 'Example Lab: Model Alpha (free)',
          prompt='0', completion='0'),
    model('Example-Lab/Model-Alpha', 'Example-Lab/Model-Alpha', 'Example Lab: Model Alpha (mirror)'),
    model('other-lab/model-gamma', 'other-lab/model-gamma-20260701', 'Other Lab: Model Gamma'),
    model('stealth/union-alpha', 'stealth/union-alpha', 'Union Alpha (stealth)', created=1791000000),
]

PRICES = {
    'sample_spec': {'max_tokens': 'LEGACY parameter. set to max_output_tokens if provider specifies it.',
                    'input_cost_per_token': 0.0, 'output_cost_per_token': 0.0, 'litellm_provider': 'one of ...',
                    'mode': 'one of chat, embedding, ...'},
    'example-lab/model-alpha': {'max_input_tokens': 131072, 'max_output_tokens': 16384, 'input_cost_per_token': 1e-06,
                                'output_cost_per_token': 4e-06, 'litellm_provider': 'example-lab', 'mode': 'chat'},
    'model-beta': {'max_input_tokens': 200000, 'max_output_tokens': 32000, 'input_cost_per_token': 3e-06,
                   'output_cost_per_token': 1.5e-05, 'litellm_provider': 'example-lab', 'mode': 'chat'},
    'openrouter/example-lab/model-alpha': {'input_cost_per_token': 1.1e-06, 'output_cost_per_token': 4.4e-06,
                                           'litellm_provider': 'openrouter', 'mode': 'chat'},
    'other/model-delta': {'input_cost_per_token': 5e-07, 'output_cost_per_token': 1e-06, 'litellm_provider': 'other',
                          'mode': 'chat'},
}


def response(folder: str, name: str, url: str, body: bytes, headers: list) -> None:
    os.makedirs(os.path.join(HERE, folder), exist_ok=True)
    with open(os.path.join(HERE, folder, name), 'wb') as f:
        f.write(body)
    with open(os.path.join(HERE, folder, name + '.headers.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'url': url, 'status': 200, 'headers': headers}, f, indent=1)
        f.write('\n')


def main() -> int:
    response('openrouter', 'models.json', 'https://openrouter.ai/api/v1/models',
             (json.dumps({'data': MODELS}, indent=1) + '\n').encode('utf-8'),
             [['Content-Type', 'application/json']])                  # the live endpoint sends no ETag
    response('litellm', 'prices.json',
             'https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json',
             (json.dumps(PRICES, indent=4) + '\n').encode('utf-8'),
             [['Content-Type', 'text/plain; charset=utf-8'], ['ETag', '"fixture-litellm-1"']])
    print('wrote %d OpenRouter models and %d LiteLLM entries' % (len(MODELS), len(PRICES)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
