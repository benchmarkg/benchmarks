# HELM bucket fixture (synthetic)

The JSON-API responses `ingest/adapters/helm.py` asks `gs://crfm-helm-public` for, written by `make_fixture.py`
and compared byte for byte by `tests/ingest/test_helm.py`.

**Why synthetic.** The bucket's data states no licence (06 S3.5), so none of it may be committed; the adapter
was checked against the live bucket on 2026-10-10 (18 suites with releases, 29,465 run specs, 175 scenario
candidates, every one through the discovery gates).

**What is real.** The shape: listing and media URLs; objects with size and generation as strings, a base64 MD5
and `contentEncoding: gzip` where HELM stores gzipped JSON; the `benchmark_output/releases/v<x.y.z>/` layout; and
three of the five `adapter_spec` key sets the adapter declares (26, 27 and 28 keys) plus `classic`'s 21.

**What is invented.** Every scenario, model, deployment, prompt and number. `PROMPT` in the generator is the
string the tests check never reaches a draft.
