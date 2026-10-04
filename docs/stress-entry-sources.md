# The stress entries' Sources (P0-S8-T08)

- **Task:** P0-S8-T08, "Write the Source records and archive captures for the seven" (04 S9, 05 S11)
- **Checked:** 2026-10-04: `bench validate --tier ref`, and `bench check-links --archive-missing` over the
  38 Sources that the seven entries and their own records (metrics, conditions, leaderboards, the rating
  pool, claims) cite. The run also covered six Sources cited by other benchmarks' metric records, all
  archived and five of them live; they are not listed here.
- **Result:** every cited Source exists and resolves (tier 2: 0 findings), and every non-DOI one carries
  an archive capture: `archive-missing: 0 non-DOI Source(s) unarchived in their records`.

Each entry task wrote its own Source records as it was curated, under ids that say what each one is, so
the seven placeholder ids in the task's CREATES list (`src-weatherbench2-paper-2023`, ...) were never
needed and are not created. What is left for a person is the verify's own judgement: whether each
archived snapshot is the right page. The links below are what to open.

## weatherbench-2 (P0-S8-T01)

| Source | Type | Archived copy, or DOI | Link check, 2026-10-04 |
| --- | --- | --- | --- |
| `src-weatherbench-2-arxiv-abs` | preprint | DOI `10.48550/arXiv.2308.15560` | live |
| `src-weatherbench-2-arxiv-html` | preprint | DOI `10.48550/arXiv.2308.15560` | live |
| `src-weatherbench-2-data-guide` | documentation | [2026-09-04](https://web.archive.org/web/20260904043316/https://weatherbench2.readthedocs.io/en/latest/data-guide.html) | live |
| `src-weatherbench-2-faq` | documentation | [2026-06-12](https://web.archive.org/web/20260612020804/https://sites.research.google/gr/weatherbench/faq/) | live |
| `src-weatherbench-2-homepage` | leaderboard-page | [2026-09-17](https://web.archive.org/web/20260917082457/https://sites.research.google/gr/weatherbench/) | live |
| `src-weatherbench-2-repo` | repository | [2026-07-02](https://web.archive.org/web/20260702051539/https://github.com/google-research/weatherbench2/) | live |
| `src-weatherbench-2-submit` | documentation | [2025-07-01](https://web.archive.org/web/20250701175517/https://weatherbench2.readthedocs.io/en/latest/submit.html) | live |

## matbench-discovery (P0-S8-T02)

| Source | Type | Archived copy, or DOI | Link check, 2026-10-04 |
| --- | --- | --- | --- |
| `src-matbench-discovery-arxiv-abs` | preprint | DOI `10.48550/arXiv.2308.14920` | live |
| `src-matbench-discovery-contribute` | documentation | [2025-04-24](https://web.archive.org/web/20250424014427/https://matbench-discovery.materialsproject.org/contribute) | live |
| `src-matbench-discovery-diatomics-page` | leaderboard-page | [2025-05-14](https://web.archive.org/web/20250514050646/https://matbench-discovery.materialsproject.org/tasks/diatomics) | archived-only |
| `src-matbench-discovery-discovery-page` | leaderboard-page | [2026-04-22](https://web.archive.org/web/20260422083919/https://matbench-discovery.materialsproject.org/tasks/discovery) | archived-only |
| `src-matbench-discovery-geo-opt-page` | leaderboard-page | [2025-05-14](https://web.archive.org/web/20250514024914/https://matbench-discovery.materialsproject.org/tasks/geo-opt) | archived-only |
| `src-matbench-discovery-homepage` | leaderboard-page | [2026-06-10](https://web.archive.org/web/20260610211707/https://matbench-discovery.materialsproject.org/) | suspect |
| `src-matbench-discovery-nature` | paper | DOI `10.1038/s42256-025-01055-1` | redirected |
| `src-matbench-discovery-repo` | repository | [2026-06-28](https://web.archive.org/web/20260628140839/https://github.com/janosh/matbench-discovery) | live |
| `src-pota-kappa-arxiv-html` | preprint | DOI `10.48550/arXiv.2408.00755` | live |

## arc-agi-3 (P0-S8-T03)

| Source | Type | Archived copy, or DOI | Link check, 2026-10-04 |
| --- | --- | --- | --- |
| `src-arc-agi-3-arxiv-abs` | preprint | DOI `10.48550/arXiv.2603.24621` | live |
| `src-arc-agi-3-community-leaderboard` | leaderboard-page | [2026-09-10](https://web.archive.org/web/20260910005944/https://arcprize.org/leaderboard/community) | live |
| `src-arc-agi-3-report-arxiv` | preprint | DOI `10.48550/arXiv.2603.24621` | live |
| `src-arc-prize-2026` | documentation | [2026-09-10](https://web.archive.org/web/20260910005930/https://arcprize.org/competitions/2026) | live |
| `src-arc-prize-leaderboard` | leaderboard-page | [2026-09-22](https://web.archive.org/web/20260922043511/https://arcprize.org/leaderboard) | live |
| `src-arc-prize-testing-policy` | documentation | [2026-09-04](https://web.archive.org/web/20260904164247/https://arcprize.org/policy) | live |

## virtual-cell-challenge (P0-S8-T04)

| Source | Type | Archived copy, or DOI | Link check, 2026-10-04 |
| --- | --- | --- | --- |
| `src-vcc-2025-cell` | paper | DOI `10.1016/j.cell.2025.06.008` | redirected |
| `src-vcc-2025-wrap-up` | blog-post | [2026-08-11](https://web.archive.org/web/20260811093502/https://arcinstitute.org/news/virtual-cell-challenge-2025-wrap-up) | live |
| `src-vcc-2026-announcement` | blog-post | [2026-09-14](https://web.archive.org/web/20260914145945/https://arcinstitute.org/news/virtual-cell-challenge-2026) | live |
| `src-vcc-2026-cell` | paper | DOI `10.1016/j.cell.2026.08.004` | redirected |
| `src-vcc-2026-data-page` | documentation | [2026-08-26](https://web.archive.org/web/20260826145701/https://virtualcellchallenge.org/_next/static/chunks/2062-284c75d3530ed5ea.js) | archived-only |
| `src-vcc-2026-evaluation` | documentation | [2026-09-20](https://web.archive.org/web/20260920002343/https://virtualcellchallenge.org/_next/static/chunks/app/(public)/evaluation/page-83d97ad9fca21302.js) | live |
| `src-vcc-2026-faq` | documentation | [2026-08-26](https://web.archive.org/web/20260826145659/https://virtualcellchallenge.org/_next/static/chunks/334-1077cec518c41e30.js) | archived-only |

## kaggle-game-arena (P0-S8-T05)

| Source | Type | Archived copy, or DOI | Link check, 2026-10-04 |
| --- | --- | --- | --- |
| `src-game-arena-arxiv-html` | preprint | DOI `10.48550/arXiv.2609.31473` | live |

## forecastbench (P0-S8-T06)

| Source | Type | Archived copy, or DOI | Link check, 2026-10-04 |
| --- | --- | --- | --- |
| `src-forecastbench-about` | documentation | [2026-09-26](https://web.archive.org/web/20260926102029/https://www.forecastbench.org/about/) | live |
| `src-forecastbench-arxiv-abs` | preprint | DOI `10.48550/arXiv.2409.19839` | live |
| `src-forecastbench-arxiv-html` | preprint | DOI `10.48550/arXiv.2409.19839` | live |
| `src-forecastbench-baseline-data` | dataset-export | [2026-09-26](https://web.archive.org/web/20260926102017/https://www.forecastbench.org/assets/js/leaderboard_baseline_full.js) | live |
| `src-forecastbench-leaderboards` | leaderboard-page | [2026-09-26](https://web.archive.org/web/20260926102034/https://www.forecastbench.org/leaderboards/) | live |
| `src-metaculus-futureeval` | leaderboard-page | [2026-09-24](https://web.archive.org/web/20260924185724/https://www.metaculus.com/futureeval/) | archived-only |

## paperbench (P0-S8-T07)

| Source | Type | Archived copy, or DOI | Link check, 2026-10-04 |
| --- | --- | --- | --- |
| `src-paperbench-arxiv-abs` | preprint | DOI `10.48550/arXiv.2504.01848` | live |
| `src-paperbench-arxiv-html` | preprint | DOI `10.48550/arXiv.2504.01848` | live |

## What the link check found

None of these changes a record; the link-rot re-check (`tools/check_links.py`, P5-S8-T01) owns them.

- **archived-only (6 of the 38):** the live URL now fails (HTTP 404 or 403) and the capture holds the
  page, which is the archive doing its job. Three Matbench Discovery task pages and two Virtual Cell
  Challenge script chunks are gone, and Metaculus refuses the checker (403).
- **suspect (1):** `src-matbench-discovery-homepage` serves a single-page-app shell with no text today, so
  a live re-read sees nothing. The entry's quotes come from its capture.
- **redirected (3):** two Cell DOIs resolving through Elsevier's linking hub, and Nature's cookie check.
  None is a change of content.
