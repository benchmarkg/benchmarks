#!/usr/bin/env python3
"""Check ingest/platform-facts.yaml against itself and against the plan (P5-S3-T02).

    python scripts/check_platform_facts.py            # offline: the file, and the plan's tags
    python scripts/check_platform_facts.py --online   # also re-fetch every source and find each quote

07-ingestion-infrastructure.md S3.1: every platform number is a claim about a third party's service,
and an unmarked one reads as verified. This fails when:

  - a row lacks a verdict, an as_of date, a source URL or a verbatim quote, or has a verdict
    outside confirmed / qualified / changed / refuted, or an as_of in the future;
  - one of the seven figures P5-S3-T02 names has no row;
  - a row's `plan` anchor is not exactly once in its document, or the paragraph that starts there
    does not carry the row's tag, or still carries an unverified marker;
  - 07 S3.2, where Phase 5's platform decisions are stated, still carries an unverified marker, or
    has a list item that states a figure without a provenance tag.

A row older than --max-age days (default 92, the quarterly re-check 08 S7 schedules) is reported
as stale but does not fail: the date is a fact about when we looked, not a defect in the file.
`--online` does fail on a quote that is no longer on its page, since that means the vendor's
wording moved and the row needs re-reading.

Exit codes: 0 clean; 1 a check failed.
"""
import argparse
import html
import os
import re
import sys
import urllib.request
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS = os.path.join(ROOT, 'ingest', 'platform-facts.yaml')
PLAN = os.path.join(ROOT, '_plan')
VERDICTS = {'confirmed', 'qualified', 'changed', 'refuted'}
# P5-S3-T02 step 1, one id per figure it names.
REQUIRED = {
    'cf-workers-cron-cpu',      # Workers 10 ms CPU per cron trigger
    'gha-job-timeout',          # 6 h job timeout
    'gha-inactivity-disable',   # 60-day inactivity disable
    'github-token-rate',        # GITHUB_TOKEN 1,000/hr/repo
    'pat-rate',                 # PAT 5,000/hr
    'artifact-retention',       # 90-day artifact retention
    'pat-max-lifetime',         # PAT maximum lifetime
}
UNVERIFIED = re.compile(r'\(unverified\b|\*\*\(unverified', re.I)
TAG = re.compile(r'\[(?:recon|checked) \d{4}-\d{2}-\d{2}, (?:measured|vendor docs)\]')
# Where a paragraph, list item or table row that starts at an anchor ends.
END = re.compile(r'\n\s*\n|\n- |\n\d+\. |\n\| |\n#')
SECTIONS = [('07-ingestion-infrastructure.md', '### 3.2 ', '### 3.3 ')]
UA = 'UAIBI/0.1 (+https://github.com/intelligence-benchmark/benchmarks)'


