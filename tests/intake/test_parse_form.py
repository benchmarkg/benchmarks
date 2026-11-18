"""The issue-intake validation bot (P2-S6-T04; 05 S6, Path A and "The validation bot"; 08 S3.4, S7.3; ADR-0022).

The verify is this file plus an end-to-end run on a test issue. That run needs the workflow switched on, which is
the maintainer's step (.github/workflows/issue-intake.yml ships off), so it is not here.

Every issue body below is built from the committed forms the way GitHub renders a submitted form: `### <label>`,
a blank line, the answer, `_No response_` for a blank, a multiple choice joined by ", ", and `- [X] <label>` for
a ticked box. The GitHub side runs against FakeGitHub, which keeps the state the bot reads back (its comments,
the labels, the refs, the pull requests), so replacing a comment and counting attempts are tested across runs.
"""
import builtins
import dataclasses
import hashlib
import json
import os
import re
import socket
import time
import urllib.parse
import urllib.request

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from schema.draft import BenchmarkDraft, SourceDraft
from schema.taxonomy import read_yaml
from tools import cli, fmt
from tools.intake import open_pr
from tools.intake import parse_form as pf
from tools.validate import quotes

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = 'benchmarkg/benchmarks'
SUBMITTER = 'a-contributor'                 # the issue's author, which nothing the bot writes may name
runner = CliRunner()


@pytest.fixture(scope='module')
def resolver():
    return pf.load_resolver(ROOT, REPO)


def option(form, fid, term):
    """The form's option text for a term id: `Weather forecasting (earth-climate/weather-forecasting)`."""
    return next(o for o in pf.load_form(form).get(fid).options if pf._term(o) == term)


def render(form, answers, unticked=()):
    """An issue body as GitHub renders a submitted form."""
    parts = []
    for f in pf.load_form(form).fields:
        if f.type == 'checkboxes':
            value = '\n'.join('- [%s] %s' % (' ' if o in unticked else 'X', o) for o in f.options)
        else:
            value = answers.get(f.id)
            value = ', '.join(value) if isinstance(value, list) else value
        parts.append('### %s\n\n%s' % (f.label, value or pf.NO_RESPONSE))
    return '\n\n'.join(parts) + '\n'


def valid(**over):
    a = {
        'name': 'Tide Gauge Bench', 'homepage': 'https://arxiv.org/abs/2501.01234',
        'tagline': 'Forecasting hourly sea level at 200 tide gauges.',
        'primary-domain': option('new-benchmark', 'primary-domain', 'earth-climate/weather-forecasting'),
        'secondary-domains': [option('new-benchmark', 'secondary-domains', 'earth-climate/remote-sensing')],
        'capabilities': [option('new-benchmark', 'capabilities', 'scientific-prediction'),
                         option('new-benchmark', 'capabilities', 'temporal-reasoning')],
        'evaluation-method': [option('new-benchmark', 'evaluation-method', 'domain-metric')],
        'what-is-evaluated': 'agent scaffold', 'repository': 'https://github.com/example-org/tide-gauge-bench',
        'licence': 'CC-BY-4.0', 'size': '2,294 task instances', 'maintainer': 'Example Ocean Lab',
        'released': '2025-01-10', 'notes': 'Hourly records from 2010 to 2020.',
    }
    a.update(over)
    return a


def issue(body, number=4242, form='new-benchmark', updated='2026-11-18T10:00:00Z'):
    """The parts of a GitHub `issues` event's issue the bot reads, and its author, which it must not read."""
    return {'number': number, 'html_url': 'https://github.com/%s/issues/%d' % (REPO, number), 'body': body,
            'state': 'open', 'created_at': '2026-11-18T09:59:00Z', 'updated_at': updated,
            'labels': [{'name': 'form:' + form}, {'name': 'source:issue-form'}], 'user': {'login': SUBMITTER}}


def event(iss, action='opened'):
    return {'action': action, 'issue': iss, 'repository': {'full_name': REPO, 'default_branch': 'main'}}


def run_intake(resolver, tmp_path, answers=None, form='new-benchmark', unticked=(), body=None, **kw):
    body = body if body is not None else render(form, answers if answers is not None else valid(), unticked)
    return pf.intake(issue(body, form=form, **kw), ROOT, str(tmp_path), REPO, resolver)


def user_facing(outcome):
    return [e['message'] for e in outcome.errors]


STACK = ('Traceback', 'File "', 'ValidationError', 'validation error', 'pydantic', 'input_value', 'errors.pydantic.dev')


