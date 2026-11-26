"""scripts/check_extract_personal_data.py: no stored extract carries an e-mail address, an arXiv submitter's name,
an arXiv abs page's or HTML rendering's author list, a fixed-layout page's labelled list of people, a paper's
author note or a copyright line that names a person. The byline, roster, affiliation, author-note and copyright
fixtures are placeholders ("First Author", "Second Editor", "A. First", "Ada Example"), not anyone's name; the
copyright fixtures take the shapes the 2026-11-26 sweep redacted, and the organisations are invented too."""
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


PDF = 'https://example.org/papers/a-challenge.pdf'
NOTE = 'names authors before "is with" or "are with" %d time'


@pytest.mark.parametrize('extract', [
    'The developed algo- [names redacted] are with the Department of Example … top algorithms',
    'combinations of the [names redacted] is also with Example AB, top algorithms result in',
    'The dataset is with the organisers, and the test labels are with the hosts',  # running text
    'Team 2 is with the leaders. Team 4, 7 and 12 are with them',                  # a number is no name
    'Copyright is with the authors. The Authors are with us',                      # no initial, no author note
    'Ada Example is with Example University',              # ... so a note without one is not caught (docstring)
    'Abstract We present A. First and B. Second … are with Example University',    # the window opens at it
    'Abstract We present A. First and B. Second are wi … th Example University',   # a window cuts the phrase off
])
def test_a_redacted_or_running_text_author_note_passes(tmp_path, extract):
    source(tmp_path, 'src-a', extract, url=PDF, quote_extract_redactions=extract.count('redacted') or None)
    assert C.check(str(tmp_path)) == []


@pytest.mark.parametrize('extract, times', [
    ('The developed algo- A. First and B. Second are with the Departm … ple, top algorithms', 1),
    ('combinations of the A. First, B. E. Second, and C. van der Third are with Example AB, top', 1),
    ('A. First is with Example University. B. Second is also with Example Lab', 2),
    ('J.-P. First are also with Example Lab … the rights are with the authors', 1),
    ('[names redacted] and B. Second are with Example Lab', 1),                    # one name left by the token
    ('Abstract We present … rst and B. Second are with Example Lab', 1),           # a window cut inside the run
])
def test_an_author_note_that_names_its_authors_fails(tmp_path, extract, times):
    source(tmp_path, 'src-a', extract, url=PDF, quote_extract_redactions=extract.count('redacted') or None)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and NOTE % times in errs[0], errs


@pytest.mark.parametrize('url', [None, ABS, HTML, ACL, 'https://example.org/proceedings/a-challenge'])
def test_the_author_note_rule_reads_every_page(tmp_path, url):
    source(tmp_path, 'src-a', 'lymph nodes A. First and B. Second are with Example University', url=url)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and NOTE % 1 in errs[0], errs


def test_an_author_note_that_a_quote_cites_stays(tmp_path):
    source(tmp_path, 'src-a', 'combinations of the A. First and B. Second are with Example AB, top', url=PDF)
    entry = tmp_path / 'data' / 'benchmarks' / 'medicine-health'
    entry.mkdir(parents=True)

    def quote(text):
        (entry / 'a.yaml').write_text(yaml.safe_dump({'id': 'a', 'maintainers': {'quote': text, 'source': 'src-a'}}),
                                      encoding='utf-8')
    quote('A. First and B. Second are with Example AB')        # the quote check needs it: it stays, for review
    assert C.check(str(tmp_path)) == []
    quote('are with Example AB')                               # a quote of the institution alone is no reason
    assert NOTE % 1 in C.check(str(tmp_path))[0]


def test_a_redacted_author_note_needs_its_count(tmp_path):
    source(tmp_path, 'src-a', 'The developed algo- [names redacted] are with the Department of Example', url=PDF)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and 'holds 1 redaction token(s) but quote_extract_redactions is unset' in errs[0], errs


