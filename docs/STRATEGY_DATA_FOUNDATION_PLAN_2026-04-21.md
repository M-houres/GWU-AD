# 策略数据底座建设方案

更新日期：2026-04-21

## 1. 目标

在继续大规模强化策略前，先建立统一、可审计、可复用的数据底座。

该底座服务于：

1. `cnki.rewrite.algorithm`
2. `cnki.rewrite.llm`
3. `cnki.dedup.algorithm`
4. `cnki.dedup.llm`
5. `vip.rewrite.algorithm`
6. `vip.rewrite.llm`
7. `vip.dedup.algorithm`
8. `vip.dedup.llm`

核心要求：

1. 先做数据
2. 再做重策略开发
3. 但保留最小必要的标签、准入和 benchmark 骨架

## 2. 基本原则

### 2.1 数据优先，但不是“只囤资料”

当前阶段的正确顺序是：

1. 先把自有资料整理成可用资产
2. 再补互联网高质量资料
3. 再围绕已知坏模式生成合成数据
4. 最后再批量反哺算法与 LLM

但必须同步保留最小落地骨架：

1. 八槽位标签
2. A/B/C 准入等级
3. 样本级 `jsonl` 结构
4. benchmark 候选池

### 2.2 平台、场景、模式严格对应

任何资料进入资产池前，必须先声明：

1. `platform`
2. `scenario`
3. `mode_scope`

未声明或不明确的资料，不允许直接进入槽位资产。

### 2.3 互联网资料只补“底座”和“泛化”

公开数据不能直接替代平台样本：

1. 不替代知网 / 维普平台信号
2. 不替代真实报告
3. 不直接当严格评分样本

它们的主要作用是：

1. 补跨专业覆盖
2. 补结构改写能力
3. 补自然改写能力
4. 补 AIGC 对抗评测能力

### 2.4 跨学科覆盖必须前置约束

当前自有资料明显偏教育场景，因此后续所有新增资产都必须显式补齐以下学科覆盖：

1. 教育
2. 医学 / 公共卫生
3. 法学 / 政策治理
4. 财经 / 管理 / 金融
5. 工程 / 计算机 / 专利技术
6. 人文 / 社会科学

执行要求：

1. 新增样本默认必须声明 `discipline`
2. 每个槽位至少都要能拿到 3 个以上非教育样本来源
3. 共享底座允许复用学科表达资源，但平台信号、few-shot、评分资产仍按槽位隔离
4. 若某学科暂时缺真实平台样本，可先用互联网高质量资料和合成负样本补盲，但不得冒充平台真实信号

## 3. 三层数据来源

### 3.1 第一层：自有资料

主来源：

1. `C:\Users\m\Desktop\算法报告`
2. `C:\Users\m\Desktop\123`
3. 已经提供的知网 / 维普样例目录

价值：

1. 最贴近业务真实场景
2. 带平台报告反馈
3. 最适合沉淀槽位专属资产

优先级：

1. 最高

### 3.2 第二层：互联网高质量资料

作用：

1. 补充跨专业学术表达
2. 补充结构级改写样本
3. 补充自然改写参考
4. 补充检测对抗评测素材

优先级：

1. 中高

### 3.3 第三层：合成数据

作用：

1. 放大真实坏模式
2. 提高负样本覆盖度
3. 为 validator、blacklist、few-shot 提供系统性反例

优先级：

1. 中高

## 4. 互联网高质量资料清单

以下资料只从官方论文、官方 GitHub、官方文档或官方技术文档进入。

### 4.1 `CSL`

来源：

1. GitHub：`https://github.com/ydli-ai/CSL`
2. 论文：`https://aclanthology.org/2022.coling-1.344`

定位：

1. 中文科学文献数据集
2. 含标题、摘要、关键词、学科、门类

适用：

1. 共享学术表达底座
2. `cnki.rewrite.*`
3. `vip.rewrite.*`
4. `cnki.dedup.*`
5. `vip.dedup.*`

限制：

1. 不能直接当平台评分样本
2. 不能直接推导知网 / 维普报告偏好

### 4.2 `CLUE / CLUECorpus2020`