# ---- the parser ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize('form', pf.KNOWN_FORMS)
def test_every_form_body_parses_back_to_its_answers_by_field_id(form):
    f = pf.load_form(form)
    answers = {}
    for x in f.fields:
        if x.type == 'dropdown':
            answers[x.id] = list(x.options[:2]) if x.multiple else x.options[-1]
        elif x.type != 'checkboxes':
            answers[x.id] = 'Line one of %s\nline two' % x.id if x.type == 'textarea' else 'Answer to %s' % x.id
    got, missing = pf.parse_body(render(form, answers, unticked=f.fields[-1].options), f)
    assert missing == []
    for x in f.fields:
        if x.type == 'checkboxes':
            last = x is f.fields[-1]
            assert got[x.id] == {o: not last for o in x.options}
        else:
            assert got[x.id] == answers[x.id], x.id


def test_crlf_blanks_and_a_deleted_heading():
    f = pf.load_form('new-benchmark')
    body = render('new-benchmark', valid(maintainer=None)).replace('### Release date\n\n2025-01-10\n\n', '')
    got, missing = pf.parse_body(body.replace('\n', '\r\n'), f)
    assert got['maintainer'] is None and got['released'] is None and missing == ['released']
    assert got['name'] == 'Tide Gauge Bench'


def test_a_multiple_choice_answer_splits_on_the_options_even_when_one_holds_a_comma():
    options = ('Alpha, beta (a-b)', 'Gamma (g)', 'Delta (d)')
    assert pf.split_options('Alpha, beta (a-b), Gamma (g)', options) == ['Alpha, beta (a-b)', 'Gamma (g)']
    assert pf.split_options('Nope (n), Delta (d)', options) == ['Nope (n)', 'Delta (d)']


def test_a_heading_inside_an_answer_is_answer_text():
    f = pf.load_form('new-benchmark')
    body = render('new-benchmark', valid(notes='### Not a field\n\nstill the notes'))
    got, _ = pf.parse_body(body, f)
    assert got['notes'] == '### Not a field\n\nstill the notes'


def test_the_proposed_id():
    assert pf.propose_id('Tide Gauge Bench') == ('tide-gauge-bench', [])
    assert pf.propose_id('τ-bench') == ('tau-bench', [])
    assert pf.propose_id('Ünïcode Bench 2.0') == ('unicode-bench-2-0', [])
    assert pf.propose_id('基准')[0] is None
    assert pf.propose_id('基准 (Latin Name Bench)') == ('latin-name-bench', ['基', '准'])
    assert len(pf.propose_id('x' * 90)[0]) == pf.SLUG_MAX


# ---- a valid submission -------------------------------------------------------------------------------------

def test_a_valid_submission_drafts_yaml_that_bench_validate_single_accepts(resolver, tmp_path):
    out = run_intake(resolver, tmp_path)
    assert out.status == 'drafted' and out.errors == []
    assert out.entity_id == 'tide-gauge-bench' and out.source_id == 'src-benchmarkg-issue-4242-2026'
    assert sorted(out.files) == ['drafts/benchmarks/tide-gauge-bench.yaml',
                                 'drafts/sources/src-benchmarkg-issue-4242-2026.yaml']
    for rel in out.files:
        path = os.path.join(str(tmp_path), *rel.split('/'))
        result = runner.invoke(cli.app, ['validate', '--single', '--tier', 'schema,ref,semantic', path])
        assert result.exit_code == 0, result.stdout
        assert 'validate: schema,ref,semantic over 1 file(s): 0 blocking' in result.stdout
    bench = read_yaml(os.path.join(str(tmp_path), 'drafts', 'benchmarks', 'tide-gauge-bench.yaml'))
    source = read_yaml(os.path.join(str(tmp_path), 'drafts', 'sources', 'src-benchmarkg-issue-4242-2026.yaml'))
    BenchmarkDraft.model_validate(bench)
    SourceDraft.model_validate(source)
    assert quotes.check(bench, {source['id']: source}) == []        # tier 3's quote-substring rule, on every quote
    assert bench['curation']['verification_status'] == 'ai-drafted-unverified'
    assert bench['domain'] == {'primary': 'earth-climate/weather-forecasting',
                               'secondary': ['earth-climate/remote-sensing']}
    assert bench['capability'] == ['scientific-prediction', 'temporal-reasoning']
    assert bench['evaluation_target'] == 'learned-system' and bench['designed_for_subjects'] == ['agent-scaffold']
    assert bench['data']['size'][0]['count'] == 2294 and bench['data']['size'][0]['unit'] == 'task instances'
    assert bench['external_ids'] == {'arxiv': '2501.01234'}
    rows = {(r['field'], r.get('term')): r for r in bench['provenance']['fields']}
    assert rows[('learned_entrant_evidence', None)]['confidence'] == 'absent'
    assert {r['confidence'] for r in rows.values()} == {'low', 'absent'}        # nobody has opened a source yet
    assert any(c.get('field') == 'id' for c in bench['curation']['review_checks'])
    for rel, text in out.files.items():                                          # what `bench fmt` would write
        assert fmt.format_text(text, fmt.model_for(rel), rel) == text


