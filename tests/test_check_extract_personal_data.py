"""scripts/check_extract_personal_data.py: no stored extract carries an e-mail address, an arXiv submitter's name,
an arXiv abs page's or HTML rendering's author list or a fixed-layout page's labelled list of people. The
byline, roster and affiliation fixtures are placeholders ("First Author", "Second Editor"), not anyone's name."""
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_extract_personal_data as C  # noqa: E402


def source(tree, sid, extract, **extra):
    d = tree / 'data' / 'sources' / '2026'
    d.mkdir(parents=True, exist_ok=True)
    (d / ('%s.yaml' % sid)).write_text(yaml.safe_dump(dict(id=sid, quote_extract=extract, **extra)),
                                       encoding='utf-8')


@pytest.mark.parametrize('extract', [
    'Submission history From: [name redacted] [view email] [v1] Tue, 10 Oct 2023',
    'history From: [name redacted] [ view email ] [v1]',
    'Title:ARC- … view email] [v1] Sat, 17 May 2025',                     # the window starts after the name
    '[name redacted] [view email] [v1] Mon',                               # ... or at the redaction token
    'please contact the team, [email redacted], for a consultation',
    'no personal data at all',
])
def test_a_clean_extract_passes(tmp_path, extract):
    redactions = 1 if 'redacted' in extract else None
    source(tmp_path, 'src-a', extract, quote_extract_redactions=redactions)
    assert C.check(str(tmp_path)) == []


@pytest.mark.parametrize('extract, message', [
    ('Submission history From: Ada Example [view email] [v1]', 'names the arXiv submitter 1 time'),
    ('ple [ view email ] [v1] Tue', 'names the arXiv submitter 1 time'),     # a window that starts in the name
    ('write to someone@example.org with questions', 'holds 1 e-mail address'),
    ('{a,b}@example.org and c@example.ac.uk', 'holds 2 e-mail address'),
])
def test_personal_data_fails(tmp_path, extract, message):
    source(tmp_path, 'src-a', extract)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and message in errs[0], errs


def test_a_redaction_token_needs_its_count(tmp_path):
    source(tmp_path, 'src-a', 'From: [name redacted] [view email]')
    assert 'quote_extract_redactions is unset' in C.check(str(tmp_path))[0]


def test_windows_are_read_one_at_a_time(tmp_path):
    source(tmp_path, 'src-a', 'From: [name redacted] … Someone Else [view email] [v2]', quote_extract_redactions=1)
    assert 'names the arXiv submitter 1 time' in C.check(str(tmp_path))[0]


ABS = 'https://arxiv.org/abs/2601.00001'


@pytest.mark.parametrize('extract', [
    'Title:A Benchmark Authors:[names redacted] View a PDF of the paper titled A Benchmark, by [names redacted] '
    'and 2 other authors View PDF HTML (experimental) Abstract:We introduce',
    'Title:A Benchmark Authors: … Abstract:We introduce',                       # the window ends at the label
    'Authors:[names redacted] … ped Benchmark, by [names redacted] View PDF',   # a window that opens in the title
    'View a PDF of the paper titled A Benchmark, by Example Prize Foundation View PDF',   # an organisation
])
def test_a_redacted_abs_byline_passes(tmp_path, extract):
    source(tmp_path, 'src-a', extract, url=ABS, quote_extract_redactions=extract.count('redacted') or None)
    assert C.check(str(tmp_path)) == []


@pytest.mark.parametrize('extract, times', [
    ('Title:A Benchmark Authors:First Author, Second Author View a PDF of the paper', 1),
    ('View a PDF of the paper titled A Benchmark, by First Author and 2 other authors View PDF', 1),
    ('Authors:First Author, Second Author, Third Author View a PDF of the paper titled A Benchmark, by First '
     'Author and 2 other authors View PDF HTML (experimental)', 2),
    ('Authors:[names redacted] … ork, by First Author View PDF', 1),           # one list redacted, the other not
    ('Authors:Fi … Abstract:We introduce', 1),                                  # a window cut inside the first name
])
def test_an_abs_byline_that_names_its_authors_fails(tmp_path, extract, times):
    source(tmp_path, 'src-a', extract, url=ABS, quote_extract_redactions=extract.count('redacted') or None)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and "names the paper's authors %d time" % times in errs[0], errs


def test_the_byline_rule_reads_abs_pages_only(tmp_path):
    """A PDF's byline has no fixed label to read; the sweep matched those against the arXiv API's names."""
    source(tmp_path, 'src-a', 'A Benchmark Authors: First Author', url='https://arxiv.org/pdf/2601.00001v1')
    assert C.check(str(tmp_path)) == []


def test_a_byline_that_a_quote_cites_stays(tmp_path):
    source(tmp_path, 'src-a', 'Title:A Benchmark Authors:First Author, Second Author View PDF', url=ABS)
    entry = tmp_path / 'data' / 'benchmarks' / 'agents'
    entry.mkdir(parents=True)

    def quote(text):
        (entry / 'a.yaml').write_text(yaml.safe_dump({'id': 'a', 'maintainers': {'quote': text, 'source': 'src-a'}}),
                                      encoding='utf-8')
    quote('Authors:First Author')                         # the quote check needs the byline: it stays, for review
    assert C.check(str(tmp_path)) == []
    quote('Title:A Benchmark')                            # a quote beside it is no reason to keep it
    assert "names the paper's authors 1 time" in C.check(str(tmp_path))[0]


ACL = 'https://aclanthology.org/2026.example-main.1/'
DB = 'https://datasets-benchmarks-proceedings.neurips.cc/paper_files/paper/2021/hash/0123abcd-Abstract-round2.html'


