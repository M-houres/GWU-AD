const env = require("./config/env")
const { clearPartnerPortalAuth, getToken, getUser } = require("./utils/storage")

App({
  globalData: {
    apiBaseUrl: env.apiBaseUrl,
    token: "",
    user: null,
    privacyContractName: "《隐私政策》",
  },

  onLaunch() {
    clearPartnerPortalAuth()
    this.globalData.token = getToken() || ""
    this.globalData.user = getUser() || null
  },

  ensurePrivacyAuthorization(handler) {
    if (typeof handler !== "function") return
    if (typeof wx.requirePrivacyAuthorize === "function") {
      wx.requirePrivacyAuthorize({
        success: () => handler(true, null),
        fail: (err) => handler(false, err || null),
      })
      return
    }
    handler(true, null)
  },

  openPrivacyContract() {
    if (typeof wx.openPrivacyContract === "function") {
      wx.openPrivacyContract({
        fail: () => {
          wx.navigateTo({ url: "/pages/legal/privacy/index" })
        },
      })
      return
    }
    wx.navigateTo({ url: "/pages/legal/privacy/index" })
  },
})
