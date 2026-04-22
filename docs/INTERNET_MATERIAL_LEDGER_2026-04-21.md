# 互联网高质量资料来源台账

更新日期：2026-04-21

## 1. 目的

为策略数据底座阶段建立一份可持续维护的互联网资料台账。

台账只记录：

1. 来源
2. 类型
3. 许可与可用边界
4. 可服务的八槽位范围
5. 禁止误用的范围

## 2. 使用原则

### 2.1 只纳入高质量来源

优先级从高到低：

1. 官方论文页
2. 官方 GitHub / 官方代码仓库
3. 官方 API / 官方文档
4. 研究机构或组织官方发布页

### 2.2 不直接替代平台样本

互联网资料不能直接替代：

1. 知网平台信号
2. 维普平台信号
3. 自有严格 benchmark
4. 真实报告反馈

### 2.3 必须先打标签

每个来源在进入内部资产池前，必须声明：

1. `source_name`
2. `source_type`
3. `allowed_scope`
4. `forbidden_scope`
5. `license_or_notes`

### 2.4 必须能回答“补的是哪一类学科空白”

新增互联网来源入账时，还必须声明它优先补哪类学科：

1. `education`
2. `medicine_public_health`
3. `law_policy`
4. `finance_management`
5. `engineering_it_patent`
6. `humanities_social_science`

## 3. 台账字段

建议统一字段：

1. `id`
2. `name`
3. `source_url`
4. `source_kind`
5. `primary_use`
6. `allowed_slots`
7. `allowed_layers`
8. `forbidden_uses`
9. `license_notes`
10. `verification_status`
11. `discipline_priority`

## 4. 已确认来源

### 4.1 `CSL`

- `id`: `internet.csl`
- `name`: `CSL`
- `source_url`:
  - `https://github.com/ydli-ai/CSL`
  - `https://aclanthology.org/2022.coling-1.344`
- `source_kind`: `official_github + official_paper`
- `primary_use`:
  - 中文学术表达底座
  - 跨专业摘要与关键词风格补充
- `allowed_slots`:
  - `cnki.rewrite.*`
  - `vip.rewrite.*`
  - `cnki.dedup.*`
  - `vip.dedup.*`
- `allowed_layers`:
  - `shared_base`
  - `positive_assets_candidate`
- `forbidden_uses`:
  - 不直接充当知网 / 维普平台评分样本
  - 不直接推导平台报告阈值
- `license_notes`:
  - 使用前需按仓库说明确认数据许可和下载方式
- `verification_status`: `confirmed`

### 4.2 `CLUE`

- `id`: `internet.clue`
- `name`: `CLUE / CLUECorpus2020`
- `source_url`:
  - `https://github.com/CLUEbenchmark/CLUE`
- `source_kind`: `official_github`
- `primary_use`:
  - 通用中文表达底座
  - 合成数据底语料
  - 通用句法变化补充
- `allowed_slots`:
  - `all`
- `allowed_layers`:
  - `shared_base`
  - `synthetic_seed`
- `forbidden_uses`:
  - 不直接进入学术 strict benchmark
  - 不直接作为平台专属规则依据
- `license_notes`:
  - 以仓库公开说明为准
- `verification_status`: `confirmed`

### 4.3 `PAWS`

- `id`: `internet.paws`
- `name`: `PAWS / PAWS-X`
- `source_url`:
  - `https://github.com/google-research-datasets/paws`
- `source_kind`: `official_github`
- `primary_use`:
  - 结构改写能力底座
  - 词序变化与语义保持评测
- `allowed_slots`:
  - `cnki.dedup.*`
  - `vip.dedup.*`
  - `cnki.rewrite.llm`
  - `vip.rewrite.llm`
- `allowed_layers`:
  - `shared_base`
  - `synthetic_seed`
  - `eval_support`
- `forbidden_uses`:
  - 不直接作为学术中文风格样本
  - 不直接作为平台 few-shot 正样本
- `license_notes`:
  - 以仓库说明为准
