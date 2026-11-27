#!/usr/bin/env python3
"""The per-domain review packet: one self-contained markdown file per family (P1-S4-T05; 03 S12.2, 14 Phase 1).

    python scripts/review_packet.py                                     # write every packet
    python scripts/review_packet.py --family robotics-embodiment        # one family's packet(s)
    python scripts/review_packet.py --family physics --all --out -      # every entry, to stdout
    python scripts/review_packet.py --check                             # exit 1 if any packet is stale or short
    python scripts/review_packet.py --family robotics-embodiment --check
    python scripts/review_packet.py --as-of 2026-12-01                  # date the packets by hand

03 S12.2 asks a reviewer for "one hour, one domain" and three things, and a packet has one section for each:

  1. The subdomain list: the family's live subdomains with their definitions, how many entries each holds
     (primary and secondary) and its page state, under 03 S12.2's questions ("What is missing? What is a
     distinction nobody in your field actually makes? What are we calling by the wrong name?").
  2. Ten entries: "Ten fully-classified benchmarks from their field ... Is any of this wrong? Is any of it
     embarrassing?" Each entry is rendered for checking against its sources without opening YAML (05 S4:
     primary-source-verified means "a human opened each cited source and confirmed each factual field
     against it"): the classification; every Source the entry cites, with its URL and its archive copy; every
     field that carries evidence (a `<field>_basis` or other block with `source` and `quote`, or a
     `<field>_quote` beside its field; tools/validate/quotes.py's `find`), as its value, the curator's reason
     where the basis gives one, the verbatim quote and the Source; the terms considered and rejected, with
     theirs; the entry's open `curation.review_checks`; and a checklist the reviewer ticks, one line per area.
  3. The coverage row: the family's 13 coarse cells (domain family x capability group) as
     tools/build/coverage_states.py decides them, with each cell's per-term counts from tools/build/gaps.py
     (12 S5.1: a group can read covered while most of its terms sit at zero), the triage note of every empty
     cell, the family's sign-off status and gap-claim refusal, and the gap question verbatim, in the task's
     words ("are these cells empty, or do we not know about the work") and in 03 S12.2's ("Are these cells
     genuinely empty, or do we just not know about the work?").

Which families. Every family with at least TEN published entries (scripts/seed_progress.py's rule: every
Benchmark file under data/benchmarks/<family>/, not _stubs/), at docs/review-packets/<family>.md.

Every entry, on demand. `--all` renders a family's packet with every entry instead of ten, at
docs/review-packets/<family>.all.md (or --out): a Core family's reviewer, and the maintainer promoting entries to
primary-source-verified (P1-S13-T01), has to be able to review all of them. It is rendered when that review
starts rather than committed now, because the Core families are still being curated and a committed copy would
be stale by then; an every-entry packet that is in the directory is checked like any other.

Which ten. Deterministic, and chosen for the reviewer's hour rather than at random:

  - only fully classified entries (CLASSIFIED below: a primary domain, at least one capability, evaluation
    method and designed-for subject, a lifecycle, a data access and a reproducibility tier). A family with
    fewer than ten such entries is filled from the rest, and each one says what it lacks;
  - spread over the subdomains first: the entries are taken in rounds, one per primary subdomain per round,
    so ten entries cover ten leaves where the family has them, and a reviewer judging the subdomain list
    (section 1) and the coverage row (section 3) sees the classification in as many leaves as possible;
  - within a round, and within a subdomain, the entry with the most quoted evidence first (quotes outside
    `curation.review_checks`), ties by id: the most checkable entry is the best use of an hour;
  - listed in subdomain order, then by id. The packet names every entry it leaves out.

People (the brief's rule: no individual's name or personal handle in a packet or in this script). Entries and
Source extracts hold some -- a `maintainer` naming a lab's head, an author list or a leaderboard's team names in a
quote, a repository under a personal account in every URL -- so every piece of text from the data goes through
`People`, and a piece that fails is withheld with a marker ("[withheld ...]") pointing at the entry file. It
refuses:

  - an e-mail address, "[view email]", an ORCID, "et al", "<Name>'s group/lab", "<Name> and colleagues", and an
    @-handle;
  - a run of two or more capitalised words, joined by spaces or initials, none of which the corpus ever writes
    in lower case (URLs aside) and none of them a NOT_A_NAME word (organisations, places, months, eponymous
    terms such as Pearson): that is how "<Given> <Family>" reads, and how few other things do;
  - any name, surname or handle the corpus itself shows to be a person's, collected at run time and never
    written down: the names in every `maintainer` field, the surnames that "et al", "and colleagues" or "'s
    group" point at, Source `authors`, the name before an arXiv "[view email]", the last word of every run of
    proper names in a list of three or more (an author list) or anywhere in an entry, and every GitHub, Hugging
    Face, Kaggle, GitLab or Bitbucket account in a URL that is not on ORG_ACCOUNTS.

A URL under such an account, with a `~` path, or on a host named for one of those names is shown with the
account replaced, or not at all. The finished packet is scanned line by line with the same rules, and a hit is
an error: nothing is written. It is a screen, not a proof: a lone given name, or a surname the corpus never
writes beside a given name, gets through, so a packet is read once by a person before it is sent.

Determinism. A packet is a function of the tree: no clock. Its date is the newest `curation.last_verified`
(or `added_on`) among the family's entries, or `--as-of`. Orders are taxonomy order, then id, then document
order.

--check asserts, for each packet, that the file exists, that it is exactly what this script renders now, that
it contains all three sections (every live subdomain, the expected number of entry sections, every capability
group, both forms of the gap question), and that no line of it fails the name screen. Without --family it also
fails on a packet for a family that no longer qualifies.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs, unquote, urlsplit

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.build import coverage_states, gaps  # noqa: E402
from tools.validate.quotes import find  # noqa: E402

PACKETS = 'docs/review-packets'
BENCHMARKS = 'data/benchmarks'
SOURCES = 'data/sources'
NOT_PUBLISHED = ('_stubs',)
TEN = 10
ALL_SUFFIX = '.all.md'
LOADER = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)

# The gap question, in the task's words (P1-S4-T05 step 2) and in 03 S12.2's.
GAP_QUESTION = 'are these cells empty, or do we not know about the work'
GAP_QUESTION_PLAN = ('Here is the row of the coverage matrix for your domain. Are these cells genuinely empty, or do '
                     'we just not know about the work?')
SUBDOMAIN_QUESTIONS = ('What is missing? What is a distinction nobody in your field actually makes? What are we '
                       'calling by the wrong name?')
ENTRY_QUESTIONS = 'Is any of this wrong? Is any of it embarrassing?'
HEADINGS = ('## 1. The subdomain list', '## 2. ', '## 3. The coverage row')

# Fully classified: the facets a reviewer is asked to judge, all set (an entry lacking one fills in last).
CLASSIFIED = (('domain', 'primary'), ('capability',), ('evaluation_method',), ('designed_for_subjects',),
              ('lifecycle',), ('data', 'access'), ('execution', 'reproducibility_tier'))

# The checklist areas, in order: id, heading, the line the reviewer ticks, and the top-level fields (or
# (block, field) pairs, which win) whose evidence is grouped under it. A field in none of them is `other`.
AREAS = (
    ('identity', 'Identity and id',
     'the name, aliases, id, paper and release date are right, and this is one benchmark, not a family or an '
     'edition of another',
     {'id', 'name', 'aliases', 'tagline', 'description', 'self_description', 'external_ids', 'paper', 'released',
      'release_venue', 'homepage', 'repository', 'leaderboard_url', 'dataset_url', 'croissant_url', 'lineage'}),
    ('classification', 'Domain and capabilities',
     'the primary and secondary subdomains, capabilities, evaluation methods and intended subjects fit, and no '
     'rejected term should have been kept',
     {'domain', 'capability', 'evaluation_method', 'designed_for_subjects', 'evaluation_target', 'secondary_axes'}),
    ('task', 'Task and evaluation',
     'the task, scoring, ground truth, entrants and harness read as the sources describe them',
     {'task', 'learned_entrant_evidence', 'execution_mode', 'ground_truth_source', 'reproducible_by_third_party',
      'execution', 'metric', 'metrics', 'aggregation_policy', 'no_legitimate_aggregate', 'baselines',
      'entrant_classes', 'entrant_classes_history', 'feedback_per_item', 'scale', 'results_observed', 'hardware',
      'policy_identity', 'observed_subjects', 'comparability'}),
    ('data', 'Data and licence',
     'access, refresh, provenance, sizes, subsets, contamination and licences match the sources',
     {'data', 'subsets', 'as_used', 'training_data_eligibility_tiers', ('execution', 'code_licence')}),
    ('governance', 'Governance and independence',
     'maintainer type, submission process, funding and independence flags are right', {'governance'}),
    ('lifecycle', 'Lifecycle and activity',
     'lifecycle, activity, versions, editions and history are current',
     {'lifecycle', 'activity', 'history', 'events', 'versions', 'editions', 'liveness', 'saturation_by_category'}),
)
OTHER = ('other', 'Other evidence', 'the remaining evidenced fields match their quotes', set())
REJECTED = '_considered_and_rejected'
# Keys that carry evidence or commentary rather than a value: left out when a block is shown as its value.
NOT_VALUE = {'source', 'quote', 'reason', 'caveat', 'note', 'notes', 'evidence', 'observed_on'}
NOT_VALUE_SUFFIX = ('_source', '_quote', '_note', '_notes', '_basis', '_caveat', REJECTED)

# ---- people --------------------------------------------------------------------------------------------------

# Accounts that are not a person's, so their URLs are shown. Organisation accounts were read from GitHub's GraphQL
# `repositoryOwner { __typename }` and Hugging Face's /api/organizations/<name>/overview on 2026-11-18, for every
# account in a URL in data/benchmarks/ and data/sources/; user accounts named for a project or a group rather
# than a person are added by hand; a lab named after the person who leads it is left off, like a user account.
# Lower case. An account not listed here is treated as a person's: add one only after checking it.
ORG_ACCOUNTS = {
    'github': frozenset('''
    acados activitynet aider-ai airvln align-to-innovate allenai arcinstitute arcprize arena-oss asapdiscovery
    asvspoof-challenge atomgptlab atomind-ai audioset autodrive-ecosystem autonomousvision balrog-ai benevolentai
    bigcode-project biocomputingup brain-score calochallenge carla-simulator centerforaisafety chimechallenge
    circuitnet cloudtostreet cluebenchmark coastalcph cocodataset critpt-benchmark crux-eval csailvision
    cvdfoundation davisvideochallenge dbd-research-group dcase-repo deepchem diagnijmegen diux-xview dl3dv-10k
    duckietown earthspecies ecmwf-lab eleutherai epistasislab epoch-research eth-lre eth-sri eth3d ethz-spylab
    evolvinglmms-lab extrality f1tenth facebookresearch fair-chem fair-universe farama-foundation
    forecastingresearch freedomintelligence future-house github google google-deepmind google-research
    google-research-datasets grid2op gso-bench gt-vision-lab harbor-framework harveyai hazyresearch hearbenchmark
    hidream-ai huggingface image-matching-workshop imagemarkup intelvcl internlm isl-org ismir-mirex iucomppath
    j-snackkb jailbreakbench jet-universe laion-ai lal lamalab-org langchain-ai laude-institute leap-stc
    learnsyslab lhco2020 lhcolympics2020 lifelong-robot-learning livebench livecodebench lm-sys lmarena locuslab
    lsstdesc magics-lab mani-skill maniskill2 mapeval masakhane-io materialsproject mathai2022 mcp-universe
    medmnist mercor-intelligence microsoft mila-iqia mims-harvard mlcommons mlresearch mme-benchmarks
    mmmu-benchmark modelcontextprotocol molecularai molecularsets molml motional multi-swe-bench nasaharvest
    natlabrockies ncbi-nlp nethack-le neurallatents nilc-nlp nlpdata nrel nttcslab nutonomy nvidia nyu-mll
    open-compass open-dac open-mmlab openai openbmb opendatalab openproblems-bio osu-nlp-group oxwhirl
    patronus-ai pdebench physionetchallenges pku-marl plinder-org polymathicai princeton-pli pytorch qwenlm
    ramanujanmachine rlworkgroup rna-puzzles robocasa robotwin-platform rte-france s3prl sakanaai
    salesforceairesearch scaleapi scannet scicode-bench scienceqa servicenow sierra-research simpler-env
    situatedevals sophelio stanford-crfm stanfordmlgroup stanfordvl stonybrooknlp swe-agent swe-bench tensorflow
    textarena the-ai-alliance theagentcompany thinklab-sjtu thudm thunlp-mt tiger-ai-lab trishullab ubc-vision
    ukgovernmentbeis usnistgov utiasdsl vals-ai varbench vchitect web-arena-x wmt-conference wur-ai x-plug
    xlang-ai yale-lily zerospeech
    agentclinic bigcode-bench causalnlp csebuetnlp cybench dihardchallenge hotpotqa humanoid-bench ideallab l3das
    libero-project llm-eval-mental-health omni-math os-world perception-test-challenge ptchallenge-workshop
    pubmedqa regnlp robo-arena s2s-ai-challenge smart-buildings-2026 stockbench usccolumbia video-mme vis-nlp
    hkust-nlp supergpqa
    '''.split()),
    'huggingface': frozenset('''
    adyen agc2024-p agc2025 ai-safety-institute aialliance aibic atomind behavior-1k bigcode cais
    cardinaloperations chime9-echi cmtbenchmark coastalcph cruxeval-org csebuetnlp dataset-org dbd-research-group
    dl3dv earthspeciesproject eleutherai eth-nlped facebook futurehouse gaia-benchmark gamma-lab-umd google
    gorilla-llm gso-bench gtbench hf-audio hoskinson-center hotpotqa huggingface-legal huggingfaceh4 ideallab ilsvrc iwslt
    jailbreakbench leap livebench livecodebench lmarena-ai lmms-eval lmms-lab lmsys locuslab mapeval
    marin-community masakhane matharena mercor mmmu ncbi open-llm-leaderboard openai opendatalab opendrivelab
    openlanguagedata osunlp patronusai phylobio plm-team qwen rethinklab roboarena sakanaai scaleai servicenow
    sklp-eda-lab tau thefinai tiger-lab vals-ai vchitect writingbench yale-nlp zai-org
    causal-nlp counterbench fermionresearch nuscenes princeton-nlp regnlp sophelio
    ceval m-a-p
    '''.split()),
    'kaggle': frozenset(['game-arena', 'googleai', 'l3dasteam']),
    'gitlab': frozenset(),
    'bitbucket': frozenset(),
}

GH_RESERVED = {'orgs', 'users', 'sponsors', 'topics', 'features', 'marketplace', 'apps', 'settings', 'search',
               'collections', 'trending', 'about', 'pricing', 'enterprise', 'login', 'site', 'security', 'contact',
               'explore', 'notifications', 'new', 'organizations', 'readme', 'customer-stories', 'events'}
HF_RESERVED = {'papers', 'docs', 'learn', 'tasks', 'pricing', 'join', 'login', 'settings', 'chat', 'collections',
               'new', 'models', 'blog', 'posts', 'organizations', 'datasets', 'spaces', 'api', 'enterprise', 'hub',
               'changelog', 'terms-of-service', 'privacy', 'leaderboard', 'open-source'}
KAGGLE_PAGES = {'competitions', 'c', 'datasets', 'code', 'models', 'discussions', 'learn', 'docs', 'api'}

EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b|\}\s*@\s*[\w-]+\.')
VIEW_EMAIL = re.compile(r'\[view email\]', re.I)
ORCID = re.compile(r'\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b')
ET_AL = re.compile(r'\bet\.?\s+al\b')
AT_HANDLE = re.compile(r'(?<![\w.@/])@[A-Za-z][\w-]{1,38}\b')
WORD = r"[A-Z][a-zß-ÿ]+(?:-[A-Z]?[a-zß-ÿ]+)?"
NAME_RUN = re.compile(r"(?<![\w.])((?:%s|[A-Z]\.)(?:\s+(?:%s|[A-Z]\.)){1,3})(?!\w)" % (WORD, WORD))
POSSESSIVE = re.compile(r"(?<![\w.])(%s)(?:'s|’s)\s+(?:group|lab|laboratory|students|thesis)\b" % WORD)
COLLEAGUES = re.compile(r"(?<![\w.])(%s)\s+(?:and|with)\s+(?:colleagues|co-?authors|collaborators)\b" % WORD)
CITED = re.compile(r"(?<![\w.])(%s)\s+et\.?\s+al\b" % WORD)
SUBMITTER = re.compile(r"((?:%s\s+){0,3}%s)\s*\[view email\]" % (WORD, WORD))
TOKEN = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*\.?")
URL = re.compile(r'(?:https?://|www\.)\S+')
# A capitalised run with one of these words names an organisation, a place or a time, not a person.
ORG_WORDS = frozenset('''
    A An The In On At Its Each From With For By Season Edition Track Task Phase Round Part Section Table Figure
    University Universität Université Universitat Universidad Università Universiteit Institute Institut
    Instituto Lab Labs Laboratory Laboratories Group Research Center Centre Centro Foundation Team Project
    Consortium College School Department Faculty Society Hospital Clinic Corporation Corp Company Inc Ltd Limited
    GmbH Network Networks Systems System Challenge Challenges Benchmark Benchmarks Bench Competition Workshop
    Conference Association Committee Organisation Organization Initiative Alliance Collaboration Commons Council
    Agency Office Service Services Programme Program Board Unit Division Science Sciences Technology Technologies
    Engineering Computer Computing Vision Learning Machine Language Speech Data Dataset Datasets Medical Medicine
    Health Bio Intelligence Artificial Robotics Analysis Imaging Information Physics Chemistry Mathematics
    National International Federal State Academy Academic Akademy Hub Platform Leaderboard Space Spaces Studio
    Cloud Arena League Rules Features Understanding Bank Bionetworks Communications Atomics Nordisk Chase Hopkins
    Children Physiology Branch Groep Ziekenhuis Vergata Jiao Tong Thérapeutique Innovation Hard Verified Extra
    Test Matching Hugging Face Google Meta Microsoft Facebook Amazon Apple Nvidia Alibaba Tencent Baidu Huawei
    Samsung Intel Sony Adobe Disney Bosch Toyota Motional Waymo Uber Salesforce Scale Harvey Kaggle Zenodo Synapse
    Codabench Grand New York San Diego Francisco Los Angeles Santa Barbara Tel Aviv Abu Dhabi Saudi Arabia Stony
    Brook Ann Arbor South North East West Carolina Zurich Lisbon Paulo Urbana Champaign Chicago Toronto Montreal
    Cambridge Oxford Berkeley Stanford Harvard Princeton Columbia Cornell Yale Rutgers Purdue Wisconsin Michigan
    Illinois Texas Georgia Tech Carnegie Mellon Planck Hughes Air Force Navy Army Open Free Deep Mind
    Brain Dark Energy Survey Telescope Observatory Collider Grid Earth Climate Weather Ocean Ice Solar Planet
    Galaxy Neutrino Particle Quantum Protein Gene Genome Cell Cancer Heart Kidney Lung Skin Eye Mental Shanghai
    Beijing Shenzhen Tsinghua Peking Seoul Tokyo Kyoto Singapore Sydney Melbourne Adelaide Paris London Berlin
    Munich Hamburg Heidelberg Darmstadt Freiburg Amsterdam Delft Nijmegen Copenhagen Basel Geneva Lausanne
    Edinburgh Glasgow Bologna Rome Madrid Barcelona Vienna Prague Warsaw Helsinki Stockholm Oslo Dublin Boston
    Seattle Pittsburgh Atlanta Houston Dallas Denver Phoenix Monte Carlo Las Vegas Costa Rica Mato Grosso Marina
    European Portuguese Bioscience Biosciences Lectures Polytechnical Woods Django Jetson Orin Franka Emika Panda
    Navier Stokes Prolific Moonshot Aperture Bokeh Boehringer Ingelheim Zeiss Fondazione
    January February March April May June July August September October November December Monday Tuesday
    Wednesday Thursday Friday Saturday Sunday Jan Feb Mar Apr Jun Jul Aug Sep Sept Oct Nov Dec Mon Tue Wed Thu
    Fri Sat Sun Isaac Sierra Tonic Stroke Primus Helmholtz Analytics Study
    '''.split())
# Methods, measures and laws named after people, which the data writes capitalised and never about a person. They
# never make a run of proper names, and never count as a surname on their own; a full name ending in one does.
EPONYMS = frozenset('''
    Pearson Spearman Kendall Matthews Adam Gaussian Bayesian Markov Fourier Laplace Euclidean Boltzmann Langevin
    Brier Elo Bradley Terry Wilcoxon Fisher Cohen Krippendorff Fleiss Jaccard Hamming Levenshtein Wasserstein
    Frechet Fréchet Hausdorff Pareto Nash Turing Hessian Kalman Poisson Bernoulli Dirichlet Kolmogorov Smirnov
    Reynolds Newton Euler Riemann Hilbert
    '''.split())
NOT_A_NAME = ORG_WORDS | EPONYMS
# Place names whose words are also common surnames: blanked before a text is read for a run of proper names.
PLACES = ('Hong Kong', 'Santa Cruz')
WITHHELD = '[withheld: it may name a person; see the entry file]'
CLAIM = 'the quote is the claim'          # a Row's value when the block holds only its source and quote


def unwrap(url: str) -> str:
    m = re.match(r'https?://web\.archive\.org/web/[^/]+/(.*)$', url)
    return m.group(1) if m else url


def account(url: str) -> tuple[str, str] | None:
    """(namespace, account) for a URL on a host whose first path segment is an account, else None."""
    p = urlsplit(url if '://' in url else 'http://' + url)
    host = (p.hostname or '').lower()
    seg = [unquote(s) for s in p.path.split('/') if s]
    if host == 'github.com':
        if len(seg) > 1 and seg[0] in ('orgs', 'users'):
            return ('github', seg[1])
        return ('github', seg[0]) if seg and seg[0] not in GH_RESERVED else None
    if host in ('raw.githubusercontent.com', 'codeload.github.com', 'gist.githubusercontent.com'):
        return ('github', seg[0]) if seg else None
    if host == 'media.githubusercontent.com':
        return ('github', seg[1]) if len(seg) > 1 else None
    if host == 'api.github.com':
        return ('github', seg[1]) if len(seg) > 1 and seg[0] in ('repos', 'users', 'orgs') else None
    if host.endswith('.github.io'):
        return ('github', host[:-len('.github.io')])
    if host == 'huggingface.co':
        if len(seg) > 2 and seg[0] == 'api' and seg[1] in ('datasets', 'models', 'spaces', 'organizations', 'users'):
            return ('huggingface', seg[2])
        if len(seg) > 1 and seg[0] in ('datasets', 'spaces', 'organizations', 'users'):
            return ('huggingface', seg[1])
        if len(seg) > 2 and seg[0] in ('blog', 'posts'):
            return ('huggingface', seg[1])
        return ('huggingface', seg[0]) if seg and seg[0] not in HF_RESERVED else None
    if host == 'datasets-server.huggingface.co':
        name = (parse_qs(p.query).get('dataset') or [''])[0]
        return ('huggingface', name.split('/')[0]) if '/' in name else None
    if host.endswith('.hf.space'):
        return ('hf-space', host[:-len('.hf.space')])
    if host in ('kaggle.com', 'www.kaggle.com'):
        if seg[:3] == ['api', 'v1', 'datasets'] and len(seg) > 4:
            return ('kaggle', seg[4])
        if len(seg) > 2 and seg[0] in ('datasets', 'code', 'models'):
            return ('kaggle', seg[1])
        return ('kaggle', seg[0]) if len(seg) == 1 and seg[0] not in KAGGLE_PAGES else None
    if host in ('gitlab.com', 'bitbucket.org'):
        return (host.split('.')[0], seg[0]) if seg else None
    return None


def _slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', s.lower())


def _signalled(text: str) -> set[str]:
    """The capitalised words a person signal points at: "<Name> et al", "<Name> and colleagues", "<Name>'s
    group". Not after "of" or "the" ("the Institute of Automation's laboratory"), and not a NOT_A_NAME word."""
    out = set()
    for pat in (POSSESSIVE, COLLEAGUES, CITED):
        for m in pat.finditer(text):
            before = text[max(0, m.start() - 5):m.start()]
            if m.group(1) not in NOT_A_NAME and not re.search(r'\b(?:of|the|The)\s+$', before):
                out.add(m.group(1))
    return out