来源：

1. GitHub：`https://github.com/CLUEbenchmark/CLUE`

定位：

1. 中文语言理解与通用语料底座

适用：

1. 通用中文表达补充
2. 术语外普通句法变化
3. 合成数据底语料

限制：

1. 更适合作为共享底座
2. 不宜直接进入学术 strict benchmark

### 4.3 `PAWS / PAWS-X`

来源：

1. GitHub：`https://github.com/google-research-datasets/paws`
2. 论文仓库中含 PAWS 与 PAWS-X 引用信息

定位：

1. 结构接近但词序不同的高难改写对
2. 强调词序、结构、上下文差异

适用：

1. `*.dedup.*`
2. `*.rewrite.llm`
3. 结构改写能力评测

限制：

1. 本身不是学术论文语料
2. 必须经二次筛选后转为中文学术风格素材

### 4.4 `MCTS`

来源：

1. GitHub：`https://github.com/blcuicall/mcts`
2. 论文：`https://aclanthology.org/2024.lrec-main.969`

定位：

1. 中文多参考改写 / 简化数据集
2. 同一句有多种自然改写路径

适用：

1. `*.rewrite.llm`
2. `*.dedup.llm`
3. 自然表达与多参考 few-shot

限制：

1. 不是平台专属学术语料
2. 更适合补“自然改写能力”，不直接补平台信号

### 4.5 `C-ReD`

来源：

1. 论文页：`https://papers.cool/arxiv/2604.11796`
2. 论文页中给出的代码仓库：`https://github.com/HeraldofLight/C-ReD`

说明：

1. 这里我目前拿到的是论文页和论文页里给出的代码仓库地址
2. 代码仓库链接来自论文页披露，应视为“待进一步拉取验证”的官方线索

定位：

1. 中文 AIGC 检测基准
2. 强调真实 prompt、多模型、多域泛化

适用：

1. `cnki.rewrite.*`
2. `vip.rewrite.*`
3. `*.platform_signals`
4. AIGC 对抗评测集

限制：

1. 属于检测基准，不是直接的改写样本库
2. 应主要用于反向构造降AIGC对抗样本与评测集

### 4.6 `OpenAlex`

来源：

1. Work object 文档：`https://docs.openalex.org/api-entities/works/work-object`
2. Search works 文档：`https://docs.openalex.org/api-entities/works/search-works`
3. Filter works 文档：`https://docs.openalex.org/api-entities/works/filter-works`

定位：

1. 开放文献发现与检索入口
2. 可定位开放获取论文与元信息

适用：

1. 发现候选开放学术资料
2. 学科覆盖扩展
3. 题材补盲

限制：

1. 文档明确说明不直接提供明文摘要，而是 `abstract_inverted_index`
2. 不能把它当成现成的全文语料源
3. 更适合作为“发现工具”，不是直接训练语料

### 4.7 `CMB`

来源：

1. GitHub：`https://github.com/FreedomIntelligence/CMB`

定位：

1. 中文医学 benchmark 与问答/病例语料入口
2. 医学专业表达、诊疗叙述、概念解释模式补充

适用：

1. `cnki.rewrite.*`
2. `vip.rewrite.*`
3. `*.rewrite.llm`
4. `shared_base`

限制：

1. 更适合作为医学表达和复杂概念改写参考
2. 不直接作为知网 / 维普平台评分样本
3. 不直接推导平台检测阈值

### 4.8 `LeCaRDv2`

来源：

1. GitHub：`https://github.com/THUIR/LeCaRDv2`
2. 论文：`https://arxiv.org/abs/2310.17609`

定位：

1. 中文法律案例检索数据集
2. 法律事实表述、裁判逻辑、程序性语句表达补充

适用：

1. `cnki.rewrite.*`
2. `vip.rewrite.*`
3. `cnki.dedup.*`
4. `vip.dedup.*`

限制：

1. 主要用于法学 / 政策治理领域表达底座和结构保持评测
2. 不直接替代平台真实法学报告样本

### 4.9 `DocFEE`

来源：