HOLDER = 'names a person as copyright holder %d time'
# The shapes the sweep of 2026-11-26 redacted, as (the line naming its holder, the line as redacted)
COPYRIGHT_SHAPES = [
    ('Example University. Previous Next © Copyright 2023, Ada Example. Revision 0a1b2c3d. Built with Sphinx',
     'Example University. Previous Next © Copyright 2023, [name redacted]. Revision 0a1b2c3d. Built with Sphinx'),
    ('Registration opens Sep 15, 2020 ... © 2026 Ada Example & EXAMPLE. Powered by Jekyll',          # a site footer
     'Registration opens Sep 15, 2020 ... © 2026 [name redacted] & EXAMPLE. Powered by Jekyll'),
    ('MIT License Copyright (c) 2024 Ada Example Permission is hereby granted, free of charge',      # a licence
     'MIT License Copyright (c) 2024 [name redacted] Permission is hereby granted, free of charge'),
    ('the Third-Party Software: 1. Example (LICENSE) Copyright 2017 Ada Example. DM19-0000 ## Example',
     'the Third-Party Software: 1. Example (LICENSE) Copyright 2017 [name redacted]. DM19-0000 ## Example'),
    ('Changelog RSS Example Discovery | © Ada Example (2022) { __sveltekit_0abc = { base: new URL',  # year after
     'Changelog RSS Example Discovery | © [name redacted] (2022) { __sveltekit_0abc = { base: new URL'),
    ('and great fun. Copyright A. Example et al. This work is licensed under the Creative Commons',  # no year, no ©
     'and great fun. Copyright [name redacted] et al. This work is licensed under the Creative Commons'),
]


@pytest.mark.parametrize('named, redacted', COPYRIGHT_SHAPES)
def test_a_copyright_line_naming_a_person_fails_and_its_redacted_form_passes(tmp_path, named, redacted):
    source(tmp_path, 'src-a', named)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and HOLDER % 1 in errs[0], errs
    source(tmp_path, 'src-a', redacted, quote_extract_redactions=1)
    assert C.check(str(tmp_path)) == []


@pytest.mark.parametrize('extract', [
    'MIT License Copyright (c) 2021 ExampleAI Permission is hereby granted',          # camel case: a company
    'BSD 3-Clause License Copyright (c) 2023, The EXAMPLE authors Redistribution and use',
    'Copyright (c) 2025 example-benchmark-examples Contributors Permission is hereby granted',
    '© 2025 The Author(s). Published by Example Press. © Author(s) 2026. This work is distributed',
    '© 2026 Example Labs Inc. All rights reserved.',
    '© Copyright 2023, Example, LLC. Built with Sphinx. Copyright 2023 Example LLC Licensed under',
    'Copyright 2021 Example Licensed under the Apache License, Version 2.0',            # one word, then licence text
    '© 2026 Example AI. All rights reserved. © 2026 Example. All Rights Reserved.',
    'Copyright (c) 2024 Example Robot Learning Lab (ERL) lab @ Example Berkeley',
    '©2024 Association for Example Linguistics. © 2018 Example Centre for Robotic Vision.',
    '© 2026 Open Problems in Example-Cell Analysis',                                    # a connector carries it on
    'Copyright © 2022-present ExampleNet Team. Copyright (c) 2015 - 2026 EXAMPLE team - INRIA, ENS',
    '© Copyright DREAM Examples . Powered by Example Bionetworks. © Example Geometry Group. Design by BootStrap',
    'Contact us © 2007-2026, University of Example. © Design: HTML5 UP',
    'Copyright 2020 by the author(s). Copyright 2024 by the a',
    'PMLR 306, 2026. Copyright 2026 … Word Problem Benchmarks mix two challenges',      # a year alone
    'PMC Disclaimer | PMC Copyright Notice Example Rev Chem . Author manuscript',       # boilerplate, no notice
    '## Generate Response with Copyright Risk Mitigation Methods Coming Soon.',
    'Copyright and License information © The Author(s) 2023. PMC Copyright notice Table 1.',
    'Neither the name of the copyright holder nor the names of its contributors',
    'In Fig. 6(c) We Compare Example Fields. (c) Did You report error bars? A 501(c)(3) Example Nonprofit',
    'HAM10000 Dataset: (c) by ExampleIR Group, Department of Dermatology',
])
def test_an_organisation_or_boilerplate_copyright_line_passes(tmp_path, extract):
    source(tmp_path, 'src-a', extract, url=PDF)
    assert C.check(str(tmp_path)) == []


