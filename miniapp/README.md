# 格物学术小程序（骨架版）

本目录是微信小程序前端，复用当前后端 `api/v1` 接口。

## 目录结构

- `app.*`：小程序入口
- `config/env.js`：后端地址配置
- `utils/`：请求、鉴权、状态文案
- `pages/login`：微信小程序登录
- `pages/home`：首页入口
- `pages/task`：任务提交（学术润色 / 降重 / AIGC 检测）
- `pages/records`：任务记录与下载
- `pages/task-detail`：任务详情（轮询 + 下载）
- `pages/pay`：积分充值（下单 + `wx.requestPayment` + 状态轮询）
- `pages/profile`：个人中心
- `QA_CHECKLIST.md`：端到端测试清单

## 已对接接口

- `POST /auth/wx/mini-login`
- `GET /auth/options`
- `POST /tasks/submit`
- `GET /tasks/my`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/download`
- `GET /users/me`
- `GET /billing/packages`
- `POST /billing/create-order`
- `GET /billing/order-status/{order_no}`
- `POST /billing/order-pay/{order_no}`

## 支付说明

- 小程序下单时传 `scene=miniprogram`
- 微信支付返回 `payment_params` 后前端直接调用 `wx.requestPayment`
- 支付成功后通过订单状态轮询确认并刷新积分
- 测试模式或其他渠道仍保留“我已支付”兜底链路

## 本地开发

1. 打开微信开发者工具并导入 `miniapp` 目录
2. 在 `config/env.js` 填写可访问的后端地址
3. 必要时在开发者工具中开启“忽略域名校验（仅开发）”

## 发布前必做

1. 微信公众平台配置合法请求域名（HTTPS）
2. 后台启用小程序登录并配置 `AppID/AppSecret`
3. 后台支付配置填好微信支付参数并完成联调
4. 按 `QA_CHECKLIST.md` 完成完整回归
