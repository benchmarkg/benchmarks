# What happens when we stop

This file says, publicly and in advance, what happens to the Universal AI Benchmark Index if its
maintainers stop working on it. It is written now, while nobody has a stake in the answer, because
the catalogues that did not write it down could not be rescued.

If you are reading this because the project has gone quiet: **you do not need anyone's permission
to continue it.** Everything below is there so you can.

## The seven commitments

1. **The licence permits a fork without asking anyone.** The data and taxonomy (`data/`,
   `taxonomy/`, `docs/`) are [CC-BY-4.0](LICENSE-DATA); the code (`tools/`, `ingest/`, `schema/`,
   `site/`, `scripts/`) is [MIT](LICENSE-CODE). [`REUSE.toml`](REUSE.toml) maps every path in the
   repository to its licence, so this is checkable by machine rather than by reading. There is no
   non-commercial clause, no share-alike, and no "contact us". Fork it, rename it, host it.

2. **Every release is citable and downloadable independently of us.** Each quarterly release is
   deposited on Zenodo with its own DOI, under a concept DOI that always resolves to the latest
   version (see [`CITATION.cff`](CITATION.cff)). A Zenodo record survives the GitHub organisation,
   the domain and the maintainers.

3. **Mirrors exist and are automatic.** GitHub is the primary copy. A Codeberg mirror and a Hugging
   Face dataset mirror are pushed on every release. A save request is submitted to Software
   Heritage explicitly for each release rather than assuming it archives the repository on its own.

4. **The build is documented and tested.** `docs/reproduce.md` gives the pinned versions (Python
   3.12, Node 22.12 or later, Astro 7.3.x, and the exact `umap-learn`, `scikit-learn` and `numba`
   pins in [`pyproject.toml`](pyproject.toml) and `uv.lock`). `reproduce.yml` rebuilds the whole
   site every month on a clean runner with no cache, so "you can just fork it" is tested, not
   assumed.

5. **Dormancy is announced by the repository itself, automatically, and succession comes before the
   banner.** The build reads the date of the last human commit to `data/`.

   - **At 90 days without a human commit to `data/`, this file is invoked.** A `Maintainer
     succession` issue is opened and pinned, the README carries the notice, the stewards and
     institutions in the handover list below are contacted in order, and the search for a
     successor begins, while the data is still current enough to be worth taking on.
   - **At 180 days without a human commit to `data/`, the site-wide staleness banner turns on**,
     driven by the same commit timestamp, with no human action required: *"This index has not been
     curated since &lt;date&gt;. Data older than that should be checked against primary sources."*

   The order is deliberate: the search for a steward has to start while the data is worth
   inheriting, and the banner is the public admission that it may no longer be. Both triggers are
   tested in CI against a fake clock, because an untested trigger is a promise, not a mechanism. A
   stale banner is far better than silent staleness, which propagates errors into other people's
   published research. Automated ingestion commits do not count as curation and do not reset
   either clock.

6. **Per-domain stewards, not one central curator.** `CODEOWNERS` is path-scoped, so a steward can
   own one domain -- robotics owns `data/benchmarks/robotics-embodiment/` -- without taking on the
   whole index. When HELM entered maintenance mode, MedHELM survived by spinning out to an
   independent steward. The vertical that found a steward lived; the parent did not. This project
   is designed for that outcome from the start.

7. **A named handover intent.** If the maintainers stop, the intent is to transfer the repository
   and the domain to a steward, approached in the order below. This file owns the list; other
   documents point here rather than keeping their own copy.

## The handover list, in priority order

1. **Per-domain stewards**, on the MedHELM model: a group already working in one domain takes that
   domain's part of the index, because the vertical that finds a steward survives.
2. **MLCommons**, which already maintains Dynabench and Croissant and is the natural home for a
   `croissant-benchmark` extension.
3. **The EvalEval coalition** (Hugging Face, the University of Edinburgh and EleutherAI), whose
   result registry is the complement to this benchmark registry.
4. **A university group** willing to host the repository and the domain.

Failing all of these, the final state is still decided in advance: the last release DOI'd on
Zenodo, the staleness banner visible, and the licence permissive. There is no scenario in which the
data goes private, and no scenario in which it goes quiet without saying so.

## If you want to take it on

Open an issue titled `Maintainer succession` (or comment on the pinned one if it already exists),
saying who you are and which part of the index you would steward. If the maintainers do not answer,
you do not need them to: fork the repository, keep the licences and the attribution in
`LICENSE-DATA`, and carry on. The git history, every source record and the taxonomy's decision
records are in the repository, so nothing needed to continue the work lives anywhere else.

---

*Status on 2026-09-25, stated so that none of the above reads as done before it is.* In place: the
licences and `REUSE.toml` (1), `CITATION.cff` (2). Not yet built, each with a task in the build plan
(`_plan/execution/tasks.yaml`): the Zenodo concept DOI and per-release deposit (2), the data-only
mirror pushed by the release workflow (3), `docs/reproduce.md` and `reproduce.yml` (4), the dormancy
triggers and their CI test (5), and `CODEOWNERS` (6). Not yet built and with no task yet: setting up
the Codeberg mirror itself, and the Software Heritage save request (3). This line is updated as each
lands.