def _strings(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, path + (k,))
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v, path)
    elif isinstance(node, str):
        yield path, node


def _initial(word: str) -> bool:
    return len(word) == 2 and word.endswith('.') and word[0].isupper()


def _bare(word: str) -> str:
    """A token without a trailing full stop or possessive."""
    word = word.rstrip('.')
    return word[:-2] if word.endswith(("'s", '’s')) else word


class People:
    """The name screen: `reason(text)` says why a text may name a person, or None; `url_ok(url)` whether a URL may
    be shown. The names and handles it refuses are read from the corpus when it is built (module docstring)."""

    def __init__(self, entries: list[dict], sources: dict[str, dict], known: list[str]):
        known_slugs = {_slug(k) for k in known if k}
        known_text = '\n'.join(k.casefold() for k in known if k)
        names, handles = set(), set()
        urls = []
        extracts = [src['quote_extract'] for src in sources.values() if isinstance(src.get('quote_extract'), str)]
        # Words the corpus writes in lower case somewhere (URLs aside), and every word of a catalogued benchmark's
        # name: a capitalised word that is neither is a proper name, and two or more in a row read as a person's.
        lower = {w.casefold() for k in known if k for w in TOKEN.findall(k)}
        texts = [x for e in entries for _, x in _strings(e)] + extracts
        for t in texts:
            lower.update(w for w in TOKEN.findall(URL.sub(' ', t)) if w == w.lower())
        self.lower = frozenset(w.rstrip('.') for w in lower)
        self._proper = {}
        for e in entries:
            for path, s in _strings(e):
                last = path[-1] if path else ''
                urls += re.findall(r'https?://[^\s\'"<>)\],]+', s)
                if last == 'quote' or str(last).endswith('_quote'):
                    continue
                if last == 'maintainer':
                    names |= self.harvest(s)
                names |= _signalled(s)
        for src in sources.values():
            urls += [src[k] for k in ('url', 'archive_url', 'rendered_url') if isinstance(src.get(k), str)]
            for a in src.get('authors') or []:
                if isinstance(a, str) and a.strip():
                    names.add(' '.join(a.split()))
        for extract in extracts:
            names |= {m.group(1) for m in SUBMITTER.finditer(extract)}
        for u in urls:
            a = account(unwrap(u.rstrip('.;:')))
            if a and not self.allowed(a) and _slug(a[1]) not in known_slugs:
                handles.add(a[1].lower())
        names = {n for n in names if n.casefold() not in known_text}
        # A surname: the last word of a name above, of a run of proper names in a list of three or more of them
        # anywhere in the corpus ("A B, C D and E F": an author list), or of any run in an entry's own text, so
        # that it is caught where it stands alone ("NVDLMED (<Surname>, NVIDIA)").
        surnames = {n.replace('.', ' ').split()[-1] for n in names if n.split()}
        for t in texts:
            surnames |= {r.split()[-1] for r in self.listed_runs(t)}
        for e in entries:                       # an entry's own text, which curators wrote or windowed: any run
            for _, t in _strings(e):
                surnames |= {r.split()[-1] for _, _, r in self.proper_runs(t)}
        self.surnames = frozenset(w for w in surnames if len(w) >= 3 and w not in NOT_A_NAME
                                  and w.casefold() not in known_text)
        self.names = sorted(names, key=lambda s: (-len(s), s))
        self.handles = sorted(handles, key=lambda s: (-len(s), s))
        self.url_tokens = sorted({w.lower() for n in names for w in re.split(r'[\s.\-]+', n) if len(w) >= 4}
                                 | {w.lower() for w in self.surnames if len(w) >= 4}
                                 | {h for h in handles if len(h) >= 4})
        self._names = (re.compile(r'(?<!\w)(?:%s)(?!\w)' % '|'.join(map(re.escape, self.names)))
                       if self.names else None)
        self._handles = (re.compile(r'(?<![a-z0-9])(?:%s)(?![a-z0-9])' % '|'.join(map(re.escape, self.handles)), re.I)
                         if self.handles else None)

    @staticmethod
    def harvest(text: str) -> set[str]:
        """The runs of capitalised words in a `maintainer` that read as a person's name."""
        out = set()
        for m in NAME_RUN.finditer(text):
            words = m.group(1).split()
            if text[max(0, m.start() - 3):m.start()] in ('of ', 'de '):
                continue
            if any(w.rstrip('.') in ORG_WORDS for w in words):
                continue
            out.add(m.group(1))
        return out

    def proper_runs(self, text: str):
        """Every run of two or more capitalised words that the corpus never writes in lower case and that are not
        NOT_A_NAME words, with only spaces or initials between them -- how "<Given> <Family>" reads -- as
        (start, end, run). PLACES are blanked first, keeping offsets."""
        for place in PLACES:
            text = text.replace(place, '-' * len(place))
        run, first, last_end = [], 0, 0
        for m in TOKEN.finditer(text):
            w = m.group(0)
            if run and text[last_end:m.start()].strip():        # a comma or other punctuation ends a run
                if sum(1 for x in run if not _initial(x)) >= 2:
                    yield first, last_end, ' '.join(run)
                run = []
            bare = _bare(w)
            if w[0].isupper() and (self.proper(bare) or (run and _initial(w))):
                if not run:
                    first = m.start()
                run.append(w if _initial(w) else bare)
                closes = bare != w.rstrip('.')                  # "Alice's Bob" is not one name
            else:
                closes = True
            if closes:
                if sum(1 for x in run if not _initial(x)) >= 2:
                    yield first, (m.end() if run and run[-1] in (w, bare) else last_end), ' '.join(run)
                run = []
            last_end = m.end()
        if sum(1 for x in run if not _initial(x)) >= 2:
            yield first, last_end, ' '.join(run)

    def listed_runs(self, text: str) -> list[str]:
        """The runs of proper names that stand in a list of three or more, joined by commas or "and"."""
        out, chain, end = [], [], None
        for at, stop, r in self.proper_runs(text):
            if chain and re.fullmatch(r'\s*(?:,|,?\s*and|&)\s*', text[end:at]):
                chain.append(r)
            else:
                out += chain if len(chain) >= 3 else []
                chain = [r]
            end = stop
        return out + (chain if len(chain) >= 3 else [])

    def proper(self, word: str) -> bool:
        """A capitalised word (each hyphenated part) that the corpus never writes in lower case."""
        known = self._proper.get(word)
        if known is None:
            known = self._proper[word] = (
                len(word) >= 2 and all(p[:1].isupper() and p[1:].islower() for p in word.split('-'))
                and not any(p in NOT_A_NAME for p in [word] + word.split('-'))
                and word.casefold() not in self.lower)
        return known

    @staticmethod
    def allowed(acct: tuple[str, str]) -> bool:
        kind, name = acct[0], acct[1].lower()
        if kind == 'hf-space':                                  # <owner>-<space>.hf.space
            return any(name.startswith(re.sub(r'[^a-z0-9]+', '-', o) + '-') for o in ORG_ACCOUNTS['huggingface'])
        return name in (ORG_ACCOUNTS.get(kind) or ())          # get-default: an unknown namespace allows none

    def reason(self, text) -> str | None:
        if text is None:
            return None
        s = str(text)
        for label, pat in (('an e-mail address', EMAIL), ('an arXiv submitter line', VIEW_EMAIL), ('an ORCID', ORCID),
                           ('a citation by surname', ET_AL), ('an @-handle', AT_HANDLE)):
            if pat.search(s):
                return label
        if _signalled(s):
            return "a person's group or co-authors"
        if self._names and self._names.search(s):
            return 'a name the corpus records as a person'
        if self._handles and self._handles.search(s):
            return 'a personal account'
        if next(self.proper_runs(s), None):
            return 'a run of proper names'
        for place in PLACES:
            s = s.replace(place, '-')
        if any(_bare(w) in self.surnames for w in TOKEN.findall(s)):
            return 'a surname the corpus records'
        return None

    def url_ok(self, url: str) -> bool:
        inner = unwrap(url)
        acct = account(inner)
        if acct and not self.allowed(acct):
            return False
        p = urlsplit(inner if '://' in inner else 'http://' + inner)
        if '~' in p.path:
            return False
        for label in [x for x in (p.hostname or '').split('.')[:-1] if x != 'www']:
            for t in self.url_tokens:
                if label.startswith(t) or label.endswith(t) or (len(label) >= 5 and t.startswith(label)):
                    return False
        return self.reason(re.sub(r'[/?&=+_]+', ' ', unquote(p.path + ' ' + p.query))) is None

    def masked(self, url: str) -> str | None:
        """The URL as plain text with a personal account's segment replaced, or None when the host itself or what
        is left still fails the screen."""
        inner = unwrap(url)
        p = urlsplit(inner if '://' in inner else 'http://' + inner)
        host = (p.hostname or '').lower()
        acct = account(inner)
        if not acct or acct[0] == 'hf-space' or host.endswith('.github.io') or '~' in p.path:
            return None
        parts = p.path.split('/')
        parts = ['[personal account]' if unquote(x).lower() == acct[1].lower() else x for x in parts]
        query = '' if host == 'datasets-server.huggingface.co' else ('?' + p.query if p.query else '')
        shown = '%s%s%s' % (host, '/'.join(parts), query)
        rest = shown.replace('[personal account]', ' ')
        return shown if self.reason(re.sub(r'[/?&=+_.]+', ' ', rest)) is None else None

    def scan(self, text: str) -> list[str]:
        """Every line of a finished packet that fails the screen, as 'line N: why'."""
        out = []
        for i, line in enumerate(text.split('\n'), 1):
            if line.startswith('[') and ']: http' in line:          # a link definition: its URL was screened as one
                why = None if self.url_ok(line.split(']: ', 1)[1]) else 'a personal URL'
            else:
                why = self.reason(line)
            if why:
                out.append('line %d: %s' % (i, why))
        return out


