# gw工作日志

最后更新：2026-04-18（第二十八次追加）

## 使用约定
- 这是当前项目的统一接管日志。
- 以后每次重要判断、代码调整、验证结果、阻塞点，都追加到本文件。
- 新会话或新工具进入项目时，优先先读本文件，再继续工作。
- 记录目标：
  - 让上下文不中断
  - 避免重复分析
  - 保留“为什么这样做”的依据
- 强制约定：
  - 后续任何继续工作的工具或人，都必须继续维护本文件。
  - 如果改了代码但没更新本日志，视为工作未完成。
  - 如果要改变 MVP 基线，必须先改文档，再改代码。

---

## 一、项目阶段判断

### 1. 当前主问题
- 项目经历了多轮方向漂移：
  - 积分制
  - 金额制迁移
  - 前后端多页面扩展
  - 推广 / 代理 / 外围业务扩展
  - 算法、支付、后台配置同时并行改动
- 结果是：
  - 全局目标失焦
  - 真相源不唯一
  - 前后端存在口径冲突
  - 外围功能过多，干扰主链路

### 2. 已确认的全局产品方向
- 项目按“学术文稿处理 MVP”收口。
- 核心目标不是大而全，而是：
  - 登录
  - 充值通用点数
  - 提交三类核心任务
  - 获取结果
  - 后台可运营、可退款、可追踪

### 3. 当前定义的主线
- 账户与短信登录主线
- 通用点数与支付主线
- 三类核心任务主线
- 算法包与 LLM 主线
- 小程序来源主线
- 后台运营主线

---

## 二、之前的关键判断

### 1. 通用点数问题的核心结论
- 前端购买页一度绕过后台套餐配置，直接按金额下单。
- 后台配置中心一度保存套餐时丢失 `credits` 字段。
- 任务计费一度仍按“元 / 百字符”换算。
- 当前已经明确：
  - 对外资产口径统一叫“通用点数”
  - 后端内部字段 `credits` 可以保留
  - 任务计费按整数 `点数 / 字符`

### 2. 对项目结构的判断
- 核心功能：
  - 用户登录
  - 通用点数充值 / 余额 / 流水
  - 三类任务：AIGC 检测 / 降重复率 / 降 AIGC 率
  - 订单 / 退款 / 后台配置 / 审计
  - 算法包与 LLM 执行链
  - 小程序登录、支付和来源追踪
- 冻结或删除：
  - 推广中心
  - 分享奖励
  - 班级裂变
  - 代理申请
  - 智能审稿
  - 答辩服务
  - 独立公告配置页
  - 独立系统日志页
  - 独立管理员权限页

---

## 三、早期已完成的事情

### 1. 已完成分析
- 检查了项目当前工作区状态。
- 阅读了项目 README、数据模型、路由、处理引擎、关键页面。
- 确认当前应按 MVP 主线收口，而不是继续金额制或外围增长路线。

### 2. 已输出文档
- 已新增：
  - `CREDIT_SYSTEM_REVIEW_LOG.md`
  - `PROJECT_BASELINE_AND_ROADMAP.md`
- 本文件作为统一接管日志持续维护。

### 3. 已做的代码收缩
- 已移除前端外围页面入口：
  - 用户侧智能审稿
  - 用户侧答辩服务
  - 用户侧推广 / 推荐
  - 后台推广管理
  - 后台公告独立配置页
  - 后台系统日志独立页
  - 后台管理员权限独立页
- 已切断部分后端外围钩子：
  - referral 注册绑定
  - 充值后 referral 奖励触发
  - promo-center 运行入口

---

## 四、早期验证结果

### 1. 前端验证
- 已执行：`frontend` 目录下 `npm run build`
- 结果：通过

### 2. 后端验证
- 已执行：`backend` 目录下 `python -m compileall app`
- 结果：通过

### 3. 后端关键用例
- 多轮关键后端回归已跑过，曾覆盖：
  - 后台配置
  - 订单创建 / 支付 / 退款
  - 认证风控
  - 新用户初始点数
  - 任务提交
  - 用户中心
  - 小程序来源

---

## 五、当前仓库状态判断

### 1. 仍然存在的主要工作
- 基线 4（算法包 / LLM）还需要体系化收口。
- 基线 5（小程序）还需要独立验收。
- 历史 referral / promo 模型仍在库中，作为兼容层保留。
- 仓库当前仍是脏工作区，提交前必须总回归。

### 2. 当前最重要的原则
- 不恢复外围业务。
- 不为了非 MVP 功能补接口、补页面、补测试。
- 短信、支付、LLM、小程序、算法包必须保留。

---

## 六、后续推进顺序

### Phase 1
- 通用点数与支付基线收口。
- 套餐购买、订单、退款、流水统一。

### Phase 2
- 三类任务处理基线收口。
- 提交、扣费、失败退款、状态、下载、后台追踪统一。

### Phase 3
- 算法包与 LLM 基线收口。
- 算法包状态、策略、LLM 降级、错误日志、后台可观测统一。

### Phase 4
- 小程序基线验收。
- 登录、支付、来源追踪、订单任务流水后台可查。

### Phase 5
- 部署前总回归。
- 整理短信、支付、LLM、小程序、算法包、Redis、Celery、数据库环境清单。

---

## 七、接管提醒

- 任何新会话开始时，先看：
  1. `gw工作日志.md`
  2. `PROJECT_BASELINE_AND_ROADMAP.md`
  3. `CREDIT_SYSTEM_REVIEW_LOG.md`
- 如果日志与代码现状不一致，以代码现状为准，并立刻回写本日志。
- 后续每次完成一轮工作，都要补：
  - 改了什么
  - 为什么改
  - 验证结果
  - 剩余问题

---

## 八、通用点数套餐与购买链路回正

### 1. 本轮目标
- 修正“后台配置套餐 -> 前台展示套餐 -> 下单到账点数”这条主交易链。

### 2. 已完成的代码调整
- 后台配置中心恢复套餐 `credits` 输入、保存和校验。
- 前台购买页改为使用 `/billing/packages` 返回的套餐列表。
- 前端主购买流程不再使用硬编码金额档位。
- 下单主流程改为传 `package_name`。
- 当前无套餐时给出清晰提示。

### 3. 判断
- 交易真相源已拉回后台套餐配置。
- 前台买到什么套餐，取决于后台配置，而不是前端自己定义。

### 4. 验证
- 前端构建通过。
- 后端语法检查通过。
- 后端关键计费 / 订单测试通过。

---

## 九、6 档通用点数套餐方案落地

### 1. 套餐方案
- 入门版：19 元，10,000 通用点数
- 基础版：39 元，20,000 通用点数
- 专业版：79 元，50,000 通用点数
- 增强版：149 元，100,000 通用点数
- 高级版：419 元，300,000 通用点数
- 旗舰版：1199 元，1,000,000 通用点数