def test_the_full_draft_tiers_accept_it_too(resolver, tmp_path):
    """Beyond --single: drafts/'s own tiers 2 and 3 (tools/validate/tiers.draft_tiers), with no corpus."""
    from tools.validate import tiers
    out = run_intake(resolver, tmp_path)
    recs = [tiers._read(os.path.join(str(tmp_path), *rel.split('/')), rel) for rel in out.files]
    found = tiers.draft_tiers(recs, [], tiers._taxonomy(ROOT), {2, 3})
    assert [f for f in found if f.blocks or f.severity == 'warning'] == []


def test_a_stub_s_id_is_drafted_with_a_check_to_promote_the_stub(resolver, tmp_path):
    out = pf.intake(issue(render('new-benchmark', valid()), number=7), ROOT, str(tmp_path), REPO,
                    dataclasses.replace(resolver, stubs=frozenset({'tide-gauge-bench'})))
    assert out.status == 'drafted'
    assert '_stubs/tide-gauge-bench.yaml already holds a stub' in out.files['drafts/benchmarks/tide-gauge-bench.yaml']


def test_other_and_a_lineage_answer_become_review_checks(resolver, tmp_path):
    out = run_intake(resolver, tmp_path, valid(**{'what-is-evaluated': 'other', 'lineage': 'A fork of TideBench'}))
    bench = YAML(typ='safe').load(out.files['drafts/benchmarks/tide-gauge-bench.yaml'])
    assert 'evaluation_target' not in bench and 'designed_for_subjects' not in bench
    checks = {c.get('field'): c for c in bench['curation']['review_checks']}
    assert checks['lineage']['quote'] == 'A fork of TideBench' and 'evaluation_target' in checks


# ---- an invalid submission ----------------------------------------------------------------------------------

def test_an_invalid_submission_gets_field_level_errors_and_no_draft(resolver, tmp_path):
    body = render('new-benchmark', valid(homepage='http://example.org/x y', tagline='x' * 130, released='March 2024',
                                         size='about two thousand'),
                  unticked=('I understand this index links to data and never hosts it',))
    body = body.replace('(earth-climate/weather-forecasting)', '(robotics-embodiment/grasping)')
    out = run_intake(resolver, tmp_path, body=body)
    assert out.status == 'invalid' and out.files == {} and not os.listdir(str(tmp_path))
    by = {e['field']: e['message'] for e in out.errors}
    assert set(by) == {'homepage', 'tagline', 'released', 'size', 'primary-domain', 'attestation'}
    # 05 S6's example, as far as string similarity reaches: "grasping" is like no subdomain's name, so the
    # message lists the family's subdomains rather than suggesting an unrelated near-spelling
    assert by['primary-domain'].startswith('Primary domain `robotics-embodiment/grasping` is not in the vocabulary. '
                                           'The robotics-embodiment subdomains are ')
    assert '`robotics-embodiment/manipulation`' in by['primary-domain']
    assert 'https://github.com/benchmarkg/benchmarks/blob/main/taxonomy/domains.yaml' in by['primary-domain']
    typo = run_intake(resolver, tmp_path, body=render('new-benchmark', valid()).replace(
        '(earth-climate/weather-forecasting)', '(robotics-embodiment/manipulaton)'))
    assert 'is not in the vocabulary. Did you mean `robotics-embodiment/manipulation`' in typo.errors[0]['message']
    assert 'https://' in by['homepage'] and '130 characters' in by['tagline'] and 'YYYY-MM-DD' in by['released']
    assert 'I understand this index links to data' in by['attestation']
    assert all(len(e['fingerprint']) == 16 for e in out.errors)
    for message in user_facing(out):
        assert not any(s in message for s in STACK), message


def test_a_family_a_blank_required_answer_and_a_deleted_heading(resolver, tmp_path):
    body = render('new-benchmark', valid(tagline=None)).replace('(earth-climate/weather-forecasting)',
                                                                '(earth-climate)')
    body = body.replace('### Evaluation method\n', '### Evaluation methods\n')
    by = {e['field']: e['message'] for e in run_intake(resolver, tmp_path, body=body).errors}
    assert 'is a domain family, which is not assignable' in by['primary-domain']
    assert by['tagline'].startswith('One-sentence description is empty, and it is required.')
    assert 'Its heading, `### Evaluation method`, is missing from the issue' in by['evaluation-method']


@pytest.mark.parametrize('name, expect', [
    ('MMLU', 'the index already holds this as `mmlu`'),
    ('GPQA diamond', 'as a subset of `gpqa` (`gpqa#diamond`), not as a benchmark of its own'),
    ('基准', 'gives the bot no id'),
])
def test_a_benchmark_the_index_holds_or_a_name_with_no_id_is_an_error_on_the_name(resolver, tmp_path, name, expect):
    out = run_intake(resolver, tmp_path, valid(name=name))
    [e] = out.errors
    assert e['field'] == 'name' and expect in e['message']
    if 'holds' in expect:
        assert 'Correction form' in e['message']