# ---- the corpus ----------------------------------------------------------------------------------------------

def _load(path: str):
    with open(path, encoding='utf-8') as fh:
        return yaml.load(fh, Loader=LOADER)


@dataclass
class Corpus:
    root: str
    families: list[dict]                 # family terms of taxonomy/domains.yaml, in order
    subdomains: dict[str, list[dict]]    # family -> its live subdomain terms, in order
    entries: dict[str, list[dict]]       # family directory -> its published entries, in path order
    sources: dict[str, dict]
    groups: list[dict]
    versions: dict[str, str]
    states: dict                         # tools/build/coverage_states.build()
    coarse: dict                         # tools/build/gaps.coarse()
    people: People


def corpus(root: str = ROOT) -> Corpus:
    domains = _load(os.path.join(root, 'taxonomy', 'domains.yaml'))
    families = [t for t in domains['terms'] if t.get('parent') is None and t.get('status') != 'retired']
    subdomains = defaultdict(list)
    for t in domains['terms']:
        if t.get('parent') and t.get('status') != 'retired':
            subdomains[t['parent']].append(t)
    entries, known = defaultdict(list), []
    for path in sorted(glob.glob(os.path.join(root, *BENCHMARKS.split('/'), '*', '*.yaml'))):
        doc = _load(path)
        known += [doc.get('id'), doc.get('name')] + list(doc.get('aliases') or [])
        fam = os.path.basename(os.path.dirname(path))
        if fam not in NOT_PUBLISHED:
            entries[fam].append(doc)
    sources = {}
    for path in sorted(glob.glob(os.path.join(root, *SOURCES.split('/'), '**', '*.yaml'), recursive=True)):
        doc = _load(path)
        if isinstance(doc, dict) and doc.get('id'):
            sources[doc['id']] = doc
    groups = _load(os.path.join(root, 'taxonomy', 'capability_groups.yaml'))
    with open(os.path.join(root, 'taxonomy', 'VERSION'), encoding='utf-8') as fh:
        taxonomy_version = fh.read().strip()
    everything = [e for fam in sorted(entries) for e in entries[fam]]               # path order, as gaps.published
    # tools/build/coverage_states.py and gaps.py read every entry through gaps.published(), three times between them;
    # they are handed the entries read above instead: the same files, by the same rule, in the same order.
    real = gaps.published
    gaps.published = lambda root=ROOT: list(everything)
    try:
        states, coarse = coverage_states.build(root), gaps.coarse(root)
    finally:
        gaps.published = real
    return Corpus(root, families, dict(subdomains), dict(entries), sources, groups['groups'],
                  {'taxonomy': taxonomy_version, 'domains': str(domains['version']), 'groups': str(groups['version'])},
                  states, coarse, People(everything, sources, known))


