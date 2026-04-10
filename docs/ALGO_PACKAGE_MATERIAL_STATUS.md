# 算法包资料现状快照

最后更新：2026-04-10

参见：

- `docs/ALGO_PACKAGE_TRAINING_WORKSPACE.md`
- `docs/AIGC_ALGO_TRAINING_MEMORY.md`
- `docs/DEDUP_ALGO_TRAINING_MEMORY.md`
- `docs/REWRITE_ALGO_TRAINING_MEMORY.md`
- `scripts/inventory_algo_training_workspace.py`

## 1. 资料总入口

当前统一资料入口固定为：

- `C:\Users\m\Desktop\001项目\算法训练资料包`

平台目录现状：

1. `知网资料包`
2. `维普资料包`
3. `PaperPass资料包`

## 2. 当前库存概览

按 2026-04-10 当前盘点结果：

### 2.1 知网资料包

共 `30` 个文件：

1. `docx`：`14`
2. `pdf`：`11`
3. `zip`：`5`

按材料角色粗分：

1. `aigc_report`：`10`
2. `rewrite_doc`：`8`
3. `dedup_report`：`7`
4. `source_doc`：`5`

### 2.2 维普资料包

共 `38` 个文件：

1. `zip`：`37`
2. `html`：`1`

当前主力材料形态：

1. `原文对照报告.pdf`
2. `格式分析报告.html`
3. `比对报告.html`
4. `片段对照报告.html`
5. `简洁报告.pdf`
6. `报告说明.txt`

这说明维普当前资料对 `vip_dedup` 很强，但对 `vip_aigc` 和 `vip_rewrite` 仍偏弱。

### 2.3 PaperPass资料包

当前为空。

## 3. 9 个算法包当前资料状态

### 3.1 知网 `cnki_aigc`

当前状态：已能推进

现有结论：

1. 已形成第一版知网 AIGC benchmark
2. 现有 v1 benchmark 为 `4` 份
3. 新增 AIGC 报告包去重后还能再补 `4` 份
4. 合计可扩到 `8` 份

当前价值：

1. 可直接用于知网 AIGC 结果拟合评分
2. 对 `0%` 误报修正尤其有价值

当前缺口：

1. 仍缺更多中风险样本
2. 仍缺更多高风险样本

### 3.2 知网 `cnki_dedup`

当前状态：可抽规则，暂未形成稳定 benchmark

现有材料：

1. `X餐饮连锁公司营销措施现状优化研究` 查重报告组
2. `主题·共情·表达...` 查重报告组

当前价值：

1. 已足够提炼知网查重的高风险骨架
2. 已补出 `CNKI_DEDUP_SAMPLE_RULESET`

当前缺口：

1. 成套样本仍太少
2. 还缺更多“原文 / 改写稿 / 改写前后报告”对照组

### 3.3 知网 `cnki_rewrite`

当前状态：规则池较强，评分池仍偏少

现有材料：

1. `（润色前）... / （润色后）...` 三组配对文档
2. `知网降AIGC.docx`
3. `改写结果_2026-3-28...` 一组改写稿及对应 AIGC 报告包

当前价值：

1. 足够提炼知网降 AIGC 改写方向
2. 已形成 `CNKI_REWRITE_SAMPLE_RULESET`

当前缺口：

1. 仍缺更多“改写前后真实 AIGC 报告”成套对照
2. 当前还不够支撑稳定量化晋级

### 3.4 维普 `vip_aigc`

当前状态：基本空白

当前结论：

1. 还没有真实 VIP AIGC 报告池
2. 暂时不能做结果拟合评分

### 3.5 维普 `vip_dedup`

当前状态：当前最强资料池之一

现有结论：

1. 当前有 `37` 个报告压缩包
2. 其中大部分都带：
   - `原文对照报告`
   - `比对报告`
   - `片段对照报告`
   - `简洁报告`
3. 已确认至少 `7` 个同题多版本标题组

当前最有价值的多版本组包括：

