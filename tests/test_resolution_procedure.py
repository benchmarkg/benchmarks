"""Tests for ingest/resolve.py, identity resolution steps 1-4 (P3-S3-T02; 04 S10, 07 S5.2).

The verify uses 07 S5.2's worked strings as fixtures. DONE WHEN: "All six worked strings resolve as 07
S5.2 shows, claude-opus-4-6_120K becomes an Unresolved rather than a guess, and _unknown yields null."
The six: 07 S5.2's five, and 04 S10's own alias example, accounts/fireworks/models/glm-4p6.
"""
import os
import sys
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest.resolve import EFFORT_FIELD, Entry, Index, normalise, parse  # noqa: E402
from schema.entities import Alias  # noqa: E402


def alias(text, to, extracts=None, conf='high', kind='provider-endpoint'):
    return Alias(alias=text, resolves_to=to, extracts=extracts or {}, kind=kind, confidence=conf,
                 decided_by='a-curator', decided_on=date(2026, 9, 17))


# The entity graph 07 S5.2's results presuppose, and the alias rows it says the matches go through
SYSTEMS = Index('system', [
    Entry('qwen3-235b-a22b-thinking', 'Qwen3-235B-A22B-Thinking',
          versions=(('2507', 'qwen3-235b-a22b-thinking-2507'),)),
    Entry('deepseek-r1', 'DeepSeek-R1', versions=(('0528', 'deepseek-ai/DeepSeek-R1-0528'),)),
    Entry('amazon-nova-pro', 'Amazon Nova Pro', versions=(('v1-0', 'amazon.nova-pro-v1:0'),)),
    Entry('gpt-6-astra', 'GPT-6 Astra'),
    Entry('claude-opus-4-6', 'Claude Opus 4.6', external_ids=('claude-opus-4-6',)),
    Entry('glm-4-6', 'GLM-4.6'),
    Entry('gpt-4o', 'GPT-4o', aliases=('GPT 4 omni',), external_ids=('openai/gpt-4o',)),
], [
    alias('qwen3-235b-a22b-thinking-2507', 'system:qwen3-235b-a22b-thinking', kind='exact'),
    alias('amazon.nova-pro-v1:0', 'system:amazon-nova-pro', {'serving_provider': 'org-aws-bedrock'}),
    alias('glm-4p6', 'system:glm-4-6', kind='spelling', conf='medium'),
])


# ---- the six worked strings --------------------------------------------------------------------------

def test_a_provider_prefix_is_stripped_routed_and_the_residue_matches_the_alias_table():
    r = SYSTEMS.resolve('accounts/fireworks/models/qwen3-235b-a22b-thinking-2507')
    assert (r.entity, r.version, r.confidence, r.step) == ('system:qwen3-235b-a22b-thinking', '2507', 'high', 4)
    assert r.extracts == {'serving_provider': 'org-fireworks'}
    assert r.residue == 'qwen3-235b-a22b-thinking-2507'


def test_chutes_and_a_version_named_by_name_plus_version():
    r = SYSTEMS.resolve('chutes/DeepSeek-R1-0528')
    assert (r.entity, r.version, r.confidence) == ('system:deepseek-r1', '0528', 'high')
    assert r.extracts == {'serving_provider': 'org-chutes'}


def test_a_bedrock_identifier_resolves_with_its_alias_records_extracts():
    # the string is also the version's api_identifier, so step 1 matches it; the alias record for the
    # same string still routes its serving provider rather than dropping it
    r = SYSTEMS.resolve('amazon.nova-pro-v1:0')
    assert (r.entity, r.version, r.step) == ('system:amazon-nova-pro', 'v1-0', 1)
    assert r.extracts == {'serving_provider': 'org-aws-bedrock'}
    no_identifier = Index('system', [Entry('amazon-nova-pro', 'Amazon Nova Pro')], SYSTEMS.alias_records)
    r = no_identifier.resolve('amazon.nova-pro-v1:0')                 # the alias alone, step 2
    assert (r.entity, r.step, r.extracts) == ('system:amazon-nova-pro', 2, {'serving_provider': 'org-aws-bedrock'})
    # 07 S5.2 writes the version v1:0; a SystemVersion id may not hold a colon, so the version is v1-0
    # and its api_identifier keeps the string verbatim


def test_an_effort_suffix_becomes_a_reasoning_effort():
    r = SYSTEMS.resolve('gpt-6-astra_max')
    assert (r.entity, r.confidence, r.step) == ('system:gpt-6-astra', 'high', 4)
    assert r.extracts == {EFFORT_FIELD: 'max'}


def test_claude_opus_4_6_120k_is_unresolved_not_a_guess():
    r = SYSTEMS.resolve('claude-opus-4-6_120K')
    assert r.entity is None and r.unresolved is not None
    u = r.unresolved
    assert u.reason == 'unparseable' and u.observed == 'claude-opus-4-6_120K'
    assert u.suggestions == [('system:claude-opus-4-6', 1.0)]          # offered, never applied
    assert 'context window or a thinking budget' in u.human_task
    assert SYSTEMS.system('claude-opus-4-6_120K') == (None, 0.0)


