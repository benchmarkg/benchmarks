"""The AI layer's self-evaluation: the pooling grading harness behind `bench eval` (P6-S3-T09; 11-ai-features.md S7,
05 S3 and S9).

    golden.py          evals/golden/ as the harness reads it, checked by scripts/check_golden_composition.py; --holdout
    retrieval.py       the retrieval configurations and the TREC-style pool (lexical_runs.mjs runs the site's BM25 leg)
    metrics.py         Recall@20, nDCG@10, must-include violations, macro-F1, over-constraint, the enum canary and the
                       correct-abstention rate, as published rates
    stats.py           the Wilson interval, by hand, and the pass / fail / inconclusive verdict against 11 S7's bars
    batch.py           the Batch API run: model ids from config/ai-models.yaml, the request shape, the transport; it
                       refuses without ANTHROPIC_API_KEY and while no prompt exists to evaluate
    harness.py         the run, the results file (evals/results/<date>-<commit>.json) and the report

P6-S6-T03 adds judge.py (the LLM-as-judge pass and judge-human agreement), and P6-S6-T04 scripts/check_eval_gates.py,
which reads a results file and blocks a release on the hard zeros.
"""
