const { request } = require("../../utils/request")
const { ensureLogin } = require("../../utils/auth")
const { getUser, setUser } = require("../../utils/storage")

Page({
  data: {
    user: {},
    notice: {
      title: "系统公告",
      content: "暂无公告内容",
      version: 1,
    },
    features: [
      { taskType: "rewrite", title: "学术润色", desc: "优化表达，降低 AI 生成痕迹" },
      { taskType: "dedup", title: "降重复率", desc: "优化文本结构，降低重复风险" },
      { taskType: "aigc_detect", title: "AIGC 检测", desc: "输出检测结果与分析报告" },
    ],
  },

  onShow() {
    if (!ensureLogin()) {
      wx.reLaunch({ url: "/pages/login/index" })
      return
    }
    this.setData({ user: getUser() || {} })
    this.reloadData()
  },

  async reloadData() {
    try {
      const [options, profile] = await Promise.all([
        request({ url: "/auth/options", method: "GET", silent: true }),
        request({ url: "/users/me", method: "GET", silent: true }),
      ])
      this.setData({
        notice: options.notice || this.data.notice,
        user: profile || this.data.user,
      })
      if (profile) {
        setUser(profile)
      }
    } catch (_) {
      // keep current UI state
    }
  },

  onTapFeature(e) {
    const taskType = e.currentTarget.dataset.task || "rewrite"
    wx.setStorageSync("gw_pending_task_type", taskType)
    wx.switchTab({ url: "/pages/task/index" })
  },

  onGoPay() {
    wx.navigateTo({ url: "/pages/pay/index" })
  },
})
