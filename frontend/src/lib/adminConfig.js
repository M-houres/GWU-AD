export const CONFIG_TABS = [
  { key: "login", label: "登录配置", desc: "短信与微信登录" },
  { key: "payment", label: "支付配置", desc: "微信支付 / 支付宝" },
  { key: "billing", label: "计费规则", desc: "按字符扣费" },
  { key: "aigc_detect_strategy", label: "AIGC检测策略", desc: "知网 / 维普内部检测" },
  { key: "dedup_strategy", label: "降重复率策略", desc: "知网 / 维普策略路由" },
  { key: "rewrite_strategy", label: "降AIGC率策略", desc: "知网 / 维普策略路由" },
  { key: "user_navigation", label: "前台导航", desc: "左侧功能编排" },
  { key: "promo_center", label: "推广中心", desc: "邀请奖励与合作联系方式" },
  { key: "llm", label: "大模型配置", desc: "国内外主流模型" },
  { key: "miniapp", label: "小程序配置", desc: "参数与域名" },
]

export const LLM_PROVIDERS = [
  { value: "openai", label: "OpenAI", desc: "官方接口" },
  { value: "anthropic", label: "Anthropic", desc: "Claude Messages" },
  { value: "gemini", label: "Gemini", desc: "Google generateContent" },
  { value: "deepseek", label: "DeepSeek", desc: "官方兼容接口" },
  { value: "qwen", label: "通义千问", desc: "百炼兼容模式" },
  { value: "doubao", label: "豆包 / 方舟", desc: "Ark 兼容模式" },
  { value: "moonshot", label: "Kimi", desc: "Moonshot 官方接口" },
  { value: "zhipu", label: "智谱 GLM", desc: "智谱兼容接口" },
  { value: "custom_openai", label: "自定义兼容", desc: "手填 OpenAI 兼容网关" },
]

