const { request } = require("../../utils/request")

Page({
  data: {
    loading: false,
    errorText: "",
    overview: null,
    subchannels: [],
    hasCredential: false,
  },

  onLoad(options = {}) {
    const channelCode = String(options.ch || "").trim().toUpperCase()
    const portalToken = String(options.pk || "").trim()
    this.channelCode = channelCode
    this.portalToken = portalToken
    this.setData({ hasCredential: !!(channelCode && portalToken) })
    if (channelCode && portalToken) {
      this.loadData()
    }
  },

  async loadData() {
    if (!this.channelCode || !this.portalToken) return
    this.setData({ loading: true, errorText: "" })
    try {
      const params = { ch: this.channelCode, pk: this.portalToken }
      const [overview, subchannelsResp] = await Promise.all([
        request({ url: "/partners/portal/overview", method: "GET", data: params, silent: true }),
        request({ url: "/partners/portal/subchannels", method: "GET", data: params, silent: true }),
      ])
      this.setData({
        overview: overview || null,
        subchannels: Array.isArray(subchannelsResp && subchannelsResp.items) ? subchannelsResp.items : [],
      })
    } catch (error) {
      this.setData({ errorText: String((error && error.message) || "加载失败，请稍后重试") })
    } finally {
      this.setData({ loading: false })
    }
  },

  onCopyText(e) {
    const value = String((e.currentTarget.dataset.value || "")).trim()
    const label = String((e.currentTarget.dataset.label || "内容")).trim()
    if (!value) {
      wx.showToast({ title: "内容为空", icon: "none" })
      return
    }
    wx.setClipboardData({
      data: value,
      success: () => wx.showToast({ title: `${label}已复制`, icon: "none" }),
      fail: () => wx.showToast({ title: "复制失败", icon: "none" }),
    })
  },

  onRefresh() {
    this.loadData()
  },

  formatFenToCny(value) {
    const amount = Number(value || 0) / 100
    return `¥${amount.toFixed(2)}`
  },

  formatLevel(value) {
    const level = Number(value || 1)
    if (level === 1) return "一级代理"
    if (level === 2) return "二级代理"
    if (level === 3) return "三级代理"
    return `L${level}`
  },
})