@pytest.mark.parametrize('url, extract', [
    (ACL, 'Address: Example City Editors: [names redacted] Venue: EMNLP SIG: Publisher: Association for'),
    (ACL, 'Year: 2025 Address: Example City Editors: … Language: URL:'),          # the window ends at the label
    (ACL, 'Editors: [names redacted] … Pages: 1–10 Bibkey: author-etal-2026-example Cite (ACL): First Author'),
    (DB, 'Bibtex Paper Supplemental Authors [names redacted] Abstract Remote sensing datasets pose'),
    (DB, 'Abstract We thank the Authors of earlier work for their data and code'),  # running text, not a list
    ('https://aclanthology.org/2026.example-main.1.pdf', 'Proceedings Editors: First Editor and Second Editor'),
    ('https://example.org/workshop', 'Editors: First Editor, Second Editor Venue: Online'),  # another layout
])
def test_a_redacted_or_unlabelled_roster_passes(tmp_path, url, extract):
    source(tmp_path, 'src-a', extract, url=url, quote_extract_redactions=extract.count('redacted') or None)
    assert C.check(str(tmp_path)) == []


@pytest.mark.parametrize('url, extract, times', [
    (ACL, 'Address: Example City Editors: First Editor, Second Editor, Third Editor Venue: Findings SIG:', 1),
    (ACL, 'Year: 2026 Address: Online Editors: First Editor, Second Ed … Language: URL:', 1),  # cut by a window
    (ACL, 'Editors: First van der Editor, B. Example Venue: ACL … Editors: Third Editor Venue: ACL', 2),
    (DB, 'Paper Supplemental Authors First Author, Second Author Abstract Remote sensing datasets pose', 1),
    (DB, 'Supplemental Authors First Author, Second Author, Third … for protein engineering', 1),
])
def test_a_labelled_roster_that_names_people_fails(tmp_path, url, extract, times):
    source(tmp_path, 'src-a', extract, url=url)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and 'names people in a labelled list %d time' % times in errs[0], errs


def test_a_roster_that_a_quote_cites_stays(tmp_path):
    source(tmp_path, 'src-a', 'Address: Online Editors: First Editor, Second Editor Venue: ACL', url=ACL)
    entry = tmp_path / 'data' / 'benchmarks' / 'language'
    entry.mkdir(parents=True)
    (entry / 'a.yaml').write_text(yaml.safe_dump({'id': 'a', 'maintainers': {'quote': 'Editors: First Editor',
                                                                            'source': 'src-a'}}), encoding='utf-8')
    assert C.check(str(tmp_path)) == []


HTML = 'https://arxiv.org/html/2601.00001v1'


@pytest.mark.parametrize('url, extract', [
    (HTML, 'A Benchmark [names redacted] Affiliation: Example University [names redacted] Affiliations: Example Lab'),
    (HTML, 'A Benchmark [names redacted] ∗ Affiliation: Example University'),     # a mark after the token
    (HTML, 'models [names redacted] Affiliation [...] more Affiliations: Example Research'),  # running text
    (HTML, 'A Benchmark … Affiliation: Example University'),                    # the window opens at the label
    (HTML, 'we report each team and its Affiliation: academic or industrial'),  # lower-case text before it
    (ABS, 'First Author Affiliation: Example University'),                      # the abs page has its own rule
    ('https://example.org/team', 'First Author Affiliation: Example University'),   # another layout
])
def test_a_redacted_or_unlabelled_affiliation_byline_passes(tmp_path, url, extract):
    source(tmp_path, 'src-a', extract, url=url, quote_extract_redactions=extract.count('redacted') or None)
    assert C.check(str(tmp_path)) == []


@pytest.mark.parametrize('extract, times', [
    ('A Benchmark First Author Affiliation: Example University', 1),
    ('Example University First Author, Second Author ∗ Affiliation: Example Lab Third Author Affiliations: '
     'Example', 2),
    ('[names redacted] Affiliation: Example University First van der Author Affiliation: Example Lab', 1),
    ('A Benchmark … ond Author Affiliation: Example University', 1),            # a window cut inside a name
])
def test_an_affiliation_byline_that_names_its_authors_fails(tmp_path, extract, times):
    source(tmp_path, 'src-a', extract, url=HTML, quote_extract_redactions=extract.count('redacted') or None)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and 'names authors before an "Affiliation:" label %d time' % times in errs[0], errs


def test_an_affiliation_byline_that_a_quote_cites_stays(tmp_path):
    source(tmp_path, 'src-a', 'A Benchmark First Author Affiliation: Example University', url=HTML)
    entry = tmp_path / 'data' / 'benchmarks' / 'agents'
    entry.mkdir(parents=True)

    def quote(text):
        (entry / 'a.yaml').write_text(yaml.safe_dump({'id': 'a', 'maintainers': {'quote': text, 'source': 'src-a'}}),
                                      encoding='utf-8')
    quote('First Author Affiliation: Example University')     # the quote check needs it: it stays, for review
    assert C.check(str(tmp_path)) == []
    quote('Affiliation: Example University')                   # a quote of the institution alone is no reason
    assert 'names authors before an "Affiliation:" label 1 time' in C.check(str(tmp_path))[0]


def test_the_repository_passes():
    assert C.check(ROOT) == []


def test_pr_validate_runs_it_and_it_blocks():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        job = yaml.safe_load(fh)['jobs']['extract-personal-data']
    assert 'continue-on-error' not in job and 'if' not in job
    runs = [s['run'] for s in job['steps'] if 'run' in s]
    assert runs == ['uv run --locked --python "$PYTHON" python scripts/check_extract_personal_data.py']
