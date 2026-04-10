# AIGC Detect Result Evaluation Framework

See also:

- `docs/AIGC_ALGO_TRAINING_MEMORY.md`

That document records the current benchmark status, current CNKI evaluation snapshot,
data collection requirements for CNKI / VIP / PaperPass, and the operational workflow
for future algorithm training.

## 1. Goal

This framework evaluates `AIGC检测` algorithm packages by one core objective:

For the same document and the same target platform, our simulated detection result should be as close as possible to the target platform's actual detection result.

The target here is **result consistency**, not report page style consistency.

This means:

1. If the target platform detects `28%`, our simulated result should ideally also be close to `28%`.
2. If the target platform marks some content as `重度 / 中度 / 轻度疑似`, our simulated result should match that structure as closely as possible.
3. If the target platform highlights certain paragraphs or spans, our simulated high-risk paragraphs and highlighted spans should overlap as much as possible.
4. The report template may continue using the project's current report template. Report style is outside the scope of this evaluation framework.

## 2. Scope

This framework currently applies to:

- `CNKI AIGC检测`
- `VIP AIGC检测`
- `PaperPass AIGC检测`

This framework does **not** directly evaluate:

- PDF visual style
- report layout similarity
- payment flow
- front-end presentation polish

## 3. North-Star Definition

For AIGC detection, the best state is:

1. The full-text overall score is close to the target platform.
2. The heavy / medium / light suspected text ratios are close to the target platform.
3. The risky paragraphs are largely the same paragraphs as the target platform.
4. The highlighted suspicious spans substantially overlap the target platform's highlighted spans.
5. Repeated runs on the same text remain stable and deterministic.

## 4. Required Reference Data

No quantitative evaluation is reliable without a normalized reference set.

Each benchmark sample should include:

1. Source text
2. Target platform
3. Target platform full-text result
4. Target platform paragraph-level judgment
5. Target platform highlighted suspicious spans
6. Manually checked normalized annotation

Recommended normalized sample schema:

```json
{
  "sample_id": "cnki_doc_001",
  "platform": "cnki",
  "source_text": "...",
  "reference": {
    "total_score_pct": 28.0,
    "band_text_ratio": {
      "high": 9.5,
      "medium": 11.0,
      "low": 7.5,
      "clean": 72.0
    },
    "paragraphs": [
      {
        "index": 1,
        "score_pct": 12.0,
        "label": "low",
        "spans": [
          { "start": 15, "end": 38, "label": "low" }
        ]
      },
      {
        "index": 2,
        "score_pct": 66.0,
        "label": "high",
        "spans": [
          { "start": 5, "end": 44, "label": "high" },
          { "start": 61, "end": 88, "label": "medium" }
        ]
      }
    ]
  }
}
```

## 5. Output Requirements For Our Algorithm

To be evaluated correctly, our result output must be normalizable to the same structure.

At minimum, the algorithm / engine result must be able to provide:

1. `score_pct`
2. heavy / medium / low / clean text ratios
3. paragraph-level risk labels or scores
4. suspicious span positions or a structure that can be converted into span positions

Current project fields already cover part of this:

- `score_pct`
- `fragment_distribution`
- `paragraph_details`
- `risk_paragraphs`
- `suspicious_segments`

However, if we want strict highlight alignment scoring, the long-term target should be to add **explicit span offsets**:

```json
{
  "paragraph_index": 3,
  "start": 42,
  "end": 96,
  "label": "high",
  "score_pct": 78.0
}
```

Without offsets, "highlight consistency" can only be evaluated approximately by text overlap, not precisely by character range overlap.

## 6. Evaluation Dimensions

Total score: `100`

### 6.1 Full-Text Score Consistency: 25 points

Measures how close our overall AIGC detection percentage is to the target platform.

Formula:

```text
diff_total = abs(our_total_score_pct - ref_total_score_pct)
score_total = max(0, 100 * (1 - diff_total / 20))
weighted_total = score_total * 0.25
```

Interpretation:

- difference `0` => full points
- difference `10` => half points
- difference `20 or more` => `0`

### 6.2 Risk Structure Consistency: 20 points

Measures whether the heavy / medium / light / clean text ratio structure matches the target platform.

For each band:

```text
score_band_x = max(0, 100 * (1 - abs(our_ratio_x - ref_ratio_x) / 15))
```

Then:

```text
score_band = average(score_band_high, score_band_medium, score_band_low, score_band_clean)
weighted_band = score_band * 0.20
```

This dimension is important because two algorithms may both output `28%`, but one may put almost all suspicion in the wrong risk band.

### 6.3 Paragraph Alignment: 25 points

Measures whether we mark the same paragraphs as risky.

This dimension contains three sub-metrics:

1. `Risk paragraph recall`
2. `Risk paragraph precision`
3. `Paragraph severity consistency`

Recommended formula:

```text
paragraph_risk_f1 = F1(binary risky paragraph set)
paragraph_label_macro_f1 = MacroF1(high, medium, low, clean)
topk_ndcg = NDCG@5 on paragraph risk ranking

score_paragraph = 0.5 * paragraph_risk_f1
                + 0.3 * paragraph_label_macro_f1
                + 0.2 * topk_ndcg
weighted_paragraph = score_paragraph * 100 * 0.25
```

