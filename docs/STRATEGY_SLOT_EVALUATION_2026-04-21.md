# 八槽位策略评估

更新日期：2026-04-21

## 1. 总体结论

- 槽位总数：8
- `strong`：5
- `moderate`：3
- `weak`：0

## 2. 槽位明细

### 2.1 `cnki.rewrite.algorithm`
- 类型：`algorithm_runtime`
- 状态：`strong`
- 样本数：`10`
- 合格数：`8`
- 合格率：`0.80`
- style_aligned：`10`
- meaningful_change_count：`10`
- warning_count：`2`
- high_quality_count：`8`

### 2.2 `cnki.rewrite.llm`
- 类型：`llm_prompt_readiness`
- 状态：`strong`
- 样本数：`4`
- 合格数：`4`
- 合格率：`1.00`
- positive_example_count：`3`
- negative_example_count：`2`
- disciplines：`engineering_it_patent,finance_management,law_policy`

### 2.3 `cnki.dedup.algorithm`
- 类型：`algorithm_runtime`
- 状态：`moderate`
- 样本数：`18`
- 合格数：`13`
- 合格率：`0.72`
- variation_ok_count：`17`
- style_aligned：`18`
- warning_count：`5`
- high_quality_count：`13`

### 2.4 `cnki.dedup.llm`
- 类型：`llm_prompt_readiness`
- 状态：`strong`
- 样本数：`4`
- 合格数：`4`
- 合格率：`1.00`
- positive_example_count：`3`
- negative_example_count：`2`
- disciplines：`engineering_it_patent,finance_management,law_policy`

### 2.5 `vip.rewrite.algorithm`
- 类型：`algorithm_runtime`
- 状态：`moderate`
- 样本数：`6`
- 合格数：`4`
- 合格率：`0.67`
- style_aligned：`6`
- meaningful_change_count：`6`
- warning_count：`2`
- high_quality_count：`4`

### 2.6 `vip.rewrite.llm`
- 类型：`llm_prompt_readiness`
- 状态：`strong`
- 样本数：`4`
- 合格数：`4`
- 合格率：`1.00`
- positive_example_count：`3`
- negative_example_count：`2`
- disciplines：`finance_management,law_policy,medicine_public_health`

### 2.7 `vip.dedup.algorithm`
- 类型：`algorithm_runtime`
- 状态：`moderate`
- 样本数：`14`
- 合格数：`9`
- 合格率：`0.64`
- variation_ok_count：`10`
- style_aligned：`14`
- warning_count：`5`
- high_quality_count：`9`

### 2.8 `vip.dedup.llm`
- 类型：`llm_prompt_readiness`
- 状态：`strong`
- 样本数：`4`
- 合格数：`4`
- 合格率：`1.00`
- positive_example_count：`3`
- negative_example_count：`2`
- disciplines：`engineering_it_patent,finance_management,law_policy`
