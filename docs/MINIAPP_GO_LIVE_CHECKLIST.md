# 小程序上线清单

最后更新：2026-04-09

## 当前状态

- 小程序代码目录已具备基础主链路：登录、任务提交、记录、任务详情、支付、个人中心。
- 后端已支持小程序登录、任务、订单、支付和多端来源归因。
- 本轮已补齐小程序统一来源头，所有请求、上传、下载会携带 `X-Client-Source: miniprogram`。
- 当前仍未达到可直接提审状态，主要差在微信侧真实配置、已备案 HTTPS 域名、真实支付联调和真机回归。

## 已完成能力

- 微信小程序登录接口：`POST /api/v1/auth/wx/mini-login`
- 用户信息接口：`GET /api/v1/users/me`
- 任务提交与记录：
  - `POST /api/v1/tasks/submit`
  - `GET /api/v1/tasks/my`
  - `GET /api/v1/tasks/{task_id}`
  - `GET /api/v1/tasks/{task_id}/download`
- 订单与支付：
  - `GET /api/v1/billing/packages`
  - `POST /api/v1/billing/create-order`
  - `GET /api/v1/billing/order-status/{order_no}`
  - `POST /api/v1/billing/order-pay/{order_no}`

## 上线前必须补齐

### 1. 微信公众平台

- 创建并确认正式小程序 `AppID`
- 获取小程序 `AppSecret`
- 配置服务器域名
- 配置 `request` 合法域名
- 配置 `uploadFile` 合法域名
- 配置 `downloadFile` 合法域名
- 配置 `websocket` 合法域名
- 如果启用微信支付，完成商户号与小程序绑定

### 2. 域名与备案

- 小程序正式环境必须使用 HTTPS 业务域名
- 域名必须完成对应备案并可被微信后台校验
- 当前主站 `restin.top` 处于首次备案审核期，备案通过前不适合作为正式公网业务域名
- 如果要先推进小程序联调，建议使用已备案并可公网访问的测试域名，或先在开发者工具中仅做本地开发验证

### 3. 后台配置中心

后台管理页需要至少完成以下配置：

- `登录配置`
  - `wechat_miniprogram_login_enabled = true`
  - `wechat_miniprogram_app_id`
  - `wechat_miniprogram_app_secret`
- `小程序配置`
  - `enabled = true`
  - `app_id`
  - `app_secret`
  - `request_domain`
  - `upload_domain`
  - `download_domain`
  - `ws_domain`
  - `business_domain`
  - `icp_filing_no`
  - `contact_phone`
  - `contact_email`
- `支付配置`
  - 微信支付商户号
  - 商户私钥
  - APIv3 Key
  - 支付回调地址

## 本地导入步骤

1. 使用微信开发者工具导入目录 [miniapp](C:/Users/m/Desktop/001项目/001测试格物/miniapp)
2. 复制 [project.private.config.json.example](C:/Users/m/Desktop/001项目/001测试格物/miniapp/project.private.config.json.example) 为本地 `project.private.config.json`
3. 在微信开发者工具中填入真实小程序 `AppID`
4. 按环境修改 [env.js](C:/Users/m/Desktop/001项目/001测试格物/miniapp/config/env.js)
5. 开发联调阶段可在开发者工具里临时关闭域名校验；提审前必须恢复严格校验

## `env.js` 使用说明

- `develop`：本地开发或内网联调
- `trial`：体验版 / 提审前联调
- `release`：正式版
- 默认会根据 `wx.getAccountInfoSync().miniProgram.envVersion` 自动选择环境
- 如需临时强制切换，可在 [env.js](C:/Users/m/Desktop/001项目/001测试格物/miniapp/config/env.js) 中设置 `forceEnvVersion`

## 提审前回归清单

- 登录成功后自动进入首页
- 退出登录后重新进入要求登录
- 三类任务均可提交成功
- 任务记录页能看到新任务
- 任务详情页状态会轮询更新
- 已完成任务可以下载并打开
- 充值套餐能正常下单
- 微信支付能拉起并回写成功状态
- 个人中心积分与昵称信息刷新正常
- 后台任务、订单、积分流水中的 `source` 正确显示为 `miniprogram`

## 当前明确未闭环项

- `project.config.json` 仍是占位 `appid`
- `trial/release` API 域名仍是占位值
- 未完成真实微信小程序后台参数接入
- 未完成真机 iOS / Android 回归
- 未完成提审素材、隐私协议、类目与服务范围核对