### 2. 已落地文件
- `backend/app/constants.py`
- `frontend/src/views/admin/AdminConfigPage.vue`
- `frontend/src/components/BuyCreditsPanel.vue`
- `frontend/src/components/TaskJourneyPanel.vue`
- `frontend/src/router/index.js`
- `frontend/src/views/admin/AdminOrderPage.vue`
- `frontend/src/views/user/UserProfilePage.vue`

### 3. 当前原则
- 后端内部仍可沿用 `credits` 字段，不做大规模重命名。
- 对外产品语言统一叫“通用点数”。
- 后台保留套餐可配置能力，默认值以当前 6 档为准。

---

## 十、通用点数口径继续统一

### 1. 本轮目标
- 把“通用点数”口径从前台核心页面继续推进到：
  - 后端接口报错文案
  - 后端流水 reason
  - 用户协议与后台配置说明
  - 后台用户 / 任务 / 订单页面

### 2. 已完成
- 后台任务、用户、用户详情页面统一“通用点数”展示。
- 用户侧记录页统一“消耗通用点数”展示。
- 任务提交不足提示兼容旧“积分不足”和新“通用点数不足”。
- 后端部分原因文案已从“积分”改为“通用点数”。

### 3. 当前判断
- 用户可见 / 运营可见 / 审计可读的主链路口径已经基本统一。
- 如果后续还看到“积分”，需要判断：
  - 内部字段名，允许保留
  - 历史注释或用户可见文案，需要继续清理

---

## 十一、按 MVP 基线继续砍外围

### 1. 本轮判断
- 当前优先级不是恢复外围功能，而是让 MVP 主链稳定：
  - 登录
  - 充值通用点数
  - 提交 3 类核心任务
  - 扣费 / 退款
  - 用户中心与后台可追踪

### 2. 已执行收缩
- 前端后台入口继续收缩：
  - 删除公告配置入口
  - 删除系统日志入口
  - 删除权限管理入口
- 前端路由同步移除：
  - `/admin/configs/notice`
  - `/admin/logs`
  - `/admin/admin-users`
- 删除对应页面文件：
  - `frontend/src/views/admin/AdminNoticeConfigPage.vue`
  - `frontend/src/views/admin/AdminLogsPage.vue`
  - `frontend/src/views/admin/AdminAdminUsersPage.vue`
- 删除已下线推广中心旧测试：
  - `backend/tests/test_promo_center.py`

### 3. 后续约束
- 后端历史服务代码暂不硬删，避免牵连模型和迁移。
- MVP 阶段判断标准：
  - 用户侧核心入口是否通
  - 充值 / 订单 / 通用点数流水是否一致
  - 3 类任务是否能稳定提交、扣费、出结果、失败退款
  - 后台能否看用户、任务、订单、配置、算法

---

## 十二、MVP 基线裁剪与报告固化

### 1. 本轮目标
- 继续删除基线之外的页面、代码和相关资源。
- 明确 MVP 只保留：
  - 短信登录
  - 支付
  - LLM
  - 小程序
  - 算法包
  - 三类核心任务
  - 通用点数交易闭环
  - 用户中心与后台运营

### 2. 删除范围
- 删除后端非 MVP 服务文件：
  - `backend/app/services/promo_center_service.py`
  - `backend/app/services/referral_module.py`
- 删除 referral 相关 Celery 任务。
- 删除 billing 中已经无效的 referral 奖励触发空函数。
- 删除 referral 注册奖励配置字段。
- 删除前端非 MVP 静态资源：
  - `frontend/src/assets/icons/defense-mark.svg`
  - `frontend/src/assets/icons/review-mark.svg`
  - `frontend/src/assets/illustrations/defense-lab.svg`
  - `frontend/src/assets/illustrations/review-workbench.svg`
- 清理用户中心和后台用户详情中的 referral / share 流水展示映射。
- 测试基线切到当前 6 档通用点数套餐。

### 3. 保留范围
- 保留短信、支付、LLM、小程序和算法包相关配置与代码。
- 保留三类核心任务：
  - `aigc_detect`
  - `dedup`
  - `rewrite`
- 保留后台：
  - 总览看板
  - 用户管理
  - 用户详情
  - 任务管理
  - 订单管理
  - 算法配置
  - 配置中心

### 4. 特别判断
- `backend/app/models.py` 中的 referral / promo 历史模型暂不硬删。
- 原因：
  - 直接删除模型可能影响既有数据库结构和历史数据读取。
  - 当前 MVP 要先保证项目可运转。
  - 已经切断运行入口、服务、任务、页面和测试，历史模型只作为兼容层存在。

### 5. 验证
- 前端构建通过。
- 后端语法检查通过。
- 后端 MVP 核心回归曾通过：`61 passed`。

---

## 十三、MVP 基线 2：整数点数字符计费收口

### 1. 本轮目标
- 把基线 2 从“充值是通用点数”推进到“任务计费也完全按通用点数运行”。
- 取消“元 / 百字符”口径，统一改成“整数点数 / 字符”。
- 默认规则固定为：
  - AIGC 检测：`1 字符 = 1 点数`
  - 降重：`1 字符 = 1 点数`
  - 降 AIGC 率：`1 字符 = 1 点数`

### 2. 已落地
- 后端默认计费常量改为整数 1。
- 计费规则解析服务强制整数化。
- 后台配置保存强制要求整数点数字段。
- 任务接口返回统一提供：
  - `cost_points`
  - `cost_fen`
  - `cost_credits`
- 充值下单接口明确禁止自定义金额充值。
- 后台配置页改成按“点数 / 字符”保存。
- 保存时主动清理旧键：
  - `aigc_rate`
  - `dedup_rate`
  - `rewrite_rate`

### 3. 当前基线 2 最终规则
- 充值链路：
  - 用户只能购买固定套餐
  - 套餐支付金额仍然用人民币
  - 套餐到账资产统一叫“通用点数”
- 任务扣费链路：
  - 按字符数直接扣点数
  - 不再使用“元 / 百字符”换算
  - 点数和字符数都按整数处理
- 管理配置：
  - 三类任务单价都按整数 `点数 / 字符`
  - 当前默认值都是 1
  - 后续可配置，但不允许小数

### 4. 验证
- 后端语法检查通过。
- 基线 2 相关测试通过：`41 passed`。

### 5. 后续禁止
- 不要再把任务计费改回金额制。
- 不要再恢复自定义金额充值主流程。
- 不要在前台硬编码充值套餐。

---

## 十四、MVP 基线 3：三类任务处理体系化收口

