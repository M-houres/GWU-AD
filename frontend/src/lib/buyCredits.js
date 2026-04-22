export const PACKAGE_PRESENTATION = {
  入门版: {
    audienceText: "适合首次提交或轻量试用",
    descriptionText: "适合首次提交或轻量试用，先完成一篇文稿的真实处理体验。",
    toneClass: "is-slate",
  },
  基础版: {
    audienceText: "适合常规单人使用",
    descriptionText: "适合常规单人使用，覆盖日常检测、降重和降 AIGC 需求。",
    toneClass: "is-azure",
  },
  专业版: {
    audienceText: "适合多篇文稿反复修改",
    descriptionText: "适合多篇文稿反复修改，在定稿阶段更从容地做多轮处理。",
    toneClass: "is-amber",
  },
  增强版: {
    audienceText: "适合连续提交和批量处理",
    descriptionText: "适合连续提交和批量处理，兼顾批量任务与点数储备。",
    toneClass: "is-graphite",
  },
  高级版: {
    audienceText: "适合中高频长期使用",
    descriptionText: "适合中高频长期使用，在较长周期内保持稳定处理能力。",
    toneClass: "is-azure",
  },
  旗舰版: {
    audienceText: "适合团队或高频大规模使用",
    descriptionText: "适合团队或高频大规模使用，满足持续批量提交场景。",
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
  const estimatedArticles = Math.max(1, Math.floor(credits / 8000))

  return {
    key: packageName || `package_${index}`,
    packageName,
    displayName: packageName,
    priceLabel: amountCny.toFixed(2),
    priceHint: "一次购买，立即到账",
    credits,
    creditsLabel: `${credits.toLocaleString()} 通用点数`,
    badge: String(item?.badge || "").trim(),
    toneClass: presentation.toneClass || "is-slate",
    audienceText: presentation.audienceText || "适合按需补充通用点数",
    descriptionText: presentation.descriptionText || String(item?.description || "").trim() || "适合当前阶段补充点数储备。",
    estimateHeadline: `约可处理 ${estimatedArticles} 篇 8000 字文稿`,
    estimateText: `按当前计费口径估算，约可处理 ${estimatedArticles} 篇 8000 字文稿。`,
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