export const LLM_PRESETS = {
  openai: { base_url: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  anthropic: { base_url: "https://api.anthropic.com/v1", model: "claude-3-5-sonnet-latest" },
  gemini: { base_url: "https://generativelanguage.googleapis.com/v1beta", model: "gemini-2.0-flash" },
  deepseek: { base_url: "https://api.deepseek.com", model: "deepseek-chat" },
  qwen: { base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" },
  doubao: { base_url: "https://ark.cn-beijing.volces.com/api/v3", model: "" },
  moonshot: { base_url: "https://api.moonshot.cn/v1", model: "moonshot-v1-8k" },
  zhipu: { base_url: "https://open.bigmodel.cn/api/paas/v4", model: "glm-4-flash" },
  custom_openai: { base_url: "", model: "" },
}

export const PAYMENT_PROVIDERS = [
  { value: "wechatpay_v3", label: "微信支付 V3", desc: "官方 Native 收款" },
  { value: "alipay", label: "支付宝", desc: "官方预创建二维码" },
  { value: "mock", label: "Mock 联调", desc: "仅开发联调" },
]

export const SMS_PROVIDERS = [
  { value: "custom_webhook", label: "自建短信", desc: "自有短信网关" },
  { value: "tencent_sms", label: "腾讯云短信", desc: "官方 API" },
  { value: "aliyun_sms", label: "阿里云短信", desc: "官方 API" },
  { value: "disabled", label: "关闭短信", desc: "仅微信或 debug" },
]

export const ADMIN_CONFIG_GUIDES = {
  login: {
    code: "Access Setup",
    lead: "至少保证短信、微信扫码、debug_code 中一种可用。",
    title: "先打通登录链路",
    desc: "保存后前台登录页会立即按最新配置切换。",
    checklist: [
      "生产环境建议至少保留 1 个正式登录方式。",
      "微信扫码登录回调必须是公网 HTTPS。",
    ],
    docs: [
      { label: "微信开放平台 网站应用登录", href: "https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html" },
      { label: "微信小程序 wx.login", href: "https://developers.weixin.qq.com/miniprogram/dev/api/open-api/login/wx.login.html" },
      { label: "腾讯云短信 SendSms", href: "https://cloud.tencent.com/document/product/382/55981" },
      { label: "阿里云短信 SendSms", href: "https://help.aliyun.com/zh/sms/developer-reference/api-dysmsapi-2017-05-25-sendsms" },
    ],
  },
  payment: {
    code: "Revenue Setup",
    lead: "关闭联调模式后才会走真实支付。正式支付必须依赖公网回调。",
    title: "真实收款必须可回调",
    desc: "本地前后端联调不等于真实收款，正式支付需要公网 HTTPS 域名。",
    checklist: [
      "微信支付需要商户号、商户私钥、APIv3 Key。",
      "支付宝需要应用私钥、支付宝公钥、AppID。",
    ],
    docs: [
      { label: "微信支付 Native 下单", href: "https://pay.wechatpay.cn/doc/v3/merchant/4012791898" },
      { label: "微信支付 回调通知", href: "https://pay.wechatpay.cn/doc/v3/merchant/4012071382" },
      { label: "支付宝预创建订单", href: "https://opendocs.alipay.com/apis/api_1/alipay.trade.precreate" },
      { label: "支付宝开放平台", href: "https://opendocs.alipay.com/open/00f0fa" },
    ],
  },
  billing: {
    code: "Pricing Setup",
    lead: "同时配置任务单价和通用点数套餐，前台会自动同步。",
    title: "定价直接影响转化",
    desc: "任务按整数点数/字符直接扣费，充值按通用点数套餐到账。运营填完即可上线生效。",
    checklist: [
      "三类单价必须都大于 0。",
      "至少启用 1 个套餐，并确保支付金额和到账通用点数都已填写。",
    ],
    docs: [
      { label: "微信支付 开发文档", href: "https://pay.wechatpay.cn/doc/v3/merchant/4012791898" },
      { label: "支付宝 开发文档", href: "https://opendocs.alipay.com/apis/api_1/alipay.trade.precreate" },
    ],
  },
  aigc_detect_strategy: {
    code: "Detect Runtime",
    lead: "把 AIGC 检测收敛成纯内部算法策略链，只保留平台启停。",
    title: "先保证检测链路稳定",
    desc: "知网和维普的 AIGC 检测任务都会经过后端统一内部检测执行器。这里只控制平台启停，不提供版本切换或大模型增强。",
    checklist: [
      "知网和维普至少应有 1 个平台保持启用。",
      "AIGC 检测现在只走内部算法策略，不依赖 LLM。",
      "这里只控制后端检测可用性，不影响前台入口、计费和下载。",
    ],
    docs: [],
  },
  dedup_strategy: {
    code: "Dedup Runtime",
    lead: "把降重复率执行收敛成最少配置项，只保留平台启用和当前策略。",
    title: "先保证降重链稳定",
    desc: "知网和维普的降重复率任务都会经过后端统一执行器。这里只保留平台启停和当前执行策略。",
    checklist: [
      "知网和维普至少应有 1 个平台保持启用。",
      "算法策略适合规则稳定阶段，大模型策略依赖 LLM 配置可用。",
      "这里只控制后端执行策略，不影响前台入口、计费和下载。",
    ],
    docs: [],
  },
  rewrite_strategy: {
    code: "Rewrite Runtime",
    lead: "把降AIGC率执行收敛成最少配置项，只保留平台启用和当前策略。",
    title: "先保证后端稳定处理",
    desc: "知网和维普的降AIGC率任务都会经过后端统一执行器。这里只保留平台启停和当前执行策略。",
    checklist: [
      "知网和维普至少应有 1 个平台保持启用。",
      "算法策略适合规则稳定阶段，大模型策略依赖 LLM 配置可用。",
      "这里只控制后端执行策略，不影响前台入口、计费和下载。",
    ],
    docs: [],
  },
  user_navigation: {
    code: "Frontend Navigation",
    lead: "在后台直接控制左侧功能顺序与是否展示，前台刷新后立即生效。",
    title: "前台导航统一编排",
    desc: "这里只控制左侧导航展示，不会删除页面路由。个人中心入口已固定从顶部进入。",
    checklist: [
      "至少保留 1 个前台功能可见，避免用户进入后无导航可用。",
      "“开发中”功能可以保留展示，也可以直接隐藏。",
    ],
    docs: [],
  },
  promo_center: {
    code: "Promotion Setup",
    lead: "配置邀请奖励积分和机构合作联系方式，前台推广中心会实时读取。",
    title: "推广页面运营配置",
    desc: "邀请人与被邀请人奖励积分支持后台调整，电话、微信号、邮箱都支持多条配置。",
    checklist: [
      "邀请奖励积分支持 0 到 100000；设为 0 时页面仅展示联系方式。",
      "电话、微信号、邮箱每类最多配置 20 条，建议至少配 1 条合作信息。",
    ],
    docs: [],
  },
  llm: {
    code: "Model Setup",
    lead: "支持 OpenAI、Anthropic、Gemini、DeepSeek、Qwen、豆包、Kimi、智谱和自定义兼容接口。",
    title: "先选提供商，再填模型与密钥",
    desc: "保存后新任务直接按这里的模型参数调用。",
    checklist: [
      "Base URL 建议保持默认，除非你明确在用代理。",
      "模型名必须和所购通道一致。",
    ],
    docs: [
      { label: "OpenAI API", href: "https://platform.openai.com/docs/api-reference" },
      { label: "Anthropic Messages API", href: "https://docs.anthropic.com/en/api/messages-examples" },
      { label: "Google Gemini API", href: "https://ai.google.dev/gemini-api/docs/text-generation" },
      { label: "DeepSeek API", href: "https://api-docs.deepseek.com/api/create-chat-completion" },
      { label: "阿里云百炼 OpenAI 兼容", href: "https://help.aliyun.com/zh/model-studio/openai-compatible-api" },
      { label: "火山引擎 Ark OpenAI 兼容", href: "https://www.volcengine.com/docs/82379/1298454" },
      { label: "智谱 OpenAI SDK 兼容", href: "https://bigmodel.cn/dev/howuse/model" },
      { label: "Moonshot API", href: "https://platform.moonshot.cn/docs/api-reference" },
    ],
  },
  miniapp: {
    code: "Mini Program Setup",
    lead: "在配置中心统一维护小程序 AppID、域名白名单和登录支付开关。",
    title: "小程序参数集中配置",
    desc: "保存后后端会直接使用该配置，便于 Web 与小程序共用同一套服务。",
    checklist: [
      "至少填写小程序 AppID 与 AppSecret。",
      "request/upload/download/ws 域名需与微信后台一致。",
      "启用小程序支付时需配置支付回调地址。",
    ],
    docs: [
      { label: "微信小程序 开发文档", href: "https://developers.weixin.qq.com/miniprogram/dev/framework/" },
      { label: "微信小程序 合法域名配置", href: "https://developers.weixin.qq.com/miniprogram/dev/devtools/projectconfig.html" },
      { label: "微信小程序 登录时序", href: "https://developers.weixin.qq.com/miniprogram/dev/framework/open-ability/login.html" },
    ],
  },
}

export const DEFAULT_BILLING_PACKAGES = [
  {
    name: "入门版",
    price: 19,
    credits: 10000,
    description: "适合新手试用或偶尔使用，低门槛体验核心功能。",
    badge: "新手推荐",
    enabled: true,
  },
  {
    name: "基础版",
    price: 39,
    credits: 20000,
    description: "适合少量多次使用，覆盖日常降重、降AI和检测需求。",
    badge: "日常常用",
    enabled: true,
  },
  {
    name: "专业版",
    price: 79,
    credits: 50000,
    description: "适合中度使用需求，兼顾成本和可用点数储备。",
    badge: "高性价比",
    enabled: true,
  },
  {
    name: "增强版",
    price: 149,
    credits: 100000,
    description: "适合常规批量使用，适配更稳定的内容处理节奏。",
    badge: "批量优选",
    enabled: true,
  },
  {
    name: "高级版",
    price: 419,
    credits: 300000,
    description: "适合中高频长期使用，兼顾规模与长期成本。",
    badge: "长期推荐",
    enabled: true,
  },
  {
    name: "旗舰版",
    price: 1199,
    credits: 1000000,
    description: "适合高频大量使用场景，提供充足通用点数储备。",
    badge: "旗舰首选",
    enabled: true,
  },
]

export const DEFAULT_MINIAPP_CONFIG = {
  enabled: false,
  app_id: "",
  app_secret: "",
  original_id: "",
  env_version: "release",
  api_base_url: "",
  web_base_url: "",
  request_domain: "",
  upload_domain: "",
  download_domain: "",
  ws_domain: "",
  business_domain: "",
  icp_filing_no: "",
  contact_phone: "",
  contact_email: "",
  publish_note: "",
  wechat_miniprogram_login_enabled: false,
  wechat_miniprogram_app_id: "",
  wechat_miniprogram_app_secret: "",
  wechat_miniprogram_payment_enabled: false,
  payment_notify_url: "",
}

export const DEFAULT_PROMO_CENTER_CONFIG = {
  enabled: true,
  invite_reward_points: 2000,
  contacts: {
    phone: [],
    wechat: [],
    email: [],
  },
}

export const DEFAULT_REWRITE_STRATEGY_CONFIG = {
  cnki: { rewrite: { enabled: true, active_strategy: "algorithm" } },
  vip: { rewrite: { enabled: true, active_strategy: "algorithm" } },
}

export const DEFAULT_AIGC_DETECT_STRATEGY_CONFIG = {
  cnki: { aigc_detect: { enabled: true } },
  vip: { aigc_detect: { enabled: true } },
}

export const DEFAULT_DEDUP_STRATEGY_CONFIG = {
  cnki: { dedup: { enabled: true, active_strategy: "algorithm" } },
  vip: { dedup: { enabled: true, active_strategy: "algorithm" } },
}

export const AIGC_DETECT_STRATEGY_PLATFORMS = [
  { key: "cnki", label: "知网AIGC检测", desc: "按知网段级双阈值特征链进行内部检测。" },
  { key: "vip", label: "维普AIGC检测", desc: "按维普段落级多特征加权链进行内部检测。" },
]

export const DEDUP_STRATEGY_PLATFORMS = [
  { key: "cnki", label: "知网降重复率", desc: "适合术语保护要求更强、偏保守的降重任务。" },
  { key: "vip", label: "维普降重复率", desc: "适合句式重排更明显、结构变化更大的降重任务。" },
]

export const REWRITE_STRATEGY_PLATFORMS = [
  { key: "cnki", label: "知网降AIGC率", desc: "适合术语保护要求更强的改写任务。" },
  { key: "vip", label: "维普降AIGC率", desc: "适合句法重组更明显的改写任务。" },
]

export const DEDUP_STRATEGY_OPTIONS = [
  { value: "algorithm", label: "算法策略" },
  { value: "llm", label: "大模型策略" },
]

export const REWRITE_STRATEGY_OPTIONS = [
  { value: "algorithm", label: "算法策略" },
  { value: "llm", label: "大模型策略" },
]

export function cloneBillingPackages(packages = DEFAULT_BILLING_PACKAGES) {
  return (Array.isArray(packages) ? packages : DEFAULT_BILLING_PACKAGES).map((pkg) => ({
    name: String(pkg?.name || "").trim(),
    price: Number(pkg?.price || 0),
    credits: Number(pkg?.credits || 0),
    description: String(pkg?.description || "").trim(),
    badge: String(pkg?.badge || "").trim(),
    enabled: pkg?.enabled !== false,
  }))
}

export function normalizeBillingForm(raw) {
  const source = raw && typeof raw === "object" ? raw : {}
  return {
    aigc_points_per_char: Math.max(1, Math.round(Number(source.aigc_points_per_char ?? source.aigc_rate) || 1)),
    dedup_points_per_char: Math.max(1, Math.round(Number(source.dedup_points_per_char ?? source.dedup_rate) || 1)),
    rewrite_points_per_char: Math.max(1, Math.round(Number(source.rewrite_points_per_char ?? source.rewrite_rate) || 1)),
    packages: cloneBillingPackages(source.packages),
  }
}

export function normalizeMiniappConfig(raw) {
  const source = { ...DEFAULT_MINIAPP_CONFIG, ...(raw || {}) }
  const envVersion = String(source.env_version || "release").toLowerCase()
  return {
    enabled: source.enabled === true,
    app_id: String(source.app_id || "").trim(),
    app_secret: String(source.app_secret || "").trim(),
    original_id: String(source.original_id || "").trim(),
    env_version: ["develop", "trial", "release"].includes(envVersion) ? envVersion : "release",
    api_base_url: String(source.api_base_url || "").trim(),
    web_base_url: String(source.web_base_url || "").trim(),
    request_domain: String(source.request_domain || "").trim(),
    upload_domain: String(source.upload_domain || "").trim(),
    download_domain: String(source.download_domain || "").trim(),
    ws_domain: String(source.ws_domain || "").trim(),
    business_domain: String(source.business_domain || "").trim(),
    icp_filing_no: String(source.icp_filing_no || "").trim(),
    contact_phone: String(source.contact_phone || "").trim(),
    contact_email: String(source.contact_email || "").trim(),
    publish_note: String(source.publish_note || "").trim(),
    wechat_miniprogram_login_enabled: source.wechat_miniprogram_login_enabled === true,
    wechat_miniprogram_app_id: String(source.wechat_miniprogram_app_id || "").trim(),
    wechat_miniprogram_app_secret: String(source.wechat_miniprogram_app_secret || "").trim(),
    wechat_miniprogram_payment_enabled: source.wechat_miniprogram_payment_enabled === true,
    payment_notify_url: String(source.payment_notify_url || "").trim(),
  }
}

export function normalizePromotionCenterConfig(raw) {
  const source = { ...DEFAULT_PROMO_CENTER_CONFIG, ...(raw || {}) }
  const contacts = source.contacts && typeof source.contacts === "object" ? source.contacts : {}
  return {
    enabled: source.enabled !== false,
    invite_reward_points: clampAdminInt(source.invite_reward_points, 2000, 0, 100000),
    contacts: {
      phone: normalizePromotionContactList(contacts.phone),
      wechat: normalizePromotionContactList(contacts.wechat),
      email: normalizePromotionContactList(contacts.email),
    },
  }
}

function normalizePromotionContactList(values) {
  if (!Array.isArray(values)) return []
  const list = []
  const seen = new Set()
  for (const value of values) {
    const text = String(value || "").trim().slice(0, 128)
    if (!text) continue
    const key = text.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    list.push(text)
    if (list.length >= 20) break
  }
  return list
}

function clampAdminInt(value, fallback, min, max) {
  const num = Number.parseInt(value, 10)
  if (!Number.isFinite(num)) return fallback
  return Math.max(min, Math.min(max, num))
}

export function normalizeRewriteStrategyConfig(raw = {}) {
  const source = raw && typeof raw === "object" ? raw : {}
  return {
    cnki: normalizeRewriteStrategyEntry(source.cnki, DEFAULT_REWRITE_STRATEGY_CONFIG.cnki),
    vip: normalizeRewriteStrategyEntry(source.vip, DEFAULT_REWRITE_STRATEGY_CONFIG.vip),
  }
}

export function normalizeRewriteStrategyEntry(raw, fallback) {
  const source = raw && typeof raw === "object" ? raw : {}
  const rewrite = source.rewrite && typeof source.rewrite === "object" ? source.rewrite : {}
  const defaultRewrite = fallback?.rewrite || DEFAULT_REWRITE_STRATEGY_CONFIG.cnki.rewrite
  const strategy = String(rewrite.active_strategy || defaultRewrite.active_strategy || "algorithm").trim().toLowerCase()
  return {
    rewrite: {
      enabled: rewrite.enabled !== undefined ? rewrite.enabled === true : defaultRewrite.enabled !== false,
      active_strategy: strategy === "llm" ? "llm" : "algorithm",
    },
  }
}

export function normalizeDedupStrategyConfig(raw = {}) {
  const source = raw && typeof raw === "object" ? raw : {}
  return {
    cnki: normalizeDedupStrategyEntry(source.cnki, DEFAULT_DEDUP_STRATEGY_CONFIG.cnki),
    vip: normalizeDedupStrategyEntry(source.vip, DEFAULT_DEDUP_STRATEGY_CONFIG.vip),
  }
}

export function normalizeDedupStrategyEntry(raw, fallback) {
  const source = raw && typeof raw === "object" ? raw : {}
  const dedup = source.dedup && typeof source.dedup === "object" ? source.dedup : {}
  const defaultDedup = fallback?.dedup || DEFAULT_DEDUP_STRATEGY_CONFIG.cnki.dedup
  const strategy = String(dedup.active_strategy || defaultDedup.active_strategy || "algorithm").trim().toLowerCase()
  return {
    dedup: {
      enabled: dedup.enabled !== undefined ? dedup.enabled === true : defaultDedup.enabled !== false,
      active_strategy: strategy === "llm" ? "llm" : "algorithm",
    },
  }
}

export function normalizeAigcDetectStrategyConfig(raw = {}) {
  const source = raw && typeof raw === "object" ? raw : {}
  return {
    cnki: normalizeAigcDetectStrategyEntry(source.cnki, DEFAULT_AIGC_DETECT_STRATEGY_CONFIG.cnki),
    vip: normalizeAigcDetectStrategyEntry(source.vip, DEFAULT_AIGC_DETECT_STRATEGY_CONFIG.vip),
  }
}

export function normalizeAigcDetectStrategyEntry(raw, fallback) {
  const source = raw && typeof raw === "object" ? raw : {}
  const detect = source.aigc_detect && typeof source.aigc_detect === "object" ? source.aigc_detect : {}
  const defaultDetect = fallback?.aigc_detect || DEFAULT_AIGC_DETECT_STRATEGY_CONFIG.cnki.aigc_detect
  return {
    aigc_detect: {
      enabled: detect.enabled !== undefined ? detect.enabled === true : defaultDetect.enabled !== false,
    },
  }
}

export function strategyDescription(strategy) {
  if (String(strategy || "").trim().toLowerCase() === "llm") {
    return "走专用大模型 prompt，适合语义重组更强的场景，同时依赖 LLM 配置可用。"
  }
  return "走内置规则算法，适合先建立稳定、可控、低复杂度的 MVP 处理链。"
}

export function resolvePaymentNotifyPreview(paymentForm) {
  const notify = String(paymentForm?.notify_url || "").trim()
  const provider = String(paymentForm?.provider || "").toLowerCase()
  if (!notify) return "未填写"
  let base = notify
  try {
    const parsed = new URL(notify)
    const path = parsed.pathname || "/"
    if (path === "/" || path === "") {
      if (provider === "alipay") {
        base = notify.replace(/\/+$/, "") + "/api/v1/billing/notify/alipay"
      } else {
        base = notify.replace(/\/+$/, "") + "/api/v1/billing/notify/wechatpay"
      }
    }
    return base
  } catch {
    return "回调地址格式不合法"
  }
}

export function adminConfigReadinessChipClass(status) {
  if (status === "ready") return "bg-[#e8f5ef] text-[#106c4f]"
  if (status === "error") return "bg-[#fff0ee] text-[#b24439]"
  return "bg-[#eef2f5] text-[#5e6c78]"
}

export function adminConfigReadinessLabel(status) {
  if (status === "ready") return "已就绪"
  if (status === "error") return "需补齐"
  return "待确认"
}

export function applyLlmProviderPreset(llmConfig, provider, presets = LLM_PRESETS) {
  const target = llmConfig || {}
  const current = presets[target.provider] || { base_url: "", model: "" }
  const next = presets[provider] || { base_url: "", model: "" }
  if (!target.base_url || target.base_url === current.base_url) {
    target.base_url = next.base_url
  }
  if (!target.model || target.model === current.model) {
    target.model = next.model
  }
  target.provider = provider
  return target
}

export function createBillingPackage() {
  return {
    name: "",
    price: 30,
    credits: 10000,
    description: "",
    badge: "",
    enabled: true,
  }
}

export function reorderAdminConfigItems(items, index, delta) {
  if (!Array.isArray(items)) {
    return items
  }
  const nextIndex = index + delta
  if (nextIndex < 0 || nextIndex >= items.length) {
    return items
  }
  const nextItems = [...items]
  const [current] = nextItems.splice(index, 1)
  nextItems.splice(nextIndex, 0, current)
  return nextItems.map((item, order) => ({
    ...item,
    order: order + 1,
  }))
}

export function validateAdminConfigCategory(category, forms, { normalizeUserNavigationConfig }) {
  if (category === "billing") {
    const { aigc_points_per_char, dedup_points_per_char, rewrite_points_per_char, packages } = normalizeBillingForm(forms.billing)
    if (!(aigc_points_per_char > 0) || !(dedup_points_per_char > 0) || !(rewrite_points_per_char > 0)) {
      return "任务点数单价必须是大于 0 的整数"
    }
    if (!Array.isArray(packages) || packages.length === 0) {
      return "至少需要配置 1 个套餐"
    }
    if (!packages.some((pkg) => pkg.enabled)) {
      return "至少需要启用 1 个套餐"
    }
    const names = new Set()
    for (const pkg of packages) {
      if (!pkg.name) return "套餐名称不能为空"
      if (names.has(pkg.name)) return `套餐名称重复：${pkg.name}`
      names.add(pkg.name)
      if (!(Number(pkg.price) > 0)) return `套餐 ${pkg.name} 价格必须大于 0`
      if (!(Number(pkg.credits) > 0)) return `套餐 ${pkg.name} 到账通用点数必须大于 0`
    }
  }
  if (category === "user_navigation") {
    const items = normalizeUserNavigationConfig(forms.user_navigation).items
    if (!items.some((item) => item.visible)) {
      return "前台导航至少需要展示 1 个功能"
    }
  }
  if (category === "payment") {
    const provider = forms.payment?.provider
    if (["wechat", "wechatpay_v3"].includes(provider) && forms.payment?.api_v3_key && String(forms.payment.api_v3_key).length !== 32) {
      return "微信支付 APIv3 Key 必须是 32 位"
    }
    if (provider === "alipay" && forms.payment?.app_private_key_pem && !forms.payment?.alipay_public_key) {
      return "支付宝已填写应用私钥时，需要同时填写支付宝公钥"
    }
    if (forms.payment?.test_mode === false && provider === "mock") {
      return "关闭联调模式后不能选择 mock"
    }
  }
  if (category === "llm") {
    const cfg = forms.llm || {}
    if (Number(cfg.retry_attempts) < 1 || Number(cfg.retry_attempts) > 5) {
      return "LLM 重试次数必须在 1 到 5 之间"
    }
    if (Number(cfg.retry_backoff_seconds) < 0.1 || Number(cfg.retry_backoff_seconds) > 5) {
      return "LLM 退避基线必须在 0.1 到 5 秒之间"
    }
  }
  if (category === "login") {
    const cfg = forms.login || {}
    if (Number(cfg.new_user_initial_credits) < 0) {
      return "新用户初始通用点数不能小于 0"
    }
    if (Number(cfg.max_code_retry) < 1) {
      return "验证码最大重试次数不能小于 1"
    }
    if (Number(cfg.phone_lock_minutes) < 1) {
      return "手机号锁定分钟数不能小于 1"
    }
    if (Number(cfg.send_code_ip_1h_limit) < 1) {
      return "发送验证码 IP 限流不能小于 1"
    }
    if (Number(cfg.login_ip_10m_limit) < 1) {
      return "登录请求 IP 限流不能小于 1"
    }
  }
  if (category === "miniapp") {
    const cfg = normalizeMiniappConfig(forms.miniapp)
    if (cfg.enabled && (!cfg.app_id || !cfg.app_secret)) {
      return "启用小程序配置时必须填写 AppID 与 AppSecret"
    }
    if (cfg.wechat_miniprogram_login_enabled) {
      const loginAppId = cfg.wechat_miniprogram_app_id || cfg.app_id
      const loginSecret = cfg.wechat_miniprogram_app_secret || cfg.app_secret
      if (!loginAppId || !loginSecret) {
        return "启用小程序登录时，需填写登录 AppID/AppSecret（可复用基础配置）"
      }
    }
    if (cfg.wechat_miniprogram_payment_enabled && !cfg.payment_notify_url) {
      return "启用小程序支付时，请填写支付回调地址"
    }
  }
  if (category === "promo_center") {
    const rawPoints = forms.promo_center?.invite_reward_points
    if (rawPoints !== undefined && rawPoints !== null && String(rawPoints).trim() !== "") {
      const points = Number(rawPoints)
      if (!Number.isFinite(points)) {
        return "邀请奖励积分必须是数字"
      }
    }
  }
  if (category === "aigc_detect_strategy") {
    const cfg = normalizeAigcDetectStrategyConfig(forms.aigc_detect_strategy)
    const enabledCount = AIGC_DETECT_STRATEGY_PLATFORMS.filter((item) => cfg[item.key]?.aigc_detect?.enabled).length
    if (enabledCount <= 0) {
      return "知网和维普至少需要启用 1 个 AIGC 检测平台"
    }
  }
  if (category === "rewrite_strategy") {
    const cfg = normalizeRewriteStrategyConfig(forms.rewrite_strategy)
    const enabledCount = REWRITE_STRATEGY_PLATFORMS.filter((item) => cfg[item.key]?.rewrite?.enabled).length
    if (enabledCount <= 0) {
      return "知网和维普至少需要启用 1 个降AIGC率平台"
    }
  }
  if (category === "dedup_strategy") {
    const cfg = normalizeDedupStrategyConfig(forms.dedup_strategy)
    const enabledCount = DEDUP_STRATEGY_PLATFORMS.filter((item) => cfg[item.key]?.dedup?.enabled).length
    if (enabledCount <= 0) {
      return "知网和维普至少需要启用 1 个降重复率平台"
    }
  }
  return ""
}

export function buildAdminConfigPayload(category, forms, { normalizeUserNavigationConfig }) {
  if (category === "user_navigation") {
    const normalized = normalizeUserNavigationConfig(forms.user_navigation)
    return {
      items: normalized.items.map((item, index) => ({
        key: item.key,
        visible: Boolean(item.visible),
        order: index + 1,
      })),
    }
  }
  const payload = { ...(forms[category] || {}) }
  if (category === "billing") {
    const normalized = normalizeBillingForm(payload)
    payload.aigc_points_per_char = normalized.aigc_points_per_char
    payload.dedup_points_per_char = normalized.dedup_points_per_char
    payload.rewrite_points_per_char = normalized.rewrite_points_per_char
    payload.packages = normalized.packages.map((pkg) => ({
      name: pkg.name,
      price: Number(pkg.price),
      credits: Number(pkg.credits),
      description: pkg.description,
      badge: pkg.badge,
      enabled: Boolean(pkg.enabled),
    }))
    delete payload.aigc_rate
    delete payload.dedup_rate
    delete payload.rewrite_rate
  }
  if (category === "payment" && payload.provider === "alipay" && payload.app_private_key_pem) {
    payload.api_key = payload.app_private_key_pem
  }
  if (category === "llm") {
    payload.timeout_seconds = Number(payload.timeout_seconds)
    payload.retry_attempts = Number(payload.retry_attempts)
    payload.retry_backoff_seconds = Number(payload.retry_backoff_seconds)
    payload.max_output_tokens = Number(payload.max_output_tokens)
    payload.temperature = Number(payload.temperature)
  }
  if (category === "miniapp") {
    const normalized = normalizeMiniappConfig(payload)
    payload.enabled = normalized.enabled
    payload.wechat_miniprogram_login_enabled = normalized.wechat_miniprogram_login_enabled
    payload.wechat_miniprogram_payment_enabled = normalized.wechat_miniprogram_payment_enabled
    payload.env_version = normalized.env_version
    payload.app_id = normalized.app_id.slice(0, 128)
    payload.app_secret = normalized.app_secret.slice(0, 256)
    payload.original_id = normalized.original_id.slice(0, 128)
    payload.api_base_url = normalized.api_base_url.slice(0, 256)
    payload.web_base_url = normalized.web_base_url.slice(0, 256)
    payload.request_domain = normalized.request_domain.slice(0, 256)
    payload.upload_domain = normalized.upload_domain.slice(0, 256)
    payload.download_domain = normalized.download_domain.slice(0, 256)
    payload.ws_domain = normalized.ws_domain.slice(0, 256)
    payload.business_domain = normalized.business_domain.slice(0, 256)
    payload.payment_notify_url = normalized.payment_notify_url.slice(0, 256)
    payload.icp_filing_no = normalized.icp_filing_no.slice(0, 128)
    payload.contact_phone = normalized.contact_phone.slice(0, 32)
    payload.contact_email = normalized.contact_email.slice(0, 128)
    payload.publish_note = normalized.publish_note.slice(0, 500)
    payload.wechat_miniprogram_app_id = normalized.wechat_miniprogram_app_id.slice(0, 128)
    payload.wechat_miniprogram_app_secret = normalized.wechat_miniprogram_app_secret.slice(0, 256)
  }
  if (category === "promo_center") {
    const normalized = normalizePromotionCenterConfig(payload)
    payload.enabled = normalized.enabled
    payload.invite_reward_points = normalized.invite_reward_points
    payload.contacts = normalized.contacts
  }
  if (category === "aigc_detect_strategy") {
    return normalizeAigcDetectStrategyConfig(payload)
  }
  if (category === "rewrite_strategy") {
    return normalizeRewriteStrategyConfig(payload)
  }
  if (category === "dedup_strategy") {
    return normalizeDedupStrategyConfig(payload)
  }
  return payload
}