### 1. 本轮目标
- 体系化收口三类核心任务，而不是只修单点页面。
- 只保留并强化：
  - `aigc_detect`
  - `dedup`
  - `rewrite`

### 2. 当前任务要求
- `aigc_detect`：
  - 上传主文稿
  - AIGC 检测每日免费额度保留
- `dedup`：
  - 上传主文稿
  - 辅助报告可选，不纳入 MVP 主链必填
- `rewrite`：
  - 上传主文稿
  - 辅助报告可选，不纳入 MVP 主链必填

### 3. 已落地能力
- 前台提交页校验任务类型与必需文件。
- 后端任务提交链以主文件为核心，辅助报告允许为空。
- 按字符数扣通用点数。
- 处理失败自动退款。
- 任务接口暴露失败原因和退款状态。
- 用户记录页显示：
  - 任务状态
  - 字符数
  - 消耗通用点数
  - 下载入口
- 后台任务页显示：
  - 任务状态
  - 扣费点数
  - 失败原因
  - 退款状态
  - 结果下载

### 4. 验证
- 后端语法检查通过。
- 前端构建通过。
- 基线 3 关键回归通过：`29 passed`。

### 5. 后续禁止
- 不要只改前台或只改后端，任务基线必须同时检查：
  - 提交页
  - 记录页
  - 任务详情接口
  - 后台任务页
  - 失败退款测试

---

## 十五、当前整体项目状态快照

### 1. 当前阶段判断
- 项目已经从“方向漂移、外围功能过多、口径不统一”的状态，收敛到 MVP 主线。
- 当前最核心的变化：
  - 已冻结非 MVP 能力
  - 已把交易与任务主链改回“通用点数制”
  - 已把三类任务处理链做到前后台都可验收

### 2. 六条基线当前状态
- 基线 1（账户与短信登录）：基本可用，保留短信、微信、小程序登录配置能力。
- 基线 2（通用点数与支付）：已打通，当前按固定套餐充值，任务计费改为整数点数字符。
- 基线 3（三类任务处理）：已完成一版体系化收口，三类任务提交、处理、退款、下载、后台追踪已对齐。
- 基线 4（算法包与 LLM）：代码与配置入口保留，但还缺一轮体系化验收收口。
- 基线 5（小程序）：来源追踪与配置能力保留，但还没有做独立的一轮基线验收。
- 基线 6（后台运营）：主入口已收缩到 MVP 必需范围，用户 / 任务 / 订单 / 配置 / 算法均保留。

### 3. 当前项目最强的部分
- 通用点数交易主线已经清晰：
  - 固定套餐
  - 订单创建
  - 支付到账
  - 点数流水
  - 退款回滚
- 三类任务主线已经基本形成闭环：
  - 上传
  - 校验
  - 扣费
  - 状态流转
  - 失败退款
  - 结果下载
  - 后台追踪

### 4. 当前主要风险
- 基线 4（算法包 / LLM）和基线 5（小程序）还没有像基线 2、3 那样做过完整收口。
- 仓库当前仍是脏工作区，近期做过大量裁剪和主线调整，提交前必须再做一轮总回归。
- 历史 referral / promo 模型仍在库中，虽然运行入口已切断，但仍属于兼容层噪音。

### 5. 当前建议
- 不要再扩需求线。
- 下一步优先做：
  - 基线 4：算法包与 LLM
  - 基线 5：小程序
- 在基线 4、5 收口前，不建议进入部署收尾或恢复外围业务。

---

## 十六、基线 4 准备工作：算法包与 LLM

### 1. 已确认的现状
- 后端已有算法包上传、安装、激活、停用能力。
- 后端已有内置算法包引导。
- 后端已有算法执行策略：
  - `algo_only`
  - `algo_llm`
- 后端已有 LLM 配置能力：
  - provider
  - model
  - API key
  - timeout
  - retry
  - `local_mock`
- 后端已有 LLM 异常日志与模式降级基础。
- 前端后台已有算法配置页面，但还缺一个面向 MVP 验收的运行总览。

### 2. 基线 4 应收口的方向
- 后台需要能直接看到：
  - 算法包槽位覆盖情况
  - 当前策略模式
  - LLM 是否可用
  - 最近 LLM 错误
  - 最近是否发生降级
- 后端需要提供统一 readiness / overview 接口。
- 测试需要锁住：
  - 算法包槽位状态
  - LLM 关闭时算法链可跑
  - LLM 打开且 `local_mock` 时组合链可跑
  - LLM 错误和降级可追踪

### 3. 当前未完成
- 还没有新增基线 4 运行总览接口。
- 还没有把后台算法页升级成“运行状态一眼可验收”的总览。
- 还没有跑完基线 4 专项回归。

---

## 十七、本轮新增进展：补充算法资料投喂规范

### 1. 本轮动作
- 已在桌面新增一份独立文档：
  - `C:\Users\m\Desktop\算法资料投喂规范.md`

### 2. 这份规范解决什么问题
- 解决基线 4 后续资料入口不统一的问题。
- 解决“只有零散算法想法、没有结构化规则和样例”的问题。
- 解决后续把规则资料、LLM 资料、算法实现资料混在一起，导致无法快速接入的问题。

### 3. 规范核心内容
- 明确只围绕 MVP 三类任务收资料：
  - `aigc_detect`
  - `dedup`
  - `rewrite`
- 明确资料目录结构、命名规范、元信息规范。
- 明确区分：
  - 规则资料
  - 样例资料
  - Prompt 资料
  - 阈值 / 评分资料
  - 算法实现资料
- 增加最小可用交付标准，避免后续又收到不可落地的散资料。

### 4. 后续执行要求
- 后续提供算法资料时，优先按 `README + 规则 + 样例 + Prompt/算法协议` 的顺序提供。
- 如果是算法包或伪代码，必须补齐输入输出协议、依赖、入口和超时约束。
- 基线 4 后续实现，将按这份规范继续收口后台可观测、执行链和回归测试。

### 5. 本次日志修复说明
- 本轮写入规范后，曾误用新增文件方式覆盖了 `gw工作日志.md`。
- 已根据本地会话记录和项目报告重建日志主体，并保留第十七节。
- 后续继续工作时仍以本文件、`PROJECT_BASELINE_AND_ROADMAP.md` 和代码现状共同判断。

---

## 十八、本轮新增进展：基线 5（小程序）完成一轮专项收口

### 1. 本轮判断
- 基线 5 不是从零开发。
- 项目原本已经具备：
  - 小程序配置页
  - 小程序登录配置
  - 小程序支付配置
  - 小程序 API / 域名配置
  - `source=miniprogram` 透传
  - 后台按来源筛选用户 / 任务 / 订单
- 这轮工作的重点不是补大功能，而是把“小程序 MVP 验收口径”锁实。

