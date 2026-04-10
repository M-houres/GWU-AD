# CNKI Dedup Ruleset From Current Sample Set

## Sample Basis

- Source folder: `C:\Users\m\Desktop\001项目\算法训练资料包\知网资料包`
- Current effective sample types:
  - CNKI full-text comparison reports
  - CNKI cited-report variants
  - matching source docx files where available
- Current directly inspected sample groups:
  - `X餐饮连锁公司营销措施现状优化研究`
  - `主题·共情·表达：基于《伊索寓言》整本书阅读的三年级学生心理健康教育途径探究`

## Current Value And Limits

This sample set is smaller than the VIP dedup pool, so it is not yet enough to build a stable CNKI dedup benchmark.

It is still useful for two things:

1. extract CNKI-style duplicate-risk sentence skeletons
2. define rewrite guardrails for `cnki_dedup`

Current limitation:

- the sample count is still too low for full quantitative promotion decisions

## Observed CNKI Dedup Traits

### 1. Policy / standard opening blocks are easy to collide

In the education sample, the main repeated fragment is concentrated in the opening block that combines:

1. curriculum-standard quotation
2. explanation of whole-book reading importance
3. generic teaching-value statement

This kind of paragraph is short, standard, and highly reusable across papers, so even when the overall copy ratio is low, CNKI still flags it clearly.

### 2. Literature review and theory summaries are the main risk zone

In the restaurant-marketing sample, the highest chapter-level risk is not the company diagnosis section itself.

The main risk sits in:

1. `绪论`
2. `相关概念、理论基础`

This suggests CNKI dedup risk often comes from:

1. stock theory definitions
2. standard model introductions
3. literature-review compression blocks

### 3. Enumerative definition chains are unstable

Several flagged fragments use the same pattern:

1. define a concept
2. list several dimensions or characteristics
3. add one sentence about practical significance

Examples include:

1. restaurant-chain feature lists
2. SERVQUAL dimension summaries
3. whole-book reading task-group explanations

These chains are academically correct, but the sentence skeleton is often too standard.

### 4. Low overall ratio does not mean low structural risk

The current CNKI samples show very low total duplication:

1. `X餐饮连锁公司营销措施现状优化研究`: `总文字复制比 1.3%`
2. `主题·共情·表达...`: `总文字复制比 2.4%`

But the repeated fragments are still structurally concentrated.

This matters because the CNKI package should not chase random word changes. It should target the small number of highly reusable academic skeletons that CNKI repeatedly catches.

## Stable Red-Flag Skeletons

The current CNKI dedup samples repeatedly point to these high-risk structures:

1. `课程标准 / 新课标` opening sentence plus direct teaching-value explanation
2. `某理论是...基础理论 / 经典框架` style theory-definition block
3. `包括A、B、C、D` style dimension enumeration
4. `现状 - 问题 - 对策` bridge sentence in abstract literature-review tone
5. generic concept explanation paragraphs that can fit many papers with only subject words changed

## Rewrite Direction That Looks Useful

For the built-in CNKI `dedup` package, the more useful direction is:

1. break the fixed opening skeleton rather than only changing a few nouns
2. split dense theory-summary chains into more article-specific explanation
3. convert stock enumeration into more task-led or case-led expression
4. keep standards, theory names, and citations intact, but rebuild the sentence order around them
5. reduce direct template reuse in `绪论 / 理论基础 / 教学价值` paragraphs

## What To Avoid

The current CNKI samples also make it clear what not to do:

1. do not rewrite standards, policy names, model names, or cited titles incorrectly
2. do not delete theory support just to lower duplication
3. do not replace academic explanation with vague filler
4. do not treat low duplication samples as proof that the package can already generalize

## Package Strategy

The practical strategy for `cnki_dedup` should be:

1. detect CNKI-style reused skeletons in opening, literature-review, and theory paragraphs
2. protect theory names, entities, citations, and numbers
3. rewrite structure first, then do limited phrase replacement
4. clean the final text to keep academic tone and logical continuity

## Intended Output Profile

- Platform: `cnki`
- Function type: `dedup`
- Goal: reduce CNKI-style duplicate-risk skeletons while preserving theory correctness and academic readability
- Priority: fix structurally reusable introduction / theory blocks, not random low-risk wording
