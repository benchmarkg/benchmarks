"""The harness and MTEB shallow-clone ingest (P5-S5-T02; 06 S3.3, 07 S1.2).

Verified against tests/ingest/fixtures/harness/: pruned copies of the two pinned commits, every file the pinned
blob byte for byte (the README says which were kept). Each is made into a one-commit repository and read by the
adapter's own object-store reader, so the offline run goes through the code a live clone does.

  - the done_when: at least 200 task directories parse from the pinned commit -- all 221 of the fixture's, and
    every task config in it;
  - the failure case: a mutated layout hard-fails, before any candidate, with an adapter-broken issue; a
    single broken config is a human task, not drift;
  - 06 S3.3's mapping, for a task whose dataset is a catalogued benchmark: shots, sampling, max tokens and
    repeats suggested only where stated; output_type and metrics kept; the prompt template a pointer, never
    its text; a dataset nobody catalogues gets no draft and is counted;
  - MTEB results enumerated with model, revision and task from the path, and never read;
  - the network: a fetch asks the gate for both smart-HTTP endpoints first; a blob the store lacks is an
    error, never a lazy fetch; the fixture run touches no gate at all.
"""
from __future__ import annotations

import json
import os
import shutil
import stat

import pytest
from typer.testing import CliRunner

from ingest import gates
from ingest.adapters import github_clones as G
from ingest.http import policy as P
from ingest.resolve import Entry, Index

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'harness')
HARNESS_FIX = os.path.join(FIX, 'lm-evaluation-harness')
MTEB_FIX = os.path.join(FIX, 'mteb-results')


def manifest():
    with open(os.path.join(FIX, 'manifest.json'), encoding='utf-8') as f:
        return json.load(f)


def resolvers():
    """Four catalogued benchmarks, matched on their Hugging Face ids, and one whose name a fuzzy match would take."""
    return {'benchmark': Index('benchmark', [
        Entry('gsm8k', 'GSM8K', external_ids=('openai/gsm8k',)),
        Entry('arc-ai2', 'ARC (AI2 Reasoning Challenge)', external_ids=('allenai/ai2_arc',)),
        Entry('mmlu', 'MMLU', external_ids=('cais/mmlu',)),
        Entry('hellaswag', 'HellaSwag', external_ids=('Rowan/hellaswag',)),
        Entry('arc-agi-3', 'ARC-AGI-3', aliases=('arc', 'ARC Easy')),
    ])}


class NoGate:
    def admit(self, url):
        raise AssertionError('the fixture run asked the gate for %s' % url)


def source(src, tmp_path):
    return G.fixture_source(src, str(tmp_path))


def harness_run(tmp_path, src=HARNESS_FIX, state=None, **kw):
    return G.run(G.HarnessClone(source(src, tmp_path), gate=NoGate()), state, resolvers(), **kw)


def mutated(tmp_path, src, change):
    dest = tmp_path / 'mutated'
    shutil.copytree(src, dest)
    change(dest)
    return str(dest)


# ---- the done_when ------------------------------------------------------------------------------------------

def test_the_fixture_is_the_pinned_commit():
    m = manifest()
    assert m['lm-eval-harness']['commit'] == G.HARNESS.pin and m['mteb-results']['commit'] == G.MTEB.pin
    assert m['lm-eval-harness']['full_tree_at_the_pin']['task_dirs'] == 221
    assert m['lm-eval-harness']['full_tree_at_the_pin']['task_configs'] == 13125


def test_at_least_200_task_directories_parse(tmp_path):
    adapter = G.HarnessClone(source(HARNESS_FIX, tmp_path), gate=NoGate())
    report = G.run(adapter, None, resolvers())
    assert report['status'] == 'ok', report['errors']
    parsed = {c.hint['path'].split('/')[2] for c in adapter.enumerate(adapter.bundle)
              if adapter.fetch(c).doc['error'] is None}
    assert len(parsed) >= 200
    assert report['counts']['task_dirs'] == len(parsed) == 220      # benchmarks/ holds groups only
    assert report['parsed'] == report['candidates_seen'] == report['counts']['task_configs']
    assert report['unresolved'] == 0