### 2. 本轮实际收口内容
- 后端强化了小程序 readiness 判断：
  - 启用小程序后，基础 `app_id / app_secret` 不能为空
  - `api_base_url` 必须存在且格式正确
  - `request_domain` 必须存在且为 HTTPS
  - 启用小程序支付后，`payment_notify_url` 必须是公网 HTTPS
  - readiness 返回信息会明确显示“小程序登录 / 支付”是否启用
- 后台用户详情补齐了来源追踪字段：
  - 点数流水返回 `source`
  - 任务列表返回 `source`
- 后台配置页补充了“小程序 MVP 验收基线”提示，明确只验收：
  - 登录链
  - 支付链
  - 域名链
  - 来源追踪链

### 3. 本轮新增测试
- 新增并锁定了小程序专项测试点：
  - 小程序配置保存后，支付开关与支付回调地址不会丢
  - 小程序相关域名配置可正确读回
  - 小程序 readiness 能进入 ready
  - 后台用户 / 任务 / 订单按 `miniapp` 来源过滤与统计正常
  - 用户详情中的用户、点数流水、任务都能看到 `miniapp` 来源

### 4. 本轮验证结果
- 后端专项回归通过：
  - `python -m pytest tests\\test_admin_config_validation.py tests\\test_admin_user_detail.py tests\\test_multi_end_source.py tests\\test_billing_order_flow.py -q`
  - 结果：`32 passed`
- 前端构建通过：
  - `cmd /c npm run build`

### 5. 当前对基线 5 的结论
- 基线 5 现在可以视为完成一轮 MVP 收口。
- 当前已经具备的验收口径：
  - 小程序配置能保存
  - 小程序登录配置能透出到认证选项
  - 小程序支付场景能走 `scene=miniprogram`
  - 小程序来源的用户 / 订单 / 任务 / 点数流水能在后台追踪
- 当前暂不继续扩：
  - 小程序新页面
  - 小程序额外业务能力
  - 小程序独立增长玩法

### 6. 后续边界
- 基线 5 后续只在两种情况下继续动：
  - 真机联调发现配置或支付链还有实际问题
  - 部署阶段需要补环境变量、域名或微信侧配置核对
- 在此之前，不再扩小程序功能面，继续回到其他基线。

---

## 十九、本轮新增进展：基线 6（后台运营）完成一轮体系化收口

### 1. 本轮判断
- 基线 6 的问题已经不是“后台入口不够”，而是“后台首页还不够像真正的运营总控面板”。
- 当前后台 6 个 MVP 入口本身都还在：
  - 总览看板
  - 用户管理
  - 任务管理
  - 订单管理
  - 算法配置
  - 配置中心
- 这轮的重点不是新增后台页面，而是把这 6 个入口的验收状态集中到总览页，让运营打开后台就能判断：
  - 现在能不能跑
  - 哪些配置没就绪
  - 哪些异常需要先处理

### 2. 本轮实际收口内容
- 后端 `/api/v1/admin/dashboard` 新增了后台基线状态聚合：
  - `mvp_baseline`
  - `operational_alerts`
  - `ops_summary`
- 其中 `mvp_baseline` 会直接汇总：
  - 登录
  - 支付
  - 计费
  - 任务处理
  - 算法 / LLM
  - 小程序
- `operational_alerts` 会直接提示当前需要处理的后台异常：
  - 失败任务
  - 失败后未退款任务
  - 支付仍处于联调模式
  - 小程序配置异常
  - 最近 24 小时 LLM 异常
- 总览页已升级为“后台运营基线状态 + 待处理事项 + 关键运营指标”三块，不再只有趋势图。

### 3. 本轮没有扩的内容
- 没有恢复独立公告页、独立系统日志页、独立管理员权限页。
- 没有新增非 MVP 的后台业务模块。
- 没有扩新的运营功能线。
- 仍然坚持“后台只服务 MVP 主链”。

### 4. 本轮新增测试
- 新增后台总览专项测试：
  - `backend/tests/test_admin_dashboard.py`
- 这轮锁定了：
  - dashboard 返回 `mvp_baseline`
  - dashboard 返回 `operational_alerts`
  - dashboard 返回 `ops_summary`
  - 小程序来源统计、失败任务、待退款任务、LLM 异常、支付联调状态都能体现在总览

### 5. 本轮验证结果
- 后端后台运营专项回归通过：
  - `python -m pytest tests\\test_admin_dashboard.py tests\\test_admin_permissions.py tests\\test_admin_order_refund.py tests\\test_admin_task_download.py tests\\test_admin_user_detail.py tests\\test_admin_switch_logs.py -q`
  - 结果：`17 passed`
- 前端构建通过：
  - `cmd /c npm run build`

### 6. 当前对基线 6 的结论
- 基线 6 现在可以视为完成一轮 MVP 收口。
- 当前后台已经满足 MVP 运营要求：
  - 能看系统总体状态
  - 能查用户与点数
  - 能查任务与结果下载
  - 能查订单与退款
  - 能查算法与配置 readiness
  - 能在首页直接看到待处理异常

### 7. 后续边界
- 基线 6 后续只建议继续做两类事情：
  - 真部署前补更真实的环境 readiness
  - 真运营中根据实际故障再补更高价值的异常看板
- 在此之前，不恢复非 MVP 后台页面，不再扩后台管理面。

---

## 二十、本轮新增进展：后台左侧导航栏固定与间距优化

### 1. 本轮动作
- 调整后台通用壳层：
  - `frontend/src/components/AdminShell.vue`

### 2. 解决的问题
- 后台左侧导航栏在桌面端改为视口内固定体验：
  - 上下顶住当前页面可视区域
  - 不随右侧业务页面内容滚动而滚动
  - 左侧导航自身内容超出时独立滚动
- 重新整理导航按钮间距：
  - 增加按钮上下间距
  - 增加按钮高度和内边距
  - 折叠态按钮保持居中和合理点击面积

### 3. 验证结果
- 前端构建通过：
  - `cmd /c npm run build`

### 4. 后续边界
- 本次只调整后台壳层样式。
- 没有改业务路由、权限、接口和后台页面功能。

---

## 二十一、本轮新增进展：降重 / 降AIGC率辅助报告改为隐藏可选

### 1. 本轮动作
- 调整用户侧两个提交页：
  - `frontend/src/views/user/UserDedupPage.vue`
  - `frontend/src/views/user/UserRewritePage.vue`

### 2. 解决的问题
- 降重复率页面原先强制上传“全文查重报告”。
- 降AIGC率页面原先强制上传“全文AIGC检测报告”。
- 当前 MVP 阶段，这两个辅助报告字段改为可选，并且前台暂时隐藏上传入口。

