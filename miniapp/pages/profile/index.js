const { request } = require("../../utils/request")
const { getUser, setUser } = require("../../utils/storage")
const { logout, ensureLogin } = require("../../utils/auth")

Page({
  data: {
    user: {},
  },

  onShow() {
    if (!ensureLogin()) {
      wx.reLaunch({ url: "/pages/login/index" })
      return
    }
    this.setData({ user: getUser() || {} })
    this.loadProfile()
  },

  async loadProfile() {
    try {
      const data = await request({ url: "/users/me", method: "GET", silent: true })
      this.setData({ user: data || {} })
      setUser(data || {})
    } catch (_) {
      // keep current view
    }
  },

  onReload() {
    this.loadProfile()
  },

  onGoPay() {
    wx.navigateTo({ url: "/pages/pay/index" })
  },

  onLogout() {
    logout()
    wx.reLaunch({ url: "/pages/login/index" })
  },
})