def eligible(c: Corpus) -> list[str]:
    """The families with at least TEN published entries, in taxonomy order."""
    return [f['id'] for f in c.families if len(c.entries.get(f['id']) or []) >= TEN]


# ---- entries -------------------------------------------------------------------------------------------------

def _get(node, path):
    for p in path:
        if isinstance(p, int):
            node = node[p] if isinstance(node, list) and p < len(node) else None
        else:
            node = node.get(p) if isinstance(node, dict) else None
    return node


def missing(entry: dict) -> list[str]:
    """The CLASSIFIED facets an entry lacks."""
    return ['.'.join(path) for path in CLASSIFIED if not _get(entry, path)]


def evidence_count(entry: dict) -> int:
    return sum(1 for q in find(entry) if q.at[:2] != ('curation', 'review_checks'))


def primary(entry: dict) -> str:
    return (entry.get('domain') or {}).get('primary') or ''                       # get-default: a stub may lack it


def choose(entries: list[dict], subdomains: list[str], everything: bool = False) -> list[dict]:
    """The entries a packet shows, in packet order (module docstring, "Which ten")."""
    order = {s: i for i, s in enumerate(subdomains)}

    def place(e):
        return (order.get(primary(e), len(order)), primary(e), e['id'])     # get-default: an unlisted leaf is last

    if everything or len(entries) <= TEN:
        return sorted(entries, key=place)
    rank = {e['id']: (-evidence_count(e), e['id']) for e in entries}
    full = [e for e in entries if not missing(e)]
    by_leaf = defaultdict(list)
    for e in sorted(full, key=lambda e: rank[e['id']]):
        by_leaf[primary(e)].append(e)
    picked = []
    while len(picked) < TEN and any(by_leaf.values()):
        heads = sorted((v.pop(0) for v in by_leaf.values() if v), key=lambda e: rank[e['id']])
        picked += heads[:TEN - len(picked)]
    if len(picked) < TEN:
        rest = sorted((e for e in entries if missing(e)), key=lambda e: (len(missing(e)), rank[e['id']]))
        picked += rest[:TEN - len(picked)]
    return sorted(picked, key=place)


