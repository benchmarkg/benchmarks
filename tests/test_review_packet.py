"""Tests for scripts/review_packet.py and docs/review-packets/ (P1-S4-T05; 03 S12.2).

The done_when: "A packet renders for any family with >= 10 entries and contains all three sections." The three
sections are re-derived here from the taxonomy files, not from the script: every live subdomain of the family in
section 1, ten entry sections in section 2, all 13 capability groups and the gap question verbatim in section 3.
Then determinism (two independent builds render the same bytes; the date comes from the data or --as-of), and
--check failing on a stale, a missing, a sectionless and a name-bearing packet, each with its own message. The
name screen is exercised on an invented corpus, so no real person's name is written here.
"""
import os
import re
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import review_packet as rp  # noqa: E402

SCRIPT = os.path.join(ROOT, 'scripts', 'review_packet.py')
PACKETS = os.path.join(ROOT, 'docs', 'review-packets')
DOMAINS = yaml.safe_load(open(os.path.join(ROOT, 'taxonomy', 'domains.yaml'), encoding='utf-8'))['terms']
GROUPS = yaml.safe_load(open(os.path.join(ROOT, 'taxonomy', 'capability_groups.yaml'), encoding='utf-8'))['groups']
FAMILIES = [t['id'] for t in DOMAINS if t.get('parent') is None and t.get('status') != 'retired']
EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}')


def published(family):
    d = os.path.join(ROOT, 'data', 'benchmarks', family)
    return sorted(f for f in os.listdir(d) if f.endswith('.yaml')) if os.path.isdir(d) else []


ELIGIBLE = [f for f in FAMILIES if len(published(f)) >= 10]


@pytest.fixture(scope='module')
def corpus():
    return rp.corpus(ROOT)


def section(text, n):
    parts = re.split(r'^## (?=\d\. )', text, flags=re.M)
    return next(p for p in parts if p.startswith('%d. ' % n))


def three_sections(family, text, entries=10):
    """The done_when's three sections, read off a packet with the taxonomy files alone."""
    one, two, three = section(text, 1), section(text, 2), section(text, 3)
    subs = [t['id'] for t in DOMAINS if t.get('parent') == family and t.get('status') != 'retired']
    assert subs and all('`%s`' % s.split('/', 1)[1] in one for s in subs), family
    assert 'What is missing?' in one
    assert len(re.findall(r'^### 2\.\d+ ', two, re.M)) == entries, family
    assert 'Is any of this wrong? Is any of it embarrassing?' in two
    assert len(GROUPS) == 13 and all('`%s`' % g['id'] in three for g in GROUPS), family
    assert 'are these cells empty, or do we not know about the work' in three
    assert ('Here is the row of the coverage matrix for your domain. Are these cells genuinely empty, or do we just '
            'not know about the work?') in three


# ---- the committed packets ------------------------------------------------------------------------------------

def test_one_packet_per_eligible_family_and_no_other():
    assert len(ELIGIBLE) >= 1 and 'robotics-embodiment' in ELIGIBLE
    assert sorted(f for f in os.listdir(PACKETS) if f.endswith('.md')) == sorted(f + '.md' for f in ELIGIBLE)


@pytest.mark.parametrize('family', ELIGIBLE)
def test_every_committed_packet_has_the_three_sections(family):
    with open(os.path.join(PACKETS, family + '.md'), encoding='utf-8') as fh:
        text = fh.read()
    three_sections(family, text)
    assert not [line for line in text.splitlines() if EMAIL.search(line) or '[view email]' in line.lower()]
    assert re.search(r'data as of \d{4}-\d{2}-\d{2}', text)


def test_a_packet_renders_for_every_family_with_ten_entries(corpus):
    assert rp.eligible(corpus) == ELIGIBLE
    for family in ELIGIBLE:
        text = rp.render(corpus, family)
        three_sections(family, text)
        assert rp.sections(corpus, family, False, text) == []


def test_the_every_entry_form_has_every_entry(corpus):
    text = rp.render(corpus, 'robotics-embodiment', everything=True)
    three_sections('robotics-embodiment', text, entries=len(published('robotics-embodiment')))
    assert '## 2. All %d entries' % len(published('robotics-embodiment')) in text