# ---- the failure case: a mutated layout -------------------------------------------------------------------

def _move_tasks(d):
    os.rename(d / 'lm_eval' / 'tasks', d / 'lm_eval' / 'task_configs')


def _drop_licence(d):
    os.remove(d / 'LICENSE.md')


def _relicence(d):
    (d / 'LICENSE.md').write_text('Apache License\nVersion 2.0\n', encoding='utf-8')


def _drop_marker(d):
    os.remove(d / 'lm_eval' / 'tasks' / '__init__.py')


def _flatten(d):
    shutil.move(str(d / 'lm_eval' / 'tasks' / 'gsm8k' / 'gsm8k.yaml'), str(d / 'lm_eval' / 'tasks' / 'gsm8k.yaml'))


def _empty_a_dir(d):
    for f in (d / 'lm_eval' / 'tasks' / 'hellaswag').iterdir():
        f.unlink()
    (d / 'lm_eval' / 'tasks' / 'hellaswag' / 'README.md').write_text('moved\n', encoding='utf-8')


def _fewer_dirs(d):
    for name in sorted(p.name for p in (d / 'lm_eval' / 'tasks').iterdir() if p.is_dir())[:25]:
        shutil.rmtree(d / 'lm_eval' / 'tasks' / name)


def _duplicate_task(d):
    p = d / 'lm_eval' / 'tasks' / 'arc' / 'arc_easy.yaml'
    (d / 'lm_eval' / 'tasks' / 'arc' / 'arc_easy_copy.yaml').write_bytes(p.read_bytes())


@pytest.mark.parametrize('change, says', [
    (_move_tasks, 'lm_eval/tasks/ is not a directory'),
    (_drop_licence, 'LICENSE.md is gone'),
    (_relicence, "no longer says 'MIT License'"),
    (_drop_marker, '__init__.py is gone'),
    (_flatten, 'task configs at the top of lm_eval/tasks/'),
    (_empty_a_dir, 'no task or group config: hellaswag'),
    (_fewer_dirs, 'returned 196 rows; at least 200 are expected'),
    (_duplicate_task, 'task names are no longer unique (arc_easy)'),
])
def test_a_mutated_harness_layout_hard_fails(tmp_path, change, says):
    report = harness_run(tmp_path, mutated(tmp_path, HARNESS_FIX, change))
    assert report['status'] == 'hard-fail'
    assert report['candidates_seen'] == 0 and report['documents'] == [] and report['snapshot'] is None
    assert len(report['errors']) == 1 and report['errors'][0].startswith('schema drift: ') and says in report['errors'][0]
    assert report['issue']['labels'] == ['adapter-broken', 'source:lm-eval-harness']


def _json_at_the_top(d):
    (d / 'results' / 'scores.json').write_text('{}\n', encoding='utf-8')


def _model_without_org(d):
    first = sorted(p for p in (d / 'results').iterdir() if p.is_dir())[0]
    os.rename(first, d / 'results' / 'bare-model')


def _too_shallow(d):
    first = sorted(p for p in (d / 'results').iterdir() if p.is_dir())[0]
    (first / 'STS12.json').write_text('{}\n', encoding='utf-8')


def _drop_results(d):
    shutil.rmtree(d / 'results')
    (d / 'results.json').write_text('{}\n', encoding='utf-8')


def _relicence_mteb(d):
    (d / 'LICENSE').write_text('All rights reserved\n', encoding='utf-8')