def test_04_s10s_fireworks_example_through_a_spelling_alias():
    r = SYSTEMS.resolve('accounts/fireworks/models/glm-4p6')
    assert (r.entity, r.confidence, r.step) == ('system:glm-4-6', 'medium', 4)   # the alias record's confidence
    assert r.extracts == {'serving_provider': 'org-fireworks'}


# ---- _unknown, and the rest of the procedure --------------------------------------------------------------

def test_unknown_effort_is_an_explicit_null_never_a_default():
    r = SYSTEMS.resolve('gpt-6-astra_unknown')
    assert r.entity == 'system:gpt-6-astra'
    assert EFFORT_FIELD in r.extracts and r.extracts[EFFORT_FIELD] is None


@pytest.mark.parametrize('raw, step', [
    ('openai/gpt-4o', 1),            # external_ids
    ('GPT 4 omni', 3),               # an alias on the entity, normalised
    ('gpt-4o', 3),                   # the id
    ('GPT-4o', 3),                   # the name, case and punctuation aside
    ('  gpt 4O ', 3),
])
def test_steps_1_to_3_in_order(raw, step):
    r = SYSTEMS.resolve(raw)
    assert (r.entity, r.step, r.extracts) == ('system:gpt-4o', step, {})


def test_an_exact_identifier_wins_before_any_parse():
    # an api_identifier carrying a date-like tail is matched whole at step 1, not taken apart
    idx = Index('system', [Entry('gpt-4o', 'GPT-4o', versions=(('2024-08-06', 'gpt-4o-2024-08-06'),))])
    r = idx.resolve('gpt-4o-2024-08-06')
    assert (r.entity, r.version, r.step) == ('system:gpt-4o', '2024-08-06', 1)


def test_a_stripped_date_tail_becomes_the_version():
    r = SYSTEMS.resolve('gpt-4o-2024-11-20_high')
    assert (r.entity, r.version, r.step) == ('system:gpt-4o', '2024-11-20', 4)
    assert r.extracts == {EFFORT_FIELD: 'high'}


def test_a_provider_suffix_is_routed():
    r = SYSTEMS.resolve('GLM-4.6 (Novita)')
    assert (r.entity, r.extracts) == ('system:glm-4-6', {'serving_provider': 'org-novita'})


def test_the_strips_run_in_04_s10s_fixed_order():
    # prefix, provider suffix, effort, date -- each anchored at its end of what the last one left
    assert parse('accounts/fireworks/models/gpt-4o-2024-11-20_high') == (
        'gpt-4o', {'serving_provider': 'org-fireworks', EFFORT_FIELD: 'high'}, '2024-11-20')
    assert parse('GLM-4.6 (Together)') == ('GLM-4.6', {'serving_provider': 'org-together'}, None)
    # the effort strip runs before the date strip, so an effort written BEFORE a date tail is not
    # reached: it stays in the residue for steps 1-3, and an unmatched residue is Unresolved, not guessed
    assert parse('together/x_xhigh-2026-01-02') == ('x_xhigh', {'serving_provider': 'org-together'}, '2026-01-02')
    # one provider prefix at most: the first that matches
    assert parse('chutes/together/x') == ('together/x', {'serving_provider': 'org-chutes'}, None)


def test_a_string_that_names_two_entities_is_not_resolved_by_normalising():
    idx = Index('system', [Entry('a-1', 'Model A'), Entry('a-2', 'model-a')])
    r = idx.resolve('MODEL A')
    assert r.entity is None and r.unresolved.reason == 'no-match'


def test_nothing_matching_is_unresolved_with_a_curation_task():
    r = SYSTEMS.resolve('chutes/mystery-model_high')
    assert r.entity is None and r.unresolved.reason == 'no-match'
    assert r.extracts == {'serving_provider': 'org-chutes', EFFORT_FIELD: 'high'}   # still routed, for the curator
    assert 'data/aliases/systems.yaml' in r.unresolved.human_task
    assert r.unresolved.fingerprint == SYSTEMS.resolve('chutes/mystery-model_high').unresolved.fingerprint


def test_an_alias_to_another_kind_is_ignored():
    idx = Index('system', [Entry('x-model', 'X Model')], [alias('xm', 'benchmark:xm-bench', kind='spelling')])
    assert idx.resolve('xm').entity is None


def test_normalise_is_04_s10s():
    assert normalise('  Claude 3.5   Sonnet (new) ') == 'claude 3 5 sonnet new'


def test_the_repository_index_loads():
    idx = Index.load('system')
    assert 'claude-opus-4-5' in idx.entries                 # a curated System (P0-S8-T05)
    assert idx.system('Claude Opus 4.5') == ('claude-opus-4-5', 1.0)
    assert idx.system('claude-opus-4-5_high')[0] == 'claude-opus-4-5'
