# VIP Dedup Ruleset From Multi-Version Reports

## Sample Basis

- Source folder: `C:\Users\m\Desktop\001项目\算法训练资料包\维普资料包`
- Material type: bundled VIP report exports with comparison HTML, segment comparison HTML, and concise PDF reports
- High-value feature: several papers appear in two or three versions, which makes it possible to compare rewrite attempts against changed report outcomes

## Why These Samples Matter

The useful target is not the full VIP scoring formula. The useful target is the stable shape of the red flagged fragments and the rewrite moves that actually reduce those fragments.

One repeated title group already showed different outcomes across versions:

- `华英公司营运资金管理现状及优化对策研究`
- Version A: `复写率 15.06%`
- Version B: `复写率 27.33%`
- Version C: `复写率 30.91%`

This means the package should optimize for `复写率` and fragment structure, not just produce superficial word substitutions.

## Stable Red-Flag Traits

These traits appeared repeatedly in the VIP samples:

1. Thesis-frame sentences with `对...进行研究` plus `从...方面进行分析`.
2. Three-step management templates like `分析现状 - 发现问题 - 解决问题`.
3. Stock problem-solution phrases such as `提出相应的解决对策` and `提高管理水平`.
4. Macro industry opening paragraphs with repeated national scale statistics.
5. Case fact paragraphs that copy a full location plus area plus project-content chain.
6. BIM and management application paragraphs built from `通过...提高...` style benefit lists.

## Rewrite Direction That Looks Useful

The rewrite direction that seems useful for VIP-style dedup is:

1. Break the stock thesis frame and replace it with a more task-led structure.
2. Split long multi-comma chains so the copied fragment is not preserved as one intact block.
3. Rebuild fact paragraphs by changing clause order while keeping entities and numbers intact.
4. Replace generic benefit claims with narrower action-result phrasing.
5. Preserve citations, entities, and domain terms instead of forcing noisy synonym swaps.

## What To Avoid

The sample set also showed low-quality rewrite behavior that should not be copied:

- mechanical synonym replacement
- awkward phrasing such as doubled modal verbs
- filler expansion that changes surface form but keeps the same sentence skeleton

## Package Strategy

For the built-in VIP `dedup` package, the practical strategy is:

1. detect VIP-style high-risk sentence skeletons
2. apply structural rewrites before simple phrase replacements
3. reorder long clauses when the sentence still keeps the original copied chain
4. estimate post-rewrite risk using the same skeleton markers that the package is trying to break

## Intended Output Profile

- Platform: `vip`
- Function type: `dedup`
- Goal: lower VIP-style duplicate-risk skeletons without damaging domain facts
- Priority: reduce `复写率`-like text patterns, not quotes or professional terms