@pytest.mark.parametrize('change, says', [
    (_json_at_the_top, 'outside results/<org>__<model>/<revision>/: results/scores.json'),
    (_model_without_org, 'results/bare-model/'),
    (_too_shallow, 'outside results/<org>__<model>/<revision>/'),
    (_drop_results, 'results/ is not a directory'),
    (_relicence_mteb, "no longer says 'CC0 1.0 Universal'"),
])
def test_a_mutated_mteb_layout_hard_fails(tmp_path, change, says):
    report = G.run(G.MtebClone(source(mutated(tmp_path, MTEB_FIX, change), tmp_path), gate=NoGate()))
    assert report['status'] == 'hard-fail' and report['candidates_seen'] == 0
    assert report['errors'][0].startswith('schema drift: ') and says in report['errors'][0], report['errors']
    assert report['issue']['labels'] == ['adapter-broken', 'source:mteb-results']


def test_one_broken_config_is_a_human_task_not_drift(tmp_path):
    def break_include(d):
        p = d / 'lm_eval' / 'tasks' / 'mmlu' / 'default' / 'mmlu_anatomy.yaml'
        p.write_text(p.read_text(encoding='utf-8').replace('_default_template_yaml', '_gone_template_yaml'),
                     encoding='utf-8')
    report = harness_run(tmp_path, mutated(tmp_path, HARNESS_FIX, break_include))
    assert report['status'] == 'ok' and report['unresolved'] == 1
    item = report['unresolved_items'][0]
    assert item['source_key'] == 'harness:mmlu_anatomy' and item['field'] == 'config' and item['reason'] == 'unparseable'
    assert 'include lm_eval/tasks/mmlu/default/_gone_template_yaml is not in the tree' in item['human_task']
    assert report['parsed'] == report['candidates_seen'] - 1


# ---- 06 S3.3's mapping -----------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def documents(tmp_path_factory):
    report = harness_run(tmp_path_factory.mktemp('map'))
    return report, {d['identity']['task']: d for d in report['documents']}


def suggested(doc):
    return {s['field']: s['value'] for s in doc['_suggested']}


def test_only_tasks_on_a_catalogued_dataset_are_drafted(documents):
    report, docs = documents
    assert sorted(docs) == ['arc_easy', 'gsm8k', 'gsm8k_cot', 'gsm8k_llama', 'hellaswag', 'mmlu_anatomy']
    assert report['drafts']['new'] == 6
    assert {d['identity']['benchmark'] for d in docs.values()} == {'arc-ai2', 'gsm8k', 'hellaswag', 'mmlu'}
    assert docs['gsm8k_llama']['identity']['task_dir'] == 'llama3'      # matched on its dataset, wherever it lives
    # ARC-AGI-3's alias `arc` is a name, and only identifiers match: AI2's arc is never ARC-AGI (07 S1.1)
    assert docs['arc_easy']['identity']['benchmark'] == 'arc-ai2'
    assert report['uncatalogued']['aclue tyouisen/aclue'] == 1
    assert sum(report['uncatalogued'].values()) == report['candidates_seen'] - 6


def test_gsm8k_states_its_shots_sampling_and_repeats(documents):
    doc = documents[1]['gsm8k']
    assert suggested(doc) == {'eval_conditions.shots': 5, 'eval_conditions.sampling.temperature': 0.0,
                              'eval_conditions.n_samples': 1, 'eval_conditions.harness': 'lm-evaluation-harness',
                              'execution.runnable_via': ['lm_eval']}
    ident = doc['identity']
    assert ident['dataset'] == {'huggingface': 'openai/gsm8k', 'config': 'main',
                                'splits': {'training': 'train', 'validation': None, 'test': 'test', 'fewshot': 'train'}}
    assert ident['output_type'] == 'generate_until' and ident['task_version'] == '3.0'
    assert ident['metrics'] == [{'metric': 'exact_match', 'aggregation': 'mean', 'higher_is_better': True}]
    assert ident['commit'] == G.HARNESS.pin and ident['config_url'].endswith('/blob/%s/lm_eval/tasks/gsm8k/gsm8k.yaml' % G.HARNESS.pin)