### 3. 实际处理方式
- 页面上移除了辅助报告上传区域。
- 表单校验不再要求 `reportFile` 必填。
- 提交时只有存在 `reportFile` 才追加 `report` 字段。
- 保留现有报告字段和上传函数，避免后续重新开放时破坏兼容。

### 4. 验证结果
- 前端构建通过：
  - `cmd /c npm run build`

### 5. 后续边界
- 后端报告字段暂不删除。
- 记录页和后台中已有的“是否有报告”展示暂时保留，用于兼容历史任务。

---

## 二十二、本轮新增进展：后台导航栏修正为真正固定侧栏

### 1. 修正原因
- 上一版后台导航栏只做成了 `sticky` 视口内停靠。
- 这不满足当前要求：
  - 顶部顶住页面最上
  - 底部顶住页面最下
  - 不随右侧页面滚动而移动

### 2. 本轮修正内容
- 继续调整：
  - `frontend/src/components/AdminShell.vue`
- 桌面端后台左侧导航改为真正固定侧栏：
  - `position: fixed`
  - `top: 0`
  - `bottom: 0`
  - `left: 0`
- 右侧主内容区改为整体让出左侧栏宽度：
  - 使用 `margin-left: var(--admin-sidebar-width)`
- 左侧导航区域自身超出时独立滚动，右侧业务内容滚动不会带动左侧栏。

### 3. 当前结果
- 现在桌面端后台导航栏是固定贴住视口上下边的，不再跟随右侧页面滑动。
- 移动端抽屉导航逻辑保持不变。

### 4. 验证结果
- 前端构建通过：
  - `cmd /c npm run build`

### 5. 二次修正
- 用户反馈左侧仍然会动。
- 重新排查后确认根因：
  - `AdminShell` 最外层带有 `academic-shell-enter`
  - 全局 `academic-shell-enter` 动画使用了 `transform: translateY(...)`
  - CSS 中 `position: fixed` 如果位于带 transform 的祖先元素内，会相对该祖先定位，而不是真正固定到视口
- 已移除后台壳层上的 `academic-shell-enter` 类。
- 当前后台侧栏的 fixed 定位不再受入场动画 transform 影响。
- 前端构建再次通过：
  - `cmd /c npm run build`

---

## 二十三、本轮新增进展：任务提交链稳定化与高并发约束收口

### 1. 本轮背景
- 用户反馈主任务链长期存在不稳定现象：
  - 提交后记录页有时看不到新任务
  - 退出再登录后记录短暂为零，稍后又恢复
  - 新任务刚提交时字符数、扣点、状态不稳定
- 这轮不是打补丁，而是按 MVP 主链要求，对“提交 -> 记录 -> 扣点 -> 排队 -> 处理”做一轮体系化收口。
- 同时新增一个明确约束：
  - 方案必须考虑高并发提交场景，不能只在低并发下成立。

### 2. 本轮核心设计判断
- 不新增一套全新状态枚举，避免改动面过大、牵连历史数据与前端状态映射。
- 继续沿用现有状态，但明确状态职责：
  - `preprocessing`：任务已接收，正在做提交预处理 / 计费准备
  - `pending`：测试环境下已完成字符统计与扣点
  - `queued`：字符数与扣点已落地，等待算法执行
  - `running`：算法处理中
  - `completed / failed`：最终态
- 结论：
  - 任务是否成立，不能再依赖异步处理结果来“补成立”
  - 前端必须以任务快照和任务详情接口为准做强跟踪
  - 并发控制必须尽量原子化，不能再依赖“先读后加”的弱控制

### 3. 本轮实际落地内容
- 后端提交链：
  - `backend/app/api/tasks.py`
  - `backend/app/worker_tasks.py`
- 前端提交与记录页：
  - `frontend/src/lib/taskSubmitFlow.js`
  - `frontend/src/lib/userRecords.js`
  - `frontend/src/views/user/UserRewritePage.vue`
  - `frontend/src/views/user/UserDedupPage.vue`
  - `frontend/src/views/user/UserDetectPage.vue`
  - `frontend/src/views/user/UserRewriteRecordsPage.vue`
  - `frontend/src/views/user/UserDedupRecordsPage.vue`
  - `frontend/src/views/user/UserDetectRecordsPage.vue`
- 测试补充：
  - `backend/tests/test_task_submission_chain.py`

### 4. 后端本轮改动要点
- 提交接口返回统一任务快照，不再只返回零散字段：
  - 任务 id / 类型 / 平台 / 状态
  - 字符数
  - 扣点
  - 退款状态
  - `billing`
  - `balance_after`
  - `created_at / updated_at`
- 幂等命中时，也返回同样结构的完整任务快照，避免前端进入两套分支逻辑。
- 提交积压控制从“先读 backlog，再 incr”收口为“先原子占位，再校验是否超限”：
  - 降低高并发穿透风险
  - 占位失败时立即释放
- 处理并发槽位也改成“先 incr，再校验，失败则回滚计数”：
  - 降低多个 worker 并发争抢时的超限误放行风险

### 5. 前端本轮改动要点
- 提交成功跳转记录页时，统一带上：
  - `focus=<taskId>`
  - `submitted=1`
- 三类提交页在拿到后端任务快照后，会先用 `balance_after` 本地更新用户余额，再异步 `refreshUser()`：
  - 避免提交成功后前台点数仍短暂显示旧值
- 三类记录页轮询条件不再依赖“当前列表里已经有 processing 任务”：
  - 只要存在聚焦任务但列表里还没拿到
  - 或聚焦任务还处于处理中状态
  - 或当前确实存在处理中任务
  - 就继续轮询
- 这样即使首屏列表没及时拉到刚提交的新任务，也不会直接停轮询。

### 6. 本轮直接解决的问题
- 提交成功后，新任务更容易稳定出现在记录页，不再严重依赖“刚好第一页就拉到它”。
- 用户点数在提交成功后可优先用后端返回快照更新，不再只依赖后续刷新。
- 高并发下提交积压限制与处理并发限制比之前更稳，减少超限穿透。
- 前端、后端对任务状态的理解更统一，减少“前端猜状态”的不确定性。

### 7. 本轮没有做的事情
- 没有新增新的数据库状态枚举。
- 没有把全文解析和扣点全部强行塞回同步接口执行。
- 没有删除现有二段 worker 架构。
- 原因：
  - 当前项目已经具备 submission queue + processing queue 的雏形
  - 在考虑高并发的前提下，保留异步分层更安全
  - 这轮重点是把现有链路改成稳定可追踪，而不是把重活重新塞回 API

### 8. 本轮验证结果
- 前端构建通过：
  - `cmd /c npm run build`
- 后端任务链专项测试通过：
  - `python -m pytest -q tests\\test_task_submission_chain.py tests\\test_task_end_to_end_flows.py tests\\test_task_billing_config.py tests\\test_task_chain_guard.py`
  - 结果：`15 passed`
