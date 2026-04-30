# 格物学术小程序

本目录是微信小程序前端，复用当前后端 `api/v1` 接口。

## 目录结构

- `app.*`：小程序入口
- `config/env.js`：后端地址配置
- `utils/`：请求、鉴权、状态文案、任务恢复
- `pages/login`：微信小程序登录
- `pages/home`：首页提交入口，统一处理 AIGC 检测 / 学术润色 / 降重复率
- `pages/records`：任务记录、结果展开与下载
- `pages/profile`：个人中心、充值、公告与账户操作
- `QA_CHECKLIST.md`：端到端测试清单

## 当前页面结构

- Tab 页面：`home / records / profile`
- 登录页：`login`
- 当前版本已将任务提交、充值、记录详情整合进三页结构
- 当前仅保留 `home / records / profile / promo-center / login` 五个业务页面，任务提交、记录详情、充值流程都已收口

## 已对接接口

- `POST /auth/wx/mini-login`
- `GET /auth/options`
- `GET /users/me`
- `GET /users/me/summary`
- `GET /users/me/invite-code`
- `POST /tasks/submit`
- `GET /tasks/my`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/download`
- `GET /billing/packages`
- `POST /billing/create-order`
- `GET /billing/order-status/{order_no}`
- `POST /billing/order-pay/{order_no}`

## 支付说明

- 小程序下单时传 `scene=miniprogram`
- 微信支付返回 `payment_params` 后，前端直接调用 `wx.requestPayment`
- 支付成功后通过订单状态轮询确认，并刷新积分
- 测试模式下保留 `mock` 兜底链路
- 正式环境小程序端仅展示微信支付

## 本地开发

1. 打开微信开发者工具并导入 `miniapp` 目录
2. 在 `config/env.js` 填写可访问的后端地址
3. 必要时在开发者工具中开启“忽略域名校验（仅开发）”

## 发布前必做

1. 微信公众平台配置合法请求域名（HTTPS）
2. 后台启用小程序登录并配置 `AppID / AppSecret`
3. 微信公众平台完成“用户隐私保护指引/隐私声明”配置，至少覆盖：
   - `getPhoneNumber` 微信手机号快捷验证
   - `chooseMessageFile` 从微信聊天记录选择文件
4. 后台支付配置填写微信支付参数并完成联调
5. 按 `QA_CHECKLIST.md` 完成完整回归

## 已知高优先级平台阻塞

- 如果真机报错 `chooseMessageFile:fail api scope is not declared in the privacyagreement`：
  - 不是前端上传代码错误
  - 是微信公众平台的隐私声明未把聊天文件选择相关范围配置完整
- 如果手机号快捷登录授权时报 `privacyagreement`：
  - 不是登录接口本身错误
  - 是微信公众平台的隐私声明未把手机号快捷验证相关范围配置完整