@dataclass
class Row:
    area: str
    field: str            # the field the quote supports, dotted, list positions dropped
    value: object         # what the field holds (a term for a per-term basis), or CLAIM
    quote: str
    source: str | None
    reason: str | None = None
    rejected: str | None = None     # the term considered and rejected, for a *_considered_and_rejected row


def _area(path: tuple) -> str:
    keys = tuple(p for p in path if isinstance(p, str))
    for a in AREAS:
        if keys[:2] in a[3]:
            return a[0]
    for a in AREAS:
        if keys[:1] and keys[0] in a[3]:
            return a[0]
    return OTHER[0]


def _dotted(path: tuple) -> str:
    return '.'.join(p for p in path if isinstance(p, str))


def rows(entry: dict) -> list[Row]:
    """Every quote in an entry outside curation.review_checks, as the field it supports and that field's value."""
    out = []
    for q in find(entry):
        at = q.at
        if at[:2] == ('curation', 'review_checks') or at[:1] == ('provenance',):
            continue
        if q.key != 'quote':                                                   # <field>_quote beside <field>
            field = at + (q.key[:-len('_quote')],)
            out.append(Row(_area(field), _dotted(field), _get(entry, field), q.text, q.source))
            continue
        block = _get(entry, at)
        reason = block.get('reason') if isinstance(block, dict) else None
        last = at[-1] if at else None
        if isinstance(last, str) and last.endswith('_basis'):                   # <field>_basis: {reason, source, quote}
            field = at[:-1] + (last[:-len('_basis')],)
            out.append(Row(_area(field), _dotted(field), _get(entry, field), q.text, q.source, reason))
        elif len(at) > 1 and isinstance(at[-2], str) and at[-2].endswith('_basis'):   # capability_basis.<term>
            field = at[:-2] + (at[-2][:-len('_basis')],)
            out.append(Row(_area(field), _dotted(field), last, q.text, q.source, reason))
        elif len(at) > 1 and isinstance(at[-2], str) and at[-2].endswith(REJECTED):
            field = at[:-2] + (at[-2][:-len(REJECTED)],)
            out.append(Row(_area(field), _dotted(field), CLAIM, q.text, q.source, reason, str(block.get('term'))))
        else:                                                                  # a block quote: the block is the value
            owner = at
            if isinstance(last, int) and len(at) > 2 and at[-2] == 'evidence':      # subsets[i].evidence[j]
                owner = at[:-2]
            value = _get(entry, owner)
            if isinstance(value, dict) and not [k for k in value if _is_value(k)]:
                value = CLAIM                                                  # only {source, quote}: the quote is it
            out.append(Row(_area(owner), _dotted(owner), value, q.text, q.source, reason))
    return out


def _is_value(key) -> bool:
    return isinstance(key, str) and key not in NOT_VALUE and not key.endswith(NOT_VALUE_SUFFIX)


# ---- markdown ------------------------------------------------------------------------------------------------

MD_SPECIAL = re.compile(r'([\\`*_\[\]<>|~])')


def md(text) -> str:
    """Text as one escaped markdown line."""
    s = MD_SPECIAL.sub(r'\\\1', ' '.join(str(text).split()))
    return '\\' + s if re.match(r'(#|[-+=]\s|\d+[.)]\s)', s) else s