def test_a_retired_or_tombstoned_id_is_never_proposed(resolver, tmp_path):
    held = dataclasses.replace(resolver, held={'tide-gauge-bench': 'was merged into `tidebench`'})
    out = pf.intake(issue(render('new-benchmark', valid())), ROOT, str(tmp_path), REPO, held)
    assert [e['field'] for e in out.errors] == ['name'] and 'was merged into `tidebench`' in out.errors[0]['message']


def test_markup_that_swallows_other_answers_is_a_field_error_not_a_misquote(resolver, tmp_path):
    # a whole tag is stripped from the answer and the snapshot alike (04 S9's one normaliser), so its quote holds
    assert run_intake(resolver, tmp_path, valid(maintainer='Example <b>Ocean</b> Lab')).status == 'drafted'
    # an open `<b` closed by a `>` two answers later reads as one tag in the snapshot, eating what lies between
    out = run_intake(resolver, tmp_path, valid(maintainer='Example <b', notes='a > b'))
    assert out.status == 'invalid' and out.files == {}
    by = {e['field']: e['message'] for e in out.errors}
    assert {'maintainer', 'released', 'notes'} <= set(by)
    assert 'Remove any HTML or angle-bracket markup' in by['maintainer']


# ---- ADR-0022: the adapter contract's front half -------------------------------------------------------------

def test_normalise_is_pure(resolver, monkeypatch):
    form = resolver.forms['new-benchmark']
    payloads = [pf.payload_from(issue(render('new-benchmark', valid(name='Bench %d' % i)), number=i), form, REPO)
                for i in range(5)] + [pf.payload_from(issue(render('new-benchmark', valid(tagline=None))), form, REPO)]
    expected = [pf.normalise(p, resolver) for p in payloads]

    def refuse(*a, **k):
        raise AssertionError('normalise() reached outside its arguments')
    for target, name in ((time, 'time'), (socket, 'create_connection'), (urllib.request, 'urlopen'),
                         (builtins, 'open')):
        monkeypatch.setattr(target, name, refuse)
    assert [pf.normalise(p, resolver) for p in payloads] == expected
    assert all(d and not u for d, u in expected[:5]) and not expected[5][0]


def test_an_edit_that_changes_no_answer_is_the_same_payload_and_the_same_draft(resolver):
    form = resolver.forms['new-benchmark']
    body = render('new-benchmark', valid())
    a = pf.payload_from(issue(body), form, REPO)
    b = pf.payload_from(issue(body.replace('\n', '\r\n'), updated='2026-11-18T10:05:00Z'), form, REPO)
    assert a.sha256_normalised == b.sha256_normalised and a.candidate.source_key == 'issue:4242'
    assert SUBMITTER not in json.dumps(a.doc)


# ---- the other four forms ---------------------------------------------------------------------------------

def test_the_forms_the_bot_does_not_draft_are_checked_and_go_to_a_person(resolver, tmp_path):
    correction = {'entity': 'swe-bench', 'field': 'data.size', 'correct-value': '2,294',
                  'source-url': 'https://www.swebench.com/', 'quote': 'SWE-bench has 2,294 task instances.'}
    assert run_intake(resolver, tmp_path, correction, form='correction').status == 'human'
    bad = run_intake(resolver, tmp_path, dict(correction, **{'source-url': 'swebench.com'}), form='correction')
    assert bad.status == 'invalid' and [e['field'] for e in bad.errors] == ['source-url']
    term = {'facet': 'capability', 'term-id': 'x', 'term-label': 'X', 'definition': 'd', 'inclusion-test': 'i',
            'exclusion-test': 'e', 'near-miss': 'n', 'benchmarks': 'b'}
    out = run_intake(resolver, tmp_path, term, form='taxonomy-term')
    assert out.status == 'human' and out.files == {} and out.steward_path == 'taxonomy/'
    claim = {'benchmark': 'swe-bench', 'system': 'S', 'metric': 'resolved rate', 'value': '49.2%',
             'date-reported': '2031-01-01', 'source-url': 'https://example.org/r', 'quote': 'q'}
    assert [e['field'] for e in run_intake(resolver, tmp_path, claim, form='new-claim').errors] == ['date-reported']


def test_an_issue_with_no_form_label_is_skipped(resolver, tmp_path):
    iss = dict(issue('anything'), labels=[{'name': 'bug'}])
    assert pf.intake(iss, ROOT, str(tmp_path), REPO, resolver).status == 'skipped'


# ---- the GitHub side --------------------------------------------------------------------------------------

