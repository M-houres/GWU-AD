# 2026-04-10 CNKI AIGC Round 2 Summary

## Scope

This round continued CNKI `aigc_detect` training on top of the earlier `clean/front_matter/human_case_relief` work.

Files touched:

- `backend/app/services/builtin_algo_packages.py`
- `backend/app/services/processing_engine.py`
- `backend/tests/test_cnki_sampled_builtin_packages.py`
- `backend/tests/test_algo_packages.py`

## What Changed

### 1. CNKI builtin package bumped to `v1.8.0`

Main adjustments:

- lowered `human_case_relief` saturation and subtraction strength
- strengthened `rhetorical_signal`
- kept `rough_edit_relief`, but changed it from a broad suppressor into a more targeted rough-edit discriminator
- added document-level `rough_edit_relief_total` so rough human-edited versions are less likely to be overestimated

### 2. CNKI engine result got an algo-package anchor

In `processing_engine.py`, CNKI final score now respects the specialized package result more carefully:

- if the package says `clean` and score is `<= 12%`, keep a low-risk ceiling
- if the package says `low` and the package score is already clearly above the clean band, prevent generic calibration from collapsing it unrealistically

This was added because the generic outer calibration was still flattening:

- `222642`: package `18.81%`, engine was previously compressed to `8.82%`
- `213030`: package `18.74%`, engine was previously compressed to `8.66%`

## Key Sample Tracking

Reference group:

- `cnki_aigc_20260409_222642_e1381b0f` -> official `27.6%`
- `cnki_aigc_20260409_223855_674b6e0a` -> official `0.0%`
- `cnki_aigc_20260409_213030_b7832163` -> official `32.5%`

Current package output:

- `222642` -> `18.81%`
- `223855` -> `10.99%`
- `213030` -> `18.74%`

Current engine output:

- `222642` -> `23.2%`
- `223855` -> `8.04%`
- `213030` -> `22.8%`

This means the three-version contrast is now at least directionally correct again:

- lowest stays `223855`
- higher-risk versions `222642 / 213030` are no longer flattened into the same clean bucket

## Offline Benchmark Result

Candidate file:

- `logs/benchmarks/cnki_aigc_current_engine_eval.v2.json`

Evaluation command:

```bash
python scripts/evaluate_aigc_detect.py --reference logs/benchmarks/cnki_aigc_reference_samples.v1.json --candidate logs/benchmarks/cnki_aigc_current_engine_eval.v2.json
```

Latest result:

- `final_score = 37.76`
- `grade = D`

Comparison:

- earlier engine-only round: `25.16`
- after package rebalance but before CNKI anchor protection: `30.04`
- current round: `37.76`

Improvement achieved this round:

- `full_text_score_consistency` hard gate now passes for all 4 samples
- the `0%` sample no longer gets dragged into the `20%+` area
- same-topic multi-version differentiation recovered to a usable level

## Remaining Bottlenecks

The core problem is no longer total-score collapse. It is now structure alignment:

1. `risk_structure_consistency` still fails
2. `paragraph_alignment` still fails
3. `highlight_span_alignment` is still very low

Observed issue:

- official risky area for `222642` is mainly `14-21`
- candidate risky indexes are still biased toward `1 / 4 / 5 / 7 / 13 / 19 / 21 / 24 / 25`
- shared “safe but polished” paragraphs are still taking score away from the truly highlighted official zone

## Next Focus

Priority for the next CNKI round:

1. train directly against official highlighted paragraph block `14-21` for the three-version sample group
2. reduce weight on shared “education logic / portability / generic polished summary” paragraphs
3. increase discrimination for the exact official high-risk zone rather than only improving whole-text score
4. continue collecting CNKI AIGC samples in the `20%-40%` range plus same-text multi-version report pairs

## Verification

Commands run in this round:

```bash
python -m pytest tests/test_cnki_sampled_builtin_packages.py -k "aigc_package_emphasizes_abstract_intro_patterns or separates_polished_and_rough_practice_variants"
python -m pytest tests/test_algo_packages.py -k "builtin_aigc_package_returns_full_text_payload"
python -m pytest tests/test_processing_engine_results.py -k "wrapped_line or clean_label or weak_suspicious_segment or front_matter or human_case_relief"
python scripts/evaluate_aigc_detect.py --reference logs/benchmarks/cnki_aigc_reference_samples.v1.json --candidate logs/benchmarks/cnki_aigc_current_engine_eval.v2.json
```