def test_what_a_config_does_not_state_is_not_suggested(documents):
    arc = suggested(documents[1]['arc_easy'])
    assert 'eval_conditions.shots' not in arc and 'eval_conditions.sampling.temperature' not in arc
    assert documents[1]['arc_easy']['identity']['metrics'] == [
        {'metric': 'acc', 'aggregation': 'mean', 'higher_is_better': True},
        {'metric': 'acc_norm', 'aggregation': 'mean', 'higher_is_better': True}]


def test_an_include_is_merged_and_the_files_own_keys_win(documents):
    doc = documents[1]['mmlu_anatomy']
    assert doc['identity']['dataset']['huggingface'] == 'cais/mmlu'               # from the template
    assert doc['identity']['dataset']['config'] == 'anatomy'                      # the file's own
    assert suggested(doc)['eval_conditions.shot_selection'] == 'fixed'            # fewshot_config.sampler: first_n
    assert doc['identity']['includes'] == [G.HARNESS.blob_url(G.HARNESS.pin, 'lm_eval/tasks/mmlu/default/_default_template_yaml')]


def test_the_prompt_template_is_a_pointer_never_its_text(documents):
    report, docs = documents
    assert docs['gsm8k']['identity']['prompt_template'] == {'source': docs['gsm8k']['identity']['config_url'],
                                                            'key': 'doc_to_text', 'kind': 'template'}
    assert docs['hellaswag']['identity']['prompt_template']['kind'] == 'template'
    text = json.dumps(report['documents'])
    for template in ('Question: {{question}}', '{{question.strip()}}', '{{query}}'):
        assert template not in text
    assert 'utils.process_docs' not in text                                     # a function is never imported, nor kept


def test_every_draft_passes_the_discovery_gates(documents):
    for doc in documents[0]['documents']:
        rel = doc['path']
        body = {k: v for k, v in doc.items() if k not in ('path', 'change_class')}
        assert rel.startswith('data/_discovery/lm-eval-harness/cand-harness-')
        gates.schema(body, rel)
        gates.metadata_only(body, rel)
        gates.attribution(body, rel, G.HARNESS_ATTRIBUTION)
        gates.licence_firewall(body, rel, 'permissive-attribution')
        gates.round_trip(body, rel)


def test_an_unreadable_value_is_asked_about_not_suggested():
    found, bad = G.suggestions({'num_fewshot': '5', 'repeats': 0, 'generation_kwargs': {'top_p': 1.5, 'max_gen_toks': 256}})
    assert found == [('eval_conditions.max_output_tokens', 256, 'generation_kwargs.max_gen_toks')]
    assert bad == [('num_fewshot', '5'), ('generation_kwargs.top_p', 1.5), ('repeats', 0)]


# ---- change classes -----------------------------------------------------------------------------------------

def test_an_unchanged_commit_is_no_change_and_a_changed_config_is_a_field_change(tmp_path):
    src, state = source(HARNESS_FIX, tmp_path), G.new_state()
    first = G.run(G.HarnessClone(src, gate=NoGate()), state, resolvers())
    assert first['drafts']['new'] == 6 and state['commit'] == G.HARNESS.pin and len(state['hashes']) == 6
    again = G.run(G.HarnessClone(src, gate=NoGate()), state, resolvers())
    assert again['status'] == 'no-change' and again['candidates_seen'] == 0
    state['commit'] = None                                   # the commit moved; one task's merged config changed
    state['hashes']['harness:gsm8k'] = '0' * 64
    third = G.run(G.HarnessClone(src, gate=NoGate()), state, resolvers())
    assert third['drafts']['field-change'] == 1 and third['drafts']['no-change'] == 5
    assert [d['identity']['task'] for d in third['documents']] == ['gsm8k']


def test_a_task_that_stops_matching_is_counted_gone(tmp_path):
    state = G.new_state()
    state['hashes']['harness:retired_task'] = '0' * 64
    report = harness_run(tmp_path, state=state)
    assert report['drafts']['gone'] == 1 and 'harness:retired_task' not in state['hashes']


# ---- MTEB ------------------------------------------------------------------------------------------------

