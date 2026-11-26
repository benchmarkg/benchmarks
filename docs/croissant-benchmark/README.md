# croissant-benchmark: three worked examples

**Status: agent draft (P4-S6-T05).** The robotics and chemistry examples are **awaiting human confirmation**
(below) and must not be attached to anything public until a person has checked them. The language example is
emitted the same way but the ledger does not ask for a human check on it. The extension itself is unofficial (15
A8). Nothing has been proposed to MLCommons yet: that is P4-S6-T06, a human task.

`croissant-benchmark` is the catalogue's extension of MLCommons Croissant, published in its own namespace
(`cb:`, `https://host.invalid/ns/croissant-benchmark/v1#` until a host is fixed; 08 S5.8). The
[Croissant specification](https://github.com/mlcommons/croissant) is CC BY-ND 4.0. Nothing here restates it or
modifies it. We only link to it and use the context the pinned `mlcroissant` writes. The extension's parts:

- [the context](../../site/public/ns/croissant-benchmark/v1/context.jsonld);
- [the mapping](../../taxonomy/crosswalks/croissant.yaml);
- [the terms and their JSON Schema](../../schema/croissant_benchmark.py)
  ([generated](../../schema/generated/croissant-benchmark.schema.json));
- [ADR-0030](../../adr/0030-croissant-benchmark-mapping.md);
- [the emitter](../../tools/build/croissant.py).

## What the extension adds that a dataset record cannot

A Croissant record describes a dataset: where its files are, how they split into records and what each field
holds, so a loader can read it. A benchmark is a dataset plus the rules that turn a system's outputs into a number,
and the conditions under which two such numbers can be compared. A dataset record has nowhere to put those rules.
The extension adds five groups on the benchmark's own `sc:Dataset` node:

| Group | Class | What it says | What a dataset record lacks |
| --- | --- | --- | --- |
| `tasks` | `cb:Task` | input, output, scoring, what is evaluated, automated or panel, where the truth comes from | any notion of a question being asked |
| `metrics` | `cb:Metric` | each metric's direction (`optimum`), range, scale (`valueType`), which one is the headline | "higher is better", a pool-relative rating |
| `protocol` | `cb:Protocol` | submission route, data access class, aggregation policy, the subsets results are reported on | who runs the evaluation, and whether one score across subsets is legitimate |
| `conditions` | `cb:EvalConditions` | the material set (`materialFields`) two results must agree on to be compared, whether a rating pool is required, and the reference conditions' values when the benchmark declares them | everything: run conditions are not a property of data |
| `lineage` | `cb:Lineage` | supersession, subset, extension, variant and fork edges between benchmarks | generic links between datasets, with no supersession or fork meaning |

Each example shows a case where the dataset record alone would mislead:

- **WMT** ranks systems by human judgement per language pair and publishes no score across pairs. Its dataset
  record would look like any parallel corpus.
- **RoboArena** has no dataset at all: no task list, no test set, items chosen by evaluators on real robots
  (`dataAccess: generated-on-demand`). What a citation needs is the protocol and the rating pool, and the extension
  carries both.
- **Matbench Discovery** scores every model on one test set, yet its leaderboard splits by training-data tier.
  The two tiers share one dataset record. They differ only in a condition.

## The three examples

Each file is the document the repository's emitter writes for one curated entry (`tools/build/croissant.py`
`benchmark_document`, through the committed mapping). Keys are sorted as in the build's canonical bytes, with
two-space indentation. The `@context` is inlined, as the build inlines it, so the documents validate offline.

| File | Entry | Why it, and what makes it hard |
| --- | --- | --- |
| [language.jsonld](examples/language.jsonld) | WMT General Machine Translation (`wmt-general-mt`) | Ranked by professional and crowd raters, not by an answer key (`executionMode: panel`, `groundTruthSource: expert-panel`). Entrants are purpose-built MT systems, online services and LLMs, so its facets hit eight comparability profiles and the material set has 19 terms. There is a constrained and an unconstrained track (`eligibilityTrack`, `trainingDataPolicy`), and four yearly editions. There is no score across pairs (`aggregationPolicy: none-by-design`). |
| [robotics.jsonld](examples/robotics.jsonld) | RoboArena (`roboarena`) | Manipulation policies run on real robots at volunteer sites, with no fixed task list. The headline is a pool-relative rating (`valueType: elo`, unbounded, no range) with `ratingPoolRequired: true`, beside a pairwise win rate. The material set is `hardwarePlatform`, `venue`, `nSamples` and `subsetUsed`, plus the simulator pair, which the entry adds through `material_extra`. |
| [chemistry.jsonld](examples/chemistry.jsonld) | Matbench Discovery (`matbench-discovery`) | The systems are interatomic potentials, scored against DFT (`groundTruthSource: simulation`). The training-data tier is a condition (`eligibilityTrack`, `trainingDataEligibility`, `trainingDataPolicy`, `decontaminationApplied`). It has nine metrics with mixed directions and physical units, and a composite headline (CPS) whose weights the reader can change. Its eight subsets mix test-set slices with task variants. |

## What the examples do not carry yet

**No condition values.** A conditions node carries values only from the record named by the entry's
`reference_conditions` (`condition_values`). No language, robotics or chemistry entry declares one. In the whole
corpus, three entries do: PaperBench, the Virtual Cell Challenge and WeatherBench 2. So each example names its
material set but fills none of it. **This is the part of the done-when ("none is the easy case alone") the
examples cannot meet yet.** They will fill when a curator sets `reference_conditions` on these entries; then
re-run the regeneration below. The curator's starting points:

- Matbench Discovery: five claims share `cond-0cf2df0d2e99`, the compliant tier on the unique-prototype set.
- RoboArena: each claim's record belongs to one policy pair, so it has no obvious reference record.
- WMT: it has no claims and no conditions records.

**Terms that are lossy or could mislead** (a fix to any of them changes `schema/croissant_benchmark.py`, which
this task does not touch):

1. `Metric.units` is not carried, and the mapping's `unmapped` list does not name it. So eV/atom (hull-distance
   MAE), percent (the win rate) and rating points (RoboArena's score) are all lost.
2. `Metric.aggregation` is not carried. CPS is a weighted composite (F1 50%, κSRME 40%, RMSD 10% by default), and
   the document cannot say what it is composed of.
3. `task.exists: false` and `task.item_definition` are not carried. RoboArena's Task node holds only
   `evaluationTarget`, so a reader cannot tell "no task list, by design" from "not curated".
4. `unbounded` is written from the Metric model's default. CPS has no range in its record and reads as
   `"unbounded": false`, which says it is bounded without saying how.
5. `valueType` names a measurement scale. F1 and an eV/atom MAE are both `ratio`, and the name reads like
   "a proportion".
6. `subsets` gives ids only, so it does not say whether each one is a data split or a task variant (an ADR-0030
   reviewer check). `benchmarkVersions` gives tags only.
7. `secondary_axes` is not carried. WMT's cost axis is one example. `released` and `paper` have no term either
   (ADR-0030 D7), so mlcroissant reports three recommended-property notices per document (version,
   datePublished, citeAs).
8. WMT's material set includes `sandbox`, `scaffold` and `toolsAllowed`, because its facets hit the `agentic`
   profile. Someone should confirm that this is intended for a translation task.

## Awaiting human confirmation: what to check

Check each item against the entry's own sources (`data/benchmarks/...`), not against this README.

**Robotics: `examples/robotics.jsonld` (RoboArena).**

- [ ] The headline `roboarena-rating` is a pool-relative rating with no absolute scale: `valueType: elo`,
      `optimum: max`, unbounded, and no range.
- [ ] The win rate's range 0-100 is in percent, with ties excluded. The document does not say percent.
- [ ] `ratingPoolRequired: true`: a rating is comparable only within one pool snapshot.
- [ ] The material set (`hardwarePlatform`, `nSamples`, `simulator`, `simulatorVersion`, `subsetUsed`, `venue`)
      is complete and right for a real-robot arena. In particular, check whether the simulator pair belongs (the
      claims answer `none`), and whether `humanInLoop`, which the claims record as true, should be material.
- [ ] `submissionProcess: live-arena`, `dataAccess: generated-on-demand` and `aggregationPolicy: official-aggregate`
      match how the arena works today.
- [ ] A Task node with only `evaluationTarget` is acceptable, and `executionMode` and `groundTruthSource` are
      rightly left unrecorded (the entry leaves both null).
- [ ] The description carries no evaluator's or maintainer's name.

**Chemistry: `examples/chemistry.jsonld` (Matbench Discovery).**

- [ ] Each of the nine metrics has the right direction and range: CPS max, the headline (no range recorded); F1
      max, 0-1; DAF max, 0 or more; hull-distance MAE min, 0 or more; RMSD min, 0 or more; κSRME min, 0-2;
      W1(ω) min, 0 or more; CMDS and CDS max, 0-1.
- [ ] Publishing without units (eV/atom, Å) and without the CPS weights is acceptable, or must wait for a term
      (lossy terms 1 and 2).
- [ ] The material set (`decontaminationApplied`, `eligibilityTrack`, `subsetUsed`, `trainingDataEligibility`,
      `trainingDataPolicy`) is what separates two leaderboard numbers. Check that nothing else does, such as the
      relaxation protocol or the hardware behind the CMDS and CDS timings, which the entry deliberately leaves out.
- [ ] The eight subset ids are real leaderboard splits or tasks, under the names the site uses.
- [ ] `groundTruthSource: simulation` (PBE DFT, not experiment) and `testsHiddenFromSystem: false` (the WBM test
      set is public) are right.
- [ ] Whether `cond-0cf2df0d2e99` (compliant tier, unique prototypes) should become the entry's
      `reference_conditions`. If it should, the example gains condition values on regeneration.

When both lists are ticked, replace "awaiting human confirmation" above with the date and the confirming reviewer's
role (not their name).

## Validate and regenerate

```sh
uv run python scripts/check_croissant.py docs/croissant-benchmark/examples/
```

This holds each example to base Croissant (mlcroissant), to the extension's JSON Schema, and to an `@context` that
is exactly the upstream context plus the published one's keys. `tests/test_check_croissant.py` also checks that
each example is from its file's domain and is in the regenerated form.

To regenerate after an entry, the mapping or the emitter changes:

```sh
uv run python scripts/preview_corpus.py --out build/preview
uv run python -c "import json; [open('docs/croissant-benchmark/examples/%s.jsonld' % k, 'w', encoding='utf-8', newline='\n').write(json.dumps(json.load(open('build/preview/croissant-benchmark/%s.jsonld' % v, encoding='utf-8')), ensure_ascii=False, sort_keys=True, indent=2) + '\n') for k, v in (('language', 'wmt-general-mt'), ('robotics', 'roboarena'), ('chemistry', 'matbench-discovery'))]"
```

Nothing checks that a committed example still equals the emitter's current output. That check would need a full
build, and it would pin three entries' content to this file. So regenerate when one of the three entries changes.