def test_an_entry_shows_its_quotes_sources_and_checks(corpus):
    """Each evidenced field's quote, each showable Source URL and each open review check that passes the name
    screen is in the packet; everything that does not is replaced by the marker, never dropped silently."""
    text = rp.render(corpus, 'robotics-embodiment')
    chosen = rp.choose(corpus.entries['robotics-embodiment'],
                       [s['id'] for s in corpus.subdomains['robotics-embodiment']])
    people = corpus.people
    blocks = {b.split('\n', 1)[0].rsplit('(', 1)[-1].rstrip(')'): b for b in text.split('\n### ')[1:]}
    assert set(blocks) == {e['id'] for e in chosen}
    for e in chosen:
        block = blocks[e['id']]
        for row in rp.rows(e):
            assert (rp.md(row.quote) if people.reason(row.quote) is None else rp.md(rp.WITHHELD)) in block, row.field
        for sid in {r.source for r in rp.rows(e) if r.source}:
            url = corpus.sources[sid].get('url')
            if url and people.url_ok(url):
                assert url.replace(' ', '%20') in block, sid
        for chk in e['curation'].get('review_checks') or []:
            want = rp.md(chk['check']) if people.reason(chk['check']) is None else rp.md(rp.WITHHELD)
            assert want in block
        assert block.count('- [ ] ') >= 8                    # the reviewer's checklist


# ---- determinism ----------------------------------------------------------------------------------------------

def test_rendering_is_deterministic(corpus):
    again = rp.corpus(ROOT)
    for family in ('robotics-embodiment', ELIGIBLE[-1]):
        assert rp.render(corpus, family) == rp.render(again, family)


def test_the_date_comes_from_the_data_or_the_argument(corpus):
    text = rp.render(corpus, 'robotics-embodiment')
    newest = max(max(str(e['curation']['last_verified']), str(e['curation']['added_on']))
                 for e in corpus.entries['robotics-embodiment'])
    assert 'data as of %s' % newest in text
    dated = rp.render(corpus, 'robotics-embodiment', as_of='2030-01-01')
    assert dated == text.replace('data as of %s' % newest, 'data as of 2030-01-01', 1)


def test_the_ten_are_spread_over_subdomains_then_ranked_by_evidence():
    def entry(i, leaf, quotes, full=True):
        e = {'id': i, 'domain': {'primary': 'fam/%s' % leaf}, 'capability': ['planning'] if full else [],
             'evaluation_method': ['exact-match'], 'designed_for_subjects': ['rl-policy'], 'lifecycle': 'active',
             'data': {'access': 'fully-open'}, 'execution': {'reproducibility_tier': 'fully-automatable'},
             'curation': {'review_checks': []}}
        e['evidence'] = [{'source': 'src-x', 'quote': 'q%d' % n} for n in range(quotes)]
        return e
    leaves = ['fam/b', 'fam/a', 'fam/c']                     # taxonomy order, which is not alphabetical
    entries = ([entry('a%02d' % n, 'a', 20 + n) for n in range(8)] + [entry('b1', 'b', 1), entry('b2', 'b', 2)]
               + [entry('c1', 'c', 50, full=False)] + [entry('d1', 'd', 3)])
    chosen = [e['id'] for e in rp.choose(entries, leaves)]
    assert len(chosen) == 10 and 'c1' not in chosen          # not fully classified, and ten others are
    assert {'b1', 'b2', 'd1'} <= set(chosen)                 # every leaf is reached before a leaf's second entry
    assert 'a00' not in chosen and 'a01' in chosen           # within a leaf, the most evidence first
    assert chosen == ['b1', 'b2', 'a01', 'a02', 'a03', 'a04', 'a05', 'a06', 'a07', 'd1']   # leaf order, then id
    assert [e['id'] for e in rp.choose(list(reversed(entries)), leaves)] == chosen


# ---- --check --------------------------------------------------------------------------------------------------

def run_check(*args):
    r = subprocess.run([sys.executable, SCRIPT, '--check'] + list(args), capture_output=True, text=True,
                       encoding='utf-8', env=dict(os.environ, PYTHONUTF8='1'))
    return r.returncode, r.stdout + r.stderr


def test_the_verify_command_passes():
    code, out = run_check('--family', 'robotics-embodiment')
    assert code == 0 and 'all three sections' in out, out


def copy_of(tmp_path, family='robotics-embodiment'):
    with open(os.path.join(PACKETS, family + '.md'), encoding='utf-8', newline='') as fh:
        text = fh.read()
    path = tmp_path / (family + '.md')
    path.write_text(text, encoding='utf-8', newline='')
    return path, text


def test_check_passes_on_an_exact_copy(corpus, tmp_path):
    copy_of(tmp_path)
    assert rp.check(corpus, str(tmp_path), 'robotics-embodiment', False, None) == []


def test_check_fails_on_a_stale_packet(corpus, tmp_path):
    path, text = copy_of(tmp_path)
    path.write_text(text.replace('data as of', 'data as at', 1), encoding='utf-8', newline='')
    errs = rp.check(corpus, str(tmp_path), 'robotics-embodiment', False, None)
    assert len(errs) == 1 and 'is not what scripts/review_packet.py renders' in errs[0], errs


def test_check_fails_on_a_missing_packet(corpus, tmp_path):
    errs = rp.check(corpus, str(tmp_path), 'robotics-embodiment', False, None)
    assert len(errs) == 1 and 'does not exist' in errs[0], errs
    code, out = run_check('--family', 'robotics-embodiment', '--packets', str(tmp_path))
    assert code == 1 and 'does not exist' in out, out