def test_mteb_results_are_enumerated_from_their_paths(tmp_path):
    adapter = G.MtebClone(source(MTEB_FIX, tmp_path), gate=NoGate())
    report = G.run(adapter)
    assert report['status'] == 'ok', report['errors']
    assert report['counts']['models'] == 13 and report['counts']['experiment_results'] == 1      # 12, and the experiment's
    assert report['candidates_seen'] == report['counts']['result_files'] == sum(report['results_by_task'].values())
    cands = list(adapter.enumerate(adapter.bundle))
    first = cands[0]
    assert first.kind == 'claim' and first.source_key.startswith('mteb:AITeamVN__Vietnamese_Embedding/')
    assert first.hint['model'] == 'AITeamVN/Vietnamese_Embedding' and first.hint['variant'] is None
    assert not any(c.source_key.endswith('model_meta') for c in cands)
    deeper = [c for c in cands if c.hint['variant']]
    assert len(deeper) == 1 and deeper[0].hint['variant'] == 'model_kwargs_{}'
    assert adapter.fetch(first).body == b''                       # the JSON is never read
    assert manifest()['mteb-results']['full_tree_at_the_pin']['result_files'] == 106225


# ---- the network ---------------------------------------------------------------------------------------------

class RecordingGate:
    def __init__(self, refuse=False):
        self.asked, self.refuse = [], refuse

    def admit(self, url):
        self.asked.append(url)
        if self.refuse:
            raise P.RobotsDisallowed(url, 'robots.txt disallows it')


def test_a_fetch_asks_the_gate_for_both_endpoints_before_git_runs(tmp_path):
    gate = RecordingGate(refuse=True)
    report = G.run(G.HarnessClone(gate=gate, clones=str(tmp_path)), None, resolvers())
    assert report['status'] == 'hard-fail' and report['errors'][0].startswith('RobotsDisallowed')
    assert gate.asked == ['https://github.com/EleutherAI/lm-evaluation-harness/info/refs?service=git-upload-pack']
    assert G.git(str(tmp_path / 'lm-eval-harness.git'), 'count-objects').startswith(b'0 objects')


def test_the_policy_lists_github_and_its_robots_txt_allows_the_endpoints():
    pol = P.Policy.load()
    assert 'github.com' in pol.hosts and pol.hosts['github.com'].max_requests == 12
    robots = P.parse_robots('User-agent: *\nDisallow: /*.git$\nDisallow: */tarball/\nDisallow: /*/archive/\n', 'UAIBI')
    assert robots.allowed('/EleutherAI/lm-evaluation-harness/info/refs?service=git-upload-pack')
    assert robots.allowed('/EleutherAI/lm-evaluation-harness/git-upload-pack')
    assert not robots.allowed('/EleutherAI/lm-evaluation-harness.git')


def test_a_missing_blob_is_an_error_never_a_lazy_fetch(tmp_path):
    src = tmp_path / 'src'
    (src / 'a').mkdir(parents=True)
    (src / 'a' / 'x.yaml').write_text('task: x\n', encoding='utf-8')
    repo = str(tmp_path / 'r')
    commit = G.repo_from_directory(str(src), repo)
    tree = G.Tree(repo, commit)
    oid = tree.entries['a/x.yaml'][1]
    loose = os.path.join(repo, '.git', 'objects', oid[:2], oid[2:])
    os.chmod(loose, stat.S_IWRITE)                           # git writes loose objects read-only
    os.remove(loose)
    with pytest.raises(G.GitError, match='not in the object store'):
        tree.read(['a/x.yaml'])
    assert G.GIT_ENV['GIT_NO_LAZY_FETCH'] == '1'


def test_bench_ingest_runs_the_fixture(tmp_path):
    from tools import cli
    for name in ('lm-eval-harness', 'mteb-results'):
        r = CliRunner().invoke(cli.app, ['ingest', name, '--dry-run', '--fixture', FIX])
        assert r.exit_code == 0, r.output
        assert 'ingest %s %s: ok' % (name, G.VERSION) in r.output
