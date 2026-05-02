const env = require("./config/env")
const { clearPartnerPortalAuth, getToken, getUser, setReferrerCode } = require("./utils/storage")
const { capturePartnerTracking } = require("./utils/partnerTracking")

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
    const options = wx.getLaunchOptionsSync()
    const query = options ? options.query || {} : {}
    const sharedRef = String(query.ref || query.invite_code || "").trim().toUpperCase()
    if (sharedRef) {
      setReferrerCode(sharedRef)
    }
    capturePartnerTracking(query)
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
