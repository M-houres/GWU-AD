# 合成数据样本规范

更新日期：2026-04-21

## 1. 目的

为策略训练与评测构建一套统一的合成数据规范。

合成数据不是为了“凑数量”，而是为了系统性覆盖真实坏模式，服务：

1. 算法门禁
2. LLM 负样例
3. validator
4. benchmark 反例集

## 2. 总原则

### 2.1 必须来源于真实问题

合成样本必须至少满足下面之一：

1. 来源于自有真实坏样本
2. 来源于平台报告高风险特征
3. 来源于公开基准暴露的结构脆弱点

### 2.2 不生成“脱离业务”的伪问题

禁止生成：

1. 完全脱离学术语境的句子
2. 只为难模型、但实际业务不会出现的问题
3. 与知网 / 维普论文场景不相关的英文互联网口语样本

### 2.3 必须声明目标槽位

每条合成样本都必须声明：

1. `target_slot`
2. `target_layer`
3. `error_type`

### 2.4 新增样本必须声明学科

从本轮开始，新增合成样本必须声明 `discipline`，取值优先使用：

1. `education`
2. `medicine_public_health`
3. `law_policy`
4. `finance_management`
5. `engineering_it_patent`
6. `humanities_social_science`

说明：

1. 历史样本可暂时缺省，后续逐步回填
2. 新样本不允许继续全部落在教育场景

## 3. 合成数据用途

### 3.1 `negative_assets`

用于：

1. 黑名单
2. 模板句拦截
3. 固定搭配门禁
4. 结构异常门禁

### 3.2 `few_shot_negative`

用于：

1. LLM 提示词中的负样例
2. 明确禁止输出模式

### 3.3 `eval_negative`

用于：

1. benchmark 反例集
2. 回归测试
3. 质量闸门测试

## 4. 第一批合成问题类型

### 4.1 机械连接词堆叠

表现：

1. `同时，`
2. `此外，`
3. `进一步看，`
4. `在此基础上，`
5. `由此可见，`

在单段中连续或累计过多出现。

适用槽位：

1. `cnki.rewrite.*`
2. `cnki.dedup.*`
3. `vip.rewrite.*`
4. `vip.dedup.*`

### 4.2 模板判断句

表现：

1. `这说明其属于`
2. `并进一步保持原有论证脉络`
3. 类似模板化判断或收束句

适用槽位：

1. `cnki.rewrite.*`
2. `cnki.dedup.*`

### 4.3 术语拆坏

表现：

1. `可视化 -> 可以视化`
2. `数字化 -> 能够数字化`
3. `信息化 -> 可以信息化`

适用槽位：

1. `cnki.rewrite.*`
2. `cnki.dedup.*`
3. `vip.rewrite.*`

### 4.4 固定搭配破坏

表现：

1. `重要参考 -> 关键参考`
2. `重要力量 -> 关键力量`
3. `重要组成部分 -> 关键组成部分`
4. `至关重要 -> 至关关键`

适用槽位：

1. `cnki.rewrite.*`
2. `cnki.dedup.*`

### 4.5 重复搭配或拼接病句

表现：

1. `探索与探索`
2. `作为属于`
3. `蕴含包括`
4. `路径方式`

适用槽位：

1. `all`

### 4.6 长句切碎

表现：

1. 原本完整的学术长句被拆成多个弱短句
2. 拆后逻辑断裂
3. 结构性机械感明显

适用槽位：

1. `cnki.rewrite.*`
2. `cnki.dedup.*`

### 4.7 字数异常扩写

表现：

1. 为了降AIGC或降重强行加 filler
2. 句长明显膨胀但信息量未增加

适用槽位：

1. `*.rewrite.*`

### 4.8 定义句伪改写

表现：

1. 定义句只做词面替换
2. 重复率下降有限
3. 可读性却变差

适用槽位：

1. `*.dedup.*`

## 5. 合成样本字段规范

每条合成样本建议至少包含：

1. `sample_id`
2. `target_slot`
3. `target_layer`
4. `source_type`
5. `source_reference`
6. `error_type`
7. `severity`
8. `source_text`
9. `synthetic_text`
10. `expected_action`
11. `notes`
12. `discipline`

## 6. 字段说明

### 6.1 `target_slot`

示例：

1. `cnki.rewrite.algorithm`
2. `vip.dedup.llm`

### 6.2 `target_layer`

示例：

1. `negative_assets`
2. `few_shot_negative`
3. `eval_negative`

### 6.3 `source_type`

示例：

1. `self_bad_sample`
2. `platform_signal`
3. `internet_seed`
4. `manual_design`

### 6.4 `expected_action`

枚举建议：

1. `reject`
2. `warn`
3. `rewrite_fix`
4. `prompt_block`

### 6.5 `discipline`

用途：

1. 控制学科覆盖均衡
2. 约束 few-shot 与 validator 不被单一领域带偏
3. 支持后续分学科回归测试

## 7. 推荐 `jsonl` 结构

```json
{
  "sample_id": "syn_cnki_rewrite_algo_0001",
  "target_slot": "cnki.rewrite.algorithm",
  "target_layer": "negative_assets",
  "discipline": "law_policy",
  "source_type": "self_bad_sample",
  "source_reference": "rewrite_result_113.docx",
  "error_type": "mechanical_connector_cascade",
  "severity": "high",
  "source_text": "原始正常句段",
  "synthetic_text": "同时，……此外，……进一步看，……在此基础上，……",
  "expected_action": "reject",
  "notes": "由真实知网坏样本抽象"
}
```

## 8. 严禁的合成方式

1. 没有真实参照，凭空乱造
2. 用英语网络文本直接硬翻成中文学术坏样本
3. 不标槽位就进资产池
4. 把一个合成坏样本同时投喂所有槽位
5. 用教育域表达模式硬套医学、法律、财经、工程文本

## 9. 第一批推荐产出

建议先做：

1. `cnki.rewrite.algorithm` 负样本
2. `cnki.rewrite.llm` 负样例
3. `cnki.dedup.algorithm` 负样本
4. `vip.rewrite.algorithm` 负样本
5. 非教育学科补盲样本

原因：

1. 当前这些槽位样本最成熟
2. 最容易形成可用资产
3. 回归价值最高
4. 但必须同步补齐医学、法学、财经、工程、人文社科覆盖

## 10. 下一步动作

1. 用当前已识别的坏样本生成第一批合成负样本模板
2. 将样本写入统一 `jsonl`
3. 接入 validator 和回归测试
4. 为每个槽位建立学科覆盖计数