- `verification_status`: `confirmed`

### 4.4 `MCTS`

- `id`: `internet.mcts`
- `name`: `MCTS`
- `source_url`:
  - `https://github.com/blcuicall/mcts`
  - `https://aclanthology.org/2024.lrec-main.969`
- `source_kind`: `official_github + official_paper`
- `primary_use`:
  - 多参考自然改写能力
  - LLM few-shot 候选
- `allowed_slots`:
  - `cnki.rewrite.llm`
  - `vip.rewrite.llm`
  - `cnki.dedup.llm`
  - `vip.dedup.llm`
- `allowed_layers`:
  - `shared_base`
  - `positive_assets_candidate`
  - `few_shot_candidate`
- `forbidden_uses`:
  - 不直接作为平台报告偏好
  - 不直接替代知网 / 维普真实改写样本
- `license_notes`:
  - 以仓库与论文页说明为准
- `verification_status`: `confirmed`

### 4.5 `C-ReD`

- `id`: `internet.cred`
- `name`: `C-ReD`
- `source_url`:
  - `https://papers.cool/arxiv/2604.11796`
  - `https://github.com/HeraldofLight/C-ReD`
- `source_kind`: `paper_page + paper_disclosed_repo`
- `primary_use`:
  - 中文 AIGC 检测对抗评测
  - 高风险文本模式参考
- `allowed_slots`:
  - `cnki.rewrite.*`
  - `vip.rewrite.*`
  - `*.platform_signals`
- `allowed_layers`:
  - `eval_support`
  - `negative_assets_candidate`
  - `synthetic_seed`
- `forbidden_uses`:
  - 不直接当作平台专属改写样本
  - 不直接当作 strict benchmark
- `license_notes`:
  - 代码仓库链接来自论文页披露，后续下载前仍需二次确认仓库可访问性与许可
- `verification_status`: `partially_confirmed`

### 4.6 `OpenAlex`

- `id`: `internet.openalex`
- `name`: `OpenAlex`
- `source_url`:
  - `https://docs.openalex.org/api-entities/works/work-object`
  - `https://docs.openalex.org/api-entities/works/search-works`
  - `https://docs.openalex.org/api-entities/works/filter-works`
- `source_kind`: `official_docs`
- `primary_use`:
  - 发现开放获取文献
  - 主题补盲
  - 学科扩展
- `allowed_slots`:
  - `all`（仅 discovery 层）
- `allowed_layers`:
  - `discovery`
- `forbidden_uses`:
  - 不直接作为训练样本库
  - 不直接当作现成全文 / 摘要语料
- `license_notes`:
  - 官方文档说明摘要使用 `abstract_inverted_index`
  - 只能作为发现入口，不直接当明文摘要库
- `verification_status`: `confirmed`

### 4.7 `CMB`

- `id`: `internet.cmb`
- `name`: `CMB`
- `source_url`:
  - `https://github.com/FreedomIntelligence/CMB`
- `source_kind`: `official_github`
- `primary_use`:
  - 医学 / 公共卫生表达补盲
  - 病例问答、概念解释、诊疗叙述风格补充
- `allowed_slots`:
  - `cnki.rewrite.*`
  - `vip.rewrite.*`
  - `cnki.rewrite.llm`
  - `vip.rewrite.llm`
- `allowed_layers`:
  - `shared_base`
  - `few_shot_candidate`
  - `eval_support`
- `forbidden_uses`:
  - 不直接充当平台评分样本
  - 不直接替代真实医学论文平台报告
- `license_notes`:
  - 以仓库公开说明与下载方式为准
- `verification_status`: `confirmed`
- `discipline_priority`: `medicine_public_health`

### 4.8 `LeCaRDv2`

- `id`: `internet.lecardv2`
- `name`: `LeCaRDv2`
- `source_url`:
  - `https://github.com/THUIR/LeCaRDv2`
  - `https://arxiv.org/abs/2310.17609`
