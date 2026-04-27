export const CONFIG_TABS = [
  { key: "login", label: "登录配置", desc: "短信与微信登录" },
  { key: "payment", label: "支付配置", desc: "微信支付 / 支付宝" },
  { key: "billing", label: "计费规则", desc: "按字符扣费" },
  { key: "aigc_detect_strategy", label: "AIGC检测策略", desc: "知网 / 维普内部检测" },
  { key: "rewrite_strategy", label: "降AIGC提示词", desc: "知网 / 维普大模型提示词" },
  { key: "dedup_strategy", label: "降重复率提示词", desc: "知网 / 维普大模型提示词" },
  { key: "user_navigation", label: "前台导航", desc: "左侧功能编排" },
  { key: "promo_center", label: "推广中心", desc: "点数规则 / 文案 / 活动素材" },
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
    code: "Detect Config",
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
  rewrite_strategy: {
    code: "Rewrite Prompt",
    lead: "这里只给运营改知网和维普的降AIGC率提示词，任务提交后运行时会直接读取这里的最新文本。",
    title: "降AIGC率提示词后台可配",
    desc: "平台只保留大模型主策略，不再给运营暴露复杂运行参数。只需要控制平台启停，并维护每个平台对应的提示词正文。",
    checklist: [
      "至少保留 1 个平台启用，避免前台提交后直接报平台不可用。",
      "提示词里必须保留 `{{paragraph}}` 占位符，运行时会把真实段落插进去。",
      "知网和维普可以共用结构，但文案内容应分别维护。",
    ],
    docs: [],
  },
  dedup_strategy: {
    code: "Dedup Prompt",
    lead: "这里只给运营改知网和维普的降重复率提示词，任务执行时会直接按这里的配置下发。",
    title: "降重复率提示词后台可配",
    desc: "平台固定走大模型主策略，后台只保留最核心的两项：是否启用、提示词文本。这样后续调整策略不需要再改代码发版。",
    checklist: [
      "至少保留 1 个平台启用，避免相关任务无法受理。",
      "提示词里必须保留 `{{paragraph}}` 占位符，运行时会自动替换为待处理段落。",
      "修改后建议立即提交一篇测试任务，确认输出风格符合预期。",
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
    lead: "运营可直接调整 4 个活动的点数规则、关键文案、平台状态和二维码素材。",
    title: "推广中心统一运营配置",
    desc: "保存后前台推广中心会直接按最新配置展示，不需要再改前端代码或后端默认值。",
    checklist: [
      "至少保留 1 张顶部活动卡启用，避免前台进入后无内容可展示。",
      "机构合作至少保留 1 个有效联系卡，并填写二维码地址或微信号。",
      "点数阶梯、标题、副标题、规则说明、平台状态和活动素材都支持后台直接修改。",
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
    name: "体验包",
    price: 19.9,
    credits: 13000,
    description: "适合短篇体验或首次充值用户，低门槛了解检测、降重、改写等处理链路。",
    badge: "新手体验",
    audience: "C端新人体验",
    discount_note: "贴近原价 1.5，几乎无优惠",
    sort_order: 1,
    enabled: true,
  },
  {
    name: "进阶包",
    price: 49.9,
    credits: 40000,
    description: "适合个人长期自用，在多次检测、降重和改写过程中保持稳定储备。",
    badge: "中档优选",
    audience: "个人长期自用",
    discount_note: "中等优惠",
    sort_order: 2,
    enabled: true,
  },
  {
    name: "团队包",
    price: 99.9,
    credits: 100000,
    description: "适合小团队、小代理或多篇文稿集中处理，兼顾成本与处理规模。",
    badge: "高优惠",
    audience: "小团队 / 小代理",
    discount_note: "高优惠",
    sort_order: 3,
    enabled: true,
  },
  {
    name: "批量包",
    price: 199.9,
    credits: 250000,
    description: "适合工作室和批量处理场景，单价达到当前套餐体系的底部区间。",
    badge: "底价档",
    audience: "B端工作室批发",
    discount_note: "完美达到约 0.8 元底价",
    sort_order: 4,
    enabled: true,
  },
]

export const DEFAULT_BILLING_SCHEMA_VERSION = 2
export const DEFAULT_BILLING_PACKAGE_PROFILE_VERSION = 2

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
  police_filing_no: "",
  police_filing_url: "",
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
  schema_version: 2,
  updated_by: "",
  updated_at: "",
  invite_reward_points: 2000,
  contacts: {
    phone: [],
    wechat: [],
    email: [],
  },
  nav_cards: [
    {
      key: "invite",
      title: "邀请有奖",
      badge: "绑定即得点数",
      description: "邀请好友完成手机号与微信绑定，双方都能拿点数。",
      sort_order: 1,
      enabled: true,
    },
    {
      key: "like",
      title: "集赞有奖",
      badge: "截图审核",
      description: "转发活动素材集赞后提交截图，审核通过发放点数。",
      sort_order: 2,
      enabled: true,
    },
    {
      key: "create",
      title: "创作有奖",
      badge: "最高 20000 点",
      description: "发布指定平台内容，按点赞阶梯领取点数奖励。",
      sort_order: 3,
      enabled: true,
    },
    {
      key: "partner",
      title: "机构合作",
      badge: "校园 / 机构",
      description: "校园大使、机构合作与企业服务统一从这里接入。",
      sort_order: 4,
      enabled: true,
    },
  ],
  pages: {
    invite: {
      enabled: true,
      title: "邀请有奖",
      subtitle: "邀请好友完成手机号与微信绑定，双方按规则获得点数奖励。",
      rule_lines: [
        "被邀请者完成手机号与微信绑定后，可获得 2000 点数。",
        "邀请者每产生 1 个有效邀请，可获得 1000 点数。",
        "支持配置里程碑加奖，全部奖励均以点数发放。",
      ],
      quick_actions_title: "快捷操作区",
      bind_code_label: "填写邀请码",
      bind_code_placeholder: "请输入好友邀请码",
      bind_code_button_text: "确认填写",
      share_copy_title: "分享文案",
      share_copy_text: "我正在参加格物推广活动，注册并完成绑定即可拿点数，欢迎通过我的邀请码加入。",
      miniapp_guide_title: "小程序 3 步邀请指引",
      miniapp_steps: [
        "保存二维码或邀请链接，发送给好友。",
        "好友注册后先完成手机号绑定，再完成微信绑定。",
        "达到有效邀请条件后，点数奖励按规则发放。",
      ],
      bind_code_notice: "邀请码在线填写入口待后端接口开放后启用。",
    },
    like: {
      enabled: true,
      title: "集赞有奖",
      subtitle: "扫码转发活动素材集赞，提交截图后由运营审核发放点数。",
      rule_lines: [
        "10 赞可得 10000 点数。",
        "20 赞可得 20000 点数。",
        "活动时间、审核时效与违规处理均支持后台调整。",
      ],
      qrcode_title: "活动二维码",
      review_notice: "截图需清晰完整，默认 1-3 个工作日内完成审核。",
      other_entries_title: "其他活动入口",
      other_entries: [],
    },
    create: {
      enabled: true,
      title: "创作有奖",
      subtitle: "按平台规则发布指定内容，审核通过后按点赞阶梯发放点数。",
      rule_lines: [
        "发帖即送 5000 点数。",
        "点赞达到 10+ 可得 10000 点数。",
        "点赞达到 20+ 可得 20000 点数，单次活动封顶。",
      ],
      platforms: [
        { key: "douyin", label: "抖音", status_text: "可参加", enabled: true },
        { key: "xiaohongshu", label: "小红书", status_text: "可参加", enabled: true },
        { key: "kuaishou", label: "快手", status_text: "可参加", enabled: true },
        { key: "weibo", label: "微博", status_text: "可参加", enabled: true },
        { key: "moments", label: "朋友圈", status_text: "可参加", enabled: true },
      ],
      template_title: "推荐文案模板",
      templates: [
        "我在用格物做论文处理，流程顺、反馈快，做完绑定和任务后还能参加创作活动拿点数。",
        "毕业季论文处理别乱找渠道，我最近在格物做检测和改写，活动期还有点赞点数奖励。",
      ],
      submit_placeholder: "请输入作品链接",
      submit_button_text: "提交链接",
      history_button_text: "查看记录",
    },
    partner: {
      enabled: true,
      title: "机构合作",
      subtitle: "校园大使、机构合作、社群联名与企业服务统一接入。",
      description: "支持校园活动合作、机构代充、批量服务采购与品牌联动推广。",
      benefits: [
        "支持校园大使、社群团长与机构代理合作模式。",
        "支持批量采购、统一对账与定制化服务方案。",
        "支持微信二维码、微信号与合作文案按活动实时替换。",
      ],
      contacts: [
        {
          title: "机构合作顾问",
          description: "院校、机构、企业合作优先对接。",
          wechat_id: "",
          qrcode_url: "/promo-contact-qr-1.jpg",
          enabled: true,
        },
        {
          title: "专属客服",
          description: "处理账号、订单与日常服务咨询。",
          wechat_id: "",
          qrcode_url: "/promo-contact-qr-2.png",
          enabled: true,
        },
      ],
    },
  },
  reward_rules: {
    invite: {
      invitee_bind_reward_points: 2000,
      inviter_valid_invite_reward_points: 1000,
      audit_mode: "manual",
      auto_grant: false,
      milestones: [
        { threshold: 5, reward_points: 3000, label: "邀请满 5 人" },
        { threshold: 20, reward_points: 10000, label: "邀请满 20 人" },
        { threshold: 50, reward_points: 30000, label: "邀请满 50 人" },
      ],
    },
    like: {
      audit_mode: "manual",
      auto_grant: false,
      tiers: [
        { threshold: 10, reward_points: 10000, label: "10 赞" },
        { threshold: 20, reward_points: 20000, label: "20 赞" },
      ],
    },
    create: {
      audit_mode: "manual",
      auto_grant: false,
      tiers: [
        { threshold: 0, reward_points: 5000, label: "发帖即送" },
        { threshold: 10, reward_points: 10000, label: "10+ 赞" },
        { threshold: 20, reward_points: 20000, label: "20+ 赞" },
      ],
    },
  },
  assets: {
    like_qrcode_url: "",
    invite_example_image_url: "",
    partner_primary_qrcode_url: "/promo-contact-qr-1.jpg",
    partner_secondary_qrcode_url: "/promo-contact-qr-2.png",
    platform_douyin_qrcode_url: "/promo-qr-douyin.jpg",
    platform_xiaohongshu_qrcode_url: "/promo-qr-xiaohongshu.jpg",
    platform_bilibili_qrcode_url: "/promo-qr-bilibili.jpg",
    platform_wechat_qrcode_url: "/promo-qr-wechat.jpg",
  },
}

export const DEFAULT_REWRITE_STRATEGY_CONFIG = {
  cnki: {
    rewrite: { enabled: true, active_strategy: "llm", prompt_template: "请严格按照策略处理以下段落：\n\n{{paragraph}}" },
    runtime: {
      chunk_min_chars: 180,
      chunk_max_chars: 260,
      algorithm_chunk_max_changes: 6,
      llm_short_chunk_max_changes: 2,
      llm_medium_chunk_max_changes: 3,
      llm_standard_chunk_max_changes: 4,
      llm_long_chunk_max_changes: 5,
      llm_xlong_chunk_max_changes: 6,
    },
  },
  vip: {
    rewrite: { enabled: true, active_strategy: "llm", prompt_template: "请严格按照策略处理以下段落：\n\n{{paragraph}}" },
    runtime: {
      chunk_min_chars: 180,
      chunk_max_chars: 260,
      algorithm_chunk_max_changes: 6,
      llm_short_chunk_max_changes: 2,
      llm_medium_chunk_max_changes: 3,
      llm_standard_chunk_max_changes: 4,
      llm_long_chunk_max_changes: 5,
      llm_xlong_chunk_max_changes: 6,
    },
  },
}

export const DEFAULT_AIGC_DETECT_STRATEGY_CONFIG = {
  cnki: { aigc_detect: { enabled: true } },
  vip: { aigc_detect: { enabled: true } },
}

export const DEFAULT_DEDUP_STRATEGY_CONFIG = {
  cnki: {
    dedup: { enabled: true, active_strategy: "llm", prompt_template: "请严格按照策略处理以下段落：\n\n{{paragraph}}" },
    runtime: {
      chunk_min_chars: 180,
      chunk_max_chars: 260,
      algorithm_chunk_max_changes: 6,
      llm_short_chunk_max_changes: 2,
      llm_medium_chunk_max_changes: 3,
      llm_standard_chunk_max_changes: 4,
      llm_long_chunk_max_changes: 5,
      llm_xlong_chunk_max_changes: 6,
    },
  },
  vip: {
    dedup: { enabled: true, active_strategy: "llm", prompt_template: "请严格按照策略处理以下段落：\n\n{{paragraph}}" },
    runtime: {
      chunk_min_chars: 180,
      chunk_max_chars: 260,
      algorithm_chunk_max_changes: 6,
      llm_short_chunk_max_changes: 2,
      llm_medium_chunk_max_changes: 3,
      llm_standard_chunk_max_changes: 4,
      llm_long_chunk_max_changes: 5,
      llm_xlong_chunk_max_changes: 6,
    },
  },
}

export const AIGC_DETECT_STRATEGY_PLATFORMS = [
  { key: "cnki", label: "知网AIGC检测", desc: "按知网段级双阈值特征链进行内部检测。" },
  { key: "vip", label: "维普AIGC检测", desc: "按维普段落级多特征加权链进行内部检测。" },
]

export const DEDUP_STRATEGY_PLATFORMS = [
  { key: "cnki", label: "知网降重复率", desc: "当前固定走知网大模型主策略，术语保护和句法重组由大模型链路执行。" },
  { key: "vip", label: "维普降重复率", desc: "当前固定走维普大模型主策略，句法重组和结构变化由大模型链路执行。" },
]

export const REWRITE_STRATEGY_PLATFORMS = [
  { key: "cnki", label: "知网降AIGC率", desc: "旧算法策略已冻结，当前固定走大模型主策略。" },
  { key: "vip", label: "维普降AIGC率", desc: "旧算法策略已冻结，当前固定走大模型主策略。" },
]

export const DEDUP_STRATEGY_OPTIONS = [
  { value: "llm", label: "大模型主策略（固定）" },
]

export function getRewriteStrategyOptions(platformKey) {
  return [{ value: "llm", label: "大模型主策略（固定）" }]
}

export function cloneBillingPackages(packages = DEFAULT_BILLING_PACKAGES) {
  return (Array.isArray(packages) ? packages : DEFAULT_BILLING_PACKAGES)
    .map((pkg, index) => ({
      name: String(pkg?.name || "").trim(),
      price: Number(pkg?.price || 0),
      credits: Number(pkg?.credits || 0),
      description: String(pkg?.description || "").trim(),
      badge: String(pkg?.badge || "").trim(),
      audience: String(pkg?.audience || "").trim(),
      discount_note: String(pkg?.discount_note || "").trim(),
      sort_order: clampAdminInt(pkg?.sort_order, index + 1, 1, 999),
      enabled: pkg?.enabled !== false,
    }))
    .sort((left, right) => {
      if (left.sort_order !== right.sort_order) return left.sort_order - right.sort_order
      return left.name.localeCompare(right.name, "zh-CN")
    })
}

export function normalizeBillingForm(raw) {
  const source = raw && typeof raw === "object" ? raw : {}
  return {
    schema_version: Math.max(
      DEFAULT_BILLING_SCHEMA_VERSION,
      Math.round(Number(source.schema_version ?? DEFAULT_BILLING_SCHEMA_VERSION) || DEFAULT_BILLING_SCHEMA_VERSION),
    ),
    package_profile_version: Math.max(
      DEFAULT_BILLING_PACKAGE_PROFILE_VERSION,
      Math.round(
        Number(source.package_profile_version ?? source.packages_version ?? DEFAULT_BILLING_PACKAGE_PROFILE_VERSION)
          || DEFAULT_BILLING_PACKAGE_PROFILE_VERSION,
      ),
    ),
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
    police_filing_no: String(source.police_filing_no || "").trim(),
    police_filing_url: String(source.police_filing_url || "").trim(),
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
  const defaults = DEFAULT_PROMO_CENTER_CONFIG
  const source = raw && typeof raw === "object" ? raw : {}
  const contacts = source.contacts && typeof source.contacts === "object" ? source.contacts : {}
  const rewardRules = source.reward_rules && typeof source.reward_rules === "object" ? source.reward_rules : {}
  const inviteRules = rewardRules.invite && typeof rewardRules.invite === "object" ? rewardRules.invite : {}
  const likeRules = rewardRules.like && typeof rewardRules.like === "object" ? rewardRules.like : {}
  const createRules = rewardRules.create && typeof rewardRules.create === "object" ? rewardRules.create : {}
  const assets = source.assets && typeof source.assets === "object" ? source.assets : {}
  const legacyInvitePoints = clampAdminInt(source.invite_reward_points, defaults.invite_reward_points, 0, 100000)
  const inviteePoints = clampAdminInt(
    inviteRules.invitee_bind_reward_points,
    legacyInvitePoints,
    0,
    1000000,
  )
  const inviterFallback = Object.keys(inviteRules).length > 0 || source.invite_reward_points === undefined
    ? Math.max(0, Math.floor(inviteePoints / 2))
    : legacyInvitePoints
  const inviterPoints = clampAdminInt(
    inviteRules.inviter_valid_invite_reward_points,
    inviterFallback,
    0,
    1000000,
  )
  const normalized = {
    enabled: source.enabled !== false,
    schema_version: clampAdminInt(source.schema_version, defaults.schema_version, 1, 99),
    updated_by: String(source.updated_by || "").trim().slice(0, 64),
    updated_at: String(source.updated_at || "").trim().slice(0, 64),
    invite_reward_points: inviteePoints,
    contacts: {
      phone: normalizePromotionContactList(contacts.phone),
      wechat: normalizePromotionContactList(contacts.wechat),
      email: normalizePromotionContactList(contacts.email),
    },
    assets: {
      like_qrcode_url: String(assets.like_qrcode_url || defaults.assets.like_qrcode_url || "").trim().slice(0, 256),
      invite_example_image_url: String(assets.invite_example_image_url || defaults.assets.invite_example_image_url || "").trim().slice(0, 256),
      partner_primary_qrcode_url: String(assets.partner_primary_qrcode_url || defaults.assets.partner_primary_qrcode_url || "").trim().slice(0, 256),
      partner_secondary_qrcode_url: String(assets.partner_secondary_qrcode_url || defaults.assets.partner_secondary_qrcode_url || "").trim().slice(0, 256),
      platform_douyin_qrcode_url: String(assets.platform_douyin_qrcode_url || defaults.assets.platform_douyin_qrcode_url || "").trim().slice(0, 256),
      platform_xiaohongshu_qrcode_url: String(assets.platform_xiaohongshu_qrcode_url || defaults.assets.platform_xiaohongshu_qrcode_url || "").trim().slice(0, 256),
      platform_bilibili_qrcode_url: String(assets.platform_bilibili_qrcode_url || defaults.assets.platform_bilibili_qrcode_url || "").trim().slice(0, 256),
      platform_wechat_qrcode_url: String(assets.platform_wechat_qrcode_url || defaults.assets.platform_wechat_qrcode_url || "").trim().slice(0, 256),
    },
  }
  normalized.nav_cards = normalizePromoNavCards(source.nav_cards, defaults.nav_cards)
  normalized.reward_rules = {
    invite: {
      invitee_bind_reward_points: inviteePoints,
      inviter_valid_invite_reward_points: inviterPoints,
      audit_mode: String(inviteRules.audit_mode || defaults.reward_rules.invite.audit_mode || "manual").trim().slice(0, 32) || "manual",
      auto_grant: inviteRules.auto_grant === true,
      milestones: normalizePromoRewardList(inviteRules.milestones, defaults.reward_rules.invite.milestones),
    },
    like: {
      audit_mode: String(likeRules.audit_mode || defaults.reward_rules.like.audit_mode || "manual").trim().slice(0, 32) || "manual",
      auto_grant: likeRules.auto_grant === true,
      tiers: normalizePromoRewardList(likeRules.tiers, defaults.reward_rules.like.tiers),
    },
    create: {
      audit_mode: String(createRules.audit_mode || defaults.reward_rules.create.audit_mode || "manual").trim().slice(0, 32) || "manual",
      auto_grant: createRules.auto_grant === true,
      tiers: normalizePromoRewardList(createRules.tiers, defaults.reward_rules.create.tiers),
    },
  }
  normalized.pages = normalizePromoPages(source.pages, defaults, normalized)
  return normalized
}

function normalizePromoNavCards(rawCards, defaultCards) {
  const sourceCards = Array.isArray(rawCards) ? rawCards : []
  const map = new Map()
  for (const item of sourceCards) {
    const key = String(item?.key || "").trim().toLowerCase()
    if (key) {
      map.set(key, item)
    }
  }
  return defaultCards
    .map((defaultCard, index) => {
      const item = map.get(defaultCard.key) || {}
      return {
        key: defaultCard.key,
        title: String(item.title || defaultCard.title || "").trim().slice(0, 32) || defaultCard.title,
        badge: String(item.badge || defaultCard.badge || "").trim().slice(0, 32),
        description: String(item.description || defaultCard.description || "").trim().slice(0, 120),
        sort_order: clampAdminInt(item.sort_order, defaultCard.sort_order || index + 1, 1, 99),
        enabled: item.enabled !== false,
      }
    })
    .sort((left, right) => {
      if (left.sort_order !== right.sort_order) return left.sort_order - right.sort_order
      return left.key.localeCompare(right.key, "zh-CN")
    })
}

function normalizePromoRewardList(rawList, fallbackList) {
  const source = Array.isArray(rawList) ? rawList : []
  const items = []
  for (const item of source) {
    const rewardPoints = clampAdminInt(item?.reward_points, 0, 0, 1000000)
    if (rewardPoints <= 0) continue
    items.push({
      threshold: clampAdminInt(item?.threshold, 0, 0, 100000),
      reward_points: rewardPoints,
      label: String(item?.label || "").trim().slice(0, 48),
    })
    if (items.length >= 12) break
  }
  if (!items.length) {
    return (Array.isArray(fallbackList) ? fallbackList : []).map((item) => ({
      threshold: clampAdminInt(item?.threshold, 0, 0, 100000),
      reward_points: clampAdminInt(item?.reward_points, 0, 0, 1000000),
      label: String(item?.label || "").trim().slice(0, 48),
    }))
  }
  return items.sort((left, right) => {
    if (left.threshold !== right.threshold) return left.threshold - right.threshold
    return left.reward_points - right.reward_points
  })
}

function normalizePromoPlatforms(rawPlatforms, fallbackPlatforms) {
  const source = Array.isArray(rawPlatforms) ? rawPlatforms : []
  const map = new Map()
  for (const item of source) {
    const key = String(item?.key || "").trim().toLowerCase()
    if (key) {
      map.set(key, item)
    }
  }
  return (Array.isArray(fallbackPlatforms) ? fallbackPlatforms : []).map((item) => {
    const current = map.get(item.key) || {}
    return {
      key: item.key,
      label: String(current.label || item.label || "").trim().slice(0, 24) || item.label,
      status_text: String(current.status_text || item.status_text || "").trim().slice(0, 32),
      enabled: current.enabled !== false && item.enabled !== false,
    }
  })
}

function normalizePromoEntries(rawEntries) {
  if (!Array.isArray(rawEntries)) return []
  const entries = []
  for (const item of rawEntries) {
    const title = String(item?.title || "").trim().slice(0, 32)
    const description = String(item?.description || "").trim().slice(0, 120)
    const qrcode_url = String(item?.qrcode_url || "").trim().slice(0, 256)
    if (!title && !description && !qrcode_url) continue
    entries.push({
      title,
      description,
      qrcode_url,
      enabled: item?.enabled !== false,
    })
    if (entries.length >= 8) break
  }
  return entries
}

function normalizePromoPartnerContacts(rawContacts, fallbackContacts) {
  const source = Array.isArray(rawContacts) ? rawContacts : []
  return (Array.isArray(fallbackContacts) ? fallbackContacts : []).map((item, index) => {
    const current = source[index] && typeof source[index] === "object" ? source[index] : {}
    return {
      title: String(current.title || item.title || "").trim().slice(0, 32) || item.title,
      description: String(current.description || item.description || "").trim().slice(0, 120),
      wechat_id: String(current.wechat_id || item.wechat_id || "").trim().slice(0, 64),
      qrcode_url: String(current.qrcode_url || item.qrcode_url || "").trim().slice(0, 256),
      enabled: current.enabled !== false && item.enabled !== false,
    }
  })
}

function normalizePromoStringList(rawList, fallbackList, limit, maxLen) {
  const source = Array.isArray(rawList) ? rawList : fallbackList
  const lines = []
  for (const item of Array.isArray(source) ? source : []) {
    const text = String(item || "").trim().slice(0, maxLen)
    if (!text) continue
    lines.push(text)
    if (lines.length >= limit) break
  }
  return lines
}

function normalizePromoPages(rawPages, defaults, normalized) {
  const pages = rawPages && typeof rawPages === "object" ? rawPages : {}
  const invite = pages.invite && typeof pages.invite === "object" ? pages.invite : {}
  const like = pages.like && typeof pages.like === "object" ? pages.like : {}
  const create = pages.create && typeof pages.create === "object" ? pages.create : {}
  const partner = pages.partner && typeof pages.partner === "object" ? pages.partner : {}
  return {
    invite: {
      enabled: invite.enabled !== false,
      title: String(invite.title || defaults.pages.invite.title || "").trim().slice(0, 32) || defaults.pages.invite.title,
      subtitle: String(invite.subtitle || defaults.pages.invite.subtitle || "").trim().slice(0, 180),
      rule_lines: normalizePromoStringList(
        invite.rule_lines,
        [
          `被邀请者完成手机号与微信绑定后，可获得 ${normalized.reward_rules.invite.invitee_bind_reward_points} 点数。`,
          `邀请者每产生 1 个有效邀请，可获得 ${normalized.reward_rules.invite.inviter_valid_invite_reward_points} 点数。`,
          "支持配置里程碑加奖，全部奖励均以点数发放。",
        ],
        6,
        120,
      ),
      quick_actions_title: String(invite.quick_actions_title || defaults.pages.invite.quick_actions_title || "").trim().slice(0, 32),
      bind_code_label: String(invite.bind_code_label || defaults.pages.invite.bind_code_label || "").trim().slice(0, 32),
      bind_code_placeholder: String(invite.bind_code_placeholder || defaults.pages.invite.bind_code_placeholder || "").trim().slice(0, 64),
      bind_code_button_text: String(invite.bind_code_button_text || defaults.pages.invite.bind_code_button_text || "").trim().slice(0, 24),
      share_copy_title: String(invite.share_copy_title || defaults.pages.invite.share_copy_title || "").trim().slice(0, 32),
      share_copy_text: String(invite.share_copy_text || defaults.pages.invite.share_copy_text || "").trim().slice(0, 300),
      miniapp_guide_title: String(invite.miniapp_guide_title || defaults.pages.invite.miniapp_guide_title || "").trim().slice(0, 40),
      miniapp_steps: normalizePromoStringList(invite.miniapp_steps, defaults.pages.invite.miniapp_steps, 5, 80),
      bind_code_notice: String(invite.bind_code_notice || defaults.pages.invite.bind_code_notice || "").trim().slice(0, 120),
    },
    like: {
      enabled: like.enabled !== false,
      title: String(like.title || defaults.pages.like.title || "").trim().slice(0, 32) || defaults.pages.like.title,
      subtitle: String(like.subtitle || defaults.pages.like.subtitle || "").trim().slice(0, 180),
      rule_lines: normalizePromoStringList(like.rule_lines, defaults.pages.like.rule_lines, 6, 120),
      qrcode_title: String(like.qrcode_title || defaults.pages.like.qrcode_title || "").trim().slice(0, 32),
      review_notice: String(like.review_notice || defaults.pages.like.review_notice || "").trim().slice(0, 180),
      other_entries_title: String(like.other_entries_title || defaults.pages.like.other_entries_title || "").trim().slice(0, 32),
      other_entries: normalizePromoEntries(like.other_entries),
    },
    create: {
      enabled: create.enabled !== false,
      title: String(create.title || defaults.pages.create.title || "").trim().slice(0, 32) || defaults.pages.create.title,
      subtitle: String(create.subtitle || defaults.pages.create.subtitle || "").trim().slice(0, 180),
      rule_lines: normalizePromoStringList(create.rule_lines, defaults.pages.create.rule_lines, 6, 120),
      platforms: normalizePromoPlatforms(create.platforms, defaults.pages.create.platforms),
      template_title: String(create.template_title || defaults.pages.create.template_title || "").trim().slice(0, 32),
      templates: normalizePromoStringList(create.templates, defaults.pages.create.templates, 8, 220),
      submit_placeholder: String(create.submit_placeholder || defaults.pages.create.submit_placeholder || "").trim().slice(0, 64),
      submit_button_text: String(create.submit_button_text || defaults.pages.create.submit_button_text || "").trim().slice(0, 24),
      history_button_text: String(create.history_button_text || defaults.pages.create.history_button_text || "").trim().slice(0, 24),
    },
    partner: {
      enabled: partner.enabled !== false,
      title: String(partner.title || defaults.pages.partner.title || "").trim().slice(0, 32) || defaults.pages.partner.title,
      subtitle: String(partner.subtitle || defaults.pages.partner.subtitle || "").trim().slice(0, 180),
      description: String(partner.description || defaults.pages.partner.description || "").trim().slice(0, 240),
      benefits: normalizePromoStringList(partner.benefits, defaults.pages.partner.benefits, 6, 120),
      contacts: normalizePromoPartnerContacts(partner.contacts, defaults.pages.partner.contacts),
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
    cnki: normalizeRewriteStrategyEntry(source.cnki, DEFAULT_REWRITE_STRATEGY_CONFIG.cnki, "cnki"),
    vip: normalizeRewriteStrategyEntry(source.vip, DEFAULT_REWRITE_STRATEGY_CONFIG.vip, "vip"),
  }
}

export function normalizeRewriteStrategyEntry(raw, fallback, platform = "") {
  const source = raw && typeof raw === "object" ? raw : {}
  const rewrite = source.rewrite && typeof source.rewrite === "object" ? source.rewrite : {}
  const runtime = source.runtime && typeof source.runtime === "object" ? source.runtime : {}
  const defaultRewrite = fallback?.rewrite || DEFAULT_REWRITE_STRATEGY_CONFIG.cnki.rewrite
  const defaultRuntime = fallback?.runtime || DEFAULT_REWRITE_STRATEGY_CONFIG.cnki.runtime
  const strategy = String(rewrite.active_strategy || defaultRewrite.active_strategy || "llm").trim().toLowerCase()
  const normalizedPlatform = String(platform || "").trim().toLowerCase()
  const resolvedStrategy = normalizedPlatform ? "llm" : strategy === "llm" ? "llm" : "llm"
  const normalizedRuntime = {
    chunk_min_chars: clampAdminInt(runtime.chunk_min_chars, Number(defaultRuntime.chunk_min_chars) || 180, 80, 1200),
    chunk_max_chars: clampAdminInt(runtime.chunk_max_chars, Number(defaultRuntime.chunk_max_chars) || 260, 100, 1600),
    algorithm_chunk_max_changes: clampAdminInt(runtime.algorithm_chunk_max_changes, Number(defaultRuntime.algorithm_chunk_max_changes) || 6, 1, 20),
    llm_short_chunk_max_changes: clampAdminInt(runtime.llm_short_chunk_max_changes, Number(defaultRuntime.llm_short_chunk_max_changes) || 2, 1, 20),
    llm_medium_chunk_max_changes: clampAdminInt(runtime.llm_medium_chunk_max_changes, Number(defaultRuntime.llm_medium_chunk_max_changes) || 3, 1, 20),
    llm_standard_chunk_max_changes: clampAdminInt(runtime.llm_standard_chunk_max_changes, Number(defaultRuntime.llm_standard_chunk_max_changes) || 4, 1, 20),
    llm_long_chunk_max_changes: clampAdminInt(runtime.llm_long_chunk_max_changes, Number(defaultRuntime.llm_long_chunk_max_changes) || 5, 1, 20),
    llm_xlong_chunk_max_changes: clampAdminInt(runtime.llm_xlong_chunk_max_changes, Number(defaultRuntime.llm_xlong_chunk_max_changes) || 6, 1, 20),
  }
  normalizedRuntime.chunk_max_chars = Math.max(normalizedRuntime.chunk_max_chars, normalizedRuntime.chunk_min_chars + 20)
  normalizedRuntime.llm_medium_chunk_max_changes = Math.max(normalizedRuntime.llm_medium_chunk_max_changes, normalizedRuntime.llm_short_chunk_max_changes)
  normalizedRuntime.llm_standard_chunk_max_changes = Math.max(normalizedRuntime.llm_standard_chunk_max_changes, normalizedRuntime.llm_medium_chunk_max_changes)
  normalizedRuntime.llm_long_chunk_max_changes = Math.max(normalizedRuntime.llm_long_chunk_max_changes, normalizedRuntime.llm_standard_chunk_max_changes)
  normalizedRuntime.llm_xlong_chunk_max_changes = Math.max(normalizedRuntime.llm_xlong_chunk_max_changes, normalizedRuntime.llm_long_chunk_max_changes)
  const defaultPromptTemplate = String(defaultRewrite.prompt_template || "").trim()
  let promptTemplate = String(rewrite.prompt_template || defaultPromptTemplate).trim().slice(0, 20000)
  if (!promptTemplate) {
    promptTemplate = defaultPromptTemplate
  }
  if (!promptTemplate.includes("{{paragraph}}")) {
    promptTemplate = `${promptTemplate}\n\n待改写段落：\n{{paragraph}}`.trim()
  }
  return {
    rewrite: {
      enabled: rewrite.enabled !== undefined ? rewrite.enabled === true : defaultRewrite.enabled !== false,
      active_strategy: resolvedStrategy,
      prompt_template: promptTemplate,
    },
    runtime: normalizedRuntime,
  }
}

export function normalizeDedupStrategyConfig(raw = {}) {
  const source = raw && typeof raw === "object" ? raw : {}
  return {
    cnki: normalizeDedupStrategyEntry(source.cnki, DEFAULT_DEDUP_STRATEGY_CONFIG.cnki, "cnki"),
    vip: normalizeDedupStrategyEntry(source.vip, DEFAULT_DEDUP_STRATEGY_CONFIG.vip, "vip"),
  }
}

export function normalizeDedupStrategyEntry(raw, fallback, platform = "") {
  const source = raw && typeof raw === "object" ? raw : {}
  const dedup = source.dedup && typeof source.dedup === "object" ? source.dedup : {}
  const runtime = source.runtime && typeof source.runtime === "object" ? source.runtime : {}
  const defaultDedup = fallback?.dedup || DEFAULT_DEDUP_STRATEGY_CONFIG.cnki.dedup
  const defaultRuntime = fallback?.runtime || DEFAULT_DEDUP_STRATEGY_CONFIG.cnki.runtime
  const strategy = String(dedup.active_strategy || defaultDedup.active_strategy || "llm").trim().toLowerCase()
  const normalizedPlatform = String(platform || "").trim().toLowerCase()
  const normalizedRuntime = {
    chunk_min_chars: clampAdminInt(runtime.chunk_min_chars, Number(defaultRuntime.chunk_min_chars) || 180, 80, 1200),
    chunk_max_chars: clampAdminInt(runtime.chunk_max_chars, Number(defaultRuntime.chunk_max_chars) || 260, 100, 1600),
    algorithm_chunk_max_changes: clampAdminInt(runtime.algorithm_chunk_max_changes, Number(defaultRuntime.algorithm_chunk_max_changes) || 6, 1, 20),
    llm_short_chunk_max_changes: clampAdminInt(runtime.llm_short_chunk_max_changes, Number(defaultRuntime.llm_short_chunk_max_changes) || 2, 1, 20),
    llm_medium_chunk_max_changes: clampAdminInt(runtime.llm_medium_chunk_max_changes, Number(defaultRuntime.llm_medium_chunk_max_changes) || 3, 1, 20),
    llm_standard_chunk_max_changes: clampAdminInt(runtime.llm_standard_chunk_max_changes, Number(defaultRuntime.llm_standard_chunk_max_changes) || 4, 1, 20),
    llm_long_chunk_max_changes: clampAdminInt(runtime.llm_long_chunk_max_changes, Number(defaultRuntime.llm_long_chunk_max_changes) || 5, 1, 20),
    llm_xlong_chunk_max_changes: clampAdminInt(runtime.llm_xlong_chunk_max_changes, Number(defaultRuntime.llm_xlong_chunk_max_changes) || 6, 1, 20),
  }
  normalizedRuntime.chunk_max_chars = Math.max(normalizedRuntime.chunk_max_chars, normalizedRuntime.chunk_min_chars + 20)
  normalizedRuntime.llm_medium_chunk_max_changes = Math.max(normalizedRuntime.llm_medium_chunk_max_changes, normalizedRuntime.llm_short_chunk_max_changes)
  normalizedRuntime.llm_standard_chunk_max_changes = Math.max(normalizedRuntime.llm_standard_chunk_max_changes, normalizedRuntime.llm_medium_chunk_max_changes)
  normalizedRuntime.llm_long_chunk_max_changes = Math.max(normalizedRuntime.llm_long_chunk_max_changes, normalizedRuntime.llm_standard_chunk_max_changes)
  normalizedRuntime.llm_xlong_chunk_max_changes = Math.max(normalizedRuntime.llm_xlong_chunk_max_changes, normalizedRuntime.llm_long_chunk_max_changes)
  const defaultPromptTemplate = String(defaultDedup.prompt_template || "").trim()
  let promptTemplate = String(dedup.prompt_template || defaultPromptTemplate).trim().slice(0, 20000)
  if (!promptTemplate) {
    promptTemplate = defaultPromptTemplate
  }
  if (!promptTemplate.includes("{{paragraph}}")) {
    promptTemplate = `${promptTemplate}\n\n待改写段落：\n{{paragraph}}`.trim()
  }
  return {
    dedup: {
      enabled: dedup.enabled !== undefined ? dedup.enabled === true : defaultDedup.enabled !== false,
      active_strategy: normalizedPlatform ? "llm" : strategy === "llm" ? "llm" : "llm",
      prompt_template: promptTemplate,
    },
    runtime: normalizedRuntime,
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

export function strategyDescription(strategy, platform = "") {
  const normalizedPlatform = String(platform || "").trim().toLowerCase()
  const normalizedStrategy = String(strategy || "").trim().toLowerCase()
  if (normalizedStrategy !== "llm") {
    return "该平台已冻结为大模型主策略，保存时会自动纠正为 llm。"
  }
  if (normalizedPlatform === "cnki") {
    return "固定走知网大模型主策略。降AIGC率严格执行 Prompt A -> Prompt B 闭环校验链路，结果仍会经过统一质检闸门。"
  }
  if (normalizedPlatform === "vip") {
    return "固定走维普大模型主策略，结果仍会经过统一质检闸门。"
  }
  return "固定走大模型主策略，结果仍会经过统一质检闸门。"
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
    audience: "",
    discount_note: "",
    sort_order: 1,
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
      if (!(Number(pkg.sort_order) > 0)) return `套餐 ${pkg.name} 排序必须大于 0`
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
    const cfg = normalizePromotionCenterConfig(forms.promo_center)
    if (!cfg.nav_cards.some((item) => item.enabled)) {
      return "顶部活动卡至少需要启用 1 个"
    }
    if (cfg.reward_rules.invite.invitee_bind_reward_points < 0 || cfg.reward_rules.invite.inviter_valid_invite_reward_points < 0) {
      return "邀请奖励点数不能小于 0"
    }
    if (!cfg.pages.partner.contacts.some((item) => item.enabled && (item.qrcode_url || item.wechat_id))) {
      return "机构合作至少需要配置 1 个有效联系卡片"
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
    payload.schema_version = normalized.schema_version
    payload.package_profile_version = normalized.package_profile_version
    payload.aigc_points_per_char = normalized.aigc_points_per_char
    payload.dedup_points_per_char = normalized.dedup_points_per_char
    payload.rewrite_points_per_char = normalized.rewrite_points_per_char
    payload.packages = normalized.packages.map((pkg) => ({
      name: pkg.name,
      price: Number(pkg.price),
      credits: Number(pkg.credits),
      description: pkg.description,
      badge: pkg.badge,
      audience: pkg.audience,
      discount_note: pkg.discount_note,
      sort_order: Number(pkg.sort_order),
      enabled: Boolean(pkg.enabled),
    }))
    delete payload.aigc_rate
    delete payload.dedup_rate
    delete payload.rewrite_rate
    delete payload.packages_version
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
    payload.police_filing_no = normalized.police_filing_no.slice(0, 128)
    payload.police_filing_url = normalized.police_filing_url.slice(0, 256)
    payload.contact_phone = normalized.contact_phone.slice(0, 32)
    payload.contact_email = normalized.contact_email.slice(0, 128)
    payload.publish_note = normalized.publish_note.slice(0, 500)
    payload.wechat_miniprogram_app_id = normalized.wechat_miniprogram_app_id.slice(0, 128)
    payload.wechat_miniprogram_app_secret = normalized.wechat_miniprogram_app_secret.slice(0, 256)
  }
  if (category === "promo_center") {
    const normalized = normalizePromotionCenterConfig(payload)
    payload.enabled = normalized.enabled
    payload.schema_version = normalized.schema_version
    payload.updated_by = normalized.updated_by
    payload.updated_at = normalized.updated_at
    payload.invite_reward_points = normalized.invite_reward_points
    payload.contacts = normalized.contacts
    payload.nav_cards = normalized.nav_cards.map((item) => ({
      key: item.key,
      title: item.title,
      badge: item.badge,
      description: item.description,
      sort_order: Number(item.sort_order),
      enabled: Boolean(item.enabled),
    }))
    payload.pages = {
      invite: {
        ...normalized.pages.invite,
        rule_lines: [...normalized.pages.invite.rule_lines],
        miniapp_steps: [...normalized.pages.invite.miniapp_steps],
      },
      like: {
        ...normalized.pages.like,
        rule_lines: [...normalized.pages.like.rule_lines],
        other_entries: normalized.pages.like.other_entries.map((item) => ({
          title: item.title,
          description: item.description,
          qrcode_url: item.qrcode_url,
          enabled: Boolean(item.enabled),
        })),
      },
      create: {
        ...normalized.pages.create,
        rule_lines: [...normalized.pages.create.rule_lines],
        templates: [...normalized.pages.create.templates],
        platforms: normalized.pages.create.platforms.map((item) => ({
          key: item.key,
          label: item.label,
          status_text: item.status_text,
          enabled: Boolean(item.enabled),
        })),
      },
      partner: {
        ...normalized.pages.partner,
        benefits: [...normalized.pages.partner.benefits],
        contacts: normalized.pages.partner.contacts.map((item) => ({
          title: item.title,
          description: item.description,
          wechat_id: item.wechat_id,
          qrcode_url: item.qrcode_url,
          enabled: Boolean(item.enabled),
        })),
      },
    }
    payload.reward_rules = {
      invite: {
        invitee_bind_reward_points: Number(normalized.reward_rules.invite.invitee_bind_reward_points),
        inviter_valid_invite_reward_points: Number(normalized.reward_rules.invite.inviter_valid_invite_reward_points),
        audit_mode: normalized.reward_rules.invite.audit_mode,
        auto_grant: Boolean(normalized.reward_rules.invite.auto_grant),
        milestones: normalized.reward_rules.invite.milestones.map((item) => ({
          threshold: Number(item.threshold),
          reward_points: Number(item.reward_points),
          label: item.label,
        })),
      },
      like: {
        audit_mode: normalized.reward_rules.like.audit_mode,
        auto_grant: Boolean(normalized.reward_rules.like.auto_grant),
        tiers: normalized.reward_rules.like.tiers.map((item) => ({
          threshold: Number(item.threshold),
          reward_points: Number(item.reward_points),
          label: item.label,
        })),
      },
      create: {
        audit_mode: normalized.reward_rules.create.audit_mode,
        auto_grant: Boolean(normalized.reward_rules.create.auto_grant),
        tiers: normalized.reward_rules.create.tiers.map((item) => ({
          threshold: Number(item.threshold),
          reward_points: Number(item.reward_points),
          label: item.label,
        })),
      },
    }
    payload.assets = {
      like_qrcode_url: normalized.assets.like_qrcode_url,
      invite_example_image_url: normalized.assets.invite_example_image_url,
      partner_primary_qrcode_url: normalized.assets.partner_primary_qrcode_url,
      partner_secondary_qrcode_url: normalized.assets.partner_secondary_qrcode_url,
      platform_douyin_qrcode_url: normalized.assets.platform_douyin_qrcode_url,
      platform_xiaohongshu_qrcode_url: normalized.assets.platform_xiaohongshu_qrcode_url,
      platform_bilibili_qrcode_url: normalized.assets.platform_bilibili_qrcode_url,
      platform_wechat_qrcode_url: normalized.assets.platform_wechat_qrcode_url,
    }
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