class Renderer:
    def __init__(self, c: Corpus):
        self.c = c
        self.people = c.people

    # -- screened pieces --
    def text(self, value, link: bool = True) -> str:
        """A piece of data as markdown, or the withheld marker. A value that is a URL is linked unless `link` is
        false, which a quote and a review check are: they are verbatim text."""
        if value is None:
            return 'null'
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, date):
            return value.isoformat()
        if link and isinstance(value, str) and re.match(r'https?://\S+$', value):
            return self.link(value)
        return md(WITHHELD) if self.people.reason(value) else md(value)

    def value(self, v) -> str:
        if isinstance(v, list):
            if all(not isinstance(x, (dict, list)) for x in v):
                return ', '.join(self.text(x) for x in v) if v else '[]'
            return '%d items' % len(v)
        if isinstance(v, dict):
            parts = ['%s %s' % (k, self.value(x)) for k, x in v.items()
                     if _is_value(k) and x is not None and x != [] and not isinstance(x, dict)
                     and not (isinstance(x, list) and isinstance(x[0], dict))]
            return '; '.join(parts) or '(see the quote)'
        return self.text(v)

    def link(self, url, label=None) -> str:
        """A URL as a markdown link, or as text with a personal account's segment replaced, or withheld."""
        if not isinstance(url, str) or not url:
            return '-'
        if self.people.url_ok(url):
            shown = label or re.sub(r'^https?://', '', url)
            shown = shown if len(shown) <= 72 else shown[:69] + '...'
            safe = url
            for ch, code in ((' ', '%20'), ('(', '%28'), (')', '%29'), ('<', '%3C'), ('>', '%3E')):
                safe = safe.replace(ch, code)
            return '[%s](%s)' % (md(shown), safe)
        if label and url.startswith('https://web.archive.org/'):
            return '%s (not linked: the page is under a personal account)' % md(label)
        masked = self.people.masked(url)
        return md(masked) + ' (not linked: a personal account)' if masked else '\\[withheld: a personal page\\]'

    # -- the packet --
    def packet(self, family: str, everything: bool = False, as_of: str | None = None) -> str:
        c = self.c
        fam = next(f for f in c.families if f['id'] == family)
        subs = c.subdomains.get(family) or []
        entries = c.entries.get(family) or []
        chosen = choose(entries, [s['id'] for s in subs], everything)
        when = as_of or max(max(str(e['curation'].get('last_verified') or ''), str(e['curation'].get('added_on') or ''))
                            for e in entries)
        status = Counter(e['curation'].get('verification_status') for e in entries)
        statuses = ', '.join('%d `%s`' % (n, s) for s, n in sorted(status.items(), key=lambda x: (-x[1], str(x[0]))))
        fstate = next(f for f in c.states['families'] if f['id'] == family)
        title = 'all %d entries' % len(chosen) if everything else 'ten entries'
        out = [
            '<!-- GENERATED by scripts/review_packet.py from taxonomy/ and data/ (P1-S4-T05). Do not edit by hand: '
            '`python scripts/review_packet.py --check` fails if it drifts. -->',
            '',
            '# Review packet: %s%s' % (md(fam['label']), ', every entry' if everything else ''),
            '',
            '`%s` · %d published entries%s · %d subdomains · data as of %s · taxonomy %s (domains %s, capability '
            'groups %s)' % (family, len(entries), ' · Core family' if fam.get('core') is True else '', len(subs), when,
                            c.versions['taxonomy'], c.versions['domains'], c.versions['groups']),
            '',
            'This packet asks for one hour on one domain (03-taxonomy-build-process.md §12.2) and has three parts: '
            '[the subdomain list](#1-the-subdomain-list), [%s](#2-%s) and [the coverage row](#3-the-coverage-row-'
            'and-the-gap-question-are-these-cells-empty-or-do-we-not-know-about-the-work), with one gap question. '
            'Comments by reply in plain text are all we need: name the entry id and the field, or the subdomain, '
            'or the capability group.' % (title, title.replace(' ', '-')),
            '',
            'Everything below is generated from the catalogue\'s files. Verification status of the family\'s %d '
            'entries: %s. %s' % (len(entries), statuses, (
                'No reviewer has signed this family off yet (`reviewer_signoff: %s`), so every entry in it is badged '
                '`curation_confidence: %s` and no gap is asserted in its row (14-roadmap.md Phase 1, "The honest '
                'gate").' % (fstate['reviewer_signoff'], fstate['curation_confidence'])
                if fstate['reviewer_signoff'] == 'none' else
                'The family\'s sign-off: `reviewer_signoff: %s`.' % fstate['reviewer_signoff'])),
            '',
            'How to read an entry: each evidenced field shows its value, the curator\'s reason where one was given, '
            'the verbatim quote it rests on and the Source it is quoted from (S1, S2, ... in the entry\'s Sources '
            'table, with the URL and the archived copy). Code has checked that every quote is an exact substring of '
            'the stored extract of its Source; whether the quote supports the value is what a reviewer judges. Text '
            'that may name a person is not reproduced here (%s); the entry file has it.' % md(WITHHELD),
            '',
        ]
        out += self.subdomain_section(family, fam, subs, entries)
        out += self.entries_section(family, subs, entries, chosen, everything)
        out += self.coverage_section(family, fstate)
        text = '\n'.join(out).rstrip('\n') + '\n'
        hits = self.people.scan(text)
        if hits:
            raise ValueError('%s: the packet fails the name screen, so nothing is written: %s'
                             % (family, '; '.join(hits[:10])))
        return text

    def subdomain_section(self, family, fam, subs, entries) -> list[str]:
        pages = {p['id']: p for p in self.c.states['subdomains'] if p['family'] == family}
        out = ['## 1. The subdomain list', '',
               '> Here are the %d subdomains under `%s`. %s' % (len(subs), family, SUBDOMAIN_QUESTIONS),
               '',
               '(03 §12.2, ask 1.) The family: %s' % self.text(fam.get('definition')), '']
        for key, label in (('inclusion_test', 'Included'), ('exclusion_test', 'Excluded')):
            if fam.get(key):
                out += ['- %s: %s' % (label, self.text(fam[key]))]
        out += ['', '| # | Subdomain | Definition | Entries (primary + secondary) | Page |',
                '| ---: | --- | --- | --- | --- |']
        for i, s in enumerate(subs, 1):
            p = pages.get(s['id']) or {}
            state = {'has-benchmarks': 'has benchmarks', 'not-yet-surveyed': 'not yet surveyed',
                     'surveyed-and-empty': 'surveyed and empty'}.get(p.get('state'), str(p.get('state')))
            if p.get('survey'):
                state += ' (survey note %s, %s)' % (p['survey'].get('conducted_on'),
                                                     self.text(p['survey'].get('note')))
            if s.get('gap_placeholder') is True:
                state += '; declared a gap-matrix placeholder'
            out.append('| %d | `%s`<br>%s | %s | %d + %d | %s |' % (
                i, s['id'].split('/', 1)[1], self.text(s['label']), self.text(s.get('definition')),
                p.get('primary') or 0, p.get('secondary') or 0, state))
        out += ['', 'Your answer:', '',
                '- [ ] Missing subdomains: ...',
                '- [ ] Distinctions nobody in the field makes (subdomains to merge): ...',
                '- [ ] Subdomains called by the wrong name: ...', '']
        return out

    def entries_section(self, family, subs, entries, chosen, everything) -> list[str]:
        title = 'All %d entries' % len(chosen) if everything else 'Ten entries'
        out = ['## 2. %s' % title, '', '> %s' % ENTRY_QUESTIONS, '', '(03 §12.2, ask 2.)', '']
        if everything:
            out += ['Every published entry in the family, in subdomain order, then by id.', '']
        else:
            left = sorted(e['id'] for e in entries if e not in chosen)
            out += ['How these were chosen, the same way every time: only fully classified entries (a primary '
                    'domain, at least one capability, evaluation method and intended subject, a lifecycle, a data '
                    'access and a reproducibility tier set), taken in rounds of one per primary subdomain so that '
                    'they cover as many subdomains as possible, and within a round the entries with the most quoted '
                    'evidence first (ties by id); then listed in subdomain order. An entry that is not fully '
                    'classified is used only when fewer than ten are, and says what it lacks.', '']
            if left:
                out += ['Not in this packet (%d): %s. `python scripts/review_packet.py --family %s --all` renders '
                        'every entry.' % (len(left), ', '.join('`%s`' % i for i in left), family), '']
        out += ['| # | Entry | Primary subdomain | Evidenced fields | Open review checks |',
                '| ---: | --- | --- | ---: | ---: |']
        for i, e in enumerate(chosen, 1):
            out.append('| 2.%d | [%s](#%s) | `%s` | %d | %d |' % (
                i, self.text(e.get('name') or e['id']), self.anchor(i, e), primary(e).split('/', 1)[-1],
                evidence_count(e), len(e['curation'].get('review_checks') or [])))
        out.append('')
        for i, e in enumerate(chosen, 1):
            out += self.entry(family, i, e)
        return out

    def anchor(self, i, e) -> str:
        """GitHub's anchor for the entry's heading: lower case, punctuation but `-` and `_` dropped, spaces to `-`."""
        heading = self.heading(i, e).replace('\\', '')
        return re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')

    def heading(self, i, e) -> str:
        return '2.%d %s (%s)' % (i, self.text(e.get('name') or e['id']), e['id'])

    def entry(self, family, i, e) -> list[str]:
        cur = e['curation']
        out = ['### %s' % self.heading(i, e), '',
               '`data/benchmarks/%s/%s.yaml` · `verification_status: %s` · curator confidence %s · added %s · last '
               'verified %s' % (family, e['id'], cur.get('verification_status'), cur.get('confidence'),
                                self.text(cur.get('added_on')), self.text(cur.get('last_verified'))), '']
        lacks = missing(e)
        if lacks:
            out += ['**Not fully classified:** no %s.' % ', '.join('`%s`' % m for m in lacks), '']
        if e.get('tagline'):
            out += ['*%s*' % self.text(e['tagline']), '']
        if e.get('description'):
            out += [self.text(e['description']), '']
        out += self.classification(e)
        tags, src_lines = self.sources(e)
        out += src_lines
        all_rows = rows(e)
        by_area = defaultdict(list)
        for r in all_rows:
            by_area[r.area].append(r)
        out += ['**Evidence** (%d quoted fields), by checklist area:' % len(all_rows), '']
        for a in AREAS + (OTHER,):
            kept = [r for r in by_area[a[0]] if r.rejected is None]
            rejected = [r for r in by_area[a[0]] if r.rejected is not None]
            if not kept and not rejected:
                continue
            out += ['#### %s · %s' % (e['id'], a[1]), '']
            for r in kept:
                out += self.row(r, tags)
            if rejected:
                out += ['', 'Considered and rejected:', '']
                for r in rejected:
                    out += self.row(r, tags)
            out.append('')
        checks = cur.get('review_checks') or []
        out += ['**Open review checks** (%d)%s' % (len(checks), ':' if checks else '.'), '']
        for n, chk in enumerate(checks, 1):
            where = ['field `%s`' % chk['field']] if chk.get('field') else []
            if chk.get('specialist') is True:
                where.append('needs a specialist')
            line = '%d. %s%s' % (n, '(%s) ' % ', '.join(where) if where else '',
                                 self.text(chk.get('check'), link=False))
            if chk.get('source'):
                line += ' · %s' % self.tag(chk['source'], tags)
            out.append(line)
            if chk.get('quote'):
                out.append('   > %s' % self.text(chk['quote'], link=False))
        if checks:
            out.append('')
        out += ['**Reviewer checklist** for `%s`:' % e['id'], '']
        present = {r.area for r in all_rows}
        for a in AREAS + (OTHER,):
            if a[0] in present or a is not OTHER:
                out.append('- [ ] %s: %s' % (a[1], a[2]))
        out += ['- [ ] Every open review check above is answered or resolved',
                '- [ ] Nothing here would embarrass the catalogue in front of a specialist', '']
        refs = ['[%s-s%d]: %s' % (e['id'], n, self.ref_url(sid))
                for sid, n in tags['by_id'].items() if self.ref_url(sid)]
        if refs:
            out += refs + ['']
        return out

    def classification(self, e) -> list[str]:
        dom, data, ex, gov = (e.get(k) or {} for k in ('domain', 'data', 'execution', 'governance'))
        flags = gov.get('independence_flags') or []
        flags = [f.get('flag') if isinstance(f, dict) else f for f in flags]
        links = ['%s %s' % (lab, self.link(e.get(k))) for k, lab in (
            ('homepage', 'homepage'), ('repository', 'repository'), ('leaderboard_url', 'leaderboard'),
            ('dataset_url', 'dataset')) if e.get(k)]
        rowsx = [
            ('Primary domain', self.value(dom.get('primary'))),
            ('Secondary domains', self.value(dom.get('secondary') or []) if dom.get('secondary') else '-'),
            ('Capabilities', self.value(e.get('capability') or [])),
            ('Evaluation methods', self.value(e.get('evaluation_method') or [])),
            ('Designed for', self.value(e.get('designed_for_subjects') or [])),
            ('Evaluation target · execution mode · ground truth', ' · '.join(
                self.value(e.get(k)) for k in ('evaluation_target', 'execution_mode', 'ground_truth_source'))),
            ('Lifecycle · activity', ' · '.join(self.value(e.get(k)) for k in ('lifecycle', 'activity'))),
            ('Data access · refresh · contamination risk', ' · '.join(
                self.value(data.get(k)) for k in ('access', 'refresh', 'contamination_risk'))),
            ('Reproducibility tier · harness', ' · '.join(
                self.value(ex.get(k)) for k in ('reproducibility_tier', 'harness_availability'))),
            ('Maintainer type · submission process', ' · '.join(
                self.value(gov.get(k)) for k in ('maintainer_type', 'submission_process'))),
            ('Independence flags', self.value(flags) if flags else 'none'),
            ('Licences: code · dataset', ' · '.join(
                self.value(x) for x in (ex.get('code_licence'), data.get('dataset_licence')))),
            ('Released', self.value(e.get('released'))),
            ('Links', ' · '.join(links) or '-'),
        ]
        return ['| Classification | |', '| --- | --- |'] + ['| %s | %s |' % r for r in rowsx] + ['']

    def sources(self, e) -> tuple[dict, list[str]]:
        """S-numbers for the entry's Sources, in order of first quotation, then the rest of curation.sources."""
        order = [q.source for q in find(e) if q.source]
        order += [s if isinstance(s, str) else s.get('id') for s in e['curation'].get('sources') or []]
        by_id = {}
        for sid in order:
            if sid and sid not in by_id:
                by_id[sid] = len(by_id) + 1
        tags = {'entry': e['id'], 'by_id': by_id}
        inline = {s['id']: s for s in e['curation'].get('sources') or [] if isinstance(s, dict) and s.get('id')}
        out = ['**Sources**', '', '| | Source | Type · publisher | URL | Archived copy |',
               '| --- | --- | --- | --- | --- |']
        for sid, n in by_id.items():
            rec = self.c.sources.get(sid) or inline.get(sid) or {}
            kind = ' · '.join(self.text(x) for x in (rec.get('type') or rec.get('kind'), rec.get('publisher'))
                              if x) or '-'
            arch = rec.get('archive_url')
            if arch:
                archived = self.link(arch, 'capture %s' % (rec.get('archive_captured') or ''))
            else:
                archived = 'none (%s)' % self.text(rec.get('archive_status')) if rec.get('archive_status') else 'none'
            sid_shown = '`%s`' % sid if self.people.reason(sid) is None else '(id withheld)'
            out.append('| S%d | %s | %s | %s | %s |' % (n, sid_shown, kind, self.link(rec.get('url')), archived))
        return tags, out + ['']

    def ref_url(self, sid) -> str | None:
        """The URL a Source's S-number links to, or None when it may not be shown."""
        url = (self.c.sources.get(sid) or {}).get('url')
        if not (isinstance(url, str) and self.people.url_ok(url)):
            return None
        return url.replace(' ', '%20').replace('<', '%3C').replace('>', '%3E')

    def tag(self, sid, tags) -> str:
        """S<n>, linked to the Source's URL through the entry's link definitions when it may be shown."""
        n = tags['by_id'].get(sid)
        if n is None:
            return 'a Source the entry does not list'
        return '[S%d][%s-s%d]' % (n, tags['entry'], n) if self.ref_url(sid) else 'S%d' % n

    def row(self, r: Row, tags) -> list[str]:
        if r.rejected is not None:
            head = '- `%s` not `%s`' % (r.field, self.text(r.rejected))
        elif r.value is CLAIM:
            head = '- `%s`' % r.field
        else:
            head = '- `%s` = %s' % (r.field, self.value(r.value))
        out = ['%s · %s' % (head, self.tag(r.source, tags) if r.source else 'no Source')]
        if r.reason:
            out.append('  - why: %s' % self.text(r.reason))
        out.append('  > %s' % self.text(r.quote, link=False))
        return out

    def coverage_section(self, family, fstate) -> list[str]:
        cells = [x for x in self.c.states['cells'] if x['family'] == family]
        terms = {x['group']: x for x in self.c.coarse['cells'] if x['family'] == family}
        label = {g['id']: g['label'] for g in self.c.groups}
        members = {g['id']: g['members'] for g in self.c.groups}
        cov = fstate['coverage']
        out = ['## 3. The coverage row and the gap question: %s?' % GAP_QUESTION, '',
               '> %s' % GAP_QUESTION_PLAN, '',
               '(03 §12.2, ask 3.) The row is this family crossed with the %d capability groups of '
               '`taxonomy/capability_groups.yaml` (the coarse grid, the only one a gap claim may come from: '
               '12-analytics-and-trends.md §5.1). A cell holds a benchmark when an entry in this family, by its '
               'primary domain or only by a secondary one, carries a capability term of that group (02-taxonomy.md '
               '§11 rule 1: presence at any weight); the two are counted apart.' % len(cells), '',
               '%d of %d cells hold a benchmark (%s%%), %d are declared not applicable, %d are empty. Gap claims in '
               'this row: %s%s.' % (
                   cov['has_benchmarks'], cov['cells'], cov['percent'], cov['not_applicable'],
                   cov['cells'] - cov['has_benchmarks'] - cov['not_applicable'], fstate['gap_claims'],
                   ' (%s)' % self.text(fstate['gap_claims_refusal']) if fstate['gap_claims_refusal'] else ''),
               '',
               '| Capability group | State | Entries (primary / secondary) | Member terms (primary entries carrying '
               'each) |',
               '| --- | --- | --- | --- |']
        for x in cells:
            t = (terms.get(x['group']) or {}).get('terms') or {}
            shown = ', '.join('%s %d' % (m, t.get(m) or 0) for m in members[x['group']])    # get-default: absent is 0
            out.append('| %s<br>`%s` | %s | %d / %d | %s |' % (md(label[x['group']]), x['group'], x['state'],
                                                             x['primary'], x['secondary'], shown))
        empty = [x for x in cells if x['state'] not in ('has-benchmarks', 'not-applicable')]
        declared = [x for x in cells if x['state'] == 'not-applicable']
        out += ['', 'An empty cell means one of three things (12-analytics-and-trends.md §5.4): nobody measures it, the '
                'taxonomy cuts this field badly there, or we have not found the work yet. Only the first may ever be '
                'published as a gap, and only after a reviewer has confirmed it.', '']
        if empty:
            out += ['The empty cells, for your answer:', '']
            for x in empty:
                out.append('- **%s** (`%s`, %s): [ ] genuinely empty · [ ] the work exists (please name it) · [ ] the '
                           'cell is cut badly for this field' % (md(label[x['group']]), x['group'], x['state']))
                if x.get('rationale'):
                    out.append('  - why we think the question applies here: %s' % self.text(x['rationale']))
                if x.get('survey_notes'):
                    out.append('  - survey notes: %s' % ', '.join('`%s`' % n for n in x['survey_notes']))
            out.append('')
        else:
            out += ['No cell of this row is empty. A term at zero inside an occupied group can still be a gap: say so '
                    'if one is.', '']
        if declared:
            out += ['The cells declared not applicable (their question is incoherent for this family), for your '
                    'answer:', '']
            for x in declared:
                out.append('- **%s** (`%s`): [ ] agreed, it does not apply · [ ] it applies (please name the work)'
                           % (md(label[x['group']]), x['group']))
                if x.get('rationale'):
                    out.append('  - why we think it does not apply: %s' % self.text(x['rationale']))
            out.append('')
        return out