class FakeGitHub:
    """The REST endpoints the bot calls, with the state it reads back. `client(who)` is one token's view."""

    def __init__(self):
        self.comments, self.labels, self.pulls, self.calls = [], {}, [], []
        self.refs = {'refs/heads/main': 'c-base'}
        self.commits = {'c-base': {'tree': 't-base'}}
        self.n = 100

    def client(self, who, login='github-actions[bot]'):
        fake = self

        class Client:
            def call(self, method, path, payload=None, ok_missing=False):
                fake.calls.append((who, method, path, payload))
                return fake.route(method, path, payload, login)
        return Client()

    def _id(self):
        self.n += 1
        return self.n

    def route(self, method, path, payload, login):
        url = urllib.parse.urlparse(path)
        q = urllib.parse.parse_qs(url.query)
        p = url.path.removeprefix('/repos/%s' % REPO)
        m = re.fullmatch(r'/issues/(\d+)/comments', p)
        if m and method == 'GET':
            return [c for c in self.comments if c['issue'] == int(m.group(1))] if q['page'] == ['1'] else []
        if m and method == 'POST':
            c = {'id': self._id(), 'issue': int(m.group(1)), 'body': payload['body'], 'user': {'login': login}}
            self.comments.append(c)
            return c
        m = re.fullmatch(r'/issues/comments/(\d+)', p)
        if m:
            [c] = [c for c in self.comments if c['id'] == int(m.group(1))]
            if method == 'DELETE':
                self.comments.remove(c)
            else:
                c['body'] = payload['body']
            return c
        m = re.fullmatch(r'/issues/(\d+)/labels(?:/(.+))?', p)
        if m:
            have = self.labels.setdefault(int(m.group(1)), set())
            if method == 'POST':
                have.update(payload['labels'])
            else:
                have.discard(urllib.parse.unquote(m.group(2)))
            return []
        m = re.fullmatch(r'/git/matching-refs/heads/(.+)', p)
        if m:
            return [{'ref': r, 'object': {'sha': s}} for r, s in self.refs.items()
                    if r.startswith('refs/heads/' + m.group(1))]
        m = re.fullmatch(r'/git/ref/heads/(.+)', p)
        if m:
            return {'object': {'sha': self.refs['refs/heads/' + m.group(1)]}}
        m = re.fullmatch(r'/git/commits/(.+)', p)
        if m and method == 'GET':
            return {'tree': {'sha': self.commits[m.group(1)]['tree']}}
        if p == '/git/trees':
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
            return {'sha': 't-' + digest}
        if p == '/git/commits':
            sha = 'c-%d' % self._id()
            self.commits[sha] = dict(payload)
            return {'sha': sha}
        if p == '/git/refs':
            self.refs[payload['ref']] = payload['sha']
            return {}
        m = re.fullmatch(r'/git/refs/(heads/.+)', p)
        if m:
            self.refs['refs/' + m.group(1)] = payload['sha']
            return {}
        if p == '/pulls' and method == 'GET':
            head = q['head'][0].split(':', 1)[1]
            return [x for x in self.pulls if x['head'] == head and x['state'] == 'open']
        if p == '/pulls' and method == 'POST':
            n = self._id()
            pr = dict(payload, number=n, state='open', html_url='https://github.com/%s/pull/%d' % (REPO, n))
            self.pulls.append(pr)
            return pr
        m = re.fullmatch(r'/pulls/(\d+)', p)
        if m and method == 'PATCH':
            [pr] = [x for x in self.pulls if x['number'] == int(m.group(1))]
            pr.update(payload)
            return pr
        raise AssertionError('the bot made a call FakeGitHub does not know: %s %s' % (method, path))

    def bot_comments(self, number=4242):
        return [c for c in self.comments if c['issue'] == number and c['body'].startswith('<!-- uaibi:issue-intake')]


def act(gh, outcome, iss, root=ROOT, action='opened'):
    result = dataclasses.asdict(outcome)
    lines = []
    code = open_pr.handle(event(iss, action), result, gh.client('issue'), gh.client('bot', 'uaibi-bot'), root,
                          out=lines.append)
    return code, lines


def test_a_failure_replaces_its_comment_and_the_third_adds_needs_human(resolver, tmp_path):
    gh = FakeGitHub()
    gh.comments.append({'id': 1, 'issue': 4242, 'body': '<!-- uaibi:issue-intake attempts=7 --> spoofed',
                        'user': {'login': SUBMITTER}})            # a marker in someone else's comment counts for nothing
    body = render('new-benchmark', valid(released='soon'))
    for attempt in (1, 2, 3, 4):
        out = run_intake(resolver, tmp_path, body=body)
        iss = issue(body)
        iss['labels'] += [{'name': x} for x in sorted(gh.labels.get(4242, ()))]
        code, lines = act(gh, out, iss, action='opened' if attempt == 1 else 'edited')
        assert code == 0
        [mine] = [c for c in gh.bot_comments() if c['user']['login'] == 'github-actions[bot]']
        assert mine['body'].startswith('<!-- uaibi:issue-intake attempts=%d -->' % attempt)
        assert 'Release date `soon` is not a date the bot can read' in mine['body']
        assert ('needs-human' in gh.labels[4242]) == (attempt >= 3) and 'needs-fix' in gh.labels[4242]
        assert ('No CODEOWNERS file names a steward yet' in mine['body']) == (attempt == 3)
        assert any(line.startswith('comment posted') for line in lines)
    assert len(gh.comments) == 2 and gh.comments[0]['id'] == 1        # the contributor's own comment is untouched
    assert not [c for c in gh.calls if '/pulls' in c[2] or '/git/' in c[2]]   # a broken submission opens nothing


