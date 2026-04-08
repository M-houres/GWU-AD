# CNKI Rewrite Ruleset From 3 Sample Pairs

## Sample Basis

- Source folder: `C:\Users\m\Desktop\学术润色`
- Corpus: 3 pairs of "before / after" academic polishing drafts
- Coverage:
  - Pair 1: AI-assisted math homework design
  - Pair 2: Ecological civilization education in primary science
  - Pair 3: Labor education teacher team construction

## Observed Stable Traits

These traits appeared repeatedly across the three pairs:

1. Dense academic expressions were expanded into clearer explanatory clauses.
2. Hidden logical relations were made explicit with cause / purpose / scope markers.
3. Abstract nominal phrases were converted into verb-led expressions.
4. Case paragraphs were rewritten into a more narrative and reader-oriented form.
5. The rewritten text usually became slightly longer, but not structurally different.

Approximate corpus-level observations after plain-text extraction:

- Changed paragraphs: 39 / 101
- Text length increase: about 5.7% on average
- Frequent insertions: `进行`, `能够`, `借助`, `关键`, `方面`, `模式`
- Frequent reductions: overly dense uses of `体系`, `围绕`, `在于`, `具备`

## What Was Filtered Out

The raw "after" samples also contained some noisy shifts that are not suitable for a controllable CNKI-style package:

- Overly colloquial wording such as `跟着`, `没办法`, `好多`, `才行`
- Excessive filler that lengthens the sentence without adding meaning
- Some local rewrites that improve "human feel" but weaken academic tone

The package keeps the stable rewrite direction, but filters out these noisy signals.

## Systematized Rewrite Method

### 1. Compression Decomposition

Turn compressed academic noun phrases into readable predicate structures.

Examples:

- `构建评价体系` -> `建立评价框架`
- `推进机制建设` -> `推动相关机制建设`
- `有机融入课堂` -> `合理融入课堂`

### 2. Logic Explicitness

When the original sentence hides the relation, expose it with stable connectives.

Typical expansions:

- `AI诊断显示` -> `通过AI诊断可以看出`
- `这对教师提出了要求` -> `这也对教师提出了新的要求`
- `从三个维度` -> `从这三个维度`

### 3. Verb-Led Rewriting

Reduce static, stacked nominalizations and prefer action-bearing predicates.

Examples:

- `系统梳理` -> `全面梳理`
- `深入分析` -> `详细分析`
- `有赖于` -> `依靠`

### 4. Case Paragraph Normalization

For sample / case paragraphs, keep the heading but rewrite the body into:

- case label
- explicit diagnostic finding
- design response
- educational purpose

### 5. Scope / Purpose Completion

Add moderate scope markers such as:

- `在...方面`
- `以此...`
- `从而...`

Only add them when the original sentence already implies that relation.

### 6. Style Guardrails

The package should:

- preserve academic entities, policy names, quoted textbook titles, and subject terminology
- avoid spoken slang
- avoid aggressive synonym replacement that changes meaning
- prefer moderate expansion over full paraphrase

## Package Strategy

The algorithm package implements a four-stage pipeline:

1. Normalize whitespace and paragraph boundaries.
2. Apply ordered phrase replacements derived from the samples.
3. Apply structural regex rules for recurring CNKI-style rewrite patterns.
4. Run a style guard pass to remove colloquial noise and estimate risk-score reduction.

## Intended Output Profile

- Platform: `cnki`
- Function type: `rewrite`
- Tone: explanatory, explicit, still academic
- Goal: reduce template-like compression while keeping subject matter intact