- 后端语法编译通过：
  - `python -m compileall backend\\app`

### 9. 当前结论
- 这轮之后，任务链从“弱一致 + 首屏碰运气拉到任务”往“任务快照稳定 + 记录页强跟踪 + 并发控制收口”推进了一大步。
- 仍然保留了 MVP 所需的可扩展性：
  - 后续接短信、支付、LLM、算法包、小程序时，不需要推翻当前任务链。
- 后续如继续加强，应优先做：
  - 提交 worker / 处理 worker 的监控指标
  - 更细的提交链超时告警
  - 必要时补单任务详情优先轮询的统一前端封装

### 10. 本轮二次收口：修复真实环境中的任务列表卡死问题
- 用户真实回归后发现：
  - 提交后虽然会跳到记录页，但记录页长时间停留在“加载中”
  - 离开记录页再回来时，任务列表会短时间像是 0
  - 过较长时间后才恢复
- 这不是前端展示问题，而是后端真实运行时的锁竞争问题。
- 排查日志确认根因：
  - 本地 fallback worker 在 `preprocess_submission_async` 中对任务行使用了 `FOR UPDATE`
  - `process_task_async` 也在长事务里持有任务行锁
  - 用户侧任务列表接口的链路保护扫描也会对处理中任务加锁
  - 三者叠加后，MySQL 出现 `maximum statement execution time exceeded`
- 本轮已补的修复：
  - 任务列表相关 guard 不再为扫描处理中任务而锁定任务行
  - worker 不再在长事务中持有任务行锁跑算法
  - `RUNNING` 状态先提交，再脱离长事务执行处理
  - 新增任务原子认领：
    - `PREPROCESSING -> PENDING`
    - `PENDING/QUEUED -> RUNNING`
  - 保证同一任务不会因为去掉长锁而被多个 worker 重复处理
- 二次收口后再次验证：
  - `python -m compileall backend\\app`
  - `python -m pytest -q tests\\test_task_submission_chain.py tests\\test_task_end_to_end_flows.py tests\\test_task_billing_config.py tests\\test_task_chain_guard.py`
  - 结果：`15 passed`

---

### 11. 本轮新增进展：基线4算法包体系继续收口
- 本轮目标：
  - 继续压缩基线4复杂度，不再让后台同时维护“平台枚举 + 槽位激活 + 策略配置”三套心智。
  - 平台先按 MVP 收敛到 `cnki` 与 `vip`。
  - 把非 MVP 第三平台从代码、配置、测试、小程序入口和本地算法包目录中移除。
- 本轮新增结构：
  - 新增统一平台注册层：`backend/app/services/platform_registry.py`
  - 平台来源开始统一收口到这一层，前后端不再各自硬编码多个预置平台。
  - 算法后台页从“算法包与策略”收口为“算法执行配置”：
    - `frontend/src/views/admin/AdminAlgoPackagePage.vue`
  - 后端补了执行配置别名接口：
    - `GET /api/v1/admin/execution-configs`
    - `PUT /api/v1/admin/execution-configs/{task_type}/{platform}`
- 当前后台运营心智已简化为：
  - 平台
  - 任务类型
  - 当前版本
  - 运行模式
  - 是否开放
  - 超时
- 非 MVP 第三平台删除范围：
  - Web 前端：
    - `frontend/src/lib/taskPlatform.js`
    - `frontend/src/views/user/UserDetectPage.vue`
    - `frontend/src/views/admin/AdminAlgoPackagePage.vue`
  - 小程序：
    - `miniapp/pages/home/index.js`
    - `miniapp/utils/display.js`
  - 后端服务：
    - `backend/app/services/algo_package_service.py`
    - `backend/app/services/process_strategy_service.py`
    - `backend/app/services/builtin_algo_packages.py`
    - `backend/app/services/processing_engine.py`
    - `backend/app/api/admin.py`
  - 测试与说明：
    - `backend/tests/test_process_strategies.py`
    - `backend/tests/test_algo_packages.py`
    - `backend/tests/test_processing_engine_results.py`
    - `backend/docs/ALGO_PACKAGE_AUTHORING_GUIDE.md`
  - 本地算法包目录已删除：
    - `backend/algorithm_packages/<removed-third-platform>`
- 本轮判断依据：
  - 当前 MVP 不需要三平台并行，继续保留第三平台只会增加平台枚举维护、算法模板维护、测试矩阵和后台认知成本。
  - 现阶段更重要的是把 `cnki` 与 `vip` 两条主线跑稳，并把后续新增平台能力留在统一平台注册层。
- 本轮验证结果：
  - 后端语法编译通过：
    - `python -m compileall backend\\app`
  - 基线4关键测试通过：
    - `python -m pytest -q tests\\test_process_strategies.py tests\\test_algo_packages.py tests\\test_processing_engine_results.py`
    - 结果：`43 passed`
  - 前端构建通过：
    - `cmd /c npm run build`
- 当前状态结论：
  - 基线4已经从“平台、槽位、策略多头并存”继续往“统一执行配置”收口。
  - 第三平台已经不再属于当前 MVP 主链。
  - 后续如果重新引入新平台，不应再回到多处硬编码，而应接在平台注册层和执行配置层上。

### 12. 本轮继续推进：算法后台改为综合表，并支持新增平台
- 本轮目标：
  - 不再让算法后台拆成“平台枚举 + 执行配置 + 版本库”三块分散认知。
  - 改成一个综合主表，后台可直接新增平台，并在同一页配置平台状态、任务状态、当前版本、运行模式和超时。

### 13. 后端本轮新增能力
- 平台注册改成 `SystemConfig` 驱动：
  - `backend/app/services/platform_registry.py`
  - 配置分类：`algo_platforms_v1`
- 平台现在不再只能写死在代码里，支持后台新增：
  - `key`
  - `label`
  - `aigc_label`
  - `task_types`
  - `enabled`
  - `sort_order`
- 新增综合表接口：
  - `GET /api/v1/admin/algo-config/table`
- 新增平台接口：
  - `POST /api/v1/admin/algo-config/platforms`
- 新增平台后，会自动为勾选的任务类型生成默认执行配置。

### 14. 前端本轮新增能力
- 算法后台页已改为综合表：
  - `frontend/src/views/admin/AdminAlgoPackagePage.vue`
- 当前页面结构：
  - 顶部：全局模式 + 新增平台 + 刷新
  - 中部：平台与任务综合表
  - 底部：算法版本库（辅助区）
- 综合表单行可直接配置：
  - 平台状态
  - 任务开放状态
  - 当前版本
  - 最新版本
  - 运行模式
  - 超时
