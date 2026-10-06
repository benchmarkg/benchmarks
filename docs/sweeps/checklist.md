# The manual sweep checklist

Some of the most valuable material in the index has no API. It changes on an annual or biennial
cycle and lives on a hand-built page an academic group maintains. No adapter will ever read it, so a
curator does, on a schedule, against this checklist. The plan is
[06-sourcing-and-scraping.md](../../_plan/06-sourcing-and-scraping.md) §6; this file is the
instrument.

The point of a sweep is as much the **"checked, no change"** record as the change. It is the difference
between an entry that is current and one that merely has not been touched.

## The checklist

Run it once per hub, for every hub [hubs.yaml](hubs.yaml) lists under the family being swept,
including any shared hub that serves the family.

```
SWEEP: <family>            date: YYYY-MM-DD      curator: <handle>
For each hub in the family list:
  [ ] Page loads; note HTTP status and any redirect
  [ ] New edition / new cycle / new task announced since last sweep?     -> new Benchmark draft
  [ ] Existing edition superseded, forked or renamed?                    -> lineage edge, superseded_by
  [ ] Leaderboard still updating? last-result date vs last sweep         -> lifecycle
  [ ] Repo pushed_at, HF lastModified, dataset still downloadable        -> lifecycle
  [ ] Licence or access terms changed (new DUA, new gating)?             -> access fields + §1.2 veto
  [ ] Paper / assessment publication since last sweep?                   -> Source + DOI
  [ ] archive_url present and CDX digest unchanged?                      -> re-archive if changed
  [ ] Rating pool composition changed (Elo families only)?               -> new RatingPool snapshot
  [ ] If nothing changed: write checked_at, do not touch any other field
```

The arrows name what each finding becomes. `§1.2` is 06 §1.2: a licence change can veto a source,
not just reorder it.

## Running a sweep

1. Open one PR per family. It holds every change the sweep found, plus a dated "checked" stamp on
   every entry that did not change.
2. Walk every hub with the checklist above. A hub whose page will not load is still a result: write
   down the status and the date. The hub list itself is corrected in the same PR when a hub has
   moved, died or been superseded.
3. For a **lineage** family, new benchmarks are not the target; forks, renames, concurrent versions
   and contamination events are. Drive the pass from `superseded_by` gaps and from version strings in
   Epoch and EEE that match no `BenchmarkVersion` we carry.
4. The **vision** sweep is capped on purpose. Its long tail is the largest in the index; stop at the
   cap and record where you stopped.
5. **OpenCompass / CompassHub** is the one hub that exists to counter the catalogue's
   English-language sourcing bias. It must not be dropped when a sweep runs late.

## Cadence

Cadence follows how fast a family's benchmark population turns over, not how interesting it is.
Every domain family appears, including the ones automation mostly covers. For those, the sweep looks
for lineage and supersession events rather than new benchmarks: no adapter notices a fork.

The table below is generated. Its family column comes from `taxonomy/domains.yaml`, and the rest
from [hubs.yaml](hubs.yaml). `python scripts/check_sweep_families.py` fails if it is stale, if
hubs.yaml's families are not exactly the domain vocabulary, or if 06 §6's cadence table disagrees.
To change it, edit hubs.yaml and run the script with `--write`.

<!-- gen: scripts/check_sweep_families.py --write; edit docs/sweeps/hubs.yaml, not this table -->
| Family | Cadence | Focus | Hubs | Anchor events |
| --- | --- | --- | --- | --- |
| robotics-embodiment | quarterly | discovery | 13 | CoRL (Nov), RSS (Jul), ICRA/IROS, CVPR Embodied AI workshop (Jun) |
| vision | quarterly, capped | discovery | 5 | CVPR (Jun), ICCV/ECCV, NTIRE, Image Matching Workshop |
| agents-tooluse | quarterly | discovery | 5 | Rolling; no conference anchor |
| medicine-health | quarterly | discovery | 6 | MICCAI (Sep/Oct), RSNA (Nov) |
| code | quarterly | lineage | 4 | Rolling |
| biology-genetics | semi-annual | discovery | 7 | CASP (biennial), CAFA, CAGI, DREAM, Virtual Cell Challenge |
| chemistry-materials | semi-annual | discovery | 5 | NeurIPS AI4Science, ACS, CACHE round announcements |
| audio-speech | semi-annual | discovery | 5 | DCASE (window Apr-Jun, results 30 Jun), INTERSPEECH, IWSLT, ISMIR |
| earth-climate | semi-annual | discovery | 7 | Climate Change AI workshop, AGU/EGU, LifeCLEF (CLEF, Sep) |
| physics | semi-annual | discovery | 6 | NeurIPS ML4PS, ACAT/CHEP, NeurIPS competition track |
| safety-alignment | semi-annual | discovery | 3 | inspect_evals releases, AISI publications |
| society-econ-law | semi-annual | discovery | 5 | ICAIL, FAccT, Metaculus quarterly tournaments |
| games-planning | semi-annual | discovery | 4 | NeurIPS competition track, IEEE CoG, ARC Prize milestones |
| multimodal | semi-annual | discovery | 0 + 1 shared | CVPR, NeurIPS, vendor releases |
| language | annual | lineage | 0 + 1 shared | ACL/EMNLP/NAACL |
| engineering-design | annual | survey | 4 | NeurIPS AI4Science, EDA/CAD venues |
| general-intelligence | annual | discovery | 0 + 1 shared | ARC Prize, HLE updates |
| mathematics | annual | lineage | 0 + 1 shared | NeurIPS, AIME/IMO cycle |
| reasoning-general | annual | lineage | 0 + 1 shared | NeurIPS, ICLR |

Quarterly 5, semi-annual 9, annual 5: 19 families.
<!-- /gen -->

What each family's sweep is for, and its hubs, are in [hubs.yaml](hubs.yaml). The effort this costs
is 06 §6's estimate: 126-169 hours a year.