def test_the_third_failure_pings_the_steward_codeowners_names(resolver, tmp_path):
    root = tmp_path / 'checkout'
    (root / '.github').mkdir(parents=True)
    (root / '.github' / 'CODEOWNERS').write_text('* @example-org/maintainers\n/data/benchmarks/earth-climate/ '
                                                 '@example-org/earth-stewards\n', encoding='utf-8')
    gh = FakeGitHub()
    gh.comments.append({'id': 1, 'issue': 4242, 'body': '<!-- uaibi:issue-intake attempts=2 -->',
                        'user': {'login': 'github-actions[bot]'}})
    out = run_intake(resolver, tmp_path, valid(size='lots'))
    act(gh, out, issue(''), str(root), 'edited')
    [mine] = gh.bot_comments()
    assert '@example-org/earth-stewards: .github/CODEOWNERS names you as the steward for `data/benchmarks/' \
           'earth-climate/`' in mine['body'] and '@example-org/maintainers' not in mine['body']


def test_steward_matching_follows_codeowners_order():
    rules = [('*', ['@o/all']), ('data/', ['@o/data']), ('/taxonomy/', ['@o/tax']), ('*.yml', ['@o/yml'])]
    assert open_pr.owners_for(rules, 'data/benchmarks/vision/x.yaml') == ['@o/data']
    assert open_pr.owners_for(rules, 'taxonomy/domains.yaml') == ['@o/tax']
    assert open_pr.owners_for(rules, 'nested/taxonomy/x.yaml') == ['@o/all']
    assert open_pr.owners_for(rules, '.github/workflows/a.yml') == ['@o/yml']
    assert open_pr.steward_line(ROOT, 'data/').startswith('No CODEOWNERS file names a steward yet')


def test_a_pass_comments_the_yaml_then_opens_one_reviewable_pr_and_never_merges(resolver, tmp_path):
    gh = FakeGitHub()
    gh.labels[4242] = {'needs-fix'}
    out = run_intake(resolver, tmp_path)
    iss = issue(render('new-benchmark', valid()))
    iss['labels'].append({'name': 'needs-fix'})
    code, lines = act(gh, out, iss)
    assert code == 0
    [comment] = gh.bot_comments()
    assert comment['body'].startswith('<!-- uaibi:issue-intake attempts=0 -->')
    assert out.files['drafts/benchmarks/tide-gauge-bench.yaml'] in comment['body']      # the rendered YAML, whole
    assert '**Pull request:** https://github.com/%s/pull/' % REPO in comment['body']
    assert 'needs-fix' not in gh.labels[4242]
    # the order: the comment (the 90-second budget) is posted before anything is pushed
    first_git = next(i for i, c in enumerate(gh.calls) if '/git/' in c[2])
    first_comment = next(i for i, c in enumerate(gh.calls) if c[1] == 'POST' and c[2].endswith('/comments'))
    assert first_comment < first_git
    [pr] = gh.pulls
    assert pr['head'] == 'contrib/4242-tide-gauge-bench' and pr['base'] == 'main'
    assert pr['title'] == 'New benchmark: Tide Gauge Bench (issue #4242)'
    assert pr['body'].startswith('From issue #4242.\n\nCloses #4242\n')
    assert gh.labels[pr['number']] == {'source:issue-form', 'verification:curator-review-needed'}
    [commit] = [c for c in gh.commits.values() if 'message' in c]
    assert commit['author'] == commit['committer'] and commit['author']['name'] == 'intelligence-benchmark'
    assert commit['author']['email'] == 'intelligence.benchmark@gmail.com' and commit['parents'] == ['c-base']
    assert commit['message'].rstrip('\n').split('\n')[-2:] == list(open_pr.TRAILERS)
    # who did what: the bot's PAT pushed and opened the pull request; the workflow token spoke on the issue
    assert {who for who, _, path, _ in gh.calls if '/git/' in path or '/pulls' in path} == {'bot'}
    assert {who for who, m, path, _ in gh.calls if '/issues/4242/' in path} == {'issue'}
    assert not [c for c in gh.calls if 'merge' in c[2]]                       # never merges
    # an edit that leaves the answers alone: no new commit, the same pull request, still one comment
    code, _ = act(gh, run_intake(resolver, tmp_path), iss, action='edited')
    assert code == 0 and len(gh.pulls) == 1 and len([c for c in gh.commits.values() if 'message' in c]) == 1
    assert len(gh.bot_comments()) == 1
    # an edit that changes an answer: a new commit on the same branch, the same pull request updated
    act(gh, run_intake(resolver, tmp_path, valid(tagline='Forecasting sea level at 200 tide gauges.')), iss,
        action='edited')
    shas = [sha for sha, c in gh.commits.items() if 'message' in c]
    assert len(gh.pulls) == 1 and len(shas) == 2
    assert gh.refs['refs/heads/contrib/4242-tide-gauge-bench'] == shas[-1]
    assert gh.commits[shas[-1]]['parents'] == ['c-base']