- 新增平台弹窗已落地：
  - 平台标识
  - 平台名称
  - AIGC 展示名称
  - 排序
  - 是否启用
  - 支持任务类型

### 15. 本轮关键判断
- 这轮仍然没有引入新数据库表，而是继续沿用 `SystemConfig`，这样风险更小，适合当前 MVP。
- 平台新增能力先做“可配置注册”，而不是一步到位做完整平台管理系统。
- 版本库保留，但降级成辅助区，正式启用哪个版本，以综合表中的“当前版本”为准。

### 16. 本轮验证结果
- 后端语法编译通过：
  - `python -m compileall backend\\app`
- 综合表专项测试通过：
  - `python -m pytest -q tests\\test_process_strategies.py`
  - 结果：`9 passed`
- 前端构建通过：
  - `cmd /c npm run build`

### 17. 当前状态结论
- 算法后台已经不再只是“执行配置页”，而是进入“综合表驱动”阶段。
- 后台现在已经具备：
  - 新增平台
  - 自动生成默认任务配置
  - 在同一页配置平台、任务、版本、模式、超时
- 后续若继续加强，优先做：
  - 平台编辑
  - 历史版本列表弹窗
  - 上传算法包入口并入综合页顶部
  - 逐步清理旧 `/strategies` 兼容层

### 18. 本轮最终收口：综合表补齐上传、历史版本与下载闭环
- 本轮继续补齐了算法后台综合表的最后一段主链，目标是不再让后台运营在“配置页、上传页、版本列表”之间来回切换。
- 已确认前端综合页 `frontend/src/views/admin/AdminAlgoPackagePage.vue` 现在包含：
  - 综合表主视图
  - 新增/编辑平台弹窗
  - 上传算法包弹窗
  - 历史版本弹窗
  - 底部版本库辅助区
- 已确认后端接口链路现在完整可用：
  - `GET /api/v1/admin/algo-config/table`
  - `POST /api/v1/admin/algo-config/platforms`
  - `GET /api/v1/admin/execution-configs`
  - `PUT /api/v1/admin/execution-configs/{task_type}/{platform}`
  - `GET /api/v1/admin/algo-packages/history`
  - `GET /api/v1/admin/algo-packages/download`

### 19. 本轮补修的问题与判断
- 修复了算法包下载链路中的一个回归问题：
  - 文件：`backend/app/services/algo_package_service.py`
  - 症状：下载归档时调用槽位校验，但函数内部没有 `db`，会触发 `NameError`
  - 处理：为 `get_algorithm_package_archive_path(...)` 增加 `db` 参数，并在 `backend/app/api/admin.py` 下载路由中透传 `db`
- 这样做的原因：
  - 当前平台已改为动态注册，下载归档时也必须走同一套平台注册校验
  - 不能为了临时过测试再退回静态平台判断，否则后续新增平台又会在下载链路上失真

### 20. 本轮最终验证结果
- 后端语法编译通过：
  - `python -m compileall backend\\app`
- 算法配置与版本链路回归通过：
  - `python -m pytest -q tests\\test_process_strategies.py tests\\test_algo_packages.py`
  - 结果：`26 passed`
- 处理引擎结果回归通过：
  - `python -m pytest -q tests\\test_processing_engine_results.py`
  - 结果：`19 passed`
- 前端构建通过：
  - `cmd /c npm run build`

### 21. 当前基线4实际完成状态
- 基线4当前已经具备 MVP 可运转所需的核心能力：
  - 平台可配置注册
  - 平台支持任务类型配置
  - 算法包上传
  - 算法包激活/切换
  - 综合表统一配置任务执行
  - 历史版本查看
  - 算法包归档下载
- 当前仍属于“后续增强”而非必须立即继续做的内容：
  - 更完整的平台治理能力
  - 更细粒度的版本对比与灰度控制
  - 清理旧 `/strategies` 兼容接口

### 22. 本轮补修：算法综合表空白问题
- 现场问题：
  - 后台“平台与任务综合表”区域没有内容。
- 排查结论：
  - 后端不是没数据。
  - 本地直接查数据库与服务层结果，当前有：
    - 2 个平台：`cnki`、`vip`
    - 6 条平台任务配置行
  - `GET /api/v1/admin/algo-config/table` 也能返回 6 条配置。
- 真正风险点：
  - 前端 `AdminAlgoPackagePage.vue` 原来只依赖 `/admin/algo-config/table.items` 渲染综合表。
  - 如果接口初始化时序、旧数据兼容或返回层级出现短暂空数组，页面会直接显示空白，不能从平台注册表兜底生成基础行。
- 本轮处理：
  - 将综合表前端改为三路合成：
    - 平台注册表 `platformConfigs`
    - 执行配置 `executionConfigs`
    - 算法包/版本信息 `rows`、`slots`
  - 即使执行配置为空，也会根据平台注册表和任务类型生成基础行。
  - 这样默认至少能稳定展示 `cnki/vip × aigc_detect/dedup/rewrite` 六行。
- 修改文件：
  - `frontend/src/views/admin/AdminAlgoPackagePage.vue`
- 验证：
  - 前端构建通过：
    - `cmd /c npm run build`

### 23. 本轮补修：彻底清除第三平台历史残留
- 这次不是只删运行代码里的第三平台残留，而是把项目内所有历史文本口径也一起清掉。
- 已处理范围：
  - 训练记忆文档：
    - `docs/AIGC_ALGO_TRAINING_MEMORY.md`
    - `docs/DEDUP_ALGO_TRAINING_MEMORY.md`
    - `docs/REWRITE_ALGO_TRAINING_MEMORY.md`
  - 结果评价框架：
    - `docs/AIGC_DETECT_RESULT_EVAL_FRAMEWORK.md`
    - `docs/DEDUP_RESULT_EVAL_FRAMEWORK.md`
    - `docs/REWRITE_RESULT_EVAL_FRAMEWORK.md`
  - 训练工作区与资料盘点：
    - `docs/ALGO_PACKAGE_TRAINING_WORKSPACE.md`
    - `docs/ALGO_PACKAGE_MATERIAL_STATUS.md`
    - `docs/ALGO_PACKAGE_MATERIAL_UPDATE_2026-04-10.md`
    - `docs/ALGO_MATERIAL_REUSE_STRATEGY.md`
    - `scripts/inventory_algo_training_workspace.py`
    - `docs/prd_tables_dump.txt`
- 本轮统一口径：
  - 从“三平台 / 9 个算法包槽位”改为“双平台 / 6 个算法包槽位”
  - 训练资料目录只保留：
    - `知网资料包`
    - `维普资料包`
  - 不再保留任何第三平台命名、槽位命名或资料规范
- 本轮验证：
  - 全项目全文检索：
    - `PaperPass|paperpass|pp_aigc|pp_dedup|pp_rewrite`
  - 结果：已无命中