1. GitHub：`https://github.com/tongzhou21/DocFEE`
2. 数据页：`https://figshare.com/articles/dataset/_b_DocFEE_A_Document-Level_Chinese_Financial_Event_Extraction_Dataset_b_/28632464`

定位：

1. 中文财经领域文档级事件抽取数据
2. 长文财务事件、公告体、监管体表达补充

适用：

1. `cnki.rewrite.*`
2. `vip.rewrite.*`
3. `cnki.dedup.*`
4. `vip.dedup.*`

限制：

1. 主要用于财经 / 管理表达与跨句结构保持
2. 不直接当作平台 few-shot 正样本

### 4.10 `CNIPA`

来源：

1. 国家知识产权局：`https://www.cnipa.gov.cn/art/2023/2/13/art_3166_182074.html`
2. 国家知识产权局：`https://www.cnipa.gov.cn/art/2022/7/26/art_53_176815.html`

定位：

1. 专利检索及分析官方入口
2. 工程、计算机、制造、生物医药等专利技术表达发现工具

适用：

1. `all`（仅 `discovery` 与 `eval_support`）

限制：

1. 主要用于发现专利技术文献和术语风格
2. 不直接当作现成训练语料
3. 仅能作为工程 / 专利技术领域的发现入口与分析参考

## 5. 互联网资料到八槽位的映射规则

### 5.1 共享底座

以下来源优先进入共享底座：

1. `CSL`
2. `CLUE`
3. `CMB`
4. `LeCaRDv2`
5. `DocFEE`
3. `OpenAlex` 发现到的开放资料

### 5.2 结构改写底座

以下来源优先进入结构改写底座：

1. `PAWS / PAWS-X`
2. `MCTS`
3. `LeCaRDv2`
4. `DocFEE`

### 5.3 AIGC 对抗底座

以下来源优先进入 AIGC 对抗底座：

1. `C-ReD`
2. 自有知网 / 维普检测报告

### 5.4 学科补盲发现层

以下来源优先进入学科补盲发现层：

1. `OpenAlex`
2. `CNIPA`

## 6. 合成数据设计

### 6.1 合成原则

合成数据不能凭空写，要围绕真实坏样本问题生成。

必须从以下来源中至少命中一种：

1. 自有真实坏样本
2. 官方报告高风险特征
3. 公开基准中的结构脆弱点

### 6.2 第一批合成类型

1. 机械连接词堆叠
2. 模板判断句
3. 术语拆坏
4. 固定搭配破坏
5. 字数异常扩写
6. 长句切碎
7. 定义句伪改写
8. 同义替换拼接病句

### 6.3 合成数据字段

每条合成样本至少包含：

1. `target_slot`
2. `discipline`
2. `source_type`
3. `source_reference`
4. `error_type`
5. `severity`
6. `source_text`
7. `synthetic_text`
8. `expected_action`

## 7. 当前阶段先做什么

### 7.1 必做

1. 自有资料样本级编目
2. 互联网资料清单确认
3. 合成数据类型清单
4. 八槽位标签方案
5. 学科覆盖缺口盘点

### 7.2 暂缓

1. 大规模 prompt 扩写
2. 大规模规则开发
3. 大规模 benchmark 跑分
4. 全量 LLM few-shot 工程

原因：

1. 数据底座还未完全成形
2. 现在重策略开发容易反复返工

## 8. 当前阶段输出物

数据底座优先阶段，应先产出：

1. 自有资料样本级清单
2. 互联网资料来源清单
3. 合成数据设计清单
4. 八槽位 `jsonl` 标签规范
5. 第一批 benchmark 骨架
6. 学科覆盖矩阵

## 9. 推荐下一步

按下面顺序推进：

1. 补一份 `互联网资料来源台账`
2. 补一份 `合成数据样本规范`
3. 先给当前 `A-triple` 做 `jsonl` 标签
4. 解压 `维普降重复率` 的 `zip`
5. 把 `vip.dedup` 候选池补起来
6. 先补齐非教育领域的合成负样本

## 10. 当前结论

当前主线应明确切到：

1. 自有资料精编
2. 互联网资料筛选
3. 合成数据设计

在这三项完成前，不继续扩大重策略开发范围。
