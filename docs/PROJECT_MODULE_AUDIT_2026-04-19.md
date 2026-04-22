# 项目模块化深度审计

最后更新：2026-04-19

## 1. 审计目的

本审计不是重新发明目录结构，而是给当前项目建立一套可长期执行的模块归属标准，确保后续：

- 增加功能时不继续堆巨型文件。
- 修复问题时能快速定位到正确模块。
- 做重构时先收职责，再搬代码。
- 后来的人或工具能沿着同一套边界继续维护。

本审计统一采用 `8 个大模块` 作为项目主结构。

## 2. 8 个大模块

### 2.1 认证与账户模块

负责：

- 用户登录、短信验证码、微信登录、小程序登录。
- 用户资料、账户基础信息。
- 管理员登录、权限、会话。

建议小模块：

- `user_auth`
- `admin_auth`
- `profile`
- `permissions`

### 2.2 计费与订单模块

负责：

- 套餐、订单、支付、支付回调、退款。
- 通用点数余额与流水。

建议小模块：

- `packages`
- `orders`
- `payment`
- `refunds`
- `credits`

### 2.3 任务中心模块

负责：

- 任务提交、上传、参数校验、报告校验。
- 频控、幂等、防积压。
- 任务列表、详情、下载、删除。

建议小模块：

- `submit`
- `validators`
- `rate_limit`
- `idempotency`
- `task_query`
- `artifacts`

### 2.4 后台执行模块

负责：

- Celery / 本地回退。
- 预处理、正式处理、失败补偿、退款补偿。
- 并发锁、清理任务产物。

建议小模块：

- `dispatcher`
- `preprocess_handler`
- `process_handler`
- `cleanup_handler`
- `compensation`
- `locks`

### 2.5 处理编排模块

负责：

- 处理链的总编排。
- 输入读取与标准化。
- 按任务类型、平台选处理链。
- 调用策略并组装统一结果。

建议小模块：

- `orchestrator`
- `input_loader`
- `task_router`
- `rewrite_pipeline`
- `dedup_pipeline`
- `detect_pipeline`
- `result_builder`

### 2.6 策略中心模块

负责：

- 平台 / 任务类型 / 策略模式的具体实现。
- 知网 / 维普差异规则。
- 算法策略与大模型策略。
- 后续降重复率、AIGC 检测策略扩展。

建议小模块：

- `strategy_registry`
- `strategy_config`
- `rewrite_cnki_algorithm`
- `rewrite_cnki_llm`
- `rewrite_vip_algorithm`
- `rewrite_vip_llm`
- 后续 `dedup_*`
- 后续 `detect_*`

### 2.7 结果与报告模块

负责：

- 统一结果结构。
- Metadata 构建。
- 报告视图、报告渲染、PDF 输出。

建议小模块：

- `schemas`
- `metadata_builder`
- `report_builder`
- `pdf_renderer`
- `serializer`

### 2.8 系统支撑模块

负责：

- 系统配置、配置中心支撑逻辑。
- 文件存储。
- 日志、审计、运行记录。
- 环境配置、部署、脚本、基础设施。

建议小模块：

- `configs`
- `admin_configs`
- `storage`
- `logs`
- `audit`
- `infra`

## 3. 当前源码归属清单

以下是按“当前项目已有代码”做的模块归属，不代表目录已经拆好，只代表职责应该归属到哪里。

### 3.1 后端 API 层

#### 认证与账户模块

- `backend/app/api/auth.py`
- `backend/app/api/users.py`

说明：

- `auth.py` 里混有登录配置读取、公告、短信、微信、小程序登录逻辑。
- `users.py` 里主要是用户资料、账户摘要、通知、流水查询，但也依赖了任务结果清洗逻辑。

#### 计费与订单模块

- `backend/app/api/billing.py`

说明：

- 套餐、订单、支付、mock 支付、支付回调主入口都在这里。

#### 任务中心模块

- `backend/app/api/tasks.py`

说明：

- 当前此文件同时承担提交入口、文件校验、幂等、频控、积压控制、恢复提交、下载、删除。

