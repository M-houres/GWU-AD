# 积分制回归审阅记录

最后更新：2026-04-18

## 背景
- 当前项目的真实产品设计已确认回到“积分制”。
- 仓库内存在一批未提交改动，部分实现仍沿用“金额制迁移”思路。
- 本记录用于：
  - 固化本次审阅结论
  - 列出需要统一修复的范围
  - 为后续接管提供执行顺序与验证清单

## 本次审阅范围
- 充值与下单链路
- 后台计费配置
- 用户侧个人中心/充值页
- 管理侧订单/用户/任务视图
- 任务提交扣费相关提示

## 已确认的产品基线
- 账户主口径：积分
- 充值主能力：积分套餐
- 套餐核心字段：`name / price / credits / description / badge / enabled`
- 任务扣费底层仍可按金额费率换算，但对外呈现与运营配置必须服务于积分体系
- 管理后台必须支持配置“到账积分”，不能只配置“充值金额”

## 核心问题

### P0-1 充值页绕过后端套餐配置
- 文件：
  - `frontend/src/components/BuyCreditsPanel.vue`
  - `backend/app/api/billing.py`
- 现状：
  - 前端未使用 `/billing/packages` 返回的套餐列表渲染可购项。
  - 前端固定写死 `50 / 100 / 200` 档。
  - 下单时优先传 `amount_cny`，不是传 `package_name`。
- 风险：
  - 后台配置的积分套餐不会真正生效。
  - 营销套餐、赠送积分、特殊积分包会被前端绕过。
  - 用户可以购买“不存在于配置中心”的金额档位。

### P0-2 后台配置中心保存套餐时丢失 `credits`
- 文件：
  - `frontend/src/views/admin/AdminConfigPage.vue`
  - `backend/app/api/admin.py`
- 现状：
  - 前端计费配置页只允许维护套餐名称、价格、文案、标签、启用状态。
  - 保存 payload 时没有携带 `credits`。
  - 后端对缺失的 `credits` 会按 `price * 100` 回填。
- 风险：
  - 运营只要保存一次配置，原本“价格不变但赠送更多积分”的套餐就会被静默抹掉。
  - 所有非 1:100 线性兑换关系都会消失。
  - 这是配置破坏，不只是展示问题。

### P1-1 默认套餐与前端展示不一致
- 文件：
  - `backend/app/constants.py`
  - `frontend/src/components/BuyCreditsPanel.vue`
  - `frontend/src/views/admin/AdminConfigPage.vue`
- 现状：
  - 后端默认套餐：`30 / 100 / 150 / 300`
  - 前端购买页固定档位：`50 / 100 / 200`
- 风险：
  - 配置、接口、购买页三套来源不一致。
  - 用户、运营、客服看到的套餐信息不一致。

### P1-2 “金额制迁移”文案和引导仍残留在关键页面
- 文件：
  - `frontend/src/views/admin/AdminConfigPage.vue`
  - `frontend/src/components/BuyCreditsPanel.vue`
  - `frontend/src/views/user/UserProfilePage.vue`
  - `MONEY_BILLING_MIGRATION_LOG.md`
- 现状：
  - 存在“任务计费（元/百字符）”“套餐按金额充值”“自定义充值金额”等引导。
  - 充值成功提示与个人中心中仍混有金额制迁移痕迹。
- 风险：
  - 业务定义被误读，后续维护继续沿错误方向扩散。

### P1-3 自定义金额充值能力与积分套餐定位冲突
- 文件：
  - `backend/app/api/billing.py`
  - `backend/app/schemas.py`
  - `frontend/src/components/BuyCreditsPanel.vue`
- 现状：
  - 接口公开支持 `amount_cny` 自定义充值。
  - `/billing/packages` 明确返回 `custom_amount_enabled: true`。
- 风险：
  - 固定套餐策略被削弱。
  - 若积分体系依赖“档位赠送”，自定义金额会绕开运营策略。
  - 与“套餐制”产品设计冲突。

### P2-1 任务提交异常提示与后端消息来源不统一
- 文件：
  - `frontend/src/lib/taskSubmitFlow.js`
  - `backend/app/services/credit_service.py`
  - `backend/app/worker_tasks.py`
