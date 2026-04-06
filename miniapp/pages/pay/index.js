const { request } = require("../../utils/request")
const { ensureLogin } = require("../../utils/auth")
const { setUser } = require("../../utils/storage")
const { getOrderStatusText, parseWxPayError, toFriendlyError } = require("../../utils/status")

Page({
  data: {
    loading: false,
    creating: false,
    paying: false,
    packages: [],
    paymentTestMode: false,
    providers: [],
    selectedProvider: "mock",
    orderNo: "",
    orderProvider: "",
    orderStatus: "created",
    orderStatusText: getOrderStatusText("created"),
    remainSeconds: 0,
    qrcodeDataUrl: "",
    paymentParams: null,
  },

  countdownTimer: null,
  pollTimer: null,

  onShow() {
    if (!ensureLogin()) {
      wx.reLaunch({ url: "/pages/login/index" })
      return
    }
    this.loadPackages()
  },

  onHide() {
    this.stopTimers()
  },

  onUnload() {
    this.stopTimers()
  },

  async loadPackages() {
    if (this.data.loading) return
    this.setData({ loading: true })
    try {
      const data = await request({ url: "/billing/packages", method: "GET" })
      const supported = Array.isArray(data.supported_providers) ? data.supported_providers : []
      const allProviders = [
        { value: "mock", label: "测试支付" },
        { value: "wechat", label: "微信支付" },
        { value: "alipay", label: "支付宝" },
      ]
      const providers = supported.length
        ? allProviders.filter((item) => supported.includes(item.value))
        : allProviders
      this.setData({
        packages: data.items || [],
        paymentTestMode: !!data.payment_test_mode,
        providers,
        selectedProvider: providers[0] ? providers[0].value : "mock",
      })
    } finally {
      this.setData({ loading: false })
    }
  },

  onSelectProvider(e) {
    this.setData({ selectedProvider: e.currentTarget.dataset.value || "mock" })
  },

  async onCreateOrder(e) {
    const packageName = e.currentTarget.dataset.name
    if (!packageName || this.data.creating) return
    this.setData({ creating: true })
    try {
      const data = await request({
        url: "/billing/create-order",
        method: "POST",
        data: {
          package_name: packageName,
          provider: this.data.selectedProvider,
          scene: "miniprogram",
        },
      })
      const orderStatus = data.status || "created"
      this.setData({
        orderNo: data.order_no || "",
        orderProvider: data.provider || this.data.selectedProvider,
        orderStatus,
        orderStatusText: getOrderStatusText(orderStatus),
        remainSeconds: Number(data.expire_seconds || 0),
        qrcodeDataUrl: data.qrcode_data_url || "",
        paymentParams: data.payment_params || null,
      })
      this.startTimers()

      if ((data.provider || this.data.selectedProvider) === "wechat" && data.payment_params) {
        await this.onStartWechatPay()
      }
    } catch (error) {
      wx.showToast({ title: toFriendlyError(error, "创建订单失败"), icon: "none" })
    } finally {
      this.setData({ creating: false })
    }
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
        remainSeconds: 0,
      })
      this.stopTimers()
      await this.refreshProfile()
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
        remainSeconds: remain >= 0 ? remain : 0,
      })
      if (status === "paid") {
        this.stopTimers()
        await this.refreshProfile()
      } else if (status === "closed") {
        this.stopTimers()
      }
    } catch (_) {
      // keep polling
    }
  },

  async refreshProfile() {
    try {
      const profile = await request({ url: "/users/me", method: "GET", silent: true })
      if (profile) setUser(profile)
    } catch (_) {
      // ignore
    }
  },
})