def render(c: Corpus, family: str, everything: bool = False, as_of: str | None = None) -> str:
    return Renderer(c).packet(family, everything, as_of)


# ---- the packets on disk, and --check --------------------------------------------------------------------------

def targets(c: Corpus, family: str | None = None, everything: bool = False) -> list[tuple[str, bool]]:
    """(family, every entry?) for each packet to write or check: every eligible family's, or one family's with
    --family; the ten-entry form, or the every-entry form with --all."""
    return [(f, everything) for f in ([family] if family else eligible(c))]


def filename(family: str, everything: bool) -> str:
    return family + (ALL_SUFFIX if everything else '.md')


def sections(c: Corpus, family: str, everything: bool, text: str) -> list[str]:
    """What a packet lacks of P1-S4-T05's three sections, re-read from the text."""
    errs = []
    for h in HEADINGS:
        if not re.search(r'^%s' % re.escape(h), text, re.M):
            errs.append('no heading %r' % h)
    parts = re.split(r'^## (?=[123]\. )', text, flags=re.M)
    one = next((p for p in parts if p.startswith('1. ')), '')
    two = next((p for p in parts if p.startswith('2. ')), '')
    three = next((p for p in parts if p.startswith('3. ')), '')
    subs = [s['id'] for s in c.subdomains.get(family) or []]
    lost = [s for s in subs if '`%s`' % s.split('/', 1)[1] not in one]
    if lost:
        errs.append('the subdomain list lacks %s' % ', '.join(lost))
    n = len(c.entries.get(family) or []) if everything else min(TEN, len(c.entries.get(family) or []))
    got = len(re.findall(r'^### 2\.\d+ ', two, re.M))
    if got != n or n < TEN:
        errs.append('%d entry sections, not %d (and a packet needs at least %d)' % (got, n, TEN))
    lost = [g['id'] for g in c.groups if '`%s`' % g['id'] not in three]
    if lost:
        errs.append('the coverage row lacks %s' % ', '.join(lost))
    if GAP_QUESTION not in text or GAP_QUESTION_PLAN not in text:
        errs.append('the gap question is not there verbatim')
    return errs


