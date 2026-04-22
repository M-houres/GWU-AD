# Strategy Asset Data

This directory stores structured asset data used by the strategy data foundation work.

Current files:

- `dedup_positive_references_v1.jsonl`
- `strict_benchmark_samples_v1.jsonl`
- `synthetic_negative_samples_v1.jsonl`
- `weak_supervised_pairs_v1.jsonl`
- `platform_signal_reports_v1.jsonl`
- `positive_few_shot_pairs_v1.jsonl`

Rules:

1. Records are slot-aware.
2. Records must declare platform, scenario, and mode scope.
3. External sample files may point to absolute local paths when the source corpus lives outside the repo.
4. `positive_few_shot_pairs_v1.jsonl` is only for rewrite paragraph pairs.
5. `dedup_positive_references_v1.jsonl` is only for single-sided dedup final-text references, not original-vs-rewrite pairs.