#### 系统支撑模块

- `backend/app/api/router.py`

说明：

- 这是 API 总装配入口，属于系统支撑，不属于具体业务域。

#### 当前严重混装文件

- `backend/app/api/admin.py`

当前它同时属于：

- 认证与账户模块
- 计费与订单模块
- 任务中心模块
- 策略中心模块
- 系统支撑模块

后续必须拆为后台域子路由，不应继续作为单体后台总线。

### 3.2 后端服务层

#### 认证与账户模块

- `backend/app/services/aigc_quota_service.py`
- `backend/app/services/user_navigation_service.py`

说明：

- `aigc_quota_service.py` 更接近账户权益。
- `user_navigation_service.py` 是前台导航配置支撑，归系统支撑也可以，但当前更靠账户 / 前台配置能力。

#### 计费与订单模块

- `backend/app/services/credit_service.py`
- `backend/app/services/billing_rules_service.py`
- `backend/app/services/payment_service.py`

#### 处理编排模块

- `backend/app/services/processing_engine.py`

说明：

- 当前是全项目最重的编排核心，但已经侵入策略、报告、PDF、检测算法等多类职责。

#### 策略中心模块

- `backend/app/services/rewrite_strategies/__init__.py`
- `backend/app/services/rewrite_strategies/config.py`
- `backend/app/services/rewrite_strategies/executor.py`
- `backend/app/services/rewrite_strategies/assets.py`
- `backend/app/services/rewrite_strategies/rule_engine.py`
- `backend/app/services/rewrite_strategies/validators.py`
- `backend/app/services/rewrite_strategies/cnki_algorithm.py`
- `backend/app/services/rewrite_strategies/cnki_llm.py`
- `backend/app/services/rewrite_strategies/vip_algorithm.py`
- `backend/app/services/rewrite_strategies/vip_llm.py`

说明：

- 这是当前最接近正确边界的一组新代码。
- 但 `rule_engine.py` 反向依赖 `ProcessingEngine`，属于边界污染。

#### 结果与报告模块

- `backend/app/services/detect_report_renderer.py`
- `backend/app/services/aigc_detect_evaluator.py`

说明：

- `detect_report_renderer.py` 目前通过类型检查和运行时调用反向感知 `ProcessingEngine`，边界还不干净。
- `aigc_detect_evaluator.py` 更偏评估框架和结果评估，不该再继续压回 `processing_engine.py`。

#### 系统支撑模块

- `backend/app/services/platform_registry.py`
- `backend/app/services/process_strategy_service.py`
- `backend/app/services/algo_package_service.py`
- `backend/app/services/algo_package_runner.py`
- `backend/app/services/builtin_algo_packages.py`
- `backend/app/services/llm_service.py`

说明：

- `platform_registry.py` 实际是平台注册与配置支撑。
- `process_strategy_service.py` 是旧体系的“任务处理策略配置服务”。
- `algo_package_*` 与 `builtin_algo_packages.py` 是旧算法包链。
- `llm_service.py` 是公共 LLM 能力底座。

### 3.3 后端基础文件

#### 系统支撑模块

- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/deps.py`
- `backend/app/database.py`
- `backend/app/logging_setup.py`
- `backend/app/bootstrap.py`
- `backend/app/constants.py`
- `backend/app/client_source.py`
- `backend/app/exceptions.py`
- `backend/app/responses.py`
- `backend/app/pagination.py`
- `backend/app/security.py`
- `backend/app/utils.py`
- `backend/app/utils_qrcode.py`
- `backend/app/money.py`

#### 结果与报告模块

- `backend/app/schemas.py`

说明：

- `schemas.py` 目前是全局 API 响应和请求结构混放，后续可以按模块或按接口 / 结果类型拆分。

#### 数据模型层

- `backend/app/models.py`

说明：

- 它不是 8 个大模块之一，而是全局数据模型层。
- 其中既包含当前有效模型，也包含已冻结的 `referral / promo` 历史兼容模型。

### 3.4 后台执行链

#### 后台执行模块

- `backend/app/worker_tasks.py`

说明：

- 当前同时承担 dispatcher、preprocess、process、cleanup、refund、locks。
- 是第二个必须优先拆的巨型文件。

### 3.5 前端用户端

#### 认证与账户模块

- `frontend/src/views/user/LoginPage.vue`
- `frontend/src/views/user/RegisterPage.vue`
- `frontend/src/views/user/components/AuthEntryPanel.vue`
- `frontend/src/views/user/UserProfilePage.vue`
- `frontend/src/composables/useUserProfile.js`
- `frontend/src/lib/session.js`
- `frontend/src/lib/redirect.js`
- `frontend/src/lib/requireLogin.js`

#### 计费与订单模块

- `frontend/src/views/user/UserBuyPage.vue`
- `frontend/src/components/BuyCreditsPanel.vue`

#### 任务中心模块

- `frontend/src/views/user/UserDetectPage.vue`
- `frontend/src/views/user/UserDedupPage.vue`
- `frontend/src/views/user/UserRewritePage.vue`
- `frontend/src/views/user/UserDetectRecordsPage.vue`
- `frontend/src/views/user/UserDedupRecordsPage.vue`
- `frontend/src/views/user/UserRewriteRecordsPage.vue`
- `frontend/src/components/WorkbenchTaskFeed.vue`
- `frontend/src/lib/taskSubmitFlow.js`
- `frontend/src/lib/taskSubmitRecovery.js`
- `frontend/src/lib/userRecords.js`
- `frontend/src/lib/taskStatus.js`
- `frontend/src/lib/taskResult.js`
- `frontend/src/lib/taskPlatform.js`
- `frontend/src/lib/download.js`
- `frontend/src/lib/paperTitle.js`

#### 系统支撑模块

- `frontend/src/components/UserShell.vue`
- `frontend/src/composables/useShellLayout.js`
- `frontend/src/lib/http.js`
- `frontend/src/lib/device.js`
- `frontend/src/lib/userNavigation.js`
- `frontend/src/router/index.js`
- `frontend/src/main.js`
- `frontend/src/App.vue`
- `frontend/src/style.css`
- `frontend/src/gewu-ui.css`

说明：

- `UserShell.vue` 当前混有导航、公告、会话、轮询、移动端布局，后续应拆成 composable + UI。

### 3.6 前端后台端

#### 认证与账户模块

- `frontend/src/views/admin/AdminLoginPage.vue`

#### 任务中心模块

- `frontend/src/views/admin/AdminTaskPage.vue`

#### 计费与订单模块

- `frontend/src/views/admin/AdminOrderPage.vue`

#### 认证与账户模块 / 后台运营

- `frontend/src/views/admin/AdminUserPage.vue`
- `frontend/src/views/admin/AdminUserDetailPage.vue`

#### 系统支撑模块 / 后台运营

- `frontend/src/views/admin/AdminDashboardPage.vue`
- `frontend/src/views/admin/AdminConfigPage.vue`
- `frontend/src/views/admin/AdminAlgoPackagePage.vue`
- `frontend/src/components/AdminShell.vue`

说明：

- `AdminConfigPage.vue` 是当前前端配置中心单体页面。
- `AdminAlgoPackagePage.vue` 主要承载旧算法包体系与旧任务模式切换能力。

### 3.7 小程序端

#### 认证与账户模块

- `miniapp/pages/login/*`
- `miniapp/utils/auth.js`
- `miniapp/utils/authFlow.js`
- `miniapp/utils/storage.js`

#### 任务中心模块

- `miniapp/pages/records/*`
- `miniapp/utils/taskRecovery.js`
- `miniapp/utils/status.js`

#### 系统支撑模块

- `miniapp/app.js`
- `miniapp/app.json`
- `miniapp/config/env.js`
- `miniapp/utils/request.js`
- `miniapp/utils/display.js`
- `miniapp/pages/home/*`
- `miniapp/pages/profile/*`
- `miniapp/pages/legal/*`

说明：

- 小程序目前是独立前端客户端，不应混进 Web 前端模块图里，但应纳入项目总模块图。

### 3.8 测试归属

测试不是业务模块，但必须按模块归属组织理解。

#### 认证与账户模块测试

- `backend/tests/test_auth_phone_login_flow.py`
- `backend/tests/test_auth_risk_controls.py`
- `backend/tests/test_auth_wx_login.py`
- `backend/tests/test_user_profile_summary.py`

#### 计费与订单模块测试

- `backend/tests/test_billing_order_flow.py`
- `backend/tests/test_billing_callback.py`
- `backend/tests/test_billing_audit_integrity.py`
- `backend/tests/test_admin_order_refund.py`
- `backend/tests/test_task_billing_config.py`
- `backend/tests/test_auth_billing_credit_journey.py`

#### 任务中心 / 后台执行 / 编排模块测试

- `backend/tests/test_task_submission_chain.py`
- `backend/tests/test_task_end_to_end_flows.py`
- `backend/tests/test_task_failure_refund.py`
- `backend/tests/test_task_chain_guard.py`
- `backend/tests/test_task_status_migration.py`
- `backend/tests/test_user_task_download_and_batch*.py`
- `backend/tests/test_local_task_dispatch.py`
- `backend/tests/test_docx_format_preservation.py`
- `backend/tests/test_processing_engine_results.py`

#### 策略中心 / 算法旧体系测试

- `backend/tests/test_process_strategies.py`
- `backend/tests/test_algo_packages.py`
- `backend/tests/test_cnki_rewrite_sample_package.py`
- `backend/tests/test_cnki_sampled_builtin_package*.py`
- `backend/tests/test_vip_sampled_builtin_package*.py`

#### 系统支撑模块测试

- `backend/tests/test_admin_config_validation.py`
- `backend/tests/test_admin_config_audit_logs.py`
- `backend/tests/test_admin_permissions.py`
- `backend/tests/test_admin_dashboard.py`
- `backend/tests/test_admin_switch_logs.py`
- `backend/tests/test_logging_setup.py`
- `backend/tests/test_multi_end_source.py`
- `backend/tests/test_production_guards.py`
- `backend/tests/test_recent_lookup_indexes.py`
- `backend/tests/conftest.py`

说明：

- `backend/tests/__pycache__/` 不属于测试源码，不能纳入模块审计。

### 3.9 部署、脚本、文档、运行目录

#### 系统支撑模块

- `deploy/*`
- `scripts/*`
- `docker-compose*.yml`
- `.env*`
- `README.md`
- `PROJECT_STATUS.md`
- `PROJECT_BASELINE_AND_ROADMAP.md`
- `CREDIT_SYSTEM_REVIEW_LOG.md`
- `QA_AUDIT_LOG.md`
- `gw工作日志.md`

#### 策略 / 质量资料文档

- `docs/CNKI_REWRITE_SAMPLE_RULESET.md`
- `docs/VIP_DEDUP_SAMPLE_RULESET.md`
- `docs/REWRITE_QUALITY_REQUIREMENTS.md`
- `docs/REWRITE_RESULT_EVAL_FRAMEWORK.md`
- `docs/AIGC_DETECT_RESULT_EVAL_FRAMEWORK.md`
- `docs/DEDUP_RESULT_EVAL_FRAMEWORK.md`
- `docs/AIGC_*`
- `docs/DEDUP_*`
- `docs/ALGO_*`

说明：

- 这些资料不是运行模块，但属于策略中心和质量评估的重要输入。

#### 运行产物目录

- `backend/logs`
- `backend/uploads`
- `backend/output`
- 项目根目录 `logs/`
- 项目根目录 `output/`
- `backend/algorithm_packages`
- `backend/custom_algo_packages`
- `.pytest_cache`
- `.claude`
- `.codex`
- `.playwright-cli`

说明：

- 这些不是业务模块，是运行产物、训练材料目录或工具目录。
- 审计、重构和定位问题时必须与源码目录分开看。

## 4. 当前确认的混乱点

### 4.1 巨型文件重新吞掉模块边界

高风险文件：

- `backend/app/services/processing_engine.py`
- `backend/app/api/admin.py`
- `backend/app/api/tasks.py`
- `backend/app/worker_tasks.py`
- `frontend/src/views/admin/AdminConfigPage.vue`
- `frontend/src/components/UserShell.vue`
- `frontend/src/components/BuyCreditsPanel.vue`

### 4.2 反向依赖

不合理依赖：

- `rewrite_strategies/rule_engine.py` 反向依赖 `ProcessingEngine`
- `detect_report_renderer.py` 通过 `ProcessingEngine` 获取渲染能力

正确方向：

- 编排层依赖策略层、报告层
- 不能反过来让策略层、报告层依赖编排层

### 4.3 同类规则重复实现

已经确认的重复点：

- `tasks.py` 与 `worker_tasks.py` 各自维护 `_report_is_full`
- `tasks.py` 与 `worker_tasks.py` 各自维护 `_validate_report_content`

风险：

- 前后台校验标准漂移
- 一个地方改了，另一个地方忘改

### 4.4 新旧体系并存

当前同时存在两套策略相关体系：

- 新的 `rewrite_strategies/*`
- 旧的 `process_strategy_service.py + algo_package_service.py + AdminAlgoPackagePage.vue + /admin/algo-packages`

这会导致：

- 后续接手的人不知道应该沿哪条线继续扩
- 新需求继续落回旧体系的概率很高

### 4.5 前后端配置规范双份维护

当前配置默认值、归一化、readiness 分布在：

- 后端 `admin.py`
- 前端 `AdminConfigPage.vue`

风险：

- 字段默认值不一致
- 配置保存和配置展示规则不一致

### 4.6 历史兼容层与当前模块图并存

确认存在的历史兼容内容：

- `models.py` 中 referral / promo 历史模型
- `CreditType` 中 referral / share 历史枚举
- 旧算法包体系目录与测试

这些内容不是当前主线模块，但又仍在代码库中，必须在审计里明确标注为“历史兼容，不是新增能力入口”。

### 4.7 运行目录与源码目录并存

例如：

- `backend/uploads`
- `backend/output`
- `backend/logs`
- `backend/algorithm_packages`

如果后续不在认知上区分：

- 会把运行产物误当成模块目录
- 会让问题定位、备份、清理和部署越来越乱

## 5. 后续整改优先级

### P0：先修结构风险

- 修复 `processing_engine.py` 中同名方法覆盖问题。
- 抽出报告校验公共模块，消除 `tasks.py` / `worker_tasks.py` 重复实现。

### P1：先收核心边界

- 拆 `admin.py` 为后台域子路由。
- 拆 `tasks.py` 为任务中心子服务。
- 拆 `worker_tasks.py` 为 dispatcher + handlers。

### P2：收主处理链

- 拆 `processing_engine.py` 为编排、策略调用、结果构建、报告输出几个子模块。
- 去掉策略层、报告层对 `ProcessingEngine` 的反向依赖。

### P3：收配置中心和前端重页面

- 后端抽离配置默认值、归一化、readiness。
- 前端拆 `AdminConfigPage.vue`。
- 前端拆 `UserShell.vue` 和 `BuyCreditsPanel.vue`。

### P4：处理旧体系与历史兼容层

- 明确旧算法包体系保留边界。
- 明确 referral / promo 历史模型只读兼容边界。
- 清理缓存、运行产物、测试缓存对认知的干扰。

## 6. 审计结论

当前项目不是“没有模块”，而是“模块存在，但边界被巨型文件和新旧体系并存重新打乱了”。

所以后续工作不能只做目录搬家，必须按下面顺序推进：

1. 先修结构风险。
2. 再收模块职责。
3. 再按模块拆代码。
4. 最后再考虑目录形态和页面拆分。

后续所有新增功能、修复、重构，都必须继续遵守本审计和 `PROJECT_BASELINE_AND_ROADMAP.md` 中的 8 模块基线。