def check(c: Corpus, directory: str, family: str | None, everything: bool, as_of: str | None) -> list[str]:
    """Every required packet exists, is current, has its three sections and passes the name screen. An every-entry
    packet is required only with --all, but one that is there is checked like any other; without --family, a
    packet for a family that does not qualify is an error."""
    wanted = targets(c, family, everything)
    present = sorted(n for n in os.listdir(directory) if n.endswith('.md')) if os.path.isdir(directory) else []
    fams = {f for f, _ in wanted}
    extra = [(n[:-len(ALL_SUFFIX)], True) for n in present if n.endswith(ALL_SUFFIX) and n[:-len(ALL_SUFFIX)] in fams]
    errs = []
    for fam, every in wanted + [x for x in extra if x not in wanted]:
        path = os.path.join(directory, filename(fam, every))
        rel = os.path.relpath(path, c.root).replace(os.sep, '/')
        if not os.path.exists(path):
            errs.append('%s does not exist: run scripts/review_packet.py%s%s' % (
                rel, ' --family %s' % fam if family else '', ' --all' if every else ''))
            continue
        with open(path, encoding='utf-8', newline='') as fh:
            text = fh.read()
        errs += ['%s: %s' % (rel, e) for e in sections(c, fam, every, text)]
        errs += ['%s: fails the name screen at %s' % (rel, h) for h in c.people.scan(text)]
        if text != render(c, fam, every, as_of):
            errs.append('%s is not what scripts/review_packet.py renders from the tree now: regenerate it' % rel)
    if family is None:
        qualify = set(eligible(c))
        for name in present:
            fam = name[:-len(ALL_SUFFIX)] if name.endswith(ALL_SUFFIX) else name[:-len('.md')]
            if fam not in qualify:
                errs.append('%s/%s is a packet for %s, which does not have %d published entries: delete it'
                            % (PACKETS, name, fam, TEN))
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--family', default=None, help='one family (default: every family with at least %d entries)' % TEN)
    ap.add_argument('--all', dest='everything', action='store_true', help='every entry, not ten')
    ap.add_argument('--as-of', default=None, help='the date printed on the packet (default: from the data)')
    ap.add_argument('--packets', default=None, help='the packet directory (default: <root>/%s)' % PACKETS)
    ap.add_argument('--out', default=None, help='with --family: write here instead, or - for stdout')
    ap.add_argument('--check', action='store_true', help='exit 1 if a packet is missing, stale, short or names a person')
    a = ap.parse_args(argv)
    if a.as_of:
        date.fromisoformat(a.as_of)
    c = corpus(a.root)
    if a.family and a.family not in {f['id'] for f in c.families}:
        print('FAIL  %s is not a domain family of taxonomy/domains.yaml' % a.family)
        return 2
    if a.family and len(c.entries.get(a.family) or []) < TEN:
        print('FAIL  %s has %d published entries; a packet needs at least %d' % (
            a.family, len(c.entries.get(a.family) or []), TEN))
        return 1
    directory = a.packets or os.path.join(a.root, *PACKETS.split('/'))
    if a.check:
        errs = check(c, directory, a.family, a.everything, a.as_of)
        for e in errs:
            print('FAIL  ' + e)
        if errs:
            return 1
        print('OK    %s: current, all three sections, no line fails the name screen' % ', '.join(
            filename(f, e) for f, e in targets(c, a.family, a.everything)))
        return 0
    if a.out:
        if not a.family:
            print('FAIL  --out needs --family')
            return 2
        text = render(c, a.family, a.everything, a.as_of)
        if a.out == '-':
            sys.stdout.buffer.write(text.encode('utf-8'))
        else:
            with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
        return 0
    os.makedirs(directory, exist_ok=True)
    for fam, every in targets(c, a.family, a.everything):
        path = os.path.join(directory, filename(fam, every))
        text = render(c, fam, every, a.as_of)
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        print('wrote %s (%d entries, %d bytes)' % (os.path.relpath(path, a.root).replace(os.sep, '/'),
                                                  len(re.findall(r'^### 2\.\d+ ', text, re.M)), len(text.encode('utf-8'))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
