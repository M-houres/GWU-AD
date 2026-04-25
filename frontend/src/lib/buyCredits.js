export const PACKAGE_PRESENTATION = {
  体验包: {
    audienceText: "C端新人体验",
    descriptionText: "适合首次充值和轻量体验，先验证整套处理链路是否符合自己的使用预期。",
    toneClass: "is-slate",
  },
  进阶包: {
    audienceText: "个人长期自用",
    descriptionText: "适合个人持续使用，兼顾价格门槛、处理规模和日常储备。",
    toneClass: "is-azure",
  },
  团队包: {
    audienceText: "小团队 / 小代理",
    descriptionText: "适合多人协作或多篇文稿集中处理，单价已经进入高优惠区间。",
    toneClass: "is-amber",
  },
  批量包: {
    audienceText: "B端工作室批发",
    descriptionText: "适合稳定批量处理场景，在现有套餐体系中达到更低的单位处理成本。",
    toneClass: "is-graphite",
  },
}

export const ALL_PAYMENT_PROVIDERS = [
  { value: "mock", label: "测试支付" },
  { value: "wechat", label: "微信支付" },
]

export function resolveProviderOptions(supportedProviderValues, paymentTestMode) {
  if (supportedProviderValues.length > 0) {
    return ALL_PAYMENT_PROVIDERS.filter((item) => supportedProviderValues.includes(item.value))
  }
  return paymentTestMode
    ? ALL_PAYMENT_PROVIDERS.filter((item) => item.value === "mock")
    : ALL_PAYMENT_PROVIDERS.filter((item) => item.value === "wechat")
}

export function normalizePackageOption(item, index) {
  const packageName = String(item?.name || "").trim()
  const amountCny = Number(item?.amount_cny ?? item?.price ?? 0)
  const credits = Number(item?.credits ?? item?.recharge_fen ?? 0)
  if (!packageName || !Number.isFinite(amountCny) || amountCny <= 0 || !Number.isFinite(credits) || credits <= 0) {
    return null
  }

  const presentation = PACKAGE_PRESENTATION[packageName] || {}
  const processableChars = Math.max(0, Math.round(Number(item?.processable_chars ?? credits) || 0))
  const pricePerKchar = Number(item?.price_per_kchar ?? (processableChars > 0 ? amountCny / (processableChars / 1000) : 0))
  const audienceText = String(item?.audience || "").trim() || presentation.audienceText || "适合按需补充处理字数"
  const descriptionText = String(item?.description || "").trim() || presentation.descriptionText || "适合当前阶段补充处理字数储备。"
  const discountNote = String(item?.discount_note || "").trim()

  return {
    key: packageName || `package_${index}`,
    packageName,
    displayName: packageName,
    priceLabel: amountCny.toFixed(1).replace(/\.0$/, ".0"),
    priceHint: "一次购买，支付成功后立即到账",
    credits,
    creditsLabel: `${credits.toLocaleString()} 积分`,
    processableChars,
    processableCharsLabel: `${processableChars.toLocaleString()} 字`,
    pricePerKchar,
    pricePerKcharLabel: `${pricePerKchar.toFixed(2)} 元/千字`,
    badge: String(item?.badge || "").trim(),
    toneClass: presentation.toneClass || "is-slate",
    audienceText,
    descriptionText,
    discountNote,
    estimateHeadline: `约可处理 ${processableChars.toLocaleString()} 字`,
    estimateText: `按当前规则 1 积分 = 1 字符，约可处理 ${processableChars.toLocaleString()} 字内容。`,
  }
}

export function resolvePaymentError(error, fallback = "操作失败") {
  const message = String(error?.message || "").trim()
  if (!message) return fallback
  if (message.includes("网络连接异常")) {
    return "支付链路连接短暂波动，请稍候重试。若订单可能已创建，请先刷新二维码，避免重复支付。"
  }
  if (message.includes("请求超时")) {
    return "支付通道响应较慢，请稍候重试。若订单已创建，可直接刷新二维码继续支付。"
  }
  if (message.includes("服务暂时不可用")) {
    return "支付服务暂时繁忙，请稍后再试。"
  }
  return message
}