def test_no_name_or_handle_of_the_submitter_is_written_anywhere(resolver, tmp_path):
    gh = FakeGitHub()
    out = run_intake(resolver, tmp_path)
    act(gh, out, issue(render('new-benchmark', valid())))
    written = json.dumps([out.files, gh.comments, gh.pulls, [c for c in gh.commits.values()]], ensure_ascii=False)
    assert SUBMITTER not in written
    assert 'Co-authored-by' not in json.dumps(out.files) and written.count('Co-authored-by: ') == 2


def test_a_pr_the_bot_cannot_open_is_reported_without_details(resolver, tmp_path):
    gh = FakeGitHub()
    out = run_intake(resolver, tmp_path)

    class Broken:
        def call(self, method, path, payload=None, ok_missing=False):
            raise open_pr.GitHubError(method, path, 401, 'Bad credentials')
    lines = []
    code = open_pr.handle(event(issue('')), dataclasses.asdict(out), gh.client('issue'), Broken(), ROOT,
                          out=lines.append)
    assert code == 1 and 'needs-human' in gh.labels[4242]
    [comment] = gh.bot_comments()
    assert 'could not open the pull request' in comment['body']
    assert 'Bad credentials' not in comment['body'] and 'HTTP 401' not in comment['body']
    assert any('Bad credentials' in line for line in lines)                  # the log has it, the issue does not