def load(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    try:
        from ruamel.yaml import YAML
        return YAML(typ='safe').load(text)
    except ImportError:
        import yaml
        return yaml.safe_load(text)


def quotes(fact):
    """(url, quote) for every quote a row carries, its own and its `also` sources'."""
    out = [(fact.get('source_url'), q) for q in (fact.get('quote') or [])]
    for extra in fact.get('also') or []:
        out.append((extra.get('url'), extra.get('quote')))
    return out


def paragraph(text, anchor):
    i = text.index(anchor)
    m = END.search(text, i + len(anchor))
    return text[i:m.start() if m else len(text)]


def check(facts, docs, today):
    errors, stale = [], []
    rows = facts.get('facts') if isinstance(facts, dict) else None
    if not rows:
        return ['platform-facts.yaml has no `facts` list'], []
    ids = [r.get('id') for r in rows]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append('%s: id appears more than once' % dup)
    for missing in sorted(REQUIRED - set(ids)):
        errors.append('%s: no row for a figure P5-S3-T02 names' % missing)
    for r in rows:
        rid = r.get('id') or '<no id>'
        if r.get('verdict') not in VERDICTS:
            errors.append('%s: verdict %r is not one of %s' % (rid, r.get('verdict'), sorted(VERDICTS)))
        as_of = r.get('as_of')
        try:
            as_of = as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of))
        except ValueError:
            errors.append('%s: as_of %r is not a date' % (rid, r.get('as_of')))
            as_of = None
        if as_of and as_of > today:
            errors.append('%s: as_of %s is in the future' % (rid, as_of))
        if as_of and today - as_of > timedelta(days=MAX_AGE):
            stale.append('%s: checked %s, %d days ago' % (rid, as_of, (today - as_of).days))
        if not r.get('claim'):
            errors.append('%s: no claim (what the plan says)' % rid)
        for url, q in quotes(r) or [(r.get('source_url'), None)]:
            if not (isinstance(url, str) and url.startswith('https://')):
                errors.append('%s: source URL %r is not https' % (rid, url))
            if not (isinstance(q, str) and q.strip()):
                errors.append('%s: a source without a verbatim quote' % rid)
        if r.get('verdict') in ('qualified', 'changed', 'refuted') and not r.get('note'):
            errors.append('%s: a %s verdict needs a note saying what differs' % (rid, r.get('verdict')))
        want_tag = '[checked %s, vendor docs]' % as_of if as_of else None
        for loc in r.get('plan') or []:
            doc, anchor, tag = loc.get('doc'), loc.get('anchor'), loc.get('tag')
            if doc not in docs:
                errors.append('%s: plan doc %r not found' % (rid, doc))
                continue
            n = docs[doc].count(anchor or '\0')
            if n != 1:
                errors.append('%s: anchor %r occurs %d times in %s' % (rid, anchor, n, doc))
                continue
            if tag != want_tag:
                errors.append('%s: tag %r in %s does not match as_of (%s)' % (rid, tag, doc, want_tag))
            para = paragraph(docs[doc], anchor)
            if tag and tag not in para:
                errors.append('%s: %s at %r does not carry %s' % (rid, doc, anchor[:40], tag))
            if UNVERIFIED.search(para):
                errors.append('%s: %s at %r still carries an unverified marker' % (rid, doc, anchor[:40]))
        if not r.get('plan'):
            errors.append('%s: no plan location' % rid)
    for doc, start, end in SECTIONS:
        text = docs.get(doc, '')
        if start not in text or end not in text:
            errors.append('%s: section %r not found' % (doc, start.strip()))
            continue
        sec = text[text.index(start):text.index(end)]
        if UNVERIFIED.search(sec):
            errors.append('%s %s: still carries an unverified marker' % (doc, start.strip()))
        for item in re.split(r'\n(?=- )', sec)[1:]:
            if re.search(r'\d', item) and not TAG.search(item):
                errors.append('%s %s: a figure with no provenance tag: %r' % (doc, start.strip(), item[:70]))
    conv = docs.get('07-ingestion-infrastructure.md', '')
    if '`[checked ' not in conv.split('### 3.2 ')[0]:
        errors.append('07-ingestion-infrastructure.md S3.1: the `[checked ...]` tag is not in the convention table')
    return errors, stale


def page_text(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode('utf-8', 'replace')
    raw = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', raw, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', raw)))


def squash(s):
    return re.sub(r'\s+', ' ', s).strip()


def online(facts):
    errors, cache = [], {}
    for r in facts['facts']:
        for url, q in quotes(r):
            if url not in cache:
                try:
                    cache[url] = squash(page_text(url))
                except OSError as e:
                    cache[url] = e
            page = cache[url]
            if isinstance(page, Exception):
                errors.append('%s: %s could not be fetched: %s' % (r['id'], url, page))
            elif squash(q) not in page:
                errors.append('%s: quote no longer on %s: %r' % (r['id'], url, q[:70]))
    return errors


MAX_AGE = 92


def main(argv=None):
    global MAX_AGE
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--facts', default=FACTS)
    ap.add_argument('--plan', default=PLAN)
    ap.add_argument('--online', action='store_true', help='re-fetch every source and find each quote on it')
    ap.add_argument('--max-age', type=int, default=MAX_AGE, help='days before a row is reported stale')
    ap.add_argument('--today', type=date.fromisoformat, default=date.today())
    a = ap.parse_args(argv)
    MAX_AGE = a.max_age
    facts = load(a.facts)
    docs = {}
    for n in sorted(os.listdir(a.plan)):
        if n.endswith('.md'):
            with open(os.path.join(a.plan, n), encoding='utf-8') as f:
                docs[n] = f.read().replace('\r\n', '\n')
    errors, stale = check(facts, docs, a.today)
    if a.online and not errors:
        errors += online(facts)
    for s in stale:
        print('stale  ' + s)
    for e in errors:
        print('FAIL   ' + e)
    rows = facts.get('facts') or [] if isinstance(facts, dict) else []
    verdicts = {}
    for r in rows:
        verdicts[r.get('verdict')] = verdicts.get(r.get('verdict'), 0) + 1
    print('%d facts (%s); %d stale; %d failures%s' % (
        len(rows), ', '.join('%d %s' % (v, k) for k, v in sorted(verdicts.items(), key=str)),
        len(stale), len(errors), '; sources re-read' if a.online and not errors else ''))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
