"""Tests for ingest/crosswalk.py and data/aliases/systems.yaml (P3-S3-T05; 04 S10, 07 S5.1-5.3).

The verify: "bench resolve --candidates reports zero unresolved model_version strings. Every entry that came
from the fuzzy band is a human decision and carries decided_by; a test asserts no alias exists without one."
The zero is reached only after the human pass (step 4), so what is tested here is the machinery that gets
there: the generator's rules on a synthetic Epoch export, the `bench resolve --systems` report, and, on the
committed table, that every row carries decided_by and no row from the band was decided by the agent.
"""
import csv
import os
import sys

import pytest
import yaml
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest import crosswalk as C  # noqa: E402
from ingest import resolve as R  # noqa: E402
from schema.entities import AliasFile, UnresolvedFile  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

HAS_EPOCH = os.path.isfile(os.path.join(C.EPOCH, C.MODELS))


# ---- a synthetic export and catalogue ------------------------------------------------------------------

REGISTRY = [
    # model_version, model_group, date, organization
    ('claude-x-20250101', 'Claude X', '2025-01-01', 'Anthropic'),
    ('claude-x-20250101_max', 'Claude X', '2025-01-01', 'Anthropic'),
    ('claude-x-20250101_unknown', 'Claude X', '2025-01-01', 'Anthropic'),
    ('claude-x-20250101_16K', 'Claude X', '2025-01-01', 'Anthropic'),
    ('chutes/Claude-X', 'Claude X', '2025-01-01', 'Anthropic'),
    ('nebula/claude-x', 'Claude X', '2025-01-01', 'Anthropic'),
    ('MiniCPM-V-2_6', 'MiniCPM-V-2_6', '2024-08-06', 'OpenBMB'),
    ('vortex-1-fast-reasoning', 'Vortex 1 Fast', '2025-06-01', 'Vortex'),
    ('vortex-1-thinking-0601', 'Vortex 1 Thinking', '2025-06-01', 'Vortex'),
    ('unused-in-results', 'Claude X', '2025-01-01', 'Anthropic'),
]
RESULTS = [
    # Model version, Name
    ('claude-x-20250101', 'Claude X'),
    ('claude-x-20250101_max', 'Claude X (max)'),
    ('claude-x-20250101_unknown', 'Claude X'),
    ('claude-x-20250101_16K', 'Claude X (16K thinking)'),
    ('claude-x-20250101_16K', 'Claude X (16K thinking)'),
    ('chutes/Claude-X', 'Claude X via Chutes'),
    ('nebula/claude-x', 'Claude X'),
    ('MiniCPM-V-2_6', 'MiniCPM-V 2.6'),
    ('vortex-1-fast-reasoning', 'Vortex 1 Fast (reasoning)'),
    ('vortex-1-thinking-0601', 'Vortex 1 Thinking'),
]


def _stub(root, ident, name, groups, versions):
    path = root / 'data' / 'systems' / '_stubs' / (ident + '.yaml')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({
        'id': ident, 'name': name, 'aliases': [], 'organizations': [],
        'external_ids': {'epoch_model_group': groups[0]},
        'epoch': {'model_groups': groups, 'versions': [{'model_version': v} for v in versions]}}), encoding='utf-8')


def _org(root, ident):
    path = root / 'data' / 'organizations' / '_stubs' / (ident + '.yaml')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({'id': ident, 'name': ident[4:].title()}), encoding='utf-8')