def test_the_bot_s_own_failure_is_said_plainly_with_no_stack_trace(resolver, tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise KeyError('a bug in the bot')
    monkeypatch.setattr(pf, 'normalise', boom)
    out = run_intake(resolver, tmp_path)
    assert out.status == 'error' and out.errors == [] and out.files == {}
    assert 'Traceback' in capsys.readouterr().err                           # the run log has the trace
    gh = FakeGitHub()
    code, _ = act(gh, out, issue(''))
    [comment] = gh.bot_comments()
    assert code == 1 and 'needs-human' in gh.labels[4242]
    assert not any(s in comment['body'] for s in STACK + ('KeyError', 'a bug in the bot'))
    assert 'problem of its own' in comment['body']


def test_the_other_forms_are_labelled_for_a_person_and_open_nothing(resolver, tmp_path):
    term = {'facet': 'capability', 'term-id': 'x', 'term-label': 'X', 'definition': 'd', 'inclusion-test': 'i',
            'exclusion-test': 'e', 'near-miss': 'n', 'benchmarks': 'b'}
    gh = FakeGitHub()
    out = run_intake(resolver, tmp_path, term, form='taxonomy-term')
    act(gh, out, issue('', form='taxonomy-term'))
    [comment] = gh.bot_comments()
    assert 'no pull request is opened' in comment['body'] and gh.labels[4242] == {'needs-human'}
    assert not [c for c in gh.calls if '/pulls' in c[2] or '/git/' in c[2]]


# ---- the commit identity ----------------------------------------------------------------------------------

def test_the_bot_refuses_any_other_identity_or_trailer():
    when = open_pr.datetime(2026, 11, 18, tzinfo=open_pr.timezone.utc)
    ok = open_pr.commit_message('intake: draft x from issue #1', 'Body.')
    assert ok.rstrip('\n').split('\n')[-2:] == ['Co-authored-by: advancedintelligence <advanced.intelligence.labs@gmail.com>',
                                                'Co-authored-by: tatra-labs <tatra.labs@gmail.com>']
    assert open_pr.commit_payload(ok, 't', ['p'], when)['author']['name'] == 'intelligence-benchmark'
    stranger = open_pr.Identity('a-contributor', 'contributor@example.org')
    with pytest.raises(open_pr.IdentityError, match='commits only as intelligence-benchmark'):
        open_pr.commit_payload(ok, 't', ['p'], when, author=stranger)
    with pytest.raises(open_pr.IdentityError, match='refusing committer'):
        open_pr.commit_payload(ok, 't', ['p'], when, committer=open_pr.CO_AUTHORS[1])
    with pytest.raises(open_pr.IdentityError, match='refusing'):
        open_pr.commit_message('s', 'Body.', open_pr.TRAILERS + ('Co-authored-by: %s' % stranger,))
    with pytest.raises(open_pr.IdentityError, match='refusing'):
        open_pr.commit_message('s', 'Body.\n\nSigned-off-by: someone <someone@example.org>')
    with pytest.raises(open_pr.IdentityError, match='ends with exactly these trailers'):
        open_pr.commit_message('s', 'Body.', open_pr.TRAILERS[:1])
    with pytest.raises(open_pr.IdentityError):
        open_pr.commit_payload(ok.replace('tatra-labs <', 'tatra-labs-2 <'), 't', ['p'], when)


# ---- the command line, the workflow and the forms -------------------------------------------------------------

def test_the_cli_takes_a_comma_list_of_tiers():
    bad = runner.invoke(cli.app, ['validate', '--single', '--tier', 'schema,bogus', 'x.yaml'])
    assert bad.exit_code == 2
    assert runner.invoke(cli.app, ['validate', '--single', '--tier', 'all,schema', 'x.yaml']).exit_code == 2


def test_dry_run_prints_every_call_and_makes_none(resolver, tmp_path, monkeypatch, capsys):
    out = run_intake(resolver, tmp_path)
    (tmp_path / 'event.json').write_text(json.dumps(event(issue(''))), encoding='utf-8')
    (tmp_path / 'result.json').write_text(json.dumps(dataclasses.asdict(out)), encoding='utf-8')

    def refuse(*a, **k):
        raise AssertionError('a dry run made a request')
    monkeypatch.setattr(urllib.request, 'urlopen', refuse)
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    monkeypatch.delenv('UAIBI_BOT_PAT', raising=False)
    assert open_pr.main(['--event', str(tmp_path / 'event.json'), '--result', str(tmp_path / 'result.json'),
                         '--dry-run']) == 0
    printed = capsys.readouterr().out
    assert 'DRY RUN (UAIBI_BOT_PAT)  POST   /repos/%s/pulls' % REPO in printed
    assert 'DRY RUN (GITHUB_TOKEN)  POST   /repos/%s/issues/4242/comments' % REPO in printed


def test_the_parse_step_writes_its_result_for_the_second_step(tmp_path):
    (tmp_path / 'event.json').write_text(json.dumps(event(issue(render('new-benchmark', valid())))), encoding='utf-8')
    assert pf.main(['--event', str(tmp_path / 'event.json'), '--out', str(tmp_path / 'out'),
                    '--result', str(tmp_path / 'result.json')]) == 0
    result = json.loads((tmp_path / 'result.json').read_text(encoding='utf-8'))
    assert result['status'] == 'drafted' and result['entity_id'] == 'tide-gauge-bench'
    assert (tmp_path / 'out' / 'drafts' / 'benchmarks' / 'tide-gauge-bench.yaml').exists()


def test_the_workflow_ships_switched_off_and_holds_the_token_away_from_the_parser():
    path = os.path.join(ROOT, '.github', 'workflows', 'issue-intake.yml')
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    doc = YAML(typ='safe').load(text)
    assert 'SHIPS SWITCHED OFF' in text.split('\nname:')[0]
    on = doc.get('on', doc.get(True))                     # get-default: PyYAML-style `on` reads as True
    assert on == {'issues': {'types': ['opened', 'edited']}}
    assert doc['jobs'] and all("vars.ISSUE_INTAKE_ENABLED == 'true'" in job['if'] for job in doc['jobs'].values())
    [job] = doc['jobs'].values()
    assert job['timeout-minutes'] <= 4
    uses = [s['uses'] for s in job['steps'] if 'uses' in s]
    assert all(re.search(r'@[0-9a-f]{40}$', u.split(' ')[0]) for u in uses)
    parse, act_ = [s for s in job['steps'] if 'run' in s]
    assert 'tools.intake.parse_form' in parse['run'] and 'env' not in parse
    assert 'secrets.UAIBI_BOT_PAT' in act_['env']['UAIBI_BOT_PAT'] and 'tools.intake.open_pr' in act_['run']
    assert '${{ github.event.issue' not in json.dumps([s.get('run', '') for s in job['steps']])
    assert 'merge' not in json.dumps(job)


def test_the_forms_promise_a_linked_issue_not_co_authorship():
    base = os.path.join(ROOT, '.github', 'ISSUE_TEMPLATE')
    for name in os.listdir(base):
        with open(os.path.join(base, name), encoding='utf-8') as fh:
            text = fh.read()
        assert 'co-author' not in text.lower(), name
        if name in ('new-benchmark.yml', 'correction.yml', 'new-claim.yml', 'dispute.yml'):
            assert 'opens a pull request that links to this issue' in text, name
