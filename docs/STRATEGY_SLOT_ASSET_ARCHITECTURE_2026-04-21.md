# 平台-场景-模式八槽位资产架构

更新日期：2026-04-21

## 1. 目标

建立统一但不混用的策略资产体系，用于同时增强：

- 平台
  - `cnki`
  - `vip`
- 场景
  - `rewrite`（降AIGC率）
  - `dedup`（降重复率）
- 模式
  - `algorithm`
  - `llm`

最终形成 `2 x 2 x 2 = 8` 个独立槽位。

## 2. 八槽位定义

### 2.1 槽位列表

1. `cnki.rewrite.algorithm`
2. `cnki.rewrite.llm`
3. `cnki.dedup.algorithm`
4. `cnki.dedup.llm`
5. `vip.rewrite.algorithm`
6. `vip.rewrite.llm`
7. `vip.dedup.algorithm`
8. `vip.dedup.llm`

### 2.2 铁律

任何资料进入资产池前，必须先打满以下标签：

1. `platform`
2. `scenario`
3. `mode_scope`

未打满标签的资料，不允许入库。

## 3. 不混用原则

### 3.1 严禁直接混用的内容

以下内容不得跨槽位直接复用：

1. 平台评分信号
2. 平台报告阈值理解
3. 平台高风险句式画像
4. 平台坏样本黑名单
5. 场景专属优质改写对
6. 模式专属 prompt / few-shot

### 3.2 允许共享的底座能力

以下内容允许共享，但只能作为“底座能力”，不得替代槽位资产：

1. `docx` 结构解析与格式保留
2. 引用、数字、术语保护框架
3. 通用病句与重复标点清洗
4. 机械连接词检测器
5. 统一评测与标签格式
6. 报告抽取、正文回抽、样本编目工具

## 4. 三层资产结构

### 4.1 第一层：共享底座

该层不带平台偏好，服务全部槽位。

包含：

1. `document_tools`
2. `text_safety_guards`
3. `term_protection_framework`
4. `format_preservation_tests`
5. `common_quality_validators`
6. `asset_catalog_schema`

### 4.2 第二层：槽位专属资产

每个槽位单独维护 5 类资产。

#### A. `positive_assets`

高质量正样本：

1. 原文 / 改后对
2. 有效局部句式重构
3. 有效段落重构
4. 有效报告前后对比

#### B. `negative_assets`

坏样本：

1. 机械连接词堆叠
2. 模板判断句
3. 术语拆坏
4. 固定搭配破坏
5. 结构切碎
6. 字数异常

#### C. `platform_signals`

平台信号：

1. 官方报告高风险段特征
2. 高风险区块分布
3. 平台特有“模板感”信号
4. 平台报告样式与字段

#### D. `algorithm_assets`

算法模式专用：

1. 黑名单
2. 白名单
3. 固定搭配保护
4. 局部改写规则
5. 段落类型规则
6. 输出门禁规则

#### E. `llm_assets`

LLM 模式专用：

1. 槽位专属 prompt
2. 正样例 few-shot
3. 负样例 few-shot
4. 输出禁止项
5. validator 与 fallback 约束

### 4.3 第三层：槽位评测集

每个槽位单独维护评测集，禁止混评。

每个评测集至少覆盖：

1. `effect`
2. `quality`
3. `safety`
4. `style`

## 5. 资料来源分流规则

### 5.1 本地真实资料

以 `C:\Users\m\Desktop\算法报告` 为主资料盘。

分流规则：

1. `知网降AIGC率`
   - 主入：`cnki.rewrite.algorithm`
   - 辅入：`cnki.rewrite.llm`
2. `知网降重复率`
   - 主入：`cnki.dedup.algorithm`
   - 辅入：`cnki.dedup.llm`
3. `维普降AIGC率`
   - 主入：`vip.rewrite.algorithm`
   - 辅入：`vip.rewrite.llm`
4. `维普降重复率`
   - 主入：`vip.dedup.algorithm`
   - 辅入：`vip.dedup.llm`
5. `知网AIGC检测`
   - 主入：`cnki.*.platform_signals`
6. `维普AIGC检测`
   - 主入：`vip.*.platform_signals`
7. `知网AIGC`
   - 主入：`cnki.rewrite.*.positive_assets`
8. `维普AIGC`
   - 主入：`vip.rewrite.*.positive_assets`

### 5.2 公开数据

公开数据只做“底座增强”和“泛化补充”，不直接当平台专属评分资产。

推荐用途：

1. `CSL`
   - 学术表达底座
2. `CLUE / CLUECorpus2020`
   - 通用中文表达底座
3. `PAWS / PAWS-X`
   - 结构改写底座
4. `MCTS`
   - 多参考自然改写底座
5. `C-ReD`
   - AIGC 对抗评测底座

### 5.3 合成数据

合成数据只能围绕某个槽位的已知问题构造。

必须带上：

1. `target_slot`
2. `error_type`
3. `severity`
4. `expected_action`

## 6. A/B/C 三层样本准入

### 6.1 A层：严格评分样本

要求：

1. 平台明确
2. 原文明确
3. 改后文明确
4. 报告明确
5. 版本对应关系明确

可用：

1. benchmark
2. 升级评分
3. 槽位回归集

### 6.2 B层：弱监督样本

要求：

1. 平台明确
2. 有报告或改后稿
3. 可抽出正文或片段
4. 但版本关系不完全干净

可用：

1. 规则提取
2. 风险片段抽取
3. prompt 补充
4. 候选 benchmark 池

### 6.3 C层：规则素材

要求：

1. 只有正文
2. 或只有报告
3. 或只有改写样例
4. 或样本对应关系不完整

可用：

1. 规则池
2. 坏样本池
3. 风格池
4. 禁止项池

## 7. 算法模式与 LLM 模式分工

### 7.1 `algorithm`

定位：

1. 默认生产主链
2. 可控
3. 可回归
4. 可审计

建设重点：

1. 术语保护
2. 固定搭配保护
3. 平台坏样本门禁
4. 局部句式重构
5. 段落级结构规则
6. 输出质量 validator

### 7.2 `llm`

定位：

1. 提升上限
2. 解决未知文本
3. 承担深层句法重构

建设重点：

1. 槽位专属 prompt
2. 槽位专属正负 few-shot
3. 输出约束
4. 后验质检
5. 算法 fallback

硬约束：

1. LLM 不得裸输出
2. 必须经过该槽位 validator
3. 失败必须回退到该槽位算法链

## 8. 槽位优先级

### P1

1. `cnki.rewrite.algorithm`
2. `cnki.rewrite.llm`
3. `cnki.dedup.algorithm`

### P2

4. `vip.rewrite.algorithm`
5. `vip.rewrite.llm`
6. `vip.dedup.algorithm`

### P3

7. `cnki.dedup.llm`
8. `vip.dedup.llm`

## 9. 执行顺序

1. 建立统一标签格式
2. 对 `算法报告` 做首轮编目
3. 按槽位拆出 `positive / negative / signals`
4. 公开数据进入底座层
5. 按槽位补合成数据
6. 为每个槽位建立回归集
7. 先做 P1，再做 P2，最后做 P3

## 10. 当前落地物

本轮先落地两份文档：

1. 本文：八槽位资产架构
2. `ALGO_REPORT_SLOT_CATALOG_2026-04-21.md`：`算法报告` 首轮编目清单

后续应继续补：

1. 槽位样本 `jsonl` 规范
2. 编目脚本
3. 资产导入脚本
4. 八槽位回归基线
