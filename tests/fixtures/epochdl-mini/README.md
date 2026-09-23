# epochdl-mini -- a synthetic three-benchmark cut of the Epoch export shape

**Every row here is synthetic.** Model names (`model-a_high` ...), organisations, scores and
log URLs are invented, and every host is under `.invalid` so no URL resolves. The real export
(`epochdl/`, dated 2026-09-16) is not in the working tree, so this is not a cut of it. It
reproduces the export's *shape*: file layout, header names and the column quirks that the
counting rules in `scripts/epoch_audit.py` depend on, as recorded in
`_plan/_workflow/recon/recon_epoch-assets.md`. Do not read any value here as Epoch data.

## What each file exercises

| File | Rows | Exercises |
| --- | --- | --- |
| `benchmark_metadata.csv` | 3 | Two rows name a `source_file`; `METR` names none and has no CSV (the 00 S8.1 case) |
| `gpqa_diamond.csv` | 5 | Epoch-run family (13 columns with `Log viewer`/`Logs`): public+viewer, private+viewer, public bucket only, no log, public via the viewer's `log_file=` only |
| `swe_bench_verified.csv` | 3 | Epoch-run: public+viewer, private bucket only, no log |
| `mmlu_external.csv` | 4 | External family; **not referenced** by any metadata row; one row with no `Model version` |
| `model_metadata.csv` | 7 | Two versions share a group; one entirely blank row; one stub with only group and date |
| `epoch_capabilities_index/processed_data_for_eci.csv` | 4 | 2 distinct `benchmark_id`, 3 distinct `model_id`; lives in the subdirectory, so it must NOT count as a result CSV |
| `epoch_capabilities_index/eci_scores.csv` | 3 | ECI fit rows |

## Hand counts (`expected.json`)

Counted by reading the files above, not by running the script:

- **Result CSVs 3, rows 12** (5 + 3 + 4); mean 4.0; largest `gpqa_diamond.csv` at 5.
- **Referenced 2, unreferenced 1** (`mmlu_external.csv`); **1 metadata row without a CSV** (`METR`).
- **Epoch-run 2 files, 8 rows; external 1 file, 4 rows.**
- **Logs:** public 4 (gpqa rows 1, 3, 5; swe row 1), private 2 (gpqa row 2; swe row 2), none 2
  (gpqa row 4; swe row 3); any 6. Viewer present 4 (gpqa 1, 2, 5; swe 1); bucket only 2 (gpqa 3;
  swe 2). 6 / 12 = 50.0%, 4 / 12 = 33.3%.
- **Models:** 7 records (the blank row counts, as 00 S8.1 counts it); groups A-E = 5; versions
  `a_high`, `a_low`, `b`, `c`, `e` = 5.
- **Distinct `Model version` across result CSVs: 8** (`a_high`, `a_low`, `b`, `c`, `d`, `e`,
  `f`, `g`; the blank one is excluded).
- **ECI:** 4 rows, 2 benchmarks, 3 models; 3 score rows.
