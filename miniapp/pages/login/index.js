const { loginWithMiniProgram, ensureLogin } = require("../../utils/auth")

Page({
  data: {
    loading: false,
    referrerCode: "",
  },

  onShow() {
    if (ensureLogin()) {
      wx.switchTab({ url: "/pages/home/index" })
    }
  },

  onInputReferrer(e) {
    this.setData({ referrerCode: (e.detail.value || "").trim() })
  },

  async onTapWeChatLogin() {
    if (this.data.loading) return
    this.setData({ loading: true })
    try {
      await loginWithMiniProgram({ referrerCode: this.data.referrerCode })
      wx.showToast({ title: "登录成功", icon: "success" })
      wx.switchTab({ url: "/pages/home/index" })
    } catch (error) {
      wx.showToast({
        title: error.message || "登录失败，请稍后重试",
        icon: "none",
      })
    } finally {
      this.setData({ loading: false })
    }
  },
})