@pytest.fixture
def world(tmp_path):
    epoch = tmp_path / 'epochdl'
    epoch.mkdir()
    with open(epoch / C.MODELS, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['model_version', 'model_group', 'date', 'display_name', 'organization', 'country',
                    'accessibility', 'training_compute_flop'])
        for v, g, d, o in REGISTRY:
            w.writerow([v, g, d, '', o, '', '', ''])
    with open(epoch / 'bench_a_external.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['Model version', 'Score', 'Name'])
        for v, n in RESULTS:
            w.writerow([v, '0.5', n])
    root = tmp_path / 'repo'
    claude = [v for v, g, _, _ in REGISTRY if g == 'Claude X']
    _stub(root, 'claude-x', 'Claude X', ['Claude X'], claude)
    _stub(root, 'minicpm-v-2-6', 'MiniCPM-V-2_6', ['MiniCPM-V-2_6'], ['MiniCPM-V-2_6'])
    _stub(root, 'vortex-1-fast', 'Vortex 1 Fast', ['Vortex 1 Fast'], ['vortex-1-fast-reasoning'])
    _stub(root, 'vortex-1-thinking', 'Vortex 1 Thinking', ['Vortex 1 Thinking'], ['vortex-1-thinking-0601'])
    return str(epoch), str(root)


def run(world):
    decisions, files = C.build(*world)
    return {d.raw: d for d in decisions}, files


def rows(files):
    return {r['alias']: r for r in yaml.safe_load(files[C.ALIASES])}


def batch(files):
    return {r['observed']: r for r in yaml.safe_load(files[C.BATCH]) or []}


# ---- the generator's rules ---------------------------------------------------------------------------

def test_every_result_string_is_an_alias_or_a_proposal_and_no_registry_only_string_is_either(world):
    d, files = run(world)
    seen = set(rows(files)) | set(batch(files))
    assert seen == {v for v, _ in RESULTS}
    assert not set(rows(files)) & set(batch(files))
    assert 'unused-in-results' not in seen


def test_a_plain_string_is_an_exact_high_confidence_alias_with_an_extracts_block(world):
    r = rows(run(world)[1])['claude-x-20250101']
    assert r == {'alias': 'claude-x-20250101', 'resolves_to': 'system:claude-x', 'extracts': {}, 'kind': 'exact',
                 'confidence': 'high', 'decided_by': C.DECIDED_BY, 'decided_on': C.date.fromisoformat(C.DECIDED_ON),
                 'source': C.SOURCE}


def test_an_effort_suffix_is_routed_and_unknown_is_null_never_a_default(world):
    r = rows(run(world)[1])
    assert r['claude-x-20250101_max']['extracts'] == {'eval_conditions.reasoning_effort': 'max'}
    assert r['claude-x-20250101_max']['kind'] == 'provider-endpoint'
    assert r['claude-x-20250101_unknown']['extracts'] == {'eval_conditions.reasoning_effort': None}


def test_a_name_with_an_underscore_in_it_is_not_a_suffix(world):
    assert rows(run(world)[1])['MiniCPM-V-2_6']['resolves_to'] == 'system:minicpm-v-2-6'


def test_a_condition_word_in_the_systems_own_name_is_identity(world):
    assert 'vortex-1-thinking-0601' in rows(run(world)[1])


def test_a_budget_suffix_is_proposed_with_the_name_column_and_three_candidates(world):
    p = batch(run(world)[1])['claude-x-20250101_16K']
    assert p['reason'] == 'unparseable'
    assert len(p['suggestions']) == 3 and p['suggestions'][0][0] == 'claude-x'
    assert "'Claude X (16K thinking)' (2 rows)" in p['human_task']
    assert "the suffix '_16K'" in p['human_task']


def test_a_condition_word_outside_the_name_is_proposed(world):
    assert "the word 'reasoning'" in batch(run(world)[1])['vortex-1-fast-reasoning']['human_task']


def test_an_unlisted_namespace_is_proposed_not_guessed(world):
    assert "the namespace 'nebula/'" in batch(run(world)[1])['nebula/claude-x']['human_task']


def test_a_serving_provider_with_no_organization_record_is_proposed(world):
    p = batch(run(world)[1])['chutes/Claude-X']
    assert 'the serving provider org-chutes' in p['human_task']


def test_with_the_organization_record_the_serving_provider_is_routed(world):
    import pathlib
    _org(pathlib.Path(world[1]), 'org-chutes')
    r = rows(run(world)[1])['chutes/Claude-X']
    assert r['extracts'] == {'serving_provider': 'org-chutes'} and r['kind'] == 'provider-endpoint'


def test_the_resolver_disagreeing_with_the_registry_is_an_ambiguous_match(world):
    import pathlib
    # The registry's System without its version list (as a promoted System is), and a second System whose id
    # is the bare string: the resolver names the second, the registry the first.
    _stub(pathlib.Path(world[1]), 'vortex-1-fast', 'Vortex 1 Fast', ['Vortex 1 Fast'], [])
    _stub(pathlib.Path(world[1]), 'vortex-1-fast-reasoning', 'vortex-1-fast-reasoning', ['Other'], [])
    d, files = run(world)
    p = batch(files)['vortex-1-fast-reasoning']
    assert p['reason'] == 'ambiguous-match'
    assert 'the resolver names system:vortex-1-fast-reasoning' in p['human_task']


def test_the_outputs_validate(world):
    _, files = run(world)
    AliasFile.model_validate(yaml.safe_load(files[C.ALIASES]))
    UnresolvedFile.model_validate(yaml.safe_load(files[C.BATCH]))


# ---- a person's decision ---------------------------------------------------------------------------------

def _decide(world, files, alias, **extracts):
    """A person writes the proposal's row into the committed table."""
    table = yaml.safe_load(files[C.ALIASES])
    table.append({'alias': alias, 'resolves_to': 'system:claude-x', 'extracts': extracts, 'kind': 'provider-endpoint',
                  'confidence': 'high', 'decided_by': 'curator-a', 'decided_on': '2026-10-08',
                  'source': C.SOURCE})
    _commit(world, {C.ALIASES: yaml.safe_dump(table, sort_keys=False)})


def test_a_human_row_is_kept_verbatim_and_its_string_leaves_the_band(world):
    _, files = run(world)
    _decide(world, files, 'claude-x-20250101_16K', **{'eval_conditions.thinking_token_budget': 16000})
    _, again = run(world)
    r = rows(again)['claude-x-20250101_16K']
    assert r['decided_by'] == 'curator-a'
    assert r['extracts'] == {'eval_conditions.thinking_token_budget': 16000}
    assert 'claude-x-20250101_16K' not in batch(again)


def _commit(world, files):
    """Write the generated table where the repository keeps it."""
    path = os.path.join(world[1], *C.ALIASES.split('/'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(files[C.ALIASES])


def test_unresolved_counts_down_as_people_decide(world):
    _, files = run(world)
    _commit(world, files)
    before = C.unresolved(*world)
    assert set(before) == set(batch(files))
    _decide(world, run(world)[1], 'claude-x-20250101_16K', **{'eval_conditions.thinking_token_budget': 16000})
    assert set(C.unresolved(*world)) == set(before) - {'claude-x-20250101_16K'}


def test_bench_resolve_systems_exits_1_while_any_is_unresolved_and_0_after(world, monkeypatch):
    from tools.cli import app
    monkeypatch.setattr(C, 'EPOCH', world[0])
    monkeypatch.setattr(C, 'ROOT', world[1])
    _, files = run(world)
    _commit(world, files)
    res = CliRunner().invoke(app, ['resolve', '--candidates', '--systems'])
    assert res.exit_code == 1, res.output
    assert 'unresolved  claude-x-20250101_16K' in res.output
    for alias in batch(files):
        _decide(world, run(world)[1], alias)
    res = CliRunner().invoke(app, ['resolve', '--candidates', '--systems'])
    assert res.exit_code == 0, res.output
    assert '0 unresolved' in res.output


def test_bench_resolve_systems_without_the_export_exits_2(tmp_path, monkeypatch):
    from tools.cli import app
    monkeypatch.setattr(C, 'EPOCH', str(tmp_path / 'nothing'))
    assert CliRunner().invoke(app, ['resolve', '--systems']).exit_code == 2


# ---- the unrouted rule, on the strings that motivated it ----------------------------------------------

@pytest.mark.parametrize('raw, names, flagged', [
    ('claude-opus-4-6_120K', ['Claude Opus 4.6'], 'suffix'),
    ('DeepSeek-V3.1_thinking', ['DeepSeek-V3.1'], 'suffix'),
    ('gpt-5.6-sol_promax', ['GPT-5.6 Sol'], 'suffix'),
    ('Qwen-1_8B', ['Qwen-1_8B'], None),
    ('phi-1_5', ['Phi-1.5'], None),
    ('video_chat2_mistral', ['video_chat2_mistral'], None),
    ('moonshotai/kimi-k2-0905', ['Kimi K2 (Sep 2025)'], 'namespace'),
    ('amazon.nova-pro-v1:0', ['Amazon Nova Pro'], 'bedrock'),
    ('QwQ-32B (16K thinking)', ['QwQ-32B'], 'condition word'),
    ('grok-4-1-fast-non-reasoning', ['Grok 4.1 Fast'], 'condition word'),
    ('Llama-4-Maverick-17B-128E-Instruct-FP8', ['Llama 4 Maverick'], 'condition word'),
    ('Qwen3-235B-A22B-Thinking-2507', ['Qwen3-235B-A22B-Thinking (Jul 2025)'], None),
    ('gemini-2.5-pro-preview-06-05', ['Gemini 2.5 Pro (Jun 2025)'], None),
])
def test_unrouted(raw, names, flagged):
    got = C.unrouted(raw, R.parse(raw)[0], names)
    assert (C.reason_key(got[0]) if got else None) == flagged, got


# ---- the committed table (no export needed) -----------------------------------------------------------------

def _committed():
    return read_yaml(os.path.join(ROOT, *C.ALIASES.split('/')))


def _systems():
    return {d['id']: d for d in C.systems(ROOT)}


def test_verify_no_alias_exists_without_decided_by():
    table = _committed()
    AliasFile.model_validate(table)
    assert table and all(str(r.get('decided_by') or '').strip() for r in table)   # get-default: the assertion is that it is there


def test_verify_no_alias_from_the_band_was_decided_by_the_agent():
    """A string 04 S10's parse cannot fully route is a person's decision (07 S5.2), whoever generated the
    rest: no such row may carry the agent's decided_by."""
    by_id = _systems()
    agent_band = []
    for r in _committed():
        if r['decided_by'] == C.DECIDED_BY:
            sid = r['resolves_to'].split(':', 1)[1]
            if C.unrouted(r['alias'], R.parse(r['alias'])[0], C._names(by_id[sid])):
                agent_band.append(r['alias'])
    assert agent_band == []


def test_every_agent_row_is_high_confidence_sourced_and_routes_what_the_parse_strips():
    for r in _committed():
        if r['decided_by'] != C.DECIDED_BY:
            continue
        assert r['confidence'] == 'high' and r['source'] == C.SOURCE and 'extracts' in r, r
        _, routed, _ = R.parse(r['alias'])
        assert r['extracts'] == routed, r
        assert r['kind'] == ('provider-endpoint' if routed else 'exact'), r


def test_the_proposals_and_the_aliases_are_disjoint_and_the_batch_validates():
    proposals = read_yaml(os.path.join(ROOT, *C.BATCH.split('/'))) or []
    UnresolvedFile.model_validate(proposals)
    assert not {p['observed'] for p in proposals} & {r['alias'] for r in _committed()}
    assert all(len(p['suggestions']) == 3 for p in proposals)


def test_the_alias_table_stays_under_the_data_file_limit():
    """05 S9 check 7 rejects any file in data/ over 256 KB."""
    assert os.path.getsize(os.path.join(ROOT, *C.ALIASES.split('/'))) < 256 * 1024


@pytest.mark.skipif(not HAS_EPOCH, reason='epochdl/ is gitignored; `python scripts/epoch_audit.py --fetch`')
def test_the_committed_files_are_a_fresh_run():
    assert C.main(['--check']) == 0


@pytest.mark.skipif(not HAS_EPOCH, reason='epochdl/ is gitignored; `python scripts/epoch_audit.py --fetch`')
def test_every_one_of_the_927_strings_is_an_alias_or_a_proposal():
    proposals = {p['observed'] for p in read_yaml(os.path.join(ROOT, *C.BATCH.split('/'))) or []}
    held = {r['alias'] for r in _committed()}
    assert set(C.observe()) == held | proposals and len(C.observe()) == 927
