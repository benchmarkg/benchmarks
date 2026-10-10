# Shallow-clone fixture: lm-evaluation-harness and MTEB results

Two pruned copies of the commits `ingest/adapters/github_clones.py` pins. `make_fixture.py` writes them from
the clones a live run leaves under `ingest/raw/clones/`; `manifest.json` records the commit, the licence and
the counts of the full tree at the pin. The test builds a one-commit git repository from each directory and
runs the adapter's own object-store reader over it, so the fixture goes through the same code a live clone
does; every URL a draft carries cites the pinned commit the manifest names, not that repository's own id.

**What is real.** Every file is the pinned commit's blob, byte for byte. Nothing is edited.

**What is pruned, and by which rule.**

`lm-evaluation-harness/` (EleutherAI/lm-evaluation-harness at `d6de816`, MIT):
- `LICENSE.md` and `lm_eval/tasks/__init__.py`, the two files the layout check reads;
- for each of the 221 task directories, its shortest-path task config that loads, with every file it
  includes (`lm_eval/tasks/benchmarks/` holds groups only, so its shortest group config);
- `arc_easy`, `gsm8k`, `hellaswag` and `mmlu_anatomy`, which the tests read by name: a literal-only config,
  a config with sampling and few-shot settings, one with a `!function`, and one that includes a template.

So the fixture holds all 221 directories, 220 of them with a task config, and 233 task configs in all, every
one of which parses, against the pin's 13,125; the test asserts the done_when's 200 directories on it.

`mteb-results/` (embeddings-benchmark/results at `b64a5db`, CC0-1.0):
- `LICENSE`, and the one file the pin keeps at the top of `results/` (`rename_and_move_over.py`);
- the first twelve models in sorted order, each at its first revision: `model_meta.json` and the first two
  result files of at most 32 kB;
- the first result under an `experiments/<variant>/` directory, the deeper of the two layouts (its model,
  `codefuse-ai/F2LLM-v2-80M`, is the thirteenth).

The adapter never reads an MTEB result's contents; the files are real so the layout is.