Why this matters:

- A package may have a close full-text percentage, but if it flags the wrong paragraphs, it is not actually simulating the target platform well.

### 6.4 Highlight Span Alignment: 25 points

This is the most important structural metric after total score.

Measures whether the exact suspicious text spans overlap with the target platform.

Recommended sub-metrics:

1. `Span overlap F1`
2. `Severity match rate`

Definitions:

- `TP`: overlapping suspicious characters
- `FP`: characters highlighted by us but not highlighted by reference
- `FN`: reference-highlighted characters missed by us

Formula:

```text
span_f1 = 2 * TP / (2 * TP + FP + FN)
severity_match = overlap_chars_with_same_label / max(overlap_chars, 1)

score_span = 0.7 * span_f1 + 0.3 * severity_match
weighted_span = score_span * 100 * 0.25
```

If offset-based spans are not yet available, a temporary approximation may be used:

1. paragraph-level snippet matching
2. sentence-level overlap matching
3. normalized text substring overlap

But the long-term standard must be offset-based scoring.

### 6.5 Stability And Determinism: 5 points

The same text should produce the same result repeatedly.

Recommended checks:

1. Run the same sample `3` times
2. Compare total score variance
3. Compare highlighted paragraph set variance
4. Compare highlighted span set variance

Formula:

```text
score_stability = 100
  if score variance <= 0.5
  and paragraph set unchanged
  and span set unchanged
else reduced proportionally
```

Weighted:

```text
weighted_stability = score_stability * 0.05
```

## 7. Final Score

```text
final_score =
  weighted_total
  + weighted_band
  + weighted_paragraph
  + weighted_span
  + weighted_stability
```

Final score range: `0 - 100`

## 8. Hard Gates

A package may not be promoted if any of the following gates fail, even if its total score is high.

### 8.1 Full-Text Gate

- average full-text score difference must be `<= 10`

### 8.2 Risk Structure Gate

- heavy + medium suspected text ratio difference must be `<= 12`

### 8.3 Paragraph Gate

- risky paragraph recall must be `>= 0.75`

### 8.4 Highlight Gate

- span overlap F1 must be `>= 0.65`
- severity match rate must be `>= 0.75`

### 8.5 Stability Gate

- repeated-run score variance must be `<= 1.0`

If any hard gate fails:

- the package cannot replace the current active package
- the package may only stay in calibration / experimental status

## 9. Grade Definition

### S

- `final_score >= 90`
- no hard gate failures
- full-text difference usually `<= 3`
- highlight span overlap already very strong

### A

- `85 <= final_score < 90`
- no hard gate failures
- can be considered production-ready

### B

- `75 <= final_score < 85`
- usable, but still not sufficiently close to target platform

### C

- `60 <= final_score < 75`
- partial simulation value only
- not suitable as a mainline promoted package

### D

- `final_score < 60`
- weak fit to target platform
- must not be used as the main promoted package

## 10. Upgrade Rule

An upgraded package may replace the active package only if:

1. `final_score >= 85`
2. no hard gate fails
3. compared with the current active package:
   - total score improves by at least `3` points, or
   - at least `2` core dimensions improve and no core dimension drops by more than `2` points

Core dimensions:

- full-text score consistency
- risk structure consistency
- paragraph alignment
- highlight span alignment

## 11. Recommended Benchmark Set Construction

Per platform, the locked benchmark set should include at least:

1. `20` low-risk documents
2. `20` medium-risk documents
3. `20` high-risk documents

And should cover:

1. abstract-heavy academic papers
2. intro-heavy papers
3. empirical papers with questionnaires / tables
4. short papers
5. long papers
6. bilingual abstract papers
7. rewritten papers with mixed human and generated content

Recommended split:

- calibration set: used for tuning
- locked benchmark set: used for promotion decisions
- challenge set: used for regression and adversarial cases

## 12. Recommended Operational Workflow

For each new AIGC detect package version:

1. Run on the calibration set
2. Generate normalized result JSON
3. Compute the five dimension scores
4. Compare against the current active package
5. If hard gates pass, run locked benchmark
6. Only after benchmark pass may the package enter active deployment

## 13. Practical Meaning For Current Project

For this project, the evaluation target is:

1. not "our report looks like CNKI / VIP / PaperPass"
2. but "our result behaves like CNKI / VIP / PaperPass"

So the project's current report template can remain unchanged.

What must become closer to target platforms is:

1. the full-text percentage
2. the heavy / medium / light suspicious structure
3. the paragraph-level judgment
4. the highlighted suspicious spans

## 14. Next Engineering Step

To make this framework executable rather than descriptive, the next implementation step should be:

1. build a normalized benchmark dataset for target platform reports
2. extend detection result data to include explicit paragraph / span offsets
3. add an offline evaluator that outputs:
   - final score
   - dimension scores
   - hard-gate results
   - regression comparison against previous package version

Until this is done, package evaluation remains only partially quantitative.