### 24. 本轮补修：算法配置页仍出现旧平台
- 现场问题：
  - 虽然代码和文档里已经删掉第三平台，但算法配置页里仍然还能看到旧平台痕迹。
- 排查结论：
  - 前端页面代码里已经没有第三平台硬编码。
  - 真正残留在数据库里的是 `SystemConfig` 的旧执行配置：
    - `aigc_detect:paperpass`
    - `dedup:paperpass`
    - `rewrite:paperpass`
- 本轮处理：
  - 服务层补过滤：
    - `backend/app/services/algo_package_service.py`
    - `list_algorithm_packages(db)` 现在只会返回当前平台注册表中存在的平台目录和槽位。
  - 数据库残留清理：
    - 删除 `process_strategies_v1` 分类下上述 3 条旧配置。
- 本轮验证：
  - 数据源复查结果：
    - `platforms = ['cnki', 'vip']`
    - `strategy_platforms = ['cnki', 'vip']`
    - `slot_platforms = ['cnki', 'vip']`
    - `item_platforms = ['cnki', 'vip']`
  - 前端构建通过：
    - `cmd /c npm run build`
  - 后端回归通过：
    - `python -m pytest -q tests\\test_process_strategies.py tests\\test_algo_packages.py`
    - 结果：`26 passed`

### 25. 本轮新增结论：按最新代码状态重评 MVP 六条基线
- 这轮不是继续补代码，而是按“当前真实代码和运行态”重新评估六条 MVP 基线，避免沿用旧报告口径。
- 当前结论：
  - 基线 1（账户与登录）：可用
  - 基线 2（通用点数与支付）：可用
  - 基线 3（三类任务处理）：基本可用，但存在一处基线口径漂移
  - 基线 4（算法包与 LLM）：基本可用，已接近一轮完整收口
  - 基线 5（小程序）：可用
  - 基线 6（后台运营）：可用
- 当前最重要的体系问题不是“还有多少功能没做”，而是“基线 3 与基线 4 的输入假设是否一致”：
  - 旧报告把 `dedup / rewrite` 定义为“必须上传全文报告”
  - 当前真实代码里，用户页和提交接口都已经允许无辅助报告提交
  - 这会直接影响算法包训练、执行链和项目验收口径
- 当前判断：
  - 项目已经具备 MVP 可运转能力
  - 后续最优先不是扩功能，而是统一这处基线定义，再回写正式项目报告

### 26. 本轮新增进展：基线 3 按“报告可选且不展示”正式收口
- 最新产品定义已经固定：
  - `dedup`、`rewrite` 的辅助报告不是 MVP 主链必填项
  - 前台页面不展示“报告是否上传”
  - 后台任务查看不再把辅助报告作为显性运营信息
- 本轮已同步修改：
  - `PROJECT_BASELINE_AND_ROADMAP.md`
  - `frontend/src/views/user/UserDedupRecordsPage.vue`
  - `frontend/src/views/user/UserRewriteRecordsPage.vue`
  - `frontend/src/views/admin/AdminTaskPage.vue`
  - `frontend/src/views/admin/AdminUserDetailPage.vue`
- 本轮收口后的基线 3 只强调：
  - 主文件上传
  - 字符数统计
  - 点数扣费
  - 状态流转
  - 失败退款
  - 结果下载
- 判断依据：
  - 用户已明确要求“那个报告是可选的，页面也不用出现”
  - 当前 MVP 应优先保证主链稳定，不再放大辅助报告链

### 27. 本轮新增进展：充值页改为 6 套餐卡片 + 支付二维码弹窗
- 本轮目标：
  - 不再使用“金额按钮 + 页面下方二维码”的旧交互。
  - 充值页直接展示 6 个套餐卡片，点击后再弹出二维码支付弹窗。
- 本轮改动：
  - 重写 `frontend/src/components/BuyCreditsPanel.vue`
  - 页面结构调整为：
    - 顶部口径说明
    - 6 个套餐卡片
    - 点击卡片后弹出支付弹窗
- 文案口径采用方案 B（偏专业稳重型）：
  - 卡片展示：
    - 套餐名
    - 金额
    - 通用点数
    - 使用场景
    - 按 `8000 字 / 篇` 的估算处理量
  - 统一说明：
    - 当前按字符数扣减通用点数
    - 估算统一按 `8000 字 / 篇` 文稿计算
- 支付弹窗保留现有主链能力：
  - 创建订单
  - 拉取二维码
  - 倒计时
  - 轮询支付状态
  - 刷新二维码
  - mock 联调支付
- 本轮额外收口：
  - 关闭支付弹窗时会停止当前订单轮询和倒计时
  - 弹窗内部直接展示支付成功 / 失败提示
- 本轮验证：
  - 前端构建通过：
    - `cmd /c npm run build`

### 28. 本轮补收口：充值页继续压缩首屏高度
- 现场目标：
  - 保留 6 张套餐卡片和支付弹窗交互不变。
  - 尽量让桌面端一屏内装下完整套餐区。
- 本轮调整：
  - 继续压缩 `frontend/src/components/BuyCreditsPanel.vue` 的首屏密度：
    - 顶部标题区更紧凑
    - 右侧口径提示块更小
    - 卡片高度、内边距、字号、按钮高度继续下调
    - 卡片间距继续缩小
- 本轮原则：
  - 只压视觉密度，不再动支付链路和文案结构。
  - 保留：
    - 6 套餐卡片
    - 点击后二维码弹窗
    - 估算口径
    - 下单 / 轮询 / 刷新二维码 / mock 支付
- 本轮验证：
  - 前端构建通过：
    - `cmd /c npm run build`

### 29. 本轮收尾：清理本地脏文件并准备提交部署
- 本轮清理：
  - 删除本地运行残留日志：
    - `backend/run_backend_*.log`
    - `frontend/run_frontend_*.log`
    - `frontend/runtime_*local.log`
  - `.gitignore` 已新增忽略规则，避免后续这些本地日志反复污染工作区。
- 本轮补修：
  - `backend/tests/test_user_profile_summary.py`
  - 旧断言仍按历史费率预期第 7 次 AIGC 提交扣 `3` 点。
  - 当前基线 2 已改为“按字符整数扣点”，测试样例正文为 `10` 字符，因此断言更新为扣 `10` 点，账户余额同步更新为 `90`。
- 提交前验证：
  - 前端构建通过：
    - `cmd /c npm run build`
  - 后端关键回归通过：
    - `python -m pytest -q tests\\test_billing_order_flow.py tests\\test_task_submission_chain.py tests\\test_user_profile_summary.py tests\\test_process_strategies.py tests\\test_algo_packages.py`
    - 结果：`50 passed`