def test_check_fails_when_a_section_is_gone(corpus, tmp_path):
    path, text = copy_of(tmp_path)
    path.write_text(text[:text.index('## 3. ')], encoding='utf-8', newline='')
    errs = rp.check(corpus, str(tmp_path), 'robotics-embodiment', False, None)
    assert any("no heading '## 3. The coverage row'" in e for e in errs), errs
    assert any('the gap question is not there verbatim' in e for e in errs), errs


def test_check_fails_on_a_line_naming_a_person(corpus, tmp_path):
    path, text = copy_of(tmp_path)
    path.write_text(text + 'Submitted by someone [view email] at someone@example.org\n', encoding='utf-8', newline='')
    errs = rp.check(corpus, str(tmp_path), 'robotics-embodiment', False, None)
    assert any('fails the name screen' in e for e in errs), errs


def test_check_fails_on_a_packet_for_a_family_that_does_not_qualify(corpus, tmp_path):
    small = next(f for f in FAMILIES if f not in ELIGIBLE)
    (tmp_path / (small + '.md')).write_text('stray\n', encoding='utf-8')
    errs = rp.check(corpus, str(tmp_path), None, False, None)
    assert len([e for e in errs if 'does not exist' in e]) == len(ELIGIBLE)
    stray = [e for e in errs if 'does not exist' not in e]
    assert len(stray) == 1 and small in stray[0] and 'delete it' in stray[0], errs


# ---- the name screen, on an invented corpus -------------------------------------------------------------------

@pytest.fixture(scope='module')
def people():
    entries = [{
        'id': 'widgetbench',
        'name': 'WidgetBench',
        'governance': {'maintainer': 'Ysolde Quarrington and collaborators (Example University)'},
        'repository': 'https://github.com/yquarr/widgetbench',
        'description': 'A benchmark of widgets, scored by the widget count; the gadget is tested in lower case.',
        'curation': {'review_checks': [{'check': 'Whether Brannoch et al. count the gadgets.'}]},
    }]
    sources = {'src-widget-abs': {'id': 'src-widget-abs', 'url': 'https://arxiv.org/abs/0000.00000',
                                  'quote_extract': 'Submission history From: Tamsin Okonkwo-Vale [view email] '
                                                   'by Odalys Ferncastle, Peregrin Achterberg and Wenna Szabolcs'}}
    return rp.People(entries, sources, ['widgetbench', 'WidgetBench'])


@pytest.mark.parametrize('text, why', [
    ('write to someone@example.org', 'an e-mail address'),
    ('From: X [view email]', 'an arXiv submitter line'),
    ('as Brannoch et al. found', 'a citation by surname'),
    ("in Quarrington's group", "a person's group or co-authors"),
    ('the paper by Ysolde Quarrington', 'a name the corpus records as a person'),
    ('Quarrington maintains it', 'a name the corpus records as a person'),
    ('cloned from yquarr/widgetbench', 'a personal account'),
    ('Thanks to Hollis Drummondine for the data', 'a run of proper names'),
    ('Achterberg ranked first', 'a surname the corpus records'),
    ('see @widgetfan on the forum', 'an @-handle'),
])
def test_the_screen_refuses(people, text, why):
    assert people.reason(text) == why


@pytest.mark.parametrize('text', [
    'Scored by the widget count over 1,000 episodes.',
    'The University of Example hosts the leaderboard on Hugging Face.',
    'pass@1 on the test split',
    'WidgetBench v2 adds gadgets.',
])
def test_the_screen_passes_ordinary_text(people, text):
    assert people.reason(text) is None


def test_urls_under_a_personal_account_are_not_linked(people):
    assert not people.url_ok('https://github.com/yquarr/widgetbench')
    assert not people.url_ok('https://web.archive.org/web/20260101000000/https://raw.githubusercontent.com/yquarr/'
                             'widgetbench/main/README.md')
    assert people.masked('https://raw.githubusercontent.com/yquarr/widgetbench/main/README.md') == \
        'raw.githubusercontent.com/[personal account]/widgetbench/main/README.md'
    assert not people.url_ok('https://www.example.edu/~someone/widgets.html')
    assert not people.url_ok('https://quarrington.example.org/widgets/')       # a host named for a person
    assert people.url_ok('https://github.com/openai/widgetbench')              # an organisation account
    assert people.url_ok('https://arxiv.org/abs/0000.00000')


def test_the_finished_packet_is_refused_rather_than_written_when_a_line_fails(corpus, monkeypatch):
    renderer = rp.Renderer(corpus)
    monkeypatch.setattr(renderer, 'coverage_section', lambda family, fstate: ['someone@example.org'])
    with pytest.raises(ValueError, match='fails the name screen'):
        renderer.packet('robotics-embodiment')