1. `华英公司营运资金管理现状及优化对策研究` x `3`
2. `海上液化石油气运输作业风险评估` x `2`
3. `肺癌患者围术期的快速康复护理` x `2`
4. `苏轼黄州诗文中的人生意识研究` x `2`
5. `基于英语学习活动观的小学绘本阅读教学活动设计` x `2`
6. `家校协同视角下小学生心理健康教育的实践研究` x `2`
7. `浅析中药安全性评价的现状及发展` x `2`

当前价值：

1. 很适合做 `vip_dedup` 高风险片段和改写有效性分析
2. 很适合做同题多版的规则回归比较
3. 已形成 `VIP_DEDUP_SAMPLE_RULESET`

当前缺口：

1. 仍需更强的原文正文提取和版本映射
2. 还需要把成套可评分样本进一步标准化

### 3.6 维普 `vip_rewrite`

当前状态：间接可用，直接评分材料不足

当前结论：

1. 有些压缩包中夹带改写结果文本
2. 但整体仍以查重报告为主，不是完整降 AIGC 评分资料

当前价值：

1. 可辅助抽取改写动作
2. 可辅助反推哪些写法更容易降低维普重复风险

当前缺口：

1. 缺成套“原文 / 改写稿 / 改写前后 AIGC 报告”
2. 缺独立 VIP 降 AIGC benchmark

### 3.7 PaperPass `pp_aigc`

当前状态：空

### 3.8 PaperPass `pp_dedup`

当前状态：空

### 3.9 PaperPass `pp_rewrite`

当前状态：空

## 4. 当前已经沉淀到项目内的成果

### 4.1 AIGC 检测

1. `docs/AIGC_DETECT_RESULT_EVAL_FRAMEWORK.md`
2. `docs/AIGC_ALGO_TRAINING_MEMORY.md`
3. `backend/app/services/aigc_detect_evaluator.py`
4. `scripts/evaluate_aigc_detect.py`
5. `scripts/build_cnki_aigc_reference_samples.py`

### 4.2 降重复率

1. `docs/DEDUP_RESULT_EVAL_FRAMEWORK.md`
2. `docs/DEDUP_REWRITE_REQUIREMENTS.md`
3. `docs/DEDUP_ALGO_TRAINING_MEMORY.md`
4. `docs/VIP_DEDUP_SAMPLE_RULESET.md`
5. `docs/CNKI_DEDUP_SAMPLE_RULESET.md`

### 4.3 降 AIGC

1. `docs/REWRITE_RESULT_EVAL_FRAMEWORK.md`
2. `docs/REWRITE_QUALITY_REQUIREMENTS.md`
3. `docs/REWRITE_ALGO_TRAINING_MEMORY.md`
4. `docs/CNKI_REWRITE_SAMPLE_RULESET.md`

### 4.4 工作区管理

1. `docs/ALGO_PACKAGE_TRAINING_WORKSPACE.md`
2. `scripts/inventory_algo_training_workspace.py`

## 5. 当前最适合立刻继续推进的方向

按照现有资料价值排序，当前最该继续推进的是：

1. `cnki_aigc`
   - 继续扩 benchmark
   - 修 `0%` 误报
2. `vip_dedup`
   - 标准化多版本样本
   - 做版本间失败原因归纳
3. `cnki_rewrite`
   - 基于现有润色前后语料继续抽规则
4. `cnki_dedup`
   - 继续补知网查重样本，逐步形成 benchmark

## 6. 当前结论

现有资料并不是平均分布在 9 个算法包上的。

当前最有价值的事实是：

1. 知网已经具备 AIGC 结果拟合的起步条件
2. 维普已经具备降重复率规则提炼和多版本对照分析的强条件
3. 知网已经具备降 AIGC 规则提炼的起步条件
4. PaperPass 目前还没有真正进入训练阶段

所以后续训练不应平均发力，而应先吃透：

1. `cnki_aigc`
2. `vip_dedup`
3. `cnki_rewrite`

这三条线最容易先出实质成果。