- 现状：
  - 前端按“积分不足”关键字分流。
  - 后端同步与异步链路仍有不同文本来源。
- 风险：
  - 后续若消息改文案，前端兜底逻辑可能失效。
  - 应改为更稳定的错误码驱动。

## 衍生影响评估

### 直接受影响模块
- 用户购买页
- 个人中心充值入口
- 后台配置中心
- 订单管理页
- 用户详情页中的累计充值/累计消耗展示

### 间接受影响模块
- 支付回调后的到账积分审计
- 运营配置生效可信度
- 客服对账与套餐说明
- 市场活动套餐投放

### 当前未发现异常的部分
- 后端主要计费/支付/退款链路回归通过
- 前端当前代码可构建通过
- 订单接口本身仍保留 `credits/recharge_fen` 等兼容字段，具备回到积分制的基础

## 建议整改方案

### Phase 1 先修正产品定义和配置源
- 目标：
  - 后台配置中心重新以“积分套餐”作为唯一真实来源
- 动作：
  - 在 `AdminConfigPage` 套餐编辑区恢复 `credits` 字段
  - 表单默认值、归一化、校验、保存 payload 全量保留 `credits`
  - 文案改为“充值金额 / 到账积分 / 套餐说明”
  - 新增测试，覆盖“保存 billing 配置后 credits 不丢失”

### Phase 2 收口购买链路
- 目标：
  - 购买页只消费后端返回套餐，不再本地硬编码
- 动作：
  - `BuyCreditsPanel` 改为渲染 `/billing/packages` 返回的套餐
  - 默认下单使用 `package_name`
  - 如产品确认不需要自定义充值，则前后端一起关闭 `amount_cny` 入口
  - 如产品仍保留自定义充值，则必须显式标注为“自定义金额充值”，并与套餐制隔离

### Phase 3 统一展示口径
- 目标：
  - 用户和运营都看到一致的积分体系
- 动作：
  - 用户侧：统一“当前积分 / 积分流水 / 任务消耗积分”
  - 管理侧：订单页明确区分“支付金额”和“到账积分”
  - 清理金额制迁移残留文案与日志

### Phase 4 修复衍生稳定性问题
- 目标：
  - 减少未来因文案变化导致的隐藏 bug
- 动作：
  - 前端“积分不足”逻辑改为优先按后端错误码处理
  - 补充配置与购买联动回归测试
  - 补充“套餐价格与到账积分非线性关系”的用例

## 建议执行顺序
1. 修 `AdminConfigPage` 和对应测试，先保住配置不会继续破坏积分套餐。
2. 修 `BuyCreditsPanel`，切回后端套餐源。
3. 再统一用户侧/管理侧文案和展示字段。
4. 最后清理 `amount_cny` / `custom_amount_enabled` 等是否保留的边界能力。

## 建议新增/补强的测试
- 后台保存 billing 配置后，`credits` 字段完整保留。
- 前台 `/billing/packages` 返回带 `credits` 的套餐时，购买页按返回项渲染。
- 购买固定套餐时，前端提交 `package_name` 而非 `amount_cny`。
- 配置“29.9 元 -> 42000 积分”这类非线性套餐时，下单后到账积分正确。
- 若关闭自定义金额充值，则接口拒绝 `amount_cny` 下单。

## 当前验证结果
- 后端关键计费回归：通过
  - `backend` 目录下运行相关 pytest 用例，结果 `25 passed`
- 前端生产构建：通过
  - `frontend` 目录下 `npm run build` 通过

## 接管建议
- 不要直接基于 `MONEY_BILLING_MIGRATION_LOG.md` 继续推进，该文件代表的是已偏离产品定义的一条路线。
- 接手时优先看本文件，再看以下文件：
  - `frontend/src/views/admin/AdminConfigPage.vue`
  - `frontend/src/components/BuyCreditsPanel.vue`
  - `backend/app/api/billing.py`
  - `backend/app/api/admin.py`
  - `backend/tests/test_admin_config_validation.py`
  - `backend/tests/test_billing_order_flow.py`

## 后续实施记录模板
- 日期：
- 修改范围：
- 解决的问题：
- 新增/调整测试：
- 验证结果：
- 剩余风险：