- `source_kind`: `official_github + official_paper`
- `primary_use`:
  - 法律 / 政策治理表达补盲
  - 案情事实、程序描述、裁判逻辑表达参考
- `allowed_slots`:
  - `cnki.rewrite.*`
  - `vip.rewrite.*`
  - `cnki.dedup.*`
  - `vip.dedup.*`
- `allowed_layers`:
  - `shared_base`
  - `eval_support`
  - `positive_assets_candidate`
- `forbidden_uses`:
  - 不直接替代平台法学场景评分样本
  - 不直接推导平台报告阈值
- `license_notes`:
  - 以仓库许可与论文公开说明为准
- `verification_status`: `confirmed`
- `discipline_priority`: `law_policy`

### 4.9 `DocFEE`

- `id`: `internet.docfee`
- `name`: `DocFEE`
- `source_url`:
  - `https://github.com/tongzhou21/DocFEE`
  - `https://figshare.com/articles/dataset/_b_DocFEE_A_Document-Level_Chinese_Financial_Event_Extraction_Dataset_b_/28632464`
- `source_kind`: `official_github + official_dataset_page`
- `primary_use`:
  - 财经 / 管理 / 金融表达补盲
  - 公告体、事件体、监管体长文本结构补充
- `allowed_slots`:
  - `cnki.rewrite.*`
  - `vip.rewrite.*`
  - `cnki.dedup.*`
  - `vip.dedup.*`
- `allowed_layers`:
  - `shared_base`
  - `synthetic_seed`
  - `eval_support`
- `forbidden_uses`:
  - 不直接替代平台真实报告样本
  - 不直接作为平台 few-shot 正样本
- `license_notes`:
  - 数据页标注 `CC BY 4.0`，使用时仍需核对仓库说明
- `verification_status`: `confirmed`
- `discipline_priority`: `finance_management`

### 4.10 `CNIPA`

- `id`: `internet.cnipa`
- `name`: `CNIPA Patent Search and Analysis`
- `source_url`:
  - `https://www.cnipa.gov.cn/art/2023/2/13/art_3166_182074.html`
  - `https://www.cnipa.gov.cn/art/2022/7/26/art_53_176815.html`
- `source_kind`: `official_site`
- `primary_use`:
  - 工程 / IT / 专利技术发现入口
  - 术语风格、专利论述结构、技术主题发现
- `allowed_slots`:
  - `all`（仅 `discovery` 与 `eval_support`）
- `allowed_layers`:
  - `discovery`
  - `eval_support`
- `forbidden_uses`:
  - 不直接作为现成训练样本库
  - 不直接替代平台专属技术论文样本
- `license_notes`:
  - 仅作为官方检索分析入口使用
- `verification_status`: `confirmed`
- `discipline_priority`: `engineering_it_patent`

## 5. 来源到层级的映射

### 5.1 `shared_base`

适合进入：

1. `CSL`
2. `CLUE`
3. `PAWS`
4. `MCTS`
5. `CMB`
6. `LeCaRDv2`
7. `DocFEE`

### 5.2 `eval_support`

适合进入：

1. `PAWS`
2. `C-ReD`
3. `CMB`
4. `LeCaRDv2`
5. `DocFEE`

### 5.3 `synthetic_seed`

适合进入：

1. `CLUE`
2. `PAWS`
3. `MCTS`
4. `C-ReD`
5. `CMB`
6. `DocFEE`

### 5.4 `discovery`

适合进入：

1. `OpenAlex`
2. `CNIPA`

## 6. 当前不建议纳入的来源类型

1. 不明版权的论文搬运站
2. 无官方出处的经验贴
3. 无法确认许可的抓取语料
4. 平台用户上传的随机碎片
5. 无法确认版本关系的二手整理包

## 7. 下一步动作

1. 为每个来源建立内部 `source_id`
2. 与八槽位样本标签结构打通
3. 为可下载来源建立“待获取”队列
4. 为不可直接下载但可 discovery 的来源建立“候选发现”队列
5. 对每个来源记录优先补齐的学科缺口
