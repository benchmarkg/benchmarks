# Releasing a version to Zenodo

The index has one Zenodo record and one **concept DOI**, which always resolves to the latest version:

| | DOI | Record |
| --- | --- | --- |
| Concept (cite this) | [10.5281/zenodo.23045827](https://doi.org/10.5281/zenodo.23045827) | https://zenodo.org/records/23045828/latest |
| v0.1.0, 2026-09-29 | [10.5281/zenodo.23045828](https://doi.org/10.5281/zenodo.23045828) | https://zenodo.org/records/23045828 |

`CITATION.cff` carries the concept DOI.

## Why by hand

05-repository-and-workflow.md §10 has GitHub's Zenodo integration mint a DOI on every release. The
first version was uploaded by hand instead, on 2026-09-29, before the integration was switched on.
The integration cannot adopt an existing record: switched on now, it would open a second record
with a second concept DOI for the same work, and a published DOI cannot be withdrawn. So versions
are added to this record by hand (a maintainer's decision of 2026-09-29), and **the Zenodo-GitHub
integration stays off for this repository**. Moving to the integration later means accepting a
second concept DOI and marking this record as superseded; decide that in an ADR, not in passing.

## Each release

1. Tag the release on `main` (`vX.Y.Z`) and publish the GitHub release. GitHub builds the source zip.
2. On Zenodo, open the record above and choose **New version**. Do not create a new upload: a new
   upload gets a new concept DOI.
3. Replace the file with the release's source zip (and the release's `data.tar.gz`, once
   05 §10's release artifacts exist).
4. Set **Version** to the tag, exactly (`vX.Y.Z`), and **Publication date** to the release date.
5. Check that the metadata carried over from the last version:
   - Title: The Universal AI Benchmark Index
   - Resource type: Dataset
   - Creators: as `CITATION.cff` `authors`
   - Licences: CC-BY-4.0 (data, taxonomy, documentation) and MIT (code); `REUSE.toml` maps every path
   - Related identifier: `https://github.com/benchmarkg/benchmarks`, "Is supplemented by"; and the
     release tag's URL, "Is identical to"
   - Keywords: AI benchmarks, evaluation, benchmark catalogue, provenance, taxonomy
6. Publish. Add a row for the new version to the table above, with its version DOI.
7. The concept DOI does not change, so `CITATION.cff` needs no edit, but check that the concept DOI
   still resolves to the new version. A freshly published DOI can take a few hours to reach doi.org.
