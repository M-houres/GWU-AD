# 算法报告首轮八槽位编目

更新日期：2026-04-21

资料根目录：`C:\Users\m\Desktop\算法报告`

## 1. 目的

对现有 `算法报告` 资料做第一轮编目，明确：

1. 来源目录
2. 对应平台
3. 对应场景
4. 对应模式适用范围
5. 样本层级
6. 建议用途

本清单用于后续资产入库，不代表已经完成全文抽取。

## 2. 编目规则

### 2.1 平台

- `知网` -> `cnki`
- `维普` -> `vip`

### 2.2 场景

- `降AIGC率` / `AIGC` -> `rewrite`
- `降重复率` / `查重` -> `dedup`
- `AIGC检测` -> `aigc_detect_signal`

### 2.3 模式适用范围

- `algorithm_primary`
  - 用于规则、黑名单、固定搭配保护、validator
- `llm_secondary`
  - 用于 prompt、few-shot、负样本、输出约束
- `shared_signal`
  - 只用于平台信号，不直接喂改写策略

### 2.4 样本层级

- `A`
  - 严格评分样本
- `B`
  - 弱监督样本
- `C`
  - 规则素材

## 3. 顶层目录映射

| 来源目录 | 平台 | 场景 | 模式适用范围 | 层级 | 当前判断 |
| --- | --- | --- | --- | --- | --- |
| `123` | `cnki` | `rewrite` | `algorithm_primary + llm_secondary` | `A` | 已包含原文、改后文、检测报告，适合做知网降AIGC严格样本 |
| `知网降AIGC率` | `cnki` | `rewrite` | `algorithm_primary + llm_secondary` | `A/B` | 润色前后成对价值高，应优先抽取成正样本对 |
| `知网AIGC` | `cnki` | `rewrite` | `algorithm_primary + llm_secondary` | `C` | 样例型规则素材，适合提炼局部句式与坏样本 |
| `知网AIGC检测` | `cnki` | `aigc_detect_signal` | `shared_signal` | `A/B` | 适合抽平台高风险段、报告样式、风险分布 |
| `知网降重复率` | `cnki` | `dedup` | `algorithm_primary + llm_secondary` | `B` | 以查重报告为主，适合做平台信号和局部规则素材 |
| `维普降AIGC率` | `vip` | `rewrite` | `algorithm_primary + llm_secondary` | `A/B` | 既有原文又有改后稿，适合提炼维普降AIGC正样本 |
| `维普AIGC` | `vip` | `rewrite` | `algorithm_primary + llm_secondary` | `C` | 样例型资料，适合做提示词和规则池 |
| `维普AIGC检测` | `vip` | `aigc_detect_signal` | `shared_signal` | `A/B` | 适合抽维普高风险段和平台偏好 |
| `维普降重复率` | `vip` | `dedup` | `algorithm_primary + llm_secondary` | `B/C` | 大量 zip，覆盖多专业，适合做泛化资产和候选 benchmark 池 |
| `新建文件夹` | `mixed` | `meta_design` | `shared_signal` | `C` | 设计报告与说明文档，适合做策略设计参考，不直接入评分集 |

## 4. 优先处理目录

### 4.1 第一优先级

1. `123`
2. `知网降AIGC率`
3. `维普降AIGC率`
4. `知网降重复率`

原因：

1. 样本对应关系最清晰
2. 与当前策略升级目标最直接相关
3. 可快速转成正样本对与回归集

### 4.2 第二优先级

1. `知网AIGC检测`
2. `维普AIGC检测`
3. `维普降重复率`

原因：

1. 平台信号价值高
2. 专业覆盖面广
3. 适合提炼平台偏好与泛化风险特征

### 4.3 第三优先级

1. `知网AIGC`
2. `维普AIGC`
3. `新建文件夹`

原因：

1. 更偏样例和设计说明
2. 适合补 prompt、few-shot、坏样本规则
3. 不应先于严格样本进入 benchmark

## 5. 八槽位入库建议

### 5.1 `cnki.rewrite.algorithm`

主资料：

1. `123`
2. `知网降AIGC率`
3. `知网AIGC`
4. `知网AIGC检测`

沉淀重点：

1. 正样本改写对
2. 坏样本门禁
3. 固定搭配保护
4. 平台高风险句式

### 5.2 `cnki.rewrite.llm`

主资料：

1. `123`
2. `知网降AIGC率`
3. `知网AIGC`

沉淀重点：

1. prompt few-shot
2. 正负样例
3. 输出禁止项

### 5.3 `cnki.dedup.algorithm`

主资料：

1. `知网降重复率`
2. `知网AIGC检测`
3. 相关知网降AIGC样本中的结构重写段

沉淀重点：

1. 定义句重构
2. 连续相似句骨架重写
3. 术语与数字保护

### 5.4 `cnki.dedup.llm`

主资料：

1. `知网降重复率`
2. `知网降AIGC率`

沉淀重点：

1. 深层结构改写示例
2. 负样例约束
3. 算法 fallback 触发条件

### 5.5 `vip.rewrite.algorithm`

主资料：

1. `维普降AIGC率`
2. `维普AIGC`
3. `维普AIGC检测`

沉淀重点：

1. 自然学术表达迁移
2. 教育类与应用研究类表达资产
3. 维普平台高风险句式

### 5.6 `vip.rewrite.llm`

主资料：

1. `维普降AIGC率`
2. `维普AIGC`

沉淀重点：

1. few-shot
2. 风格约束
3. 局部学术表达替换样例

### 5.7 `vip.dedup.algorithm`

主资料：

1. `维普降重复率`

沉淀重点：

1. 跨专业降重句式
2. 通用结构替换
3. 低风险局部改写资产

### 5.8 `vip.dedup.llm`

主资料：

1. `维普降重复率`
2. `维普降AIGC率`

沉淀重点：

1. 跨专业 few-shot
2. 降重深改示例
3. 坏样本负提示

## 6. 当前不建议直接混用的内容

1. 知网 AIGC 报告特征直接用于维普评分
2. 维普降重有效改写直接作为知网降AIGC优质改写
3. 降重复率样本直接当降AIGC正样本
4. 算法规则样本直接当 LLM few-shot
5. LLM 优秀输出直接当算法规则

## 7. 下一步抽取动作

### 7.1 第一轮

1. 抽取 `123`
2. 抽取 `知网降AIGC率`
3. 抽取 `维普降AIGC率`

产出：

1. 原文 / 改后文 pair 清单
2. 平台报告映射清单
3. 局部优质改写片段

### 7.2 第二轮

1. 抽取 `知网降重复率`
2. 抽取 `维普降重复率`

产出：

1. 查重高风险骨架
2. 定义句 / 综述句 / 结论句风险模板
3. 候选泛化资产

### 7.3 第三轮

1. 抽取 `知网AIGC`
2. 抽取 `维普AIGC`
3. 抽取 `新建文件夹`

产出：

1. few-shot 素材
2. 负样例
3. 设计约束清单

## 8. 说明

本清单只是第一轮“目录级编目”，还未进入全文抽取与逐条打标签阶段。

后续应继续落：

1. 样本级 `jsonl` 编目
2. 文件对照关系表
3. 报告字段抽取脚本
4. 八槽位 benchmark 清单
