# 小程序本地联调

最后更新：2026-04-28

## 当前默认值

- 小程序 `AppID`：`wxf330c17322dfbd98`
- 小程序原始 ID：`gh_41c6044ce31a`
- 本地开发 `API`：`http://127.0.0.1:8000/api/v1`
- 正式回调地址：`https://restin.top/api/v1/billing/notify/wechatpay`
- 微信支付商户号：`1740438525`

## 本地导入

1. 用微信开发者工具打开 [miniapp](C:/Users/m/Desktop/001项目/001测试格物/miniapp)
2. 复制 [project.private.config.json.example](C:/Users/m/Desktop/001项目/001测试格物/miniapp/project.private.config.json.example) 为本地 `project.private.config.json`
3. 确认开发者工具里 `AppID` 是 `wxf330c17322dfbd98`
4. 本地开发阶段关闭域名校验

## 初始化本地后端配置

在 [backend](C:/Users/m/Desktop/001项目/001测试格物/backend) 目录执行：

```powershell
$env:GW_MINIAPP_APP_SECRET="你的小程序AppSecret"
$env:GW_MINIAPP_CONTACT_PHONE="你的联系电话"
$env:GW_MINIAPP_CONTACT_EMAIL="你的联系邮箱"
python scripts/bootstrap_local_miniapp.py
```

如果你不额外传 `GW_WECHATPAY_MERCHANT_PRIVATE_KEY_PEM`，脚本会默认读取：

- `C:\Users\m\Desktop\001项目\格物学术资料\_cert_20260401\apiclient_key.pem`

## 已内置的本地默认项

- 自动写入 `miniapp/login/payment` 三类本地系统配置
- 小程序域名默认使用 `https://restin.top`
- `develop` 环境默认请求本机 `127.0.0.1:8000`
- 支付默认仍保持 `test_mode = true`
- 如果未手填微信支付平台公钥，后端会在联调时用商户证书自动拉取平台证书

## 还缺的关键项

- `GW_MINIAPP_APP_SECRET`
- 联系电话
- 联系邮箱
- 如果要提审，还需要 ICP / 公安备案号

## 登录说明

- 本地 `develop` 环境默认会显示“开发调试登录”
- 如果后端已灌入真实小程序登录配置，页面会显示“正式微信登录”
- 如果只开了内测开关，页面会显示“内测登录”
