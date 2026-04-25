const { request } = require("../../utils/request")
const { getUser, setUser, getPartnerTracking } = require("../../utils/storage")
const { logout, ensureLogin } = require("../../utils/auth")
const { requireAuth, getPendingAuth, clearPendingAuth } = require("../../utils/authFlow")
const { getOrderStatusText, parseWxPayError, toFriendlyError } = require("../../utils/status")
const { getOrderStatusTone } = require("../../utils/display")

const DEFAULT_NOTICE = {
  title: "系统公告",
  content: "当前暂无公告内容。",
  version: 1,
}

const PACKAGE_BADGES = ["轻量", "常用", "进阶", "高频"]

function getProviderLabel(value, providers = []) {
  const matched = providers.find((item) => item.value === value)
  return matched ? matched.label : value || "-"
}

function pickDefaultProvider(providers = []) {
  const order = ["wechat", "mock"]
  for (const value of order) {
    if (providers.some((item) => item.value === value)) return value
  }
  return providers[0] ? providers[0].value : "wechat"
}

function formatQuotaText(quota = {}) {
  const limit = Number(quota.daily_free_limit || 0)
  const remaining = Number(quota.free_remaining_today)
  if (!Number.isFinite(limit) || limit <= 0 || !Number.isFinite(remaining)) {
    return "每日免费 6 篇"
  }
  return `今日剩余 ${Math.max(remaining, 0)} / ${limit}`
}

function normalizePackages(items = []) {
  return items.map((item, index) => ({
    ...item,
    badgeText: String(item.badge || "").trim() || PACKAGE_BADGES[index % PACKAGE_BADGES.length],
    descText: String(item.description || "").trim() || "支付成功后积分会自动到账",
  }))
}

function normalizePayError(error) {
  const message = toFriendlyError(error, "创建订单失败")
  if (message.includes("openid")) {
    return "当前账号缺少微信支付身份，请退出后重新微信登录"
  }
  return message
}