@pytest.mark.parametrize('extract, times', [
    ('Copyright Example et al. This work is licensed', 1),                     # a surname before "et al."
    ('© 2020 by Ada van der Example. All rights reserved.', 1),                # "by", a name particle
    ('MIT License Copyright (c) 2021 A. Example and B. Example Permission is hereby granted', 1),   # one holder
    ('Copyright (C) 2019 Jean-Pierre O\'Example', 1),
    ('© Ada Example (2022) { … } Copyright 2019 Bo Example. Licensed', 2),
    ('© 2026 [name redacted] & Ada Example. Powered by Jekyll', 1),            # a token holds one name's place
    ('Round opens Sep 15, 2020 ... © 2026 Ada Exa … Powered by Jekyll', 1),     # a window cut inside the name
    ('its footer reads "© 2026 Ada Example"; unlicensed is the default', 1),   # quotes around it
])
def test_a_copyright_holder_that_names_a_person_fails(tmp_path, extract, times):
    source(tmp_path, 'src-a', extract, quote_extract_redactions=extract.count('redacted') or None)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and HOLDER % times in errs[0], errs


@pytest.mark.parametrize('url', [None, ABS, HTML, ACL, PDF])
def test_the_copyright_rule_reads_every_page(tmp_path, url):
    source(tmp_path, 'src-a', 'MIT License Copyright (c) 2024 Ada Example Permission is hereby granted', url=url)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and HOLDER % 1 in errs[0], errs


def test_the_copyright_rule_reads_a_withheld_source(tmp_path):
    """Its body is never archived, but its extract is stored and published like any other: every rule reads it."""
    source(tmp_path, 'src-a', 'Example Lab | © 2026 Ada Example', archive_status='withheld',
           contains_personal_data=True, failure_reason='the page lists its team')
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and HOLDER % 1 in errs[0], errs


def test_a_copyright_holder_that_a_quote_cites_stays(tmp_path):
    """As for the other rules; it is also how an organisation that reads as a person's name stays."""
    source(tmp_path, 'src-a', 'MIT License Copyright (c) 2022 Neural Example Permission is hereby granted, free')
    entry = tmp_path / 'data' / 'benchmarks' / 'biology-genetics'
    entry.mkdir(parents=True)

    def quote(text):
        (entry / 'a.yaml').write_text(yaml.safe_dump({'id': 'a', 'maintainers': {'quote': text, 'source': 'src-a'}}),
                                      encoding='utf-8')
    quote('MIT License Copyright (c) 2022 Neural Example')       # the quote check needs it: it stays, for review
    assert C.check(str(tmp_path)) == []
    quote('MIT License')                                         # a quote beside it is no reason to keep it
    assert HOLDER % 1 in C.check(str(tmp_path))[0]


def test_a_redacted_copyright_holder_needs_its_count(tmp_path):
    source(tmp_path, 'src-a', 'Example Discovery | © [name redacted] (2022) { __sveltekit')
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and 'holds 1 redaction token(s) but quote_extract_redactions is unset' in errs[0], errs


def test_the_repository_passes():
    assert C.check(ROOT) == []


def test_pr_validate_runs_it_and_it_blocks():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        job = yaml.safe_load(fh)['jobs']['extract-personal-data']
    assert 'continue-on-error' not in job and 'if' not in job
    runs = [s['run'] for s in job['steps'] if 'run' in s]
    assert runs == ['uv run --locked --python "$PYTHON" python scripts/check_extract_personal_data.py']
