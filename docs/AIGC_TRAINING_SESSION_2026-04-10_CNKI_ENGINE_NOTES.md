# 2026-04-10 CNKI AIGC 检测训练记录

## 本轮目标

围绕 `cnki_aigc_detect` 的运行层误差做一轮收敛，不直接改业务链路，优先修：

1. 段落切分把报告恢复文本拆成大量伪段落。
2. 低风险文本没有 `clean` 出口，整体可疑占比被抬高。
3. 疑似高亮片段过宽，导致命中范围和严重度偏差过大。

## 已落地改动

代码位置：`backend/app/services/processing_engine.py`

1. 补了检测文本行归一化和“版式换行文本”识别，开始尝试把短行密集的报告恢复文本重新并回段落。
2. 检测标签增加 `clean` 档位，不再把所有低分内容都塞进 `low`。
3. 片段分布统计中，`clean` 片段改走 `no_ai` 桶，避免把清洁文本继续计入可疑比例。
4. 收紧了 `_local_suspicious_segments_v2()` 的触发条件，减少弱信号句子直接进高亮列表。
5. 论文前置页材料加入 `no_ai` 过滤规则：
   - `分类号`
   - `密级`
   - `学号`
   - `独创性说明`
   - `知识产权声明`
   - `学位论文作者签名`
   - `指导教师签名`
   - 典型声明正文
6. 新增了 `human_case_relief`，用于压低“实践案例/园本项目/家校互动”一类强人写风格文本的误报。

## 新增测试

代码位置：`backend/tests/test_processing_engine_results.py`

新增覆盖：

1. 版式换行文本能合并为逻辑段落。
2. `clean -> low -> medium` 的标签分档生效。
3. 弱信号句子不会直接进入疑似高亮。
4. 论文前置页材料可被识别为 `no_ai`。
5. 实践案例段落能触发 `human_case_relief`。

本轮相关测试通过：

1. `tests/test_processing_engine_results.py`
2. `tests/test_aigc_detect_evaluator.py`

## 离线基准结果

参考集：

- `logs/benchmarks/cnki_aigc_reference_samples.v1.json`

候选结果：

- `logs/benchmarks/cnki_aigc_current_engine_eval.v2.json`

评测命令：

- `python scripts/evaluate_aigc_detect.py --reference logs/benchmarks/cnki_aigc_reference_samples.v1.json --candidate logs/benchmarks/cnki_aigc_current_engine_eval.v2.json`

本轮评测结论：

1. 当前仍是 `D`，`final_score = 25.16`，不能晋级。
2. 正向变化：
   - `clean` 比例开始回升。
   - `0%` 样本不再像上一轮那样几乎全量落入中风险。
   - 论文前置页误报开始下降。
3. 负向变化：
   - 高风险样本整体分数被压低，导致全文总分一致性变差。
   - 高亮片段数量被压得过少，`highlight_span_alignment` 明显掉分。
4. 关键事实：
   - `sample cnki_aigc_20260409_101401_85f9a105` 仍然存在大规模过检，候选风险段索引远超参考。
   - 实践案例类文本三份样本之间，当前规则仍缺少真正能区分“高风险版”和“低风险版”的特征。

## 当前判断

这轮修复证明两件事：

1. 运行层确实有问题，修它是必要的。
2. 只靠运行层减权还不够，已经进入“需要从样本里提炼区分特征”的阶段。

也就是说：

- `clean` 档和前置页过滤是对的，要保留。
- `human_case_relief` 不能再粗暴直减，后面要改成“条件式减权”。
- 真实提升点已经从“后处理 bug”转到“高风险/低风险样本的区分特征训练”。

## 下一步建议

下一轮优先级：

1. 给 `human_case_relief` 加阻尼条件。
   - 当 `template/opening/artifact` 明显时，不允许大幅减权。
2. 单独做 `front_matter` / `declaration` / `abstract` / `body` 的区域识别。
   - 不再把整篇恢复文本当成同一种内容对待。
3. 从新增知网资料里抽“高风险段落 -> 对应高亮文本 -> 最终风险级别”样本。
   - 不再只看全文总分。
4. 把 `sample 222642 / 223855 / 213030` 这组三篇作为一组对照训练样本。
   - 当前最缺的是能把“同题不同版本”真正拉开的特征。

## 备注

这一轮没有提交代码，也没有替换主线算法包版本。
原因不是实现失败，而是离线基准还没有达到可升级状态。