Page({
  data: {
    guestMode: true,
    user: {},
    quotaInfo: {},
    displayName: "未命名用户",
    avatarText: "格",
    profileItems: [],
    notice: DEFAULT_NOTICE,
    showNotice: false,
    loadingPackages: false,
    creating: false,
    creatingPackageName: "",
    paying: false,
    packages: [],
    paymentTestMode: false,
    paymentMessage: "",
    providers: [],
    selectedProvider: "wechat",
    selectedProviderLabel: "微信支付",
    orderNo: "",
    orderProvider: "",
    orderProviderLabel: "",
    orderStatus: "created",
    orderStatusText: getOrderStatusText("created"),
    orderStatusClass: getOrderStatusTone("created"),
    remainSeconds: 0,
    qrcodeDataUrl: "",
    paymentParams: null,
    partnerTrackingLabel: "",
  },

  countdownTimer: null,
  pollTimer: null,

  onShow() {
    if (ensureLogin()) {
      this.syncProfile(getUser() || {})
      this.loadProfile()
      this.consumePendingAction()
      this.loadPackages()
    } else {
      this.syncGuestProfile()
    }
  },

  onHide() {
    this.stopTimers()
  },

  onUnload() {
    this.stopTimers()
  },

  syncProfile(user = {}, quota = {}) {
    const rawNickname = String(user.nickname || "").trim()
    const displayName = rawNickname || "未命名用户"
    const avatarText = displayName ? displayName.slice(0, 1) : "格"

      this.setData({
        guestMode: false,
      user,
      quotaInfo: quota,
      displayName,
      avatarText,
        profileItems: [
          { label: "手机号", value: user.phone || "未绑定" },
          { label: "当前积分", value: String(Number(user.credits || 0)) },
          { label: "AIGC权益", value: formatQuotaText(quota) },
        ],
        partnerTrackingLabel: this.formatPartnerTrackingLabel(),
      })
  },

  syncGuestProfile() {
    this.setData({
      guestMode: true,
      user: {},
      quotaInfo: {},
      displayName: "微信游客",
      avatarText: "游",
      profileItems: [],
      notice: DEFAULT_NOTICE,
      showNotice: false,
      loadingPackages: false,
      packages: [],
      paymentTestMode: false,
      paymentMessage: "",
      providers: [],
      selectedProvider: "wechat",
      selectedProviderLabel: "微信支付",
      orderNo: "",
      orderProvider: "",
      orderProviderLabel: "",
      orderStatus: "created",
      orderStatusText: getOrderStatusText("created"),
      orderStatusClass: getOrderStatusTone("created"),
      remainSeconds: 0,
      qrcodeDataUrl: "",
      paymentParams: null,
      partnerTrackingLabel: "",
    })
  },

  formatPartnerTrackingLabel() {
    const tracking = getPartnerTracking()
    if (!tracking || !tracking.channel_code) return ""
    return `当前渠道归属：${tracking.channel_code}`
  },

  consumePendingAction() {
    const pending = getPendingAuth()
    if (!pending || pending.targetTab !== "profile") return

    clearPendingAuth()

    if (pending.action === "create_order" && pending.packageName) {
      wx.nextTick(() => this.createOrderByName(pending.packageName))
      return
    }

    if (pending.action === "session_expired") {
      wx.showToast({ title: "登录状态已更新，请继续操作", icon: "none" })
    }
  },

  async loadProfile() {
    if (!ensureLogin()) return
    try {
      const [options, profile, summary] = await Promise.all([
        request({ url: "/auth/options", method: "GET", silent: true }),
        request({ url: "/users/me", method: "GET", silent: true }),
        request({ url: "/users/me/summary", method: "GET", silent: true }),
      ])

      const notice = options && options.notice ? options.notice : this.data.notice

      this.syncProfile(profile || {}, (summary && summary.aigc_quota) || {})
      this.setData({
        notice,
        showNotice: !!(notice && notice.enabled !== false && (notice.title || notice.content)),
      })
      setUser(profile)
    } catch (_) {
      // keep current view
    }
  },

  async loadPackages() {
    if (this.data.loadingPackages) return

    this.setData({ loadingPackages: true })
    try {
      const data = await request({ url: "/billing/packages", method: "GET", silent: true })
      const supported = Array.isArray(data.supported_providers) ? data.supported_providers : []
      const paymentTestMode = !!data.payment_test_mode
      const allProviders = paymentTestMode
        ? [
            { value: "wechat", label: "微信支付" },
            { value: "mock", label: "测试支付" },
          ]
        : [{ value: "wechat", label: "微信支付" }]

      let providers = supported.length
        ? allProviders.filter((item) => supported.includes(item.value))
        : allProviders

      if (!providers.length) {
        providers = allProviders
      }

      const selectedProvider = providers.some((item) => item.value === this.data.selectedProvider)
        ? this.data.selectedProvider
        : pickDefaultProvider(providers)

      this.setData({
        packages: normalizePackages(data.items || []),
        paymentTestMode,
        paymentMessage: String(data.message || "").trim(),
        providers,
        selectedProvider,
        selectedProviderLabel: getProviderLabel(selectedProvider, providers),
        partnerTrackingLabel: this.formatPartnerTrackingLabel(),
      })
    } catch (_) {
      // keep current view
    } finally {
      this.setData({ loadingPackages: false })
    }
  },

  onReload() {
    if (ensureLogin()) {
      this.loadProfile()
      this.loadPackages()
    } else {
      this.syncGuestProfile()
    }
  },

  onTapGuestLogin() {
    requireAuth({ targetTab: "profile", action: "open_profile" })
  },

  onSelectProvider(e) {
    const selectedProvider = e.currentTarget.dataset.value || "wechat"
    this.setData({
      selectedProvider,
      selectedProviderLabel: getProviderLabel(selectedProvider, this.data.providers),
    })
  },

  async createOrderByName(packageName) {
    if (!packageName || this.data.creating) return

    this.setData({ creating: true, creatingPackageName: packageName })
    try {
      const data = await request({
        url: "/billing/create-order",
        method: "POST",
        data: {
          package_name: packageName,
          provider: this.data.selectedProvider,
          scene: "miniprogram",
          ...(function() {
            const tracking = getPartnerTracking()
            if (!tracking) return {}
            return {
              channel_code: tracking.channel_code,
              channel_token: tracking.channel_token,
            }
          })(),
        },
      })

      const orderStatus = data.status || "created"
      const orderProvider = data.provider || this.data.selectedProvider

      if (orderProvider === "wechat" && !data.payment_params) {
        throw new Error("微信支付参数缺失，请检查支付配置")
      }

      this.setData({
        orderNo: data.order_no || "",
        orderProvider,
        orderProviderLabel: getProviderLabel(orderProvider, this.data.providers),
        orderStatus,
        orderStatusText: getOrderStatusText(orderStatus),
        orderStatusClass: getOrderStatusTone(orderStatus),
        remainSeconds: Number(data.expire_seconds || 0),
        qrcodeDataUrl: data.qrcode_data_url || "",
        paymentParams: data.payment_params || null,
      })

      this.startTimers()

      if (data.provider_fallback) {
        wx.showToast({ title: "当前已切换为测试支付", icon: "none" })
      }

      if (orderProvider === "wechat" && data.payment_params) {
        await this.onStartWechatPay()
      }
    } catch (error) {
      wx.showToast({ title: normalizePayError(error), icon: "none" })
    } finally {
      this.setData({ creating: false, creatingPackageName: "" })
    }
  },

  async onCreateOrder(e) {
    const packageName = e.currentTarget.dataset.name
    if (!packageName) return
    if (!ensureLogin()) {
      requireAuth({ targetTab: "profile", action: "create_order", packageName })
      return
    }
    await this.createOrderByName(packageName)
  },

  async onRefreshOrder() {
    await this.checkOrderStatus()
  },

  async onConfirmPaid() {
    if (!this.data.orderNo) return

    try {
      const data = await request({
        url: `/billing/order-pay/${this.data.orderNo}`,
        method: "POST",
      })
      const status = data.status || "paid"
      this.setData({
        orderStatus: status,
        orderStatusText: getOrderStatusText(status),
        orderStatusClass: getOrderStatusTone(status),
        remainSeconds: 0,
      })
      this.stopTimers()
      await this.loadProfile()
      wx.showToast({ title: "支付成功", icon: "success" })
    } catch (error) {
      wx.showToast({ title: toFriendlyError(error, "支付确认失败"), icon: "none" })
    }
  },

  async onStartWechatPay() {
    if (!this.data.paymentParams || this.data.paying) return

    this.setData({ paying: true })
    try {
      await this.requestWechatPayment(this.data.paymentParams)
      wx.showToast({ title: "支付结果确认中", icon: "none" })
      await this.checkOrderStatus()
    } catch (error) {
      wx.showToast({ title: parseWxPayError(error), icon: "none" })
    } finally {
      this.setData({ paying: false })
    }
  },

  requestWechatPayment(params) {
    return new Promise((resolve, reject) => {
      wx.requestPayment({
        timeStamp: String(params.timeStamp || ""),
        nonceStr: String(params.nonceStr || ""),
        package: String(params.package || ""),
        signType: String(params.signType || "RSA"),
        paySign: String(params.paySign || ""),
        success: resolve,
        fail: reject,
      })
    })
  },

  startTimers() {
    this.stopTimers()

    this.countdownTimer = setInterval(() => {
      const next = Number(this.data.remainSeconds || 0) - 1
      if (next <= 0) {
        this.setData({
          remainSeconds: 0,
          orderStatus: "closed",
          orderStatusText: getOrderStatusText("closed"),
          orderStatusClass: getOrderStatusTone("closed"),
        })
        this.stopTimers()
        return
      }
      this.setData({ remainSeconds: next })
    }, 1000)

    this.pollTimer = setInterval(() => {
      this.checkOrderStatus()
    }, 3000)
  },

  stopTimers() {
    if (this.countdownTimer) {
      clearInterval(this.countdownTimer)
      this.countdownTimer = null
    }
    if (this.pollTimer) {
      clearInterval(this.pollTimer)
      this.pollTimer = null
    }
  },

  async checkOrderStatus() {
    if (!this.data.orderNo) return

    try {
      const data = await request({
        url: `/billing/order-status/${this.data.orderNo}`,
        method: "GET",
        silent: true,
      })

      const status = data.status || "created"
      const remain = Number(data.remain_seconds || 0)

      this.setData({
        orderStatus: status,
        orderStatusText: getOrderStatusText(status),
        orderStatusClass: getOrderStatusTone(status),
        remainSeconds: remain >= 0 ? remain : 0,
      })

      if (status === "paid") {
        this.stopTimers()
        await this.loadProfile()
      } else if (status === "closed") {
        this.stopTimers()
      }
    } catch (_) {
      // keep polling
    }
  },

  onLogout() {
    wx.showModal({
      title: "退出登录",
      content: "退出后将清除当前登录状态，需要重新登录后才能继续下单和查看记录。是否继续？",
      success: (res) => {
        if (!res.confirm) return
        logout()
        this.syncGuestProfile()
        wx.switchTab({ url: "/pages/home/index" })
      },
    })
  },

  onDeleteAccount() {
    wx.showModal({
      title: "注销账号",
      content: "注销后将清空当前账号的任务文件与登录身份，无法恢复。是否继续？",
      success: async (res) => {
        if (!res.confirm) return
        try {
          await request({ url: "/users/me", method: "DELETE" })
          logout()
          this.syncGuestProfile()
          wx.switchTab({ url: "/pages/home/index" })
        } catch (error) {
          wx.showToast({ title: toFriendlyError(error, "注销失败"), icon: "none" })
        }
      },
    })
  },
})
